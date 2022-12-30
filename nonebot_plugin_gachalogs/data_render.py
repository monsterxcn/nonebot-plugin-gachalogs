from copy import deepcopy
from datetime import datetime
from io import BytesIO
from math import floor
from time import localtime, strftime, time
from typing import Dict, List, Literal, Tuple

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from nonebot.log import logger
from PIL import Image, ImageDraw, ImageFont
from pytz import timezone

from .__meta__ import (
    GACHA_TYPE,
    PIE_FONT,
    PIL_FONT,
    POOL_INFO,
    ACHIEVE_FONT,
    ACHIEVE_BG,
    ACHIEVE_BG_DETAIL,
)
from .gacha_achieve import calcAchievement


def percent(a: int, b: int, rt: Literal["pct", "rgb"] = "pct") -> str:
    """
    概率百分数字符串或根据概率生成的 RGB 颜色生成
    ref: https://github.com/voderl/genshin-gacha-analyzer/blob/main/src/pages/ShowPage/AnalysisChart/utils.ts

    * ``param a: int`` 数值
    * ``param b: int`` 基准值
    * ``param rt: Literal["pct", "rgb"] = "pct"`` 返回类型，默认返回概率百分数字符串
    - ``return: str`` 概率百分数字符串（格式为 ``23.33%``）或根据概率生成的 RGB 颜色（格式为 ``#FFFFFF``）
    """
    if rt == "pct":
        return str(round(a / b * 100, 2)) + "%"
    # 由概率生成 RGB 颜色
    percentColors = [
        {"pct": 0.0, "color": {"r": 46, "g": 200, "b": 5}},
        {"pct": 0.77, "color": {"r": 67, "g": 93, "b": 250}},
        {"pct": 1.0, "color": {"r": 255, "g": 0, "b": 0}},
    ]
    pct = a / b
    for level in percentColors:
        if pct < level["pct"]:
            prevKey = percentColors.index(level) - 1
            prevCl = percentColors[prevKey]["color"]
            prevPct = percentColors[prevKey]["pct"]
            upPct = (pct - prevPct) / (level["pct"] - prevPct)
            lowPct = 1 - upPct
            nowCl = level["color"]
            clR = floor(lowPct * prevCl["r"] + upPct * nowCl["r"])
            clG = floor(lowPct * prevCl["g"] + upPct * nowCl["g"])
            clB = floor(lowPct * prevCl["b"] + upPct * nowCl["b"])
            return "#{:02X}{:02X}{:02X}".format(clR, clG, clB)
            # return "rgb({},{},{})".format(clR, clG, clB)
    return "#FF5652"


def getPoolTag(num: int) -> Tuple[str, str, str]:
    """
    卡池运势标签
    ref: https://github.com/vikiboss/genshin-helper/blob/main/src/render/pages/gacha/components/Overview/index.tsx

    * ``param num: int`` 卡池五星平均抽数
    - ``return: Tuple[str, str, str]`` 卡池运势、字体背景色、字体边缘色
    """
    if num == 0:
        return "无", "#759abf", "#4d8ccb"
    if num >= 72:
        return "非", "#6c6c6c", "#505a6d"
    if num >= 68:
        return "愁", "#b8b8b8", "#9a9fa8"
    if num >= 60:
        return "平", "#a0bb77", "#9ed052"
    if num >= 54:
        return "吉", "#aa96c7", "#9d78d2"
    return "欧", "#e4b95b", "#e4b44d"


def fs(size: int, achieve: bool = False) -> ImageFont.FreeTypeFont:
    """
    Pillow 绘制字体设置

    * ``param size: int`` 字体大小
    - ``return: ImageFont.FreeTypeFont`` Pillow 字体对象
    """
    return ImageFont.truetype(str(ACHIEVE_FONT if achieve else PIL_FONT), size=size)


