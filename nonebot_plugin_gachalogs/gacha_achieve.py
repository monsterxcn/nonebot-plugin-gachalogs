import asyncio
from collections import Counter
from datetime import datetime
from typing import Dict, List, Tuple

from pytz import timezone

from nonebot.log import logger
from nonebot.utils import run_sync

from .__meta__ import GACHA_TYPE, POOL_INFO


@run_sync
def getLogsAnalysis(gachaLogs: Dict) -> Dict:
    """获取抽卡记录分析数据"""
    analysis = {
        "all": {"5-角色": {}, "5-武器": {}, "4-角色": {}, "4-武器": {}, "3-武器": {}},  # 全物品出货统计
        "null": [],  # 未抽卡池统计
        "five": [],  # 五星物品统计
        "logs": {},  # 按抽卡时间分离记录
    }
    renderOrder = sorted(GACHA_TYPE.keys(), key=lambda k: k[0], reverse=True)
    for banner in renderOrder:
        gachaList = gachaLogs.get(banner)
        if not gachaList:
            analysis["null"] += [banner]  # 未抽卡池统计
            continue

        gachaList.reverse()  # 千万不可以 gachaList.sort(key=lambda item: item["time"], reverse=False)
        pityCounter = 0  # 保底计数

        # 遍历某个卡池全部记录
        for item in gachaList:
            rankType = int(item["rank_type"])
            itemName, itemType = item["name"], item["item_type"]

            pityCounter += 1  # 保底计数递增

            # 全物品出货统计
            allIdx = f"{rankType}-{itemType}"
            analysis["all"][allIdx][itemName] = (
                analysis["all"][allIdx].get(itemName, 0) + 1
            )

            # 按抽卡时间分离记录
            dropCounter = analysis["logs"].get(item["time"], [])
            dropSimple = {
                "pool": banner,
                "name": itemName,
                "rank": rankType,
                "type": itemType,
            }
            if rankType == 5:
                dropSimple["pity"] = pityCounter
                if banner in ["301", "302"]:
                    gachaTime = timezone("Asia/Shanghai").localize(
                        datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")
                    )
                    belongTo = [
                        p
                        for p in POOL_INFO
                        if p["Type"] == int(item["gacha_type"])
                        and gachaTime >= datetime.fromisoformat(p["From"])
                        and gachaTime <= datetime.fromisoformat(p["To"])
                    ]
                    if not belongTo or len(belongTo) > 1:
                        logger.error(
                            "卡池 {} 异常的 UP 判断：{}({}) in {}".format(
                                banner,
                                item["name"],
                                item["time"],
                                "/".join(bp["Name"] for bp in belongTo)
                                if belongTo
                                else "null",
                            )
                        )
                    dropSimple["up"] = item["name"] in belongTo[0]["UpOrangeList"]
                analysis["five"].append(
                    {**dropSimple, "time": item["time"].split()[0]}
                )  # 五星物品统计
                pityCounter = 0  # 重置保底计数器

            analysis["logs"][item["time"]] = dropCounter + [dropSimple]

    # 记录按时间重新排序
    analysis["logs"] = dict(
        sorted(
            analysis["logs"].items(),
            key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S"),
        )
    )

    return analysis


def mergeItemStr(items: List[str]) -> str:
    """合并出货记录消息，最多显示三个物品"""
    _items = [f"「{k}」{f'×{v}' if v > 1 else ''}" for k, v in Counter(items).items()]
    return "、".join(_items[:3]) + ("等" if len(_items) > 3 else "")


