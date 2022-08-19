from base64 import b64encode
from copy import deepcopy
from io import BytesIO
from math import floor
from time import localtime, strftime
from typing import Dict, List, Literal, Tuple, Union

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from numpy import average
from PIL import Image, ImageDraw, ImageFont

from .__meta__ import GACHA_TYPE, PIE_FONT, PIL_FONT


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


def fs(size: int):
    """
    Pillow 绘制字体设置

    * ``param size: int`` 字体大小
    - ``return: ImageFont`` Pillow 字体对象
    """
    return ImageFont.truetype(str(PIL_FONT), size=size)


def img2Base64(pic: Image.Image) -> str:
    """
    Image 对象的 Base64 编码字符串转换

    * ``param pic: Image.Image`` Pillow 图片对象
    - ``return: str`` Base64 编码字符串
    """
    buf = BytesIO()
    pic.save(buf, format="PNG")
    b64Str = b64encode(buf.getbuffer()).decode()
    return "base64://" + b64Str


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
    ImageSize = (maxWidth, 400)
    coordX, coordY = 0, 0  # 绘制坐标
    fontPadding = 10  # 字体行间距
    result = Image.new("RGBA", ImageSize, "#f9f9f9")
    tDraw = ImageDraw.Draw(result)
    # 首行固定文本绘制
    text1st = "五星历史记录："
    tDraw.text((coordX, coordY), text1st, font=fs(fontSize), fill="black")
    indent1st, fH = fs(fontSize).getsize(text1st)
    spaceW = indent1st / len(text1st)  # 单个空格宽度，即 fs(fontSize).getsize("宽")[0]
    stepY = fH + fontPadding  # 单行绘制结束后的 Y 轴偏移量
    coordX += indent1st  # 首行绘制结束偏移 X 轴绘制坐标
    # 逐行绘制五星历史记录
    for item in star5Data:
        color = percent(item["count"], 80 if isWeapon else 90, "rgb")
        # 逐个绘制每个物品名称、抽数
        for word in [item["name"], f"[{item['count']}]"]:
            wordW = fs(fontSize).getsize(word)[0]
            if coordX + wordW <= maxWidth:
                # 当前行绘制未超过最大宽度限制，正常绘制
                tDraw.text((coordX, coordY), word, font=fs(fontSize), fill=color)
                # 偏移 X 轴绘制坐标使物品名称与自己的抽数间隔半个空格、抽数与下一个物品名称间隔一个空格
                coordX += (wordW + spaceW) if word[0] == "[" else (wordW + spaceW / 2)
            elif word[0] == "[":
                # 当前行绘制超过最大宽度限制，且当前绘制为抽数，换行绘制（保证 [ 与数字不分离）
                coordX, coordY = 0, (coordY + stepY)  # 偏移绘制坐标至下行行首
                tDraw.text((coordX, coordY), word, font=fs(fontSize), fill=color)
                coordX = wordW + spaceW  # 偏移 X 轴绘制坐标使抽数与下一个物品名称间隔一个空格
            else:
                # 当前行绘制超过最大宽度限制，且当前绘制为物品名称，逐字绘制直至超限后换行绘制
                aval = int((maxWidth - coordX) / spaceW)  # 当前行可绘制的最大字符数
                splitStr = [item["name"][:aval], item["name"][aval:]]
                for i in range(len(splitStr)):
                    s = splitStr[i]
                    tDraw.text((coordX, coordY), s, font=fs(fontSize), fill=color)
                    if i == 0:
                        # 当前行绘制完毕，偏移绘制坐标至下行行首
                        coordX, coordY = 0, (coordY + stepY)
                    else:
                        # 下一行绘制完毕，偏移 X 轴绘制坐标使物品名称与自己的抽数间隔半个空格
                        partW = fs(fontSize).getsize(s)[0]
                        coordX = partW + spaceW / 2
    # 所有五星物品数据绘制完毕，绘制五星概率统计结果
    coordY += stepY + fontPadding * 2  # 偏移 Y 轴绘制坐标至下两行行首（空出一行）
    star5Avg = average([item["count"] for item in star5Data])
    tDraw.text((0, coordY), "五星平均抽数：", font=fs(fontSize), fill="black")
    tDraw.text(
        (indent1st, coordY),
        f"{star5Avg:.2f}",
        font=fs(fontSize),
        fill=percent(round(star5Avg), 80 if isWeapon else 90, "rgb"),
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
                if rankType == 5:
                    gachaStat["star5"].append({"name": itemName, "count": pityCounter})
                    pityCounter = 0  # 重置保底计数器
        # 计算未出五星抽数
        star5Cnts = [
            gachaStat["star5"][n]["count"] for n in range(len(gachaStat["star5"]))
        ]
        gachaStat["cntNot5"] = counter - sum(star5Cnts)
        # 记录抽卡记录开始时间、结束时间
        if len(gachaList):
            timeNow = strftime("%Y-%m-%d %H:%M:%S", localtime())
            gachaStat["startTime"] = gachaList[0].get("time", timeNow)
            gachaStat["endTime"] = gachaList[-1].get("time", timeNow)
        # 更新待返回统计数据
        stat[banner] = gachaStat
    return stat


async def drawPie(
    stat: Dict, rt: Literal["base64", "image"] = "base64"
) -> Tuple[Union[str, Image.Image], bool]:
    """
    单个饼图绘制

    * ``param stat: Dict`` 统计数据，由 ``calcStat()`` 生成
    * ``param rt: Literal["base64", "image"] = "base64"`` 返回结果类型，默认为 Base64 编码字符串，传入 ``image`` 则返回 ``PIL.Image.Image`` 对象
    - ``return: Tuple[Union[str, Image.Image], bool]`` 返回结果、是否展示三星物品数据
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
    fig, ax = plt.subplots()
    fmProp = fm.FontProperties(fname=PIE_FONT)
    txtProp = {"fontsize": 16, "fontproperties": fmProp}
    ax.set_facecolor("#f9f9f9")
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
        textprops=txtProp,
    )
    ax.axis("equal")
    plt.tight_layout()
    # 生成图片
    ioBytes = BytesIO()
    plt.savefig(ioBytes, format="png")
    ioBytes.seek(0)
    if rt == "base64":
        b64Code = b64encode(ioBytes.read()).decode()
        return b64Code, showStar3
    else:
        return Image.open(ioBytes), showStar3


async def gnrtGachaInfo(rawData: Dict, uid: str) -> str:
    """
    抽卡统计信息图片生成，通过 pillow 和 matplotlib 绘制图片

    * ``param rawData: Dict`` 抽卡记录数据
    * ``param uid: str`` 用户 UID
    - ``return: str`` 图片 Base64 编码字符串
    """
    wishStat = await calcStat(rawData)
    gotPool = [key for key in wishStat if wishStat[key]["total"] > 0]
    imageList = []
    for banner in gotPool:
        poolName, poolStat = GACHA_TYPE[banner], wishStat[banner]
        isWeapon = True if banner == "302" else False  # 是否为武器祈愿
        poolImg = Image.new("RGBA", (500, 1500), "#f9f9f9")
        tDraw = ImageDraw.Draw(poolImg)
        # 绘制祈愿活动标题
        poolNameW, poolImgH = fs(30).getsize(poolName)
        tDraw.text(
            (int((500 - poolNameW) / 2), 20), poolName, font=fs(30), fill="black"
        )
        poolImgH += 20 * 2
        # 绘制饼状图
        pieImg, showStar3 = await drawPie(poolStat, rt="image")
        assert isinstance(pieImg, Image.Image)
        # pieImg.size = (640, 480)
        pieImg = pieImg.resize(
            (500, int(pieImg.height * 500 / pieImg.width)), Image.ANTIALIAS
        ).convert("RGBA")
        poolImg.paste(pieImg, (0, poolImgH), pieImg)
        poolImgH += pieImg.height
        if not showStar3:
            # 绘制隐藏三星数据提示
            tDraw.text(
                (15, int(poolImgH - 35)), "* 三星武器数据已隐藏", font=fs(20), fill="#808080"
            )
        # 绘制抽卡时间
        startTime = poolStat["startTime"].split(" ")[0]
        endTime = poolStat["endTime"].split(" ")[0]
        timeStat = f"{startTime} ~ {endTime}"
        poolImgH += 10
        timeStatW, timeStatH = fs(20).getsize(timeStat)
        tDraw.text(
            (int((500 - timeStatW) / 2), poolImgH),
            timeStat,
            font=fs(20),
            fill="#808080",
        )
        poolImgH += timeStatH + 20
        # 绘制抽数统计  TODO: 优化
        poolTotal = poolStat["total"]
        notStar5 = poolStat["cntNot5"]
        totalStr1 = "共计 "
        totalStr2 = str(poolTotal)
        totalStr3 = " 抽"
        totalStr4 = "，已累计 "
        totalStr5 = str(notStar5)
        totalStr6 = " 抽未出 5 星"
        startW = 20
        tDraw.text((startW, poolImgH), totalStr1, font=fs(25), fill="black")
        startW += fs(25).getsize(totalStr1)[0]
        tDraw.text((startW, poolImgH), totalStr2, font=fs(25), fill="rgb(24,144,255)")
        startW += fs(25).getsize(totalStr2)[0]
        tDraw.text((startW, poolImgH), totalStr3, font=fs(25), fill="black")
        if notStar5 > 0 and poolName != "新手祈愿":
            pityCnt = 80 if isWeapon else 90
            notStar5Color = percent(notStar5, pityCnt, "rgb")
            startW += fs(25).getsize(totalStr3)[0]
            tDraw.text((startW, poolImgH), totalStr4, font=fs(25), fill="black")
            startW += fs(25).getsize(totalStr4)[0]
            tDraw.text((startW, poolImgH), totalStr5, font=fs(25), fill=notStar5Color)
            startW += fs(25).getsize(totalStr5)[0]  # "rgb(47,192,22)"
            tDraw.text((startW, poolImgH), totalStr6, font=fs(25), fill="black")
        poolImgH += fs(25).getsize(totalStr1)[1] + 20 * 2
        # 绘制概率统计
        totalStar = {
            "五星": {
                "cnt": poolStat["cntWeapon5"] + poolStat["cntChar5"],
                "color": "#C0713D",
            },
            "四星": {
                "cnt": poolStat["cntWeapon4"] + poolStat["cntChar4"],
                "color": "#A65FE2",
            },
            "三星": {"cnt": poolStat["cntStar3"], "color": "#4D8DF7"},
        }
        probList = [
            {"level": key, "total": value["cnt"], "color": value["color"]}
            for key, value in totalStar.items()
            if value["cnt"] > 0
        ]
        for item in probList:
            cntStr = f"{item['level']}：{item['total']} 次"
            probStr = f"[{item['total'] / poolTotal * 100:.2f}%]"
            tDraw.text((20, poolImgH), cntStr, font=fs(25), fill=item["color"])
            probStrW = fs(25).getsize(probStr)[0]
            tDraw.text(
                (int(400 - probStrW), poolImgH),
                probStr,
                font=fs(25),
                fill=item["color"],
            )
            poolImgH += fs(25).getsize(cntStr)[1] + 20
        # 绘制五星物品统计
        poolImgH += 20
        star5Data = poolStat["star5"]
        if star5Data:
            statPic = await colorfulFive(star5Data, 25, 460, isWeapon)
            statPicW, statPicH = statPic.size
            statPicCoord = (int((500 - statPicW) / 2), poolImgH)
            poolImg.paste(statPic, statPicCoord, statPic)
            poolImgH += statPicH
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
    stampW, stampH = fs(30).getsize(stampStr)
    tDraw.text(
        (int(maxWidth - stampW), int(maxHeight - stampH)),
        stampStr,
        font=fs(30),
        fill="#808080",
    )
    return img2Base64(resultImg)