async def colorfulFive(
    star5Data: List, fontSize: int, maxWidth: int, isWeapon: bool = False
) -> Image.Image:
    """
    不超过宽度限制的彩色五星历史记录文字逐行绘制

    * ``param star5Data: List`` 五星历史记录列表
    * ``param fontSize: int`` 字体大小
    * ``param maxWidth: int`` 最大宽度
    * ``param isWeapon: bool = False`` 是否为武器祈愿活动
    - ``return: Image.Image`` Pillow 图片对象
    """
    ImageSize = (maxWidth, 1000)
    coordX, coordY = 0, 0  # 绘制坐标
    fontPadding = 10  # 字体行间距
    result = Image.new("RGBA", ImageSize, "#f9f9f9")
    tDraw = ImageDraw.Draw(result)
    # 首行固定文本绘制
    text1st = "五星历史记录："
    tDraw.text((coordX, coordY), text1st, font=fs(fontSize), fill="black")
    indent1st, fH = fs(fontSize).getbbox(text1st)[-2:]
    spaceW = indent1st / len(text1st)  # 单个空格宽度，即 fs(fontSize).getlength("宽")
    stepY = fH + fontPadding  # 单行绘制结束后的 Y 轴偏移量
    coordX += indent1st  # 首行绘制结束偏移 X 轴绘制坐标
    # 逐行绘制五星历史记录
    for item in star5Data:
        color = percent(item["count"], 80 if isWeapon else 90, "rgb")
        # 逐个绘制每个物品名称、抽数
        for word in [item["name"], f"[{item['count']}]"]:
            wordW = fs(fontSize).getlength(word)
            if coordX + wordW <= maxWidth:
                # 当前行绘制未超过最大宽度限制，正常绘制
                tDraw.text(
                    (coordX, coordY),
                    word,
                    font=fs(fontSize),
                    fill=color,
                    stroke_width=int(item["up"]),
                    stroke_fill=color,
                )
                # 偏移 X 轴绘制坐标使物品名称与自己的抽数间隔 1/4 个空格、抽数与下一个物品名称间隔一个空格
                coordX += (wordW + spaceW) if word[0] == "[" else int(wordW + spaceW / 4)
            elif word[0] == "[":
                # 当前行绘制超过最大宽度限制，且当前绘制为抽数，换行绘制（保证 [ 与数字不分离）
                coordX, coordY = 0, (coordY + stepY)  # 偏移绘制坐标至下行行首
                tDraw.text(
                    (coordX, coordY),
                    word,
                    font=fs(fontSize),
                    fill=color,
                    stroke_width=int(item["up"]),
                    stroke_fill=color,
                )
                coordX = wordW + spaceW  # 偏移 X 轴绘制坐标使抽数与下一个物品名称间隔一个空格
            else:
                # 当前行绘制超过最大宽度限制，且当前绘制为物品名称，逐字绘制直至超限后换行绘制
                aval = int((maxWidth - coordX) / spaceW)  # 当前行可绘制的最大字符数
                splitStr = [item["name"][:aval], item["name"][aval:]]
                for i in range(len(splitStr)):
                    s = splitStr[i]
                    tDraw.text(
                        (coordX, coordY),
                        s,
                        font=fs(fontSize),
                        fill=color,
                        stroke_width=int(item["up"]),
                        stroke_fill=color,
                    )
                    if i == 0:
                        # 当前行绘制完毕，偏移绘制坐标至下行行首
                        coordX, coordY = 0, (coordY + stepY)
                    else:
                        # 下一行绘制完毕，偏移 X 轴绘制坐标使物品名称与自己的抽数间隔 1/4 个空格
                        partW = fs(fontSize).getlength(s)
                        coordX = int(partW + spaceW / 4)
    # 所有五星物品数据绘制完毕
    # 绘制五星概率统计结果
    star5Avg = sum(item["count"] for item in star5Data) / len(star5Data)
    coordY += stepY + fontPadding * 2  # 偏移 Y 轴绘制坐标至下两行行首（空出一行）
    tDraw.text((0, coordY), "五星平均抽数：", font=fs(fontSize), fill="black")
    tDraw.text(
        (indent1st, coordY),
        f"{star5Avg:.2f}",
        font=fs(fontSize),
        fill=percent(round(star5Avg), 80 if isWeapon else 90, "rgb"),
    )
    if len(star5Data) > 1:
        startW = maxWidth
        for extreme in [
            str(max(x["count"] for x in star5Data)),
            "  最非 ",
            str(min(x["count"] for x in star5Data)),
            "最欧 ",
        ]:
            tDraw.text(
                (startW - fs(fontSize).getlength(extreme), coordY),
                extreme,
                font=fs(fontSize),
                fill=percent(int(extreme), 80 if isWeapon else 90, "rgb")
                if extreme.isdigit()
                else "black",
            )
            startW -= fs(fontSize).getlength(extreme)
    # 绘制限定五星概率统计结果
    upStar5Cnts = [
        (
            item["count"]
            + (
                star5Data[iIdx - 1]["count"]
                if iIdx >= 1 and not star5Data[iIdx - 1]["up"]
                else 0
            )
        )
        for iIdx, item in enumerate(star5Data)
        if item["up"]
    ]
    if upStar5Cnts:
        upStar5Avg = sum(upStar5Cnts) / len(upStar5Cnts)
        coordY += stepY + fontPadding * 2  # 偏移 Y 轴绘制坐标至下两行行首（空出一行）
        tDraw.text((0, coordY), "限定五星平均抽数：", font=fs(fontSize), fill="black")
        tDraw.text(
            (indent1st + spaceW * 2, coordY),  # 多出 2 个字宽度
            f"{upStar5Avg:.2f}",
            font=fs(fontSize),
            fill=percent(round(upStar5Avg), 160 if isWeapon else 180, "rgb"),
        )
    # 裁剪图片
    result = result.crop((0, 0, maxWidth, coordY + fH))
    return result