@run_sync
def gachaPityLimit(fiveData: List[Dict]) -> List[Dict[str, str]]:
    """五星最欧最非成就"""
    if not len(fiveData):
        return []
    achievements = []

    _fiveData = sorted(
        fiveData,
        key=lambda x: (x["pity"], datetime.strptime(x["time"], "%Y-%m-%d")),
    )
    minPityItem, maxPityItem = _fiveData[0], _fiveData[-1]
    if minPityItem["pity"] <= 30:
        _results = [d["name"] for d in fiveData if d["pity"] == minPityItem["pity"]]
        achievements.append(
            {
                "title": "「欧皇时刻」",
                "info": f"只抽了 {minPityItem['pity']} 次就抽到了{mergeItemStr(_results)}{'，你的欧气无人能敌！' if minPityItem['pity'] <= 5 else ''}",
                "achievedTime": minPityItem["time"].replace("-", "/"),
                "value": "达成" if len(_results) == 1 else f"总计 {len(_results)}",
            }
        )
    if maxPityItem["pity"] >= 30:
        _rarity = (
            ["百", "千", "万", "十万", "百万"][maxPityItem["pity"] - 84]
            if 83 < maxPityItem["pity"] < 89
            else "无穷"
        )
        _results = [d["name"] for d in fiveData if d["pity"] == maxPityItem["pity"]]
        achievements.append(
            {
                "title": "「原来非酋竟是我自己」",
                "info": f"抽了 {maxPityItem['pity']} 次才最终抽到了{mergeItemStr(_results)}{f'，你竟是{_rarity}里挑一的非酋！' if minPityItem['pity'] >= 84 else ''}",
                "achievedTime": maxPityItem["time"].replace("-", "/"),
                "value": "达成" if len(_results) == 1 else f"总计 {len(_results)}",
            }
        )

    return achievements


@run_sync
def gachaNotExist(nullData: List[str]) -> List[Dict[str, str]]:
    """未抽卡池成就"""
    achievements = []

    if "100" in nullData:
        achievements.append({"title": "「永远的新手」", "info": "没有在「新手祈愿」中进行抽卡"})
    if "200" in nullData:
        achievements.append({"title": "「传说中的毒池」", "info": "没有在「常驻祈愿」中进行抽卡"})
    if "301" in nullData:
        achievements.append({"title": "「角色 UP 池？不稀罕！」", "info": "没有在「角色活动祈愿」中进行抽卡"})
    if "302" in nullData:
        achievements.append({"title": "「武器池？能吃吗？」", "info": "没有在「武器活动祈愿」中进行抽卡"})

    return achievements


@run_sync
def gachaWrongUp(fiveData: List[Dict]) -> List[Dict[str, str]]:
    """角色活动祈愿限定 UP 成就"""
    _fiveData = [x for x in fiveData if x["pool"] == "301"]
    if not len(_fiveData):
        return []

    hitCount = len([x for x in _fiveData if x["up"]])
    notHitCount = len(_fiveData) - hitCount
    achievements = [
        {
            "title": "",
            "info": "",
            "achievedTime": "小保底歪的概率",
            "value": f"{notHitCount} / {hitCount}",
        }
    ]
    if notHitCount == 0:
        achievements[0]["title"] = "「不倒翁」"
        achievements[0]["info"] = "在「角色活动祈愿」中抽中的五星角色均为当期 UP 角色"
    if hitCount > notHitCount:
        achievements[0]["title"] = "「晴时总比雨时多」"
        achievements[0]["info"] = "在「角色活动祈愿」中，小保底偏向于抽中当期 UP 角色"
    if hitCount == notHitCount:
        achievements[0]["title"] = "「晴雨各半」"
        achievements[0]["info"] = "在「角色活动祈愿」中小保底歪与不歪次数持平"
    if hitCount < notHitCount:
        achievements[0]["title"] = "「雨时偏比晴时多」"
        achievements[0]["info"] = "在「角色活动祈愿」中，小保底偏向于没有抽中当期 UP 角色"

    return achievements


@run_sync
def gachaMaxDay(logsData: Dict[str, List[Dict]]) -> List[Dict[str, str]]:
    """单日抽卡次数极多成就"""
    days, achievements = {}, []
    for timeStr, logs in logsData.items():
        idx = timeStr.split()[0]
        _day = days.get(idx, {})
        days[idx] = {
            "count": _day.get("count", 0) + len(logs),
            "five": _day.get("five", []) + [x for x in logs if x["rank"] == 5],
        }

    days = dict(sorted(days.items(), key=lambda x: x[1]["count"]))
    dayIdx = list(days.keys())[-1]
    dayDisplay = dayIdx.replace("-", "/")
    if not days[dayIdx]["five"]:
        achievements.append(
            {
                "title": "「最黑暗的一天」",
                "info": f"在 {dayDisplay} 这一天，你共抽取了 {days[dayIdx]['count']} 次，然而并没有出金",
                "achievedTime": dayDisplay,
                "value": "达成",
            }
        )
    else:
        _five = [i["name"] for i in days[dayIdx]["five"]]
        achievements.append(
            {
                "title": "「豪掷千金」",
                "info": f"在 {dayDisplay} 这一天，你共抽取了 {days[dayIdx]['count']} 次。在抽到{mergeItemStr(_five)}时，你有没有很开心呢？",
                "achievedTime": dayDisplay,
                "value": "达成",
            }
        )

    return achievements


