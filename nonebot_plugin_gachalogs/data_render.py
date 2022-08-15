from base64 import b64encode
from copy import deepcopy
from io import BytesIO
from math import floor
from pathlib import Path
from time import localtime, strftime
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from numpy import average
from PIL import Image, ImageDraw, ImageFont

from .__meta__ import getMeta

localDir = getMeta("localDir")
gachaTypeDict = getMeta("gachaTypeDict")
assert isinstance(localDir, Path)
assert isinstance(gachaTypeDict, Dict)
pieFontPath = localDir / "LXGW-Bold-minipie.ttf"
pilFontPath = localDir / "LXGW-Bold.ttf"


# 返回百分数字符串 / 根据百分数返回颜色
def percent(a: int, b: int, rt: str = "") -> str:
    if not rt:
        return str(round(a / b * 100, 2)) + "%"
    # 由概率生成颜色
    # https://github.com/voderl/genshin-gacha-analyzer/blob/main/src/pages/ShowPage/AnalysisChart/utils.ts
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


# 设置 Pillow 绘制字体
def fs(size: int):
    return ImageFont.truetype(str(pilFontPath), size=size)


# 转换 Image 对象图片为 Base64 编码字符串
def img2Base64(pic: Image.Image) -> str:
    buf = BytesIO()
    pic.save(buf, format="PNG", quality=100)
    base64_str = b64encode(buf.getbuffer()).decode()
    return "base64://" + base64_str


# 逐行绘制不超过宽度限制的彩色五星历史记录文字
async def colorfulFive(
    star5Data: List, fontSize: int, maxWidth: int, isWeapon: bool = False
) -> Image.Image:
    ImageSize = (maxWidth, 400)
    coordX, coordY = 0, 0
    fontPadding = 10
    text1st = "五星历史记录："
    indent1st, fH = fs(fontSize).getsize(text1st)
    spaceW = indent1st / len(text1st)
    stepY = fH + fontPadding
    result = Image.new("RGBA", ImageSize, "#f9f9f9")
    tDraw = ImageDraw.Draw(result)
    tDraw.text((coordX, coordY), text1st, font=fs(fontSize), fill="black")
    coordX += indent1st
    for item in star5Data:
        color = percent(item["count"], 80 if isWeapon else 90, "color")
        for word in [item["name"], f"[{item['count']}]"]:
            wordW = fs(fontSize).getsize(word)[0]
            if coordX + wordW <= maxWidth:
                tDraw.text((coordX, coordY), word, font=fs(fontSize), fill=color)
                coordX += wordW + spaceW / 2
            elif word[0] == "[":
                coordX, coordY = 0, (coordY + stepY)
                tDraw.text((coordX, coordY), word, font=fs(fontSize), fill=color)
                coordX = wordW + spaceW
            else:
                aval = int((maxWidth - coordX) / spaceW)
                splitStr = [item["name"][:aval], item["name"][aval:]]
                for i in range(len(splitStr)):
                    s = splitStr[i]
                    tDraw.text((coordX, coordY), s, font=fs(fontSize), fill=color)
                    if i == 0:
                        coordX, coordY = 0, (coordY + stepY)
                    else:
                        partW = fs(fontSize).getsize(s)[0]
                        coordX = partW + spaceW / 2
    coordY += stepY + fontPadding * 2
    star5Avg = average([item["count"] for item in star5Data])
    tDraw.text((0, coordY), "五星平均抽数：", font=fs(fontSize), fill="black")
    tDraw.text(
        (indent1st, coordY),
        f"{star5Avg:.2f}",
        font=fs(fontSize),
        fill=percent(round(star5Avg), 80 if isWeapon else 90, "color"),
    )
    result = result.crop((0, 0, maxWidth, coordY + fH))
    return result