async def calcStat(gachaLogs: Dict) -> Dict:
    """
    统计数据提取

    * ``param gachaLogs: Dict`` 原始抽卡记录数据
    - ``return: Dict`` 统计数据
    """
    single = {
        "total": 0,  # 总抽数
        "cntNot5": 0,  # 未出五星抽数
        "cntStar3": 0,  # 三星物品总数
        "cntChar4": 0,  # 四星角色总数
        "cntWeapon4": 0,  # 四星武器总数
        "cntChar5": 0,  # 五星角色总数
        "cntWeapon5": 0,  # 五星武器总数
        "star5": [],  # 五星物品列表
        "startTime": "",  # 抽卡记录开始时间
        "endTime": "",  # 抽卡记录结束时间
    }
    # 重排顺序为 301 302 200 100（角色、武器、常驻、新手
    renderOrder = sorted(GACHA_TYPE.keys(), key=lambda k: k[0], reverse=True)
    stat = {}  # 待返回统计数据
    for banner in renderOrder:
        if not gachaLogs.get(banner):
            continue
        gachaStat = deepcopy(single)
        gachaList = gachaLogs[banner]
        gachaList.reverse()  # 千万不可以 gachaList.sort(key=lambda item: item["time"], reverse=False)
        counter, pityCounter = 0, 0  # 总抽数计数器、保底计数器
        upCounter = {}  # UP 物品计数器
        for item in gachaList:
            counter += 1  # 总抽数计数器递增
            pityCounter += 1  # 保底计数器递增
            rankType = int(item["rank_type"])
            itemName, itemType = item["name"], item["item_type"]
            # 更新统计数据字典
            gachaStat["total"] = counter  # 总抽数更新
            if rankType == 3:
                gachaStat["cntStar3"] += 1  # 三星物品总数递增
            else:
                t = "cntChar" if itemType == "角色" else "cntWeapon"
                gachaStat[t + str(rankType)] += 1  # 对应星级对应类型物品总数递增
                # 对应星级对应类型物品 UP 总数递增
                gotUpStar5 = False
                if int(banner) in [301, 302]:
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
                    elif item["name"] in belongTo[0]["UpPurpleList"]:
                        upCounter["cntUp4"] = 1 + upCounter.get("cntUp4", 0)
                    elif item["name"] in belongTo[0]["UpOrangeList"]:
                        upCounter["cntUp5"] = 1 + upCounter.get("cntUp5", 0)
                        gotUpStar5 = True
                if rankType == 5:
                    gachaStat["star5"].append(
                        {"name": itemName, "count": pityCounter, "up": gotUpStar5}
                    )
                    pityCounter = 0  # 重置保底计数器
        # 计算未出五星抽数
        star5Cnts = [item["count"] for item in gachaStat["star5"]]
        gachaStat["cntNot5"] = counter - sum(star5Cnts)
        # 记录抽卡记录开始时间、结束时间
        if len(gachaList):
            timeNow = strftime("%Y-%m-%d %H:%M:%S", localtime())
            gachaStat["startTime"] = gachaList[0].get("time", timeNow)
            gachaStat["endTime"] = gachaList[-1].get("time", timeNow)
        # UP 物品总数
        if upCounter:
            gachaStat.update(upCounter)
        # 更新待返回统计数据
        stat[banner] = gachaStat
    return stat


