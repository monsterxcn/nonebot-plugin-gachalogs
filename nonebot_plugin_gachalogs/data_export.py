import json
from time import localtime, strftime, time

from xlsxwriter import Workbook

from .__meta__ import getMeta

localDir = getMeta("localDir")
gachaTypeDict = getMeta("gachaTypeDict")
gachaTypeDictFull = getMeta("gachaTypeDictFull")


# 生成物品 ID
def gnrtId():
    id = 1000000000000000000
    while True:
        id = id + 1
        yield str(id)


# 转换原始请求结果为 UIGF JSON
async def transUIGF(uid: str, gachaLogs: dict) -> dict:
    UIGF = {
        "info": {
            "uid": uid,
            "lang": "zh-cn",
            "export_time": strftime("%Y-%m-%d %H:%M:%S", localtime()),
            "export_timestamp": int(time()),
            "export_app": "nonebot-genshin-gacha-export",
            "export_app_version": "v0.1.0",
            "uigf_version": "v2.2"
        },
        "list": []
    }
    # 写入数据
    for gachaType in gachaTypeDict:
        gachaLog = gachaLogs.get(gachaType, [])
        gachaLog = sorted(gachaLog, key=lambda i: i["time"], reverse=False)
        for item in gachaLog:
            item["uigf_gacha_type"] = gachaType
        UIGF["list"].extend(gachaLog)
    UIGF["list"] = sorted(UIGF["list"], key=lambda item: item["time"])
    # 缺失物品 ID 补充
    id = gnrtId()
    for item in UIGF["list"]:
        if item.get("id", "") == "":
            item["id"] = next(id)
    UIGF["list"] = sorted(UIGF["list"], key=lambda item: item["id"])
    # 返回 UIGF JSON
    return UIGF


# 转换原始请求结果为 UIGF XLSX
async def transXLSX(uid: str, gachaLogs: dict, uigfList: list) -> str:
    exportTime = strftime("%Y%m%d%H%M%S", localtime())
    wbPath = f"{localDir}Wish-{uid}-{exportTime}.xlsx"
    wb = Workbook(wbPath)
    # 重排顺序为 301 302 200 100（角色、武器、常驻、新手
    # sorted(gachaTypeDict.keys(), key=lambda item: item[0], reverse=True)
    gachaTypeList = ["301", "302", "200", "100"]
    for gachaType in gachaTypeList:
        # 新建页面和样式
        worksheet = wb.add_worksheet(gachaTypeDict[gachaType])
        headerStyle = wb.add_format({
            "align": "left",
            "font_name": "微软雅黑",
            "color": "#757575",
            "bg_color": "#dbd7d3",
            "border_color": "#c4c2bf",
            "border": 1,
            "bold": True
        })
        contentStyle = wb.add_format({
            "align": "left",
            "font_name": "微软雅黑",
            "border_color": "#c4c2bf",
            "bg_color": "#ebebeb",
            "border": 1
        })
        star5Style = wb.add_format({"color": "#bd6932", "bold": True})
        star4Style = wb.add_format({"color": "#a256e1", "bold": True})
        star3Style = wb.add_format({"color": "#8e8e8e"})
        worksheet.set_column("A:A", 22)
        worksheet.set_column("B:B", 14)
        worksheet.set_column("E:E", 14)
        # 表头
        header = ["时间", "名称", "物品类型", "星级", "祈愿类型", "总次数", "保底内"]
        worksheet.write_row(0, 0, header, headerStyle)
        worksheet.freeze_panes(1, 0)
        # 从最旧的数据开始写入
        counter = 0
        pityCounter = 0
        gachaList = gachaLogs[gachaType]
        gachaList.reverse()
        for item in gachaList:
            timeStr = item["time"]
            itemName = item["name"]
            itemType = item["item_type"]
            rankType = int(item["rank_type"])
            gachaType = item["gacha_type"]
            gachaTypeName = gachaTypeDictFull.get(gachaType, "")
            counter = counter + 1
            pityCounter = pityCounter + 1
            content = [
                timeStr, itemName, itemType, rankType,
                gachaTypeName, counter, pityCounter
            ]
            worksheet.write_row(counter, 0, content, contentStyle)
            if content[3] == 5:
                pityCounter = 0
        # 三星、四星、五星物品高亮
        contentRow1st, contentCol1st = 1, 0
        contentRowLast, contentColLast = len(gachaList), len(header) - 1
        worksheet.conditional_format(
            contentRow1st, contentCol1st, contentRowLast, contentColLast,
            {"type": "formula", "criteria": "=$D2=3", "format": star3Style}
        )
        worksheet.conditional_format(
            contentRow1st, contentCol1st, contentRowLast, contentColLast,
            {"type": "formula", "criteria": "=$D2=4", "format": star4Style}
        )
        worksheet.conditional_format(
            contentRow1st, contentCol1st, contentRowLast, contentColLast,
            {"type": "formula", "criteria": "=$D2=5", "format": star5Style}
        )
    # 原始数据表
    worksheet = wb.add_worksheet("原始数据")
    rawHeader = [
        "count", "gacha_type", "id", "item_id", "item_type", "lang",
        "name", "rank_type", "time", "uid", "uigf_gacha_type"
    ]
    worksheet.write_row(0, 0, rawHeader)
    allCounter = 0
    for item in uigfList:
        count = item.get("count", "")
        gachaType = item.get("gacha_type", "")
        id = item.get("id", "")
        itemId = item.get("item_id", "")
        itemType = item.get("item_type", "")
        lang = item.get("lang", "")
        name = item.get("name", "")
        rankType = item.get("rank_type", "")
        timeStr = item.get("time", "")
        uigfUid = item.get("uid", "")
        uigfGachaType = item.get("uigf_gacha_type", "")
        rawContent = [
            count, gachaType, id, itemId, itemType, lang,
            name, rankType, timeStr, uigfUid, uigfGachaType
        ]
        worksheet.write_row(allCounter + 1, 0, rawContent)
        allCounter += 1
    # 关闭工作簿
    wb.close()
    # 返回文件路径
    return wbPath


# 导出抽卡数据
async def exportGacha(rawData: dict, outFormat: str) -> dict:
    rt = {"msg": "", "file": ""}
    # 无抽卡记录数据直接返回
    if not rawData.get("gachaLogs", ""):
        rt["msg"] = "没有抽卡记录可供导出哦！"
        return rt
    # 判断输出格式
    if outFormat.lower() in ["j", "json", "u", "uigf"]:
        outFormat = "uigf"
    else:
        # if outFormat.lower() in ["x", "xlsx", "excel"]:
        outFormat = "xlsx"
    uid = rawData["uid"]
    gachaLogs = rawData["gachaLogs"]
    # 转换原始数据为 UIGF 格式数据
    uigfData = await transUIGF(uid, gachaLogs)
    # 生成对应格式文件
    if outFormat == "xlsx":
        xlsxPath = await transXLSX(uid, gachaLogs, uigfData["list"])
        rt["msg"] = "抽卡记录导出 Excel 完成！"
        rt["file"] = xlsxPath
    elif outFormat == "uigf":
        exportTime = strftime("%Y%m%d%H%M%S", localtime())
        uigfPath = f"{localDir}UIGF-{uid}-{exportTime}.json"
        with open(uigfPath, "w", encoding="utf-8") as f:
            json.dump(uigfData, f, ensure_ascii=False, indent=2)
        rt["msg"] = "抽卡记录导出 JSON(UIGF) 完成！"
        rt["file"] = uigfPath
    else:
        rt["msg"] = "暂未支持的导出格式！"
    return rt
