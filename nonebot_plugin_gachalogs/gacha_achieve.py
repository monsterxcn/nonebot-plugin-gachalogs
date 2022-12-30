import asyncio
from collections import Counter
from datetime import datetime
from typing import Dict, List

from pytz import timezone

from nonebot.log import logger

from .__meta__ import GACHA_TYPE, POOL_INFO


async def getLogsAnalysis(gachaLogs: Dict) -> Dict:
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


async def gachaPityLimit(fiveData: List[Dict]) -> List[Dict[str, str]]:
    """五星最欧最非成就"""
    if not len(fiveData):
        return []
    achievements = []

    _fiveData = sorted(fiveData, key=lambda x: x["pity"])
    minPityItem, maxPityItem = _fiveData[0], _fiveData[-1]
    if minPityItem["pity"] <= 30:
        achievements.append(
            {
                "title": "「欧皇时刻」",
                "info": f"只抽了 {minPityItem['pity']} 次就抽到了「{minPityItem['name']}」{'，你的欧气无人能敌！' if minPityItem['pity'] <= 5 else ''}",
                "achievedTime": minPityItem["time"],
                "value": str(minPityItem["pity"]),
            }
        )
    if maxPityItem["pity"] >= 30:
        _rarity = (
            ["百", "千", "万", "十万", "百万"][maxPityItem["pity"] - 84]
            if 83 < maxPityItem["pity"] < 89
            else "无穷"
        )
        achievements.append(
            {
                "title": "「原来非酋竟是我自己」",
                "info": f"抽了 {maxPityItem['pity']} 次才最终抽到了「{maxPityItem['name']}」{f'，你竟是{_rarity}里挑一的非酋！' if minPityItem['pity'] >= 84 else ''}",
                "achievedTime": maxPityItem["time"],
                "value": str(maxPityItem["pity"]),
            }
        )

    return achievements


async def gachaNotExist(nullData: List[str]) -> List[Dict[str, str]]:
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


async def gachaWrongUp(fiveData: List[Dict]) -> List[Dict[str, str]]:
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


async def gachaMaxDay(logsData: Dict[str, List[Dict]]) -> List[Dict[str, str]]:
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
    if not days[dayIdx]["five"]:
        achievements.append(
            {
                "title": "「最黑暗的一天」",
                "info": f"在 {dayIdx} 这一天，你共抽取了 {days[dayIdx]['count']} 次，然而并没有出金",
                "achievedTime": dayIdx,
                "value": str(days[dayIdx]["count"]),
            }
        )
    else:
        _five = [f"「{i['name']}」" for i in days[dayIdx]["five"]]
        results = "、".join(
            f"{k}{f'×{v}' if v > 1 else ''}" for k, v in Counter(_five).items()
        )
        achievements.append(
            {
                "title": "「豪掷千金」",
                "info": f"在 {dayIdx} 这一天，你共抽取了 {days[dayIdx]['count']} 次。在抽到{results}时，你有没有很开心呢？",
                "achievedTime": dayIdx,
                "value": str(days[dayIdx]["count"]),
            }
        )

    return achievements


async def gachaHamster(logsData: Dict[str, List[Dict]]) -> List[Dict[str, str]]:
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
    fromTo = f"{start:%Y-%m-%d} 到 {end:%Y-%m-%d}"
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