async def drawPie(stat: Dict) -> Tuple[Image.Image, bool]:
    """
    单个饼图绘制

    * ``param stat: Dict`` 统计数据，由 ``calcStat()`` 生成
    - ``return: Tuple[Image.Image, bool]`` 返回饼图、是否展示三星物品数据
    """
    partMap = [
        {"label": "三星武器", "color": "#73c0de", "total": stat["cntStar3"]},
        {"label": "四星武器", "color": "#91cc75", "total": stat["cntWeapon4"]},
        {"label": "四星角色", "color": "#5470c6", "total": stat["cntChar4"]},
        {"label": "五星武器", "color": "#ee6666", "total": stat["cntWeapon5"]},
        {"label": "五星角色", "color": "#fac858", "total": stat["cntChar5"]},
    ]
    # 如果可显示项目多于 4 项，考虑隐藏三星数据
    showStar3 = True
    if len([p for p in partMap if p["total"]]) > 4:
        partMap = [p for p in partMap if p["label"] != "三星武器"]
        showStar3 = False
    # 提取数据
    labels = [p["label"] for p in partMap if p["total"]]
    colors = [p["color"] for p in partMap if p["total"]]
    sizes = [p["total"] for p in partMap if p["total"]]
    explode = [(0.05 if "五星" in p["label"] else 0) for p in partMap if p["total"]]
    # 绘制饼图
    textprops = {"fontproperties": fm.FontProperties(fname=PIE_FONT, size=18)}  # type: ignore
    fig, ax = plt.subplots()
    ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct="%0.2f%%",
        labeldistance=1.1,
        pctdistance=0.7,
        startangle=60,
        radius=0.7,
        explode=explode,
        shadow=False,
        textprops=textprops,
    )
    ax.axis("equal")
    # plt.tight_layout()  # 让饼图几乎占满整个图片
    # 生成图片
    ioBytes = BytesIO()
    fig.set_alpha(1.0)
    plt.savefig(ioBytes, format="png", facecolor="#ffffff")
    pieImg = Image.open(ioBytes)
    # (640, 480) => (500, 375)
    pieImg = pieImg.resize((500, 375), Image.Resampling.LANCZOS).convert("RGBA")
    # pieImg.save("pie.png")
    return pieImg, showStar3