# 提取统计数据
async def calcStat(gachaLogs: Dict) -> Dict:
    single = {
        "total": 0,
        "cntNot5": 0,
        "cntStar3": 0,
        "cntChar4": 0,
        "cntWeapon4": 0,
        "cntChar5": 0,
        "cntWeapon5": 0,
        "star5": [],
        "startTime": "",
        "endTime": "",
    }
    # 重排顺序为 301 302 200 100（角色、武器、常驻、新手
    selfType = sorted(gachaTypeDict.keys(), key=lambda k: k[0], reverse=True)
    stat = {gachaTypeId: deepcopy(single) for gachaTypeId in selfType}
    for gachaType in gachaLogs:
        counter = 0
        pityCounter = 0
        gachaStat = stat[gachaType]
        gachaList = gachaLogs[gachaType]
        gachaList.reverse()
        # !dont gachaList.sort(key=lambda item: item["time"], reverse=False)
        for item in gachaList:
            counter = counter + 1
            pityCounter = pityCounter + 1
            itemName = item["name"]
            itemType = item["item_type"]
            rankType = int(item["rank_type"])
            gachaStat["total"] = counter
            if rankType == 3:
                gachaStat["cntStar3"] += 1
            else:
                t = "cntChar" if itemType == "角色" else "cntWeapon"
                gachaStat[t + str(rankType)] += 1
                if rankType == 5:
                    gachaStat["star5"].append({"name": itemName, "count": pityCounter})
                    pityCounter = 0
        star5Cnts = [
            gachaStat["star5"][n]["count"] for n in range(len(gachaStat["star5"]))
        ]
        gachaStat["cntNot5"] = counter - sum(star5Cnts)
        if len(gachaList):
            timeNow = strftime("%Y-%m-%d %H:%M:%S", localtime())
            gachaStat["startTime"] = gachaList[0].get("time", timeNow)
            gachaStat["endTime"] = gachaList[-1].get("time", timeNow)
    return stat


# 绘制单个饼图
async def drawPie(stat: Dict, rt: str = "") -> Tuple[str, Image.Image, bool]:
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
    fmProp = fm.FontProperties(fname=pieFontPath)
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
        return b64Code, Image.new("RGB", (0, 0)), showStar3
    else:
        return "", Image.open(ioBytes), showStar3


# 通过 PIL 和 matplotlib 绘制统计信息图片
async def gnrtGachaInfo(rawData: Dict) -> str:
    wishStat = await calcStat(rawData["gachaLogs"])
    gotPool = [key for key in wishStat if wishStat[key]["total"] > 0]
    imageList = []
    for gachaType in gotPool:
        poolImg = Image.new("RGBA", (500, 1500), "#f9f9f9")
        tDraw = ImageDraw.Draw(poolImg)
        poolStat = wishStat[gachaType]
        poolName = gachaTypeDict[gachaType]
        isWeapon = True if gachaType == "302" else False
        # 绘制标题
        poolNameW, poolImgH = fs(30).getsize(poolName)
        tDraw.text(
            (int((500 - poolNameW) / 2), 20), poolName, font=fs(30), fill="black"
        )
        poolImgH += 20 * 2
        # 绘制饼状图
        _, pieImg, showStar3 = await drawPie(poolStat)
        # pieImg.size = (640, 480)
        pieImg = pieImg.resize(
            (500, int(pieImg.height * 500 / pieImg.width)), Image.ANTIALIAS
        ).convert("RGBA")
        poolImg.paste(pieImg, (0, poolImgH), pieImg)
        poolImgH += pieImg.height
        if not showStar3:
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
        # 绘制抽数统计
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
            notStar5Color = percent(notStar5, pityCnt, "color")
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
    # 右下角待绘制数据（更新时间戳及 UID
    # reportTime = strftime("%m-%d %H:%M:%S", localtime(rawData["time"]))
    stampStr = f"[{rawData['uid'].replace(rawData['uid'][3:-3], '***', 1)}]"
    stampW, stampH = fs(30).getsize(stampStr)
    # 合并图片
    maxWidth = 500 * len(imageList)
    maxHeight = max([img.height for img in imageList])
    resultImg = Image.new("RGBA", (maxWidth, maxHeight), "#f9f9f9")
    tDraw = ImageDraw.Draw(resultImg)
    for i, img in enumerate(imageList):
        resultImg.paste(img, (500 * i, 0), img)
    tDraw.text(
        (int(maxWidth - stampW), int(maxHeight - stampH)),
        stampStr,
        font=fs(30),
        fill="#808080",
    )
    resImgB64 = img2Base64(resultImg)
    return resImgB64