@run_sync
def gachaHamster(logsData: Dict[str, List[Dict]]) -> List[Dict[str, str]]:
    """未抽卡持续天数极长成就"""
    times = []
    for timeStr, logs in logsData.items():
        if len([x for x in logs if x["pool"] in ["301", "302"]]):
            times.append(timeStr)

    # 转换 datatime 对象
    datetimes = [datetime.strptime(time, "%Y-%m-%d %H:%M:%S") for time in times]
    # 计算最大差值、起点和终点
    diff, start, end = max((b - a, a, b) for a, b in zip(datetimes, datetimes[1:]))
    # 格式化字符串
    fromTo = f"{start:%Y/%m/%d} 到 {end:%Y/%m/%d}"
    duration = f"{diff.days} 天 {diff.seconds // 3600} 时"

    if diff.days <= 15:
        level, info = "随缘", "是一只不太合格的仓鼠呢~"
    elif diff.days <= 30:
        level, info = "合格", "你已经是一只合格的仓鼠了"
    elif diff.days <= 60:
        level, info = "专家", "作为仓鼠，你就是专家！"
    else:
        level, info = "大师", "您的传说受到了众仓鼠的景仰！"

    return [
        {
            "title": f"「{level}仓鼠」",
            "info": f"{fromTo} 期间没有使用「纠缠之缘」进行抽卡。{info}",
            "achievedTime": "持续时间",
            "value": duration,
        }
    ]


@run_sync
def gachaTogether(logsData: Dict[str, List[Dict]]) -> List[Dict[str, str]]:
    """十连相关成就"""
    # 「单抽/十连出奇迹」在 LIMIT 抽内获取五星
    # 「N黄蛋！」在一次十连中，抽取到了 N 个五星
    # 「四叶草」在一次十连中，抽取到 4 个或以上的四或五星
    # 「这才是角色池！」在一次十连中，抽出的角色不少于武器
    achievements = []
    miracle, yolk, realChar, manyGood = {"single": 0, "ten": 0}, {}, {}, {}
    miracleLimit, miraclePct = 40, 0.3

    for timeStr, logs in logsData.items():
        # 单抽
        if len(logs) == 1:
            # 「单抽出奇迹」
            if logs[0]["rank"] == 5 and logs[0]["pity"] <= miracleLimit:
                miracle["single"] += 1
        elif len(logs) == 10:
            _charCnt = len([x for x in logs if x["type"] == "角色"])
            _fourCnt = len([x for x in logs if x["rank"] == 4])
            _fiveCnt = len([x for x in logs if x["rank"] == 5])
            # 「十连出奇迹」
            miracle["ten"] += len(
                [x for x in logs if x["rank"] == 5 and x["pity"] <= miracleLimit]
            )
            # 「N黄蛋！」
            if _fiveCnt > 1:
                yolk[str(_fiveCnt)] = {
                    "count": yolk.get(str(_fiveCnt), {}).get("count", 0) + 1,
                    "first": yolk.get(str(_fiveCnt), {}).get("first") or timeStr,
                }
            # 「这才是角色池！」
            if _charCnt >= 5:
                realChar[timeStr] = _charCnt
            # 「四叶草」「福至五彩」等
            elif _fiveCnt + _fourCnt >= 4:
                manyGoodKey = str(_fiveCnt + _fourCnt)
                manyGood[manyGoodKey] = {
                    "count": manyGood.get(manyGoodKey, {}).get("count", 0) + 1,
                    "first": manyGood.get(manyGoodKey, {}).get("first") or timeStr,
                }

    if miracle["single"] + miracle["ten"]:
        _str = "、".join(
            f"通过{'十连' if k == 'ten' else '单抽'}获取 {v} 次" for k, v in miracle.items() if v
        )
        _achievement = {
            "title": "「单抽出奇迹？」",
            "info": f"在 {miracleLimit} 抽内获取五星共计 {miracle['single'] + miracle['ten']} 次，其中{_str}",
        }
        if miracle["ten"] and miracle["single"] / miracle["ten"] < miraclePct:
            _achievement["title"] = "「十连出奇迹！」"
        if miracle["single"] and miracle["ten"] / miracle["single"] < miraclePct:
            _achievement["title"] = "「单抽出奇迹！」"
        achievements.append(_achievement)

    if yolk:
        _map = ["双", "三", "四", "五", "六", "七", "八", "九", "十"]
        achievements.extend(
            [
                {
                    "title": f"「{_map[int(k) - 2]}黄蛋！」",
                    "info": f"在一次十连中，你抽取到了 {k} 个五星{'，你就是极致的欧皇！' if int(k) > 2 else ''}",
                    "achievedTime": v["first"].split()[0].replace("-", "/"),
                    "value": "达成" if v["count"] == 1 else f"总计 {v['count']}",
                }
                for k, v in yolk.items()
            ]
        )

    if manyGood:
        _map = ["四叶草", "福至五彩", "六六顺意", "七星高照", "八方鸿运", "九九同心", "十全十美"]
        achievements.extend(
            [
                {
                    "title": f"「{_map[int(k) - 4]}」",
                    "info": f"在一次十连中，你抽取到了 {k} 个四星或五星{'，这何尝不是另类的欧皇！' if int(k) > 4 else ''}",
                    "achievedTime": v["first"].split()[0].replace("-", "/"),
                    "value": "达成" if v["count"] == 1 else f"总计 {v['count']}",
                }
                for k, v in manyGood.items()
            ]
        )

    if realChar:
        achievements.append(
            {
                "title": "「这才是角色池！」",
                "info": "在一次十连中，抽出的角色不少于武器",
                "achievedTime": list(realChar.keys())[0].split()[0].replace("-", "/"),
                "value": f"总计 {len(realChar.keys())}"
                if len(realChar.keys()) > 1
                else f"角色 {list(realChar.values())[0]}",
            }
        )

    return achievements