async def gnrtGachaInfo(rawData: Dict, uid: str) -> bytes:
    """
    抽卡统计信息图片生成，通过 pillow 和 matplotlib 绘制图片

    * ``param rawData: Dict`` 抽卡记录数据
    * ``param uid: str`` 用户 UID
    - ``return: bytes`` 图片字节数据
    """
    wishStat = await calcStat(rawData)
    gotPool = [key for key in wishStat if wishStat[key]["total"] > 0]
    imageList = []
    for banner in gotPool:
        poolName, poolStat = GACHA_TYPE[banner], wishStat[banner]
        isWeapon = True if banner == "302" else False  # 是否为武器祈愿
        pityCnt = 80 if isWeapon else 90
        poolImg = Image.new("RGBA", (500, 1500), "#f9f9f9")
        tDraw = ImageDraw.Draw(poolImg)
        # 绘制祈愿活动标题
        tDraw.text(
            (
                int((500 - fs(30).getlength(poolName)) / 2),
                int((75 - fs(30).getbbox(poolName)[-1]) / 2),
            ),
            poolName,
            font=fs(30),
            fill="black",
            stroke_width=1,
            stroke_fill="grey",
        )
        poolImgH = 75
        # 绘制饼状图
        pieImg, showStar3 = await drawPie(poolStat)
        poolImg.paste(pieImg, (0, poolImgH), pieImg)
        poolImgH += 375  # pieImg.height
        if not showStar3:
            # 绘制隐藏三星数据提示
            tDraw.text(
                (15, poolImgH - 375 + 13), "* 三星武器数据已隐藏", font=fs(20), fill="#808080"
            )
        # 绘制抽卡时间
        startTime: str = poolStat["startTime"].split(" ")[0]
        endTime: str = poolStat["endTime"].split(" ")[0]
        timeStat = f"{startTime} ~ {endTime}"
        tDraw.text(
            (int((500 - fs(20).getlength(timeStat)) / 2), poolImgH - 35),
            timeStat,
            font=fs(20),
            fill="#808080",
        )
        # 绘制卡池运势
        star5Data: List[Dict] = poolStat["star5"]
        star5Avg = (
            sum(item["count"] for item in star5Data) / len(star5Data) if star5Data else 0
        )
        poolTag, poolTagBg, poolTagEdge = getPoolTag(round(star5Avg))
        tDraw.rounded_rectangle(
            (500 - 13 - 80, poolImgH - 13 - 80, 500 - 13, poolImgH - 13),
            fill=poolTagBg,
            radius=15,
            width=0,
        )
        tDraw.text(
            (
                int(500 - 13 - 80 + (80 - fs(60).getlength(poolTag)) / 2),
                int(poolImgH - 15 - 80 + (80 - fs(60).getbbox(poolTag)[-1]) / 2),
            ),
            poolTag,
            font=fs(60),
            fill="#ffffff",
            stroke_width=2,
            stroke_fill=poolTagEdge,
        )
        poolImgH += 20
        # 绘制抽数统计
        poolTotal: int = poolStat["total"]
        notStar5: int = poolStat["cntNot5"]
        texts = ["共计 ", str(poolTotal), " 抽，相当于 ", str(poolTotal * 160), " 原石"]
        if notStar5 and poolName != "新手祈愿":
            texts.extend(
                [
                    "\n",
                    str(notStar5),
                    " 抽未出{}五星，最多还需 ".format(
                        "限定"
                        if ("活动祈愿" in poolName)
                        and star5Data
                        and (not star5Data[-1]["up"])
                        else ""
                    ),
                    str((pityCnt - notStar5) * 160),
                    " 原石",
                ]
            )
        startW = 20
        for txtIdx, text in enumerate(texts):
            if text == "\n":
                poolImgH += fs(25).getbbox("高")[-1] + 10
                startW = 20
                continue
            color = (
                (
                    "#1890ff"
                    if txtIdx in [1, 3]
                    else percent(
                        (pityCnt - int(text)) if int(text) < 91 else (pityCnt - notStar5),
                        pityCnt,
                        "rgb",
                    )
                )
                if text.isdigit()
                else "black"
            )
            tDraw.text((startW, poolImgH), text, font=fs(25), fill=color)
            startW += fs(25).getlength(text)
        poolImgH += fs(25).getbbox("高")[-1] + 20 * 2
        # 绘制概率统计
        totalList = [
            {
                "rank": "五星",
                "cnt": poolStat["cntWeapon5"] + poolStat["cntChar5"],
                "cntUp": poolStat.get("cntUp5", 0),
                "color": "#C0713D",
            },
            {
                "rank": "四星",
                "cnt": poolStat["cntWeapon4"] + poolStat["cntChar4"],
                "cntUp": poolStat.get("cntUp4", 0),
                "color": "#A65FE2",
            },
            {"rank": "三星", "cnt": poolStat["cntStar3"], "color": "#4D8DF7"},
        ]
        for item in totalList:
            if not item["cnt"]:
                continue
            cntStr = "{}：{} 次{}".format(
                item["rank"],
                item["cnt"],
                f"（{item['cntUp']} 次限定）" if item.get("cntUp") else "",
            )
            probStr = f"[{item['cnt'] / poolTotal * 100:.2f}%]"
            tDraw.text((20, poolImgH), cntStr, font=fs(25), fill=item["color"])
            probStrW = fs(25).getlength(probStr)
            tDraw.text(
                (int((480 if int(banner) in [301, 302] else 400) - probStrW), poolImgH),
                probStr,
                font=fs(25),
                fill=item["color"],
            )
            poolImgH += fs(25).getbbox("高")[-1] + 20
        # 绘制五星物品统计
        poolImgH += 20
        if star5Data:
            statPic = await colorfulFive(star5Data, 25, 460, isWeapon)
            poolImg.paste(statPic, (20, poolImgH), statPic)
            poolImgH += statPic.size[1]
        # 绘制完成
        poolImgH += 20
        poolImg = poolImg.crop((0, 0, 500, poolImgH))
        imageList.append(poolImg)

    # 合并图片
    maxWidth = 500 * len(imageList)
    maxHeight = max([img.height for img in imageList])
    resultImg = Image.new("RGBA", (maxWidth, maxHeight), "#f9f9f9")
    tDraw = ImageDraw.Draw(resultImg)
    for i, img in enumerate(imageList):
        resultImg.paste(img, (500 * i, 0), img)

    # 绘制右下角更新时间戳及 UID
    # reportTime = strftime("%m-%d %H:%M:%S", localtime(rawData["time"]))
    stampStr = f"[{uid.replace(uid[3:-3], '***', 1)}]"
    stampW, stampH = fs(30).getbbox(stampStr)[-2:]
    tDraw.text(
        (int(maxWidth - stampW), int(maxHeight - stampH)),
        stampStr,
        font=fs(30),
        fill="#808080",
    )

    buf = BytesIO()
    resultImg.save(buf, format="PNG")
    return buf.getvalue()