async def gachaTogether(logsData: Dict[str, List[Dict]]) -> List[Dict[str, str]]:
    """十连相关成就"""
    # 「单抽/十连出奇迹」在 LIMIT 抽内获取 5 星
    # 「N黄蛋！」在一次十连中，抽取到了 N 个五星
    # 「四叶草」在一次十连中，抽取到 4 个或以上的 4 星或 5 星
    # 「福至五彩」在一次十连中，抽取到 5 个或以上的 4 星或 5 星
    # 「这才是角色池！」在一次十连中，抽出的角色不少于武器
    achievements = []
    miracle, yolk, realChar = {"single": 0, "ten": 0}, {}, {}
    fourCounter, fiveCounter = 0, 0
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
                yolk[str(_fiveCnt)] = yolk.get(str(_fiveCnt), 0) + 1
            # 「这才是角色池！」
            if _charCnt >= 5:
                realChar[timeStr] = _charCnt
            # 「福至五彩」
            if _fiveCnt + _fourCnt >= 5:
                fiveCounter += 1
            # 「四叶草」
            elif _fiveCnt + _fourCnt >= 4:
                fourCounter += 1

    if miracle["single"] + miracle["ten"]:
        _str = "、".join(
            f"通过{'十连' if k == 'ten' else '单抽'}获取 {v} 次" for k, v in miracle.items() if v
        )
        _achievement = {
            "title": "「单抽出奇迹？」",
            "info": f"在 {miracleLimit} 抽内获取 5 星共计 {miracle['single'] + miracle['ten']} 次，其中{_str}",
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
                    "info": f"在一次十连中，你抽取到了 {k} 只五星{'，你就是极致的欧皇！' if int(k) > 2 else ''}",
                    "achievedTime": "达成次数",
                    "value": f"{v}",
                }
                for k, v in yolk.items()
            ]
        )

    if fourCounter:
        achievements.append(
            {
                "title": "「四叶草」",
                "info": "在一次十连中，抽取到 4 个或以上的 4 星或 5 星",
                "achievedTime": "达成次数",
                "value": f"{fourCounter}",
            }
        )

    if fiveCounter:
        achievements.append(
            {
                "title": "「福至五彩」",
                "info": "在一次十连中，抽取到 5 个或以上的 4 星或 5 星",
                "achievedTime": "达成次数",
                "value": f"{fiveCounter}",
            }
        )

    if realChar:
        achievements.append(
            {
                "title": "「这才是角色池！」",
                "info": "在一次十连中，抽出的角色不少于武器",
                "achievedTime": "达成次数"
                if len(realChar.keys()) > 1
                else list(realChar.keys())[0].split()[0],
                "value": f"{len(realChar.keys())}"
                if len(realChar.keys()) > 1
                else f"角色：{list(realChar.values())[0]}",
            }
        )

    return achievements


async def gachaMostChar(allData: Dict[str, Dict[str, int]]) -> List[Dict[str, str]]:
    """获取最多角色成就"""
    achievements = []
    mostFive = dict(sorted(allData["5-角色"].items(), key=lambda x: x[1]))
    mostFour = dict(sorted(allData["4-角色"].items(), key=lambda x: x[1]))
    if mostFive and mostFive[list(mostFive.keys())[-1]] > 1:
        count = mostFive[list(mostFive.keys())[-1]]
        names = "、".join(
            f"「{n}」×{count}" for n in [k for k, v in mostFive.items() if v == count]
        )
        achievements.append(
            {
                "title": "「情有独钟(五星角色)」",
                "info": f"你共抽取了{names}，这是上天对你的眷顾还是你对{'他们' if '、' in names else ' ta '}的情有独钟呢？",
            }
        )
    if mostFour and mostFour[list(mostFour.keys())[-1]] > 1:
        count = mostFour[list(mostFour.keys())[-1]]
        names = "、".join(
            f"「{n}」×{count}" for n in [k for k, v in mostFour.items() if v == count]
        )
        achievements.append(
            {
                "title": "「情有独钟(四星角色)」",
                "info": f"你共抽取了{names}，这是上天对你的眷顾还是你对{'他们' if '、' in names else ' ta '}的情有独钟呢？",
            }
        )

    return achievements


async def calcAchievement(rawData: Dict) -> List[Dict[str, str]]:
    """
    成就数据提取

    * ``param rawData: Dict`` 抽卡记录数据
    - ``return: List[Dict[str, str]]`` 成就数据
    """
    analysis = await getLogsAnalysis(rawData)
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
    return [item for subList in calcRes for item in subList]