@run_sync
def gachaMostChar(allData: Dict[str, Dict[str, int]]) -> List[Dict[str, str]]:
    """获取最多角色成就"""
    achievements = []
    mostFive = dict(sorted(allData["5-角色"].items(), key=lambda x: x[1]))
    mostFour = dict(sorted(allData["4-角色"].items(), key=lambda x: x[1]))
    if mostFive and mostFive[list(mostFive.keys())[-1]] > 1:
        count = mostFive[list(mostFive.keys())[-1]]
        names = [k for k, v in mostFive.items() if v == count for _ in range(v)]
        multi = "他们" if len(Counter(names).keys()) > 1 else " ta "
        achievements.append(
            {
                "title": "「情有独钟(五星角色)」",
                "info": f"你共抽取了{mergeItemStr(names)}，这是上天对你的眷顾还是你对{multi}的情有独钟呢？",
            }
        )
    if mostFour and mostFour[list(mostFour.keys())[-1]] > 1:
        count = mostFour[list(mostFour.keys())[-1]]
        names = [k for k, v in mostFour.items() if v == count for _ in range(v)]
        multi = "他们" if len(Counter(names).keys()) > 1 else " ta "
        achievements.append(
            {
                "title": "「情有独钟(四星角色)」",
                "info": f"你共抽取了{mergeItemStr(names)}，这是上天对你的眷顾还是你对{multi}的情有独钟呢？",
            }
        )

    return achievements


async def calcAchievement(rawData: Dict) -> Tuple[str, List[Dict[str, str]]]:
    """
    成就数据提取

    * ``param rawData: Dict`` 抽卡记录数据
    - ``return: Tuple[str, List[Dict[str, str]]]`` 记录范围、成就数据
    """
    analysis = await getLogsAnalysis(rawData)

    times = list(analysis["logs"].keys())
    total = sum(sum(n for _, n in d.items()) for _, d in analysis["all"].items())
    scope = "{} 共 {} 抽".format(
        f"{times[0]} ~ {times[-1]}" if len(times) > 1 else f"{times[0]}", total
    )

    tasks = [
        gachaPityLimit(analysis["five"]),
        gachaNotExist(analysis["null"]),
        gachaWrongUp(analysis["five"]),
        gachaMaxDay(analysis["logs"]),
        gachaHamster(analysis["logs"]),
        gachaTogether(analysis["logs"]),
        gachaMostChar(analysis["all"]),
    ]
    calcRes = await asyncio.gather(*tasks)
    achievements = [item for subList in calcRes for item in subList]

    return scope, achievements