async def gnrtGachaArchieve(rawData: Dict, uid: str) -> bytes:
    """
    抽卡成就图片生成，通过 pillow 绘制图片

    * ``param rawData: Dict`` 抽卡记录数据
    * ``param uid: str`` 用户 UID
    - ``return: bytes`` 图片字节数据
    """
    achievements = await calcAchievement(rawData)
    result = Image.new("RGBA", (720, 110 * len(achievements) + 10 + 100), "#f9f9f9")
    drawer = ImageDraw.Draw(result)

    # 标题
    title = f"UID{uid} 抽卡成就"
    drawer.text(
        (int((720 - fs(36, True).getlength(title)) / 2), 20),
        title,
        font=fs(36, True),
        fill="black",
        stroke_width=1,
        stroke_fill="grey",
    )
    # TODO: 使用绘制成就时的最后一抽的时间
    timeStr = strftime("%Y-%m-%d %H:%M:%S", localtime(int(time())))
    drawer.text(
        (int((720 - fs(18, True).getlength(timeStr)) / 2), 70),
        timeStr,
        font=fs(18, True),
        fill="#808080",
    )

    bgPure = Image.open(ACHIEVE_BG)
    bgDetail = Image.open(ACHIEVE_BG_DETAIL)
    for aIdx, achievement in enumerate(achievements):
        startHeight = 110 * (aIdx + 1)
        bg = bgDetail if achievement.get("value") else bgPure
        result.paste(bg, (10, startHeight), bg)
        # 名称
        drawer.text(
            (115, startHeight + 18),
            achievement["title"],
            font=fs(22, True),
            fill="#585757",
        )
        # 描述
        multilineText, tmpText, tmpLength = [], "", 0
        maxLength = 445 if achievement.get("value") else 565
        for s in achievement["info"]:
            length = fs(16, True).getlength(s)
            if tmpLength + length <= maxLength:
                tmpText += s
                tmpLength += length
            else:
                multilineText.append(tmpText)
                tmpText = s
                tmpLength = length
        if tmpText.strip():
            multilineText.append(tmpText)
        multilineText = [s.strip() for s in multilineText if s.strip()]
        spacing = (0.3 if len(multilineText) < 3 else 0.1) * 16
        drawer.multiline_text(
            (
                125,
                startHeight
                + 100
                - 18
                - 16 * len(multilineText)
                - spacing * (len(multilineText) - 1),
            ),
            "\n".join(multilineText),
            font=fs(16, True),
            fill="#988B81",
            spacing=spacing,
            align="left",
        )
        # 详情
        if achievement.get("value"):
            drawer.text(
                (
                    int(582 + (128 - fs(20, True).getlength(achievement["value"])) / 2),
                    int(
                        startHeight
                        + (100 - fs(20, True).getbbox(achievement["value"])[-1]) / 2
                    ),
                ),
                achievement["value"],
                font=fs(20, True),
                fill="#988B81",
            )
            drawer.text(
                (
                    int(
                        582
                        + (128 - fs(15, True).getlength(achievement["achievedTime"])) / 2
                    ),
                    int(
                        startHeight
                        + 76
                        + (20 - fs(15, True).getbbox(achievement["value"])[-1]) / 2
                    ),
                ),
                achievement["achievedTime"],
                font=fs(15, True),
                fill="#988B81",
            )

    buf = BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()
