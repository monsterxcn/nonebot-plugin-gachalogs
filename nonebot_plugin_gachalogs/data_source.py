
import json
import os
import re
import sys
from asyncio import sleep as asleep
from time import time
from urllib import parse

from httpx import AsyncClient
from nonebot.log import logger

from .__meta__ import getMeta

localDir = getMeta("localDir")
expireSec = getMeta("expireSec")
basicUrl = getMeta("basicUrl")
basicUrlOversea = getMeta("basicUrlOversea")
gachaTypeDict = getMeta("gachaTypeDict")


# 检查抽卡记录链接是否失效 [httpx]
# 返回值：str
#   "成功" / 错误信息
async def checkAuthKey(url: str) -> str:
    try:
        async with AsyncClient() as client:
            res = await client.get(url)
            resJson = res.json()
        # with open(f"{localDir}checkAuthKey-{int(time.time())}.json", "w",
        #           encoding="utf-8") as f:
        #     json.dump(resJson, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("抽卡记录 API 请求解析出错："
                     + str(sys.exc_info()[0]) + "\n" + str(e))
        return "检查链接时效性出错\n[{}]".format(str(sys.exc_info()[0]))
    if not resJson["data"]:
        return "链接 AuthKey 可能失效\n[{}]".format(resJson["message"])
    return "成功"


# 检查及提取抽卡记录链接 [checkAuthKey]
# 返回值：str
#   抽卡记录链接 / 错误信息
async def checkLogUrl(logUrl: str) -> str:
    if not logUrl:
        return "请至少给我一次抽卡记录链接！"
    logUrl = logUrl.replace("&amp;", "&")
    # 含有关键词视为正确链接
    if "getGachaLog" in logUrl:
        url = logUrl
    else:
        # 提取输入字符中的抽卡记录链接并转换
        matchUrl = re.search("hk4e/event/.*#/log", logUrl)
        if not matchUrl:
            return "未找到有效的抽卡记录链接！"
        url = f"https://webstatic.mihoyo.com/{matchUrl.group(0)}"
        splitUrl = url.split("?")
        if "webstatic-sea" in splitUrl[0] or "hk4e-api-os" in splitUrl[0]:
            splitUrl[0] = basicUrlOversea
        else:
            splitUrl[0] = basicUrl
        url = "?".join(splitUrl)
    # 检查抽卡记录链接是否有效
    keyStatus = await checkAuthKey(url)
    if keyStatus != "成功":
        return keyStatus
    return url


