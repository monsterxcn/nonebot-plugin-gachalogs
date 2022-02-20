import json
import os
from time import time

from .__meta__ import getMeta
from .data_source import cacheData, mergeData

localDir = getMeta("localDir")


async def importUIGF(qq: str, uigfData: dict) -> dict:
    rawData = {
        "uid": uigfData["info"]["uid"],
        "time": uigfData["info"].get("export_timestamp", int(time())),
        "url": "",
        "gachaLogs": {
            "100": [],
            "200": [],
            "301": [],
            "302": [],
        }
    }
    rt = {"msg": "", "data": rawData}
    uigfData["list"].reverse()
    for item in uigfData["list"]:
        gachaType = item.get("gacha_type", "")
        uigfType = item.get("uigf_gacha_type", "")
        item.update({
            "uid": item.get("uid", rawData["uid"]),
            "gacha_type": gachaType if gachaType != "" else uigfType,
            "item_id": item.get("item_id", ""),
            "count": item.get("count", "1"),
            "time": item["time"],
            "name": item["name"],
            "lang": item.get("lang", "zh-cn"),
            "item_type": item["item_type"],
            "rank_type": item["rank_type"],
            "id": item["id"],
        })
        item.pop("uigf_gacha_type")
        nowType = item["gacha_type"]
        gachaTypeId = nowType if nowType != "400" else "301"
        rawData["gachaLogs"][gachaTypeId].append(item)
    import2File = f"{localDir}cache-{rawData['uid']}.json"
    # 如果已有本地记录尝试合并
    if os.path.isfile(import2File):
        backupFile = import2File.replace(".json", "-last.json")
        with open(import2File, "r", encoding="utf-8") as f:
            existData = json.load(f)
        with open(backupFile, "w", encoding="utf-8") as f:
            json.dump(existData, f, ensure_ascii=False, indent=2)
        wait2Merge = {"msg": "正在导入新的数据..", "data": existData}
        rt = await mergeData(wait2Merge, rt, qq, fw=False)
    # 写入本地缓存
    await cacheData(qq, rt["data"])
    return rt
