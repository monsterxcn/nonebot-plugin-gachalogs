# Modified from @sunfkny/genshin-gacha-export
# https://github.com/sunfkny/genshin-gacha-export/blob/main/UIGF_converter.py
# https://github.com/sunfkny/genshin-gacha-export/blob/main/writeXLSX.py

import json
from pathlib import Path
from time import localtime, strftime, time
from typing import Dict, List, Literal

from nonebot.log import logger
from xlsxwriter import Workbook

from .__meta__ import GACHA_TYPE, GACHA_TYPE_FULL, LOCAL_DIR
from .data_source import logsHelper


def gnrtId():
    """生成物品 ID"""
    id = 1000000000000000000
    while True:
        id = id + 1
        yield str(id)


async def transUIGF(uid: str, gachaLogs: Dict) -> Dict:
    """
    转换原始请求结果为 UIGF JSON

    * ``param uid: str`` 抽卡记录所属 UID
    * ``param gachaLogs: dict`` 原始请求结果
    - ``return: Dict`` UIGF 格式数据
    """
    uigf = {
        "info": {
            "uid": uid,
            "lang": "zh-cn",
            "export_time": strftime("%Y-%m-%d %H:%M:%S", localtime()),
            "export_timestamp": int(time()),
            "export_app": "nonebot-plugin-gachalogs",
            "export_app_version": "v0.2.0",
            "uigf_version": "v2.2",
        },
        "list": [],
    }
    # 转换数据
    for banner in GACHA_TYPE:
        gachaLog = gachaLogs.get(banner, [])
        gachaLog = sorted(gachaLog, key=lambda i: i["time"], reverse=False)
        for item in gachaLog:
            item["uigf_gacha_type"] = banner
        uigf["list"].extend(gachaLog)
    uigf["list"] = sorted(uigf["list"], key=lambda i: i["time"])
    # 缺失物品 ID 补充
    id = gnrtId()
    for item in uigf["list"]:
        if not item.get("id"):
            item["id"] = next(id)
    uigf["list"] = sorted(uigf["list"], key=lambda i: i["id"])
    # 返回 UIGF JSON
    return uigf