# 获取本地缓存抽卡记录 [fileread]
# 返回值：dict
#   msg: "" / 错误信息
#   data: 抽卡记录数据 / {"time": int}
async def getCacheData(qq: str) -> dict:
    cache = {"msg": "", "data": {}}
    cacheFile = localDir + "cache-config.json"
    # 本地无缓存配置文件时，创建缓存配置文件
    if not os.path.isfile(cacheFile):
        with open(cacheFile, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        cache["msg"] = "暂无本地抽卡记录！"
        cache["data"]["time"] = int(time()) - expireSec - 1
        return cache
    with open(cacheFile, "r", encoding="utf-8") as f:
        cacheConfig = json.load(f)
    # 本地有缓存配置文件时，检查是否有用户缓存
    if qq not in cacheConfig.keys():
        cache["msg"] = "暂无本地抽卡记录！"
        cache["data"]["time"] = int(time()) - expireSec - 1
        return cache
    # 本地有用户缓存时读取缓存的抽卡记录
    with open(cacheConfig[qq], "r", encoding="utf-8") as f:
        cachedRawData = json.load(f)
    cache["data"] = cachedRawData
    return cache


# 获取指定类型抽卡记录单页链接
# 返回值：str "https://..."
def getGachaLogsApi(url: str, page: int, typeId: str, endId: str) -> str:
    parsed = parse.urlparse(url)
    querys = parse.parse_qsl(str(parsed.query))
    paramDict = dict(querys)
    paramDict.update({
        "size": "20",  # 限制单页最大获取总抽数 20
        "gacha_type": typeId,
        "page": str(page),
        "lang": "zh-cn",
        "end_id": endId,
    })
    param = parse.urlencode(paramDict)
    path = str(url).split("?")[0]
    api = path + "?" + param
    return api


# 获取指定类型抽卡记录 [getGachaLogsApi]
# 返回值：list [{}, {}, ...]
async def getGachaList(url: str, gachaTypeId: str) -> list:
    gachaList, endId, page = [], "0", 1
    for pageTryCnt in range(1, 9999):
        logger.debug(f"正在获取 {gachaTypeDict[gachaTypeId]} 第 {page} 页")
        api = getGachaLogsApi(url, page, gachaTypeId, endId)
        gachaListPage = []
        async with AsyncClient() as client:
            res = await client.get(api)
            resJson = res.json()
        # with open(f"{localDir}getGachaList-{gachaTypeId}-{page}.json", "w",
        #           encoding="utf-8") as f:
        #     json.dump(resJson, f, ensure_ascii=False, indent=2)
        if resJson["data"]:
            gachaListPage = resJson["data"].get("list", [])
        elif resJson["message"] == "visit too frequently":
            # 访问过于频繁，等待 5s
            await asleep(5)
            continue
        if not gachaListPage:
            break
        for item in gachaListPage:
            gachaList.append(item)
        # 更新下一页用于生成链接的数据
        endId = resJson["data"]["list"][-1]["id"]
        page += 1
        await asleep(1)
    return gachaList


# 获取全部类型抽卡记录 [checkLogUrl] [getGachaList]
# 返回值：dict
#   msg: "" / 错误信息
#   data: 抽卡记录数据 / {"uid": "", ...}
async def getRawData(logUrl: str, force: bool = False) -> dict:
    raw = {"msg": "" if not force else "强制获取最新数据..", "data": {}}
    # 检查链接是否失效
    logUrlChecked = await checkLogUrl(logUrl)
    if "getGachaLog" not in logUrlChecked:
        raw["msg"] += logUrlChecked
        return raw
    # 获取最新抽卡记录
    uidGot = False
    gachaData = {
        "uid": "",
        "time": "",
        "url": logUrlChecked,
        "gachaLogs": {}
    }
    for gachaType in gachaTypeDict:
        gachaList = await getGachaList(logUrlChecked, gachaType)
        gachaData["gachaLogs"][gachaType] = gachaList
        # 从记录中获取一次 UID
        if gachaList and not uidGot:
            gachaData["uid"] = gachaList[0]["uid"]
            uidGot = True
    gachaData["time"] = int(time())
    raw["data"] = gachaData
    if not uidGot:
        raw["msg"] = "获取最新抽卡记录失败！"
    return raw


# 缓存数据 [filewrite]
async def cacheData(qq: str, rawData: dict) -> None:
    uid = rawData["uid"]
    # 创建 UID 对应缓存文件
    cacheFile = localDir + f"cache-{uid}.json"
    with open(cacheFile, "w", encoding="utf-8") as f:
        json.dump(rawData, f, ensure_ascii=False, indent=2)
    # 更新用于 getCacheData 的缓存配置文件
    cgfFile = localDir + "cache-config.json"
    with open(cgfFile, "r", encoding="utf-8") as f:
        cacheConfig = json.load(f)
    cacheConfig[qq] = cacheFile
    with open(cgfFile, "w", encoding="utf-8") as f:
        json.dump(cacheConfig, f, ensure_ascii=False, indent=2)


# 合并数据 [cacheData]
# 返回值：dict
#   msg: 合并消息
#   data: 合并数据
async def mergeData(cache: dict, raw: dict, qq: str, fw: bool = True) -> dict:
    # 若无新增数据，则直接返回缓存数据
    if not raw["data"].get("gachaLogs", {}):
        cache["msg"] += raw["msg"]
        return cache
    # 若无缓存数据，则直接返回新增数据
    if not cache["data"].get("gachaLogs", {}):
        raw["msg"] = cache["msg"] + raw["msg"]
        if raw["data"].get("gachaLogs", {}):
            await cacheData(qq, raw["data"])
        return raw
    # 既有缓存数据又有新增数据，执行合并
    locData = cache["data"]
    newData = raw["data"]
    msgList = []
    merged = {"msg": "", "data": {}}
    for gachaType in gachaTypeDict:
        logsLoc = locData["gachaLogs"][gachaType]
        logsNew = newData["gachaLogs"][gachaType]
        # 新增数据与缓存数据不同时合并
        if logsNew != logsLoc:
            tempList = []
            itemsGot = [[got["time"], got["name"]] for got in logsLoc]
            for i in range(len(logsNew)):
                item = [logsNew[i]["time"], logsNew[i]["name"]]
                if item not in itemsGot:
                    tempList.insert(0, logsNew[i])
                else:
                    pass
            for item in tempList:
                locData["gachaLogs"][gachaType].insert(0, item)
            if tempList:
                s = f"新增 {len(tempList)} 条{gachaTypeDict[gachaType]}记录.."
                msgList.append(s)
        else:
            pass
    # 处理附加信息
    locData["uid"] = newData["uid"]
    locData["time"] = newData["time"]
    locData["url"] = newData["url"]
    # 缓存合并数据并生成结果
    if fw:
        await cacheData(qq, locData)
    merged["data"] = locData
    merged["msg"] = "\n".join(msgList)
    if cache["msg"] or raw["msg"]:
        merged["msg"] = cache["msg"] + raw["msg"] + "\n" + merged["msg"]
    return merged


# 获取抽卡记录入口 [getCacheData] [getRawData] [mergeData]
# 返回值：dict
#   msg: "" / 合并消息 / 错误信息
#   data: 抽卡记录数据 / 合并数据 / {"": "", ...}
async def getGachaData(qq: str, logUrl: str = "",
                       cache: dict = {}, force: bool = False) -> dict:
    # 读取缓存
    cache = await getCacheData(qq) if not cache else cache
    now = int(time())
    # 缓存未过期且未要求强制刷新，返回缓存数据
    if now - cache["data"]["time"] < expireSec and not force:
        return cache
    if force and not logUrl:
        cache["msg"] += "（强制刷新不可用！"
        return cache
    # 无链接且要求强制刷新，返回缓存数据
    logUrl = logUrl if logUrl else cache["data"].get("url", "")
    # 刷新数据
    raw = await getRawData(logUrl, force=force)
    # 合并数据
    fullData = await mergeData(cache, raw, qq)
    return fullData