async def transXLSX(uid: str, gachaLogs: Dict, uigfList: List) -> Path:
    """
    转换原始请求结果为 UIGF XLSX

    * ``param uid: str`` 抽卡记录所属 UID
    * ``param gachaLogs: dict`` 原始请求结果
    * ``param uigfList: list`` UIGF 格式数据，由 ``transUIGF()`` 生成
    - ``return: str`` XLSX 文件路径
    """
    exportTime = strftime("%Y%m%d%H%M%S", localtime())
    wbPath = LOCAL_DIR / f"Wish-{uid}-{exportTime}.xlsx"
    wb = Workbook(wbPath)
    # 重排顺序为 301 302 200 100（角色、武器、常驻、新手
    writeOrder = sorted(GACHA_TYPE.keys(), key=lambda t: t[0], reverse=True)
    for banner in writeOrder:
        # 新建页面
        worksheet = wb.add_worksheet(GACHA_TYPE[banner])
        # 定义样式
        headerStyle = wb.add_format(
            {
                "align": "left",
                "font_name": "微软雅黑",
                "color": "#757575",
                "bg_color": "#dbd7d3",
                "border_color": "#c4c2bf",
                "border": 1,
                "bold": True,
            }
        )
        contentStyle = wb.add_format(
            {
                "align": "left",
                "font_name": "微软雅黑",
                "border_color": "#c4c2bf",
                "bg_color": "#ebebeb",
                "border": 1,
            }
        )
        star5Style = wb.add_format({"color": "#bd6932", "bold": True})
        star4Style = wb.add_format({"color": "#a256e1", "bold": True})
        star3Style = wb.add_format({"color": "#8e8e8e"})
        worksheet.set_column("A:A", 22)
        worksheet.set_column("B:B", 14)
        worksheet.set_column("E:E", 14)
        # 写入表头
        header = ["时间", "名称", "物品类型", "星级", "祈愿类型", "总次数", "保底内"]
        worksheet.write_row(0, 0, header, headerStyle)
        worksheet.freeze_panes(1, 0)
        # 写入记录，从最旧的数据开始
        counter = 0
        pityCounter = 0
        gachaList = gachaLogs.get(banner, [])
        gachaList.reverse()
        for item in gachaList:
            counter = counter + 1
            pityCounter = pityCounter + 1
            content = [
                item["time"],
                item["name"],
                item["item_type"],
                int(item["rank_type"]),
                GACHA_TYPE_FULL.get(item["gacha_type"], ""),
                counter,
                pityCounter,
            ]
            worksheet.write_row(counter, 0, content, contentStyle)
            if content[3] == 5:
                pityCounter = 0
        # 三星、四星、五星物品高亮
        row1st, rowLast = 1, len(gachaList)
        col1st, colLast = 0, len(header) - 1
        tmpRank = 3
        for style in [star3Style, star4Style, star5Style]:
            formula = {
                "type": "formula",
                "criteria": f"=$D2={tmpRank}",
                "format": style,
            }
            worksheet.conditional_format(row1st, col1st, rowLast, colLast, formula)
    # 额外新建原始数据页面
    worksheet = wb.add_worksheet("原始数据")
    rawHeader = [
        "count",
        "gacha_type",
        "id",
        "item_id",
        "item_type",
        "lang",
        "name",
        "rank_type",
        "time",
        "uid",
        "uigf_gacha_type",
    ]
    worksheet.write_row(0, 0, rawHeader)
    allCounter = 0
    for item in uigfList:
        rawContent = [
            item.get("count", ""),
            item.get("gacha_type", ""),
            item.get("id", ""),
            item.get("item_id", ""),
            item.get("item_type", ""),
            item.get("lang", ""),
            item.get("name", ""),
            item.get("rank_type", ""),
            item.get("time", ""),
            item.get("uid", ""),
            item.get("uigf_gacha_type", ""),
        ]
        worksheet.write_row(allCounter + 1, 0, rawContent)
        allCounter += 1
    # 关闭工作簿
    wb.close()
    # 返回文件路径
    return wbPath


# 导出抽卡数据
async def gnrtGachaFile(config: Dict, outFormat: Literal["xlsx", "json"]) -> Dict:
    """
    导出抽卡数据

    * ``param config: Dict`` 配置文件
    * ``param outFormat: Literal["xlsx", "json"]`` 导出格式
    * ``return: Dict`` 导出结果，出错时返回 ``{"error": "错误信息"}``
    """
    # 无抽卡记录数据直接返回
    if not config.get("logs"):
        return {"error": "没有抽卡记录可供导出哦！"}
    # 读取抽卡记录缓存
    uid, gachaLogs = await logsHelper(config["logs"])
    if not uid.isdigit():
        return {"error": uid}
    # 转换原始数据为 UIGF 格式数据
    uigfData = await transUIGF(uid, gachaLogs)
    # 生成对应格式文件
    try:
        if outFormat == "xlsx":
            xlsxPath = await transXLSX(uid, gachaLogs, uigfData["list"])
            return {"msg": "导出抽卡记录 Excel 完成！", "path": xlsxPath}
        elif outFormat == "json":
            exportTime = strftime("%Y%m%d%H%M%S", localtime())
            uigfPath = LOCAL_DIR / f"UIGF-{uid}-{exportTime}.json"
            with open(uigfPath, "w", encoding="utf-8") as f:
                json.dump(uigfData, f, ensure_ascii=False, indent=2)
            return {"msg": "导出抽卡记录 JSON(UIGF) 完成！", "path": uigfPath}
    except Exception as e:
        logger.error(f"导出抽卡记录失败 {type(e)}\n{e}")
        return {"error": f"因为 {type(e)} 导出失败了.."}
