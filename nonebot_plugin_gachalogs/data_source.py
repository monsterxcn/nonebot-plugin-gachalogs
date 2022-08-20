import json
import random
import string
import uuid
from asyncio import sleep as asyncsleep
from hashlib import md5
from pathlib import Path
from re import search
from time import localtime, strftime, time
from typing import Dict, List, Literal, Tuple, Union
from urllib import parse

from httpx import AsyncClient
from nonebot.log import logger

from .__meta__ import (
    AUTHKEY_API,
    CLIENT_SALT,
    CLIENT_TYPE,
    CLIENT_VERSION,
    EXPIRE_SEC,
    GACHA_TYPE,
    LOCAL_DIR,
    POOL_API,
    ROLE_API,
    ROOT_OVERSEA_URL,
    ROOT_URL,
    TOKEN_API,
)


def formatInput(input: str, find: Literal["url", "cookie"]) -> Dict:
    """
    输入内容格式化，可根据输入内容提取抽卡记录链接或米游社 Cookie

    * ``param input: str`` 输入内容
    * ``param find: Literal["url", "cookie"]`` 提取内容类型
    - ``return: str`` 提取结果，格式为 ``{"url": "链接"}`` 或 ``{"login_ticket": "xx", "stoken": "xx", ...}``，出错时返回 ``{}``
    """
    if find == "cookie":
        if not input:
            return {}
        cookieDict = {}
        params = [
            "account_id",
            "cookie_token",
            "login_ticket",
            "login_uid",
            "ltoken",
            "ltuid",
            "mid",
            "stoken",
            "stuid",
        ]
        for param in params:
            match = search(rf"(^| ){param}=([^;]*)", input)
            if match:
                # 去除结尾分号、空格、引号
                cookieDict[param] = match.group(2).rstrip("; '\"")
        # account_id, login_uid, stuid, ltuid 同为米游社 ID
        for param in ["account_id", "login_uid", "stuid", "ltuid"]:
            if cookieDict.get(param):
                for p in ["account_id", "login_uid", "stuid", "ltuid"]:
                    cookieDict[p] = cookieDict[param]
                break
        # return "; ".join([f"{k}={v}" for k, v in cookieDict.items()])
        return cookieDict
    elif find == "url":
        # ref: https://ihateregex.io/expr/url
        urlReg = r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()!@:%_\+.~#?&\/\/=]*)"
        matchUrl = search(urlReg, input.replace("&amp;", "&"))
        if matchUrl:
            # 找到链接后替换 Host
            root, query = matchUrl[0].split("?")
            urlRoot = (
                ROOT_OVERSEA_URL
                if any(x in root for x in ["webstatic-sea", "hk4e-api-os"])
                else ROOT_URL
            )
            return {"url": urlRoot + "?" + query}
        return {}


async def configHelper(qq: str, data: Dict = {}) -> Dict:
    """
    配置缓存助手，既可根据 QQ 读取配置，也可根据数据写入/删除配置缓存

    * ``param qq: str`` 目标 QQ
    * ``param data: Dict = {}`` 配置数据，根据是否传入决定更新或读取，只有配置中有链接、Cookie 或抽卡记录缓存 或 配置中包含 force/delete 参数时才写入
    - ``return: Dict`` 目标 QQ 的配置数据，删除时返回 ``{}``，出错时返回 ``{"error": "错误信息"}``
    """
    cfgFile = LOCAL_DIR / "config.json"
    # 尝试读取本地配置文件
    if not cfgFile.exists():
        cfgFile.write_text("{}", encoding="utf-8")
        cfg = {}
    else:
        cfg = json.loads(cfgFile.read_text(encoding="utf-8"))
    assert isinstance(cfg, Dict)
    # 根据是否传入配置数据决定写入/删除或读取
    if data:
        # 配置中有链接、Cookie 或抽卡记录缓存 或 配置中包含 force/delete 参数时视为有效输入
        if data.get("delete"):
            validInput, delMode = True, data["delete"]
            modeStr = "配置已删除" if delMode == "全部配置" else "记录已删除"
            data.pop("delete")
        elif data.get("force"):
            validInput = bool(data["force"])
            delMode, modeStr = "", ("已更新" if validInput else "未更新")
            data.pop("force")
        else:
            validInput = bool(data.get("url") or data.get("cookie") or data.get("logs"))
            delMode, modeStr = "", ("已更新" if validInput else "未更新")
        try:
            if validInput:
                if delMode == "全部配置":
                    cfg.pop(qq)
                else:
                    cfg[qq] = data
                cfgFile.write_text(
                    json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            else:
                cfg[qq] = {}
                logger.info(f"QQ{qq} 的配置写入被跳过")
            logger.info(f"QQ{qq} 的配置{modeStr}\n{'{}' if delMode else cfg[qq]}")
            return {} if delMode else cfg[qq]
        except Exception as e:
            logger.error(f"QQ{qq} 的配置缓存{modeStr}失败：{type(e)}")
            return {"error": f"QQ{qq} 的配置缓存{modeStr}失败！"}
    else:
        return cfg.get(qq, {"error": f"暂无 QQ{qq} 的抽卡记录配置！"})


async def logsHelper(file: Union[Path, str], data: Dict = {}) -> Tuple[str, Dict]:
    """
    抽卡记录缓存助手，既可根据 ``file`` 路径读取抽卡记录，也可根据 ``data`` 数据写入/删除抽卡记录缓存

    * ``param file: Union[Path, str]`` 抽卡记录缓存文件路径
    * ``param data: Dict = {}`` 抽卡记录数据，根据是否传入决定写入/删除或读取
    - ``return: Tuple[str, Dict]`` 抽卡记录所属 UID（出错时返回错误信息）、抽卡记录数据（写入/删除时固定返回 ``{}``）
    """
    uid = search(r"gachalogs-([0-9]{9}).json", str(file))
    if not uid:
        raise ValueError(f"记录所属 UID 不存在！{str(file)}")
    uid, logsFile = uid.group(1), Path(file)
    # 根据是否传入抽卡记录数据决定写入/删除或读取
    if data:
        delMode = bool(data.get("delete"))
        modeStr = "删除" if delMode else "更新"
        try:
            if delMode:
                logsFile.unlink(missing_ok=True)
            else:
                logsFile.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            logger.info(f"UID{uid} 的抽卡记录已{modeStr}")
            return uid, {}
        except Exception as e:
            logger.error(f"UID{uid} 的抽卡记录缓存{modeStr}失败：{type(e)}")
            return f"UID{uid} 的抽卡记录缓存{modeStr}失败！", {}
    elif logsFile.exists():
        logs = json.loads(logsFile.read_text(encoding="utf-8"))
        assert isinstance(logs, Dict)
        return uid, logs
    else:
        raise ValueError(f"UID{uid} 的本地抽卡记录不存在！")


async def queryMihoyo(
    cookie: str, aType: Literal["获取令牌", "获取角色", "获取卡池", "生成密钥"], data: Dict = {}
) -> Dict:
    """
    米哈游接口请求，支持获取 ``stoken`` 令牌、获取指定 ``cookie`` 名下原神游戏角色数据、查询最新祈愿活动 ``gacha_id`` 卡池数据、生成用于抽卡记录查询的 ``authkey`` 密钥

    * ``param cookie: str`` 米哈游通行证 Cookie，获取令牌和获取卡池时可传入空
    * ``param aType: Literal["获取令牌", "获取角色", "获取卡池", "生成密钥"]`` 请求类型
    * ``param data: Dict = {}`` 请求数据，根据需要被赋值为 ``params`` ``content`` 等
    - ``return: Dict`` 请求结果，出错时返回 ``{"error": "错误信息"}``
    """
    if aType == "获取卡池":
        # 可能不需要每次都向米游社发起请求，此处将返回固定为常驻祈愿活动数据
        return {"type": "200", "pool": "fecafa7b6560db5f3182222395d88aaa6aaac1bc"}
    t = str(int(time()))
    r = "".join(random.sample(string.ascii_lowercase + string.digits, 6))
    m = md5(f"salt={CLIENT_SALT}&t={t}&r={r}".encode()).hexdigest()
    headers = {
        "cookie": cookie,
        "ds": f"{t},{r},{m}",
        "host": "api-takumi.mihoyo.com",
        "referer": "https://app.mihoyo.com",
        "user-agent": "okhttp/4.8.0",
        "x-rpc-app_version": CLIENT_VERSION,
        "x-rpc-channel": "mihoyo",
        "x-rpc-client_type": CLIENT_TYPE,
        "x-rpc-device_id": str(uuid.uuid3(uuid.NAMESPACE_URL, cookie)),
        "x-rpc-device_model": "SM-977N",
        "x-rpc-device_name": "Samsung SM-G977N",
        "x-rpc-sys_version": "12",
    }
    if aType == "获取令牌":
        headers.update(
            {
                "origin": "https://webstatic.mihoyo.com",
                "referer": "https://webstatic.mihoyo.com/",
                "user-agent": (
                    # "Mozilla/5.0 (Linux; Android 10; MIX 2 Build/QKQ1.190825.002; wv) "
                    # "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                    # f"Chrome/83.0.4103.101 Mobile Safari/537.36 miHoYoBBS/{CLIENT_VERSION}"
                    "Mozilla/5.0 (Linux; Android 12; SM-G977N Build/SP1A.210812.016; wv) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0"
                    f"Chrome/104.0.5112.69 Mobile Safari/537.36 miHoYoBBS/{CLIENT_VERSION}"
                ),
                "x-requested-with": "com.mihoyo.hyperion",
            }
        )
    elif aType == "生成密钥":
        headers["content-type"] = "application/json; charset=UTF-8"
    async with AsyncClient() as client:
        try:
            if aType == "获取令牌":
                res = await client.get(TOKEN_API, headers=headers, params=data)
                rt = {"stoken": res.json()["data"]["list"][0]["token"]}
            elif aType == "获取角色":
                res = await client.get(ROLE_API, headers=headers)
                rt = [
                    char
                    for char in res.json()["data"]["list"]
                    if char["game_biz"] == "hk4e_cn"
                ][0]
            elif aType == "获取卡池":
                res = await client.get(POOL_API, params={"ts": str(time())[:8]})
                rt = {
                    "type": "200",
                    "pool": [
                        p["gacha_id"]
                        for p in res.json()["data"]["list"]
                        if p["gacha_type"] == 200
                    ][0],
                }
            elif aType == "生成密钥":
                res = await client.post(
                    AUTHKEY_API,
                    headers=headers,
                    content=json.dumps(data, ensure_ascii=False),
                )
                rt = {"authkey": res.json()["data"]["authkey"]}
            else:
                raise ValueError(f"未知的请求类型：{aType}")
        except Exception as e:
            logger.error(f"米游社 {aType} 请求失败：{type(e)}\n{e}")
            return {"error": f"未能成功{aType}！"}
    return rt


async def checkAuthKey(url: str, skipFmt: bool = True) -> str:
    """
    抽卡记录链接验证，检查传入抽卡记录链接 `url` 是否有效（AuthKey 有效期 24h）

    * ``param url: str`` 抽卡记录链接
    * ``param skipFmt: bool = True`` 是否跳过格式检查，传入 ``False`` 将根据格式检查结果修正抽卡记录链接
    - ``return: str`` 抽卡记录链接，出错时返回错误信息
    """
    if not skipFmt:
        urlRes = formatInput(url, find="url")
        if not urlRes:
            return "未找到有效的抽卡记录链接！"
        else:
            url = urlRes["url"]
    logger.debug(f"验证抽卡记录链接 {url}")
    async with AsyncClient() as client:
        try:
            res = await client.get(url)
            resJson = res.json()
            # checkFile = LOCAL_DIR / f"checkAuthKey-{int(time())}.json"
            # with open(checkFile, "w", encoding="utf-8") as f:
            #     resJson["url"] = url
            #     json.dump(resJson, f, ensure_ascii=False, indent=2)
        except json.decoder.JSONDecodeError:
            return "链接返回无法解析！"
        except Exception as e:
            logger.error(f"抽卡记录链接验证出错 {type(e)}：{e}")
            return f"[{type(e)}]链接验证出错！"
    if not resJson["data"]:
        if resJson.get("message", "") == "authkey timeout":
            return "链接 AuthKey 失效！"
        if resJson.get("message", "") == "authkey error":
            return "链接 AuthKey 错误！"
        # ref: https://webstatic.mihoyo.com/admin/mi18n/hk4e_cn/20190926_5d8c80193de82/20190926_5d8c80193de82-zh-cn.json
        logger.error(
            f"抽卡记录链接有问题 {resJson.get('retcode', 777)} {resJson.get('message', '')}"
        )
        return f"[{resJson.get('retcode', 777)}]链接有问题！"
    return url


async def updateLogsUrl(url: str, cookie: str) -> Tuple[str, Dict]:
    """
    抽卡记录链接更新，可根据 `cookie` 初始化或更新抽卡记录链接

    * ``param url: str`` 抽卡记录链接
    * ``param cookie: str`` 含有 `stoken` 字段的米游社 Cookie
    - ``return: Tuple[str, Dict]`` 抽卡记录链接（出错时返回 ``"错误信息"``）、角色及 Cookie 字典数据（出错或旧链接未过期时返回 ``{}``）
    """
    # 检查传入链接是否仍然有效
    url = await checkAuthKey(url)
    if url.startswith("https://"):
        return url, {}
    # 提取 cookie 中有效字段字典
    usefulCk = formatInput(cookie, find="cookie")
    # Cookie 验证及补全
    if not usefulCk:
        return "无法自动更新链接！", {}
    elif not usefulCk.get("account_id"):
        return "Cookie 缺少米游社 ID 数据！", {}
    elif not usefulCk.get("stoken"):
        mysId, loginTicket = usefulCk.get("account_id"), usefulCk.get("login_ticket")
        if not loginTicket:
            return "Cookie 缺少 login_ticket 数据！", {}
        data = {"login_ticket": loginTicket, "token_types": "3", "uid": mysId}
        stokenRes = await queryMihoyo("", "获取令牌", data=data)
        if not stokenRes.get("stoken"):
            return "获取令牌失败！", {}
        usefulCk["stoken"] = stokenRes["stoken"]
    ckStr = "; ".join([f"{k}={v}" for k, v in usefulCk.items()])
    # 获取 Cookie 名下角色数据
    role = await queryMihoyo(ckStr, "获取角色")
    if role.get("error"):
        return role["error"], {"cookie": ckStr}
    # 更新抽卡记录链接中的 AuthKey
    data = {
        "auth_appid": "webview_gacha",
        "game_biz": role["game_biz"],
        "game_uid": role["game_uid"],
        "region": role["region"],
    }
    authkeyRes = await queryMihoyo(ckStr, "生成密钥", data=data)
    if not authkeyRes.get("authkey"):
        return "生成密钥失败！", {"cookie": ckStr}
    # 更新抽卡记录链接中的卡池 ID
    poolRes = await queryMihoyo("", "获取卡池")
    if not poolRes.get("pool"):
        poolRes = {
            "type": "200",  # querys.get("init_type")
            "pool": "fecafa7b6560db5f3182222395d88aaa6aaac1bc",  # querys.get("gacha_id")
        }
    # 提取传入 url 中请求参数字典
    parsed = parse.urlparse(url)
    querys = dict(parse.parse_qsl(str(parsed.query)))
    # 更新抽卡记录链接
    if not querys:
        querys = {
            "authkey_ver": "1",
            "sign_type": "2",
            "auth_appid": "webview_gacha",
            "init_type": poolRes["type"],
            "gacha_id": poolRes["pool"],
            "timestamp": str(int(time())),
            "lang": "zh-cn",
            "device_type": "mobile",
            # "ext": {"loc":{"x":-672.817138671875,"y":122.54130554199219,"z":-87.4539794921875},"platform":"IOS"},  # "platform":"Android"
            # "game_version": "CNRELiOS2.8.0_R9182063_S9401797_D9464149",  # CNRELAndroid2.8.0_R9182063_S9401797_D9464149
            "plat_type": "android",  # ios
            "region": role["region"],
            "authkey": authkeyRes["authkey"],
            "game_biz": role["game_biz"],
            "gacha_type": "301",
            "page": "1",
            "size": "6",
            "end_id": 0,
        }
    else:
        querys.update(
            {
                "init_type": poolRes["type"],
                "gacha_id": poolRes["pool"],
                "timestamp": str(int(time())),
                "region": role["region"],
                "authkey": authkeyRes["authkey"],
                "game_biz": role["game_biz"],
            }
        )
    urlRoot = (
        ROOT_OVERSEA_URL
        if any(x in url for x in ["webstatic-sea", "hk4e-api-os"])
        else ROOT_URL
    )
    url = urlRoot + "?" + parse.urlencode(querys)
    return await checkAuthKey(url), {"role": role, "cookie": ckStr}


def getGachaLogsApi(logUrl: str, gachaType: str, page: int, endId: int) -> str:
    """
    指定类型抽卡记录接口生成

    * ``param logUrl: str`` 抽卡记录链接
    * ``param gachaType: str`` 祈愿类型（请求参数 ``gacha_type``）
    * ``param page: int`` 页码（请求参数 ``page``）
    * ``param endId: int`` 结束 ID（请求参数 ``end_id``）
    - ``return: str`` 指定类型抽卡记录接口
    """
    parsed = parse.urlparse(logUrl)
    querys = dict(parse.parse_qsl(str(parsed.query)))
    querys.update(
        {
            "lang": "zh-cn",
            "gacha_type": gachaType,
            "page": str(page),
            "size": "20",
            "end_id": str(endId),
        }
    )
    return logUrl.split("?")[0] + "?" + parse.urlencode(querys)


async def getSingleTypeLogs(logUrl: str, gachaType: str) -> List:
    """
    指定类型抽卡记录获取

    * ``param logUrl: str`` 抽卡记录链接
    * ``param gachaType: str`` 祈愿类型，实际类型应为 ``Literal["100", "200", "301", "302"]``
    * ``return: List`` 指定类型抽卡记录
    """
    logsList, endId, page = [], 0, 1
    async with AsyncClient() as client:
        while True:
            logger.debug(f"正在获取 {GACHA_TYPE[gachaType]} 第 {page} 页")
            api = getGachaLogsApi(logUrl, gachaType, page, endId)
            res = await client.get(api)
            try:
                resJson = res.json()
                if resJson.get("message") == "visit too frequently":
                    logger.info("访问过于频繁，等待 3 秒后重试")
                    await asyncsleep(3)
                elif resJson.get("data", {}).get("list", []):
                    # 成功解析记录数据，更新请求参数
                    logsList.extend(resJson["data"]["list"])
                    endId = resJson["data"]["list"][-1]["id"]
                    page += 1
                    await asyncsleep(0.6)
                else:
                    # 未解析到记录数据，跳出循环
                    break
            except json.decoder.JSONDecodeError:
                logger.error(f"{GACHA_TYPE[gachaType]} 第 {page} 页解析失败！")
                await asyncsleep(2)
                continue
    return logsList


async def getAllTypeLogs(logUrl: str) -> Dict:
    """
    全部抽卡记录获取，可根据输入的抽卡记录链接获取 6 个月内全部抽卡记录

    * ``param logUrl: str`` 抽卡记录链接
    * ``return: Dict`` 全部抽卡记录，格式为``{"msg": "uid 或错误信息", "logs": {}]``
    """
    start, uidGot, newLogs = time(), "", {}
    # 获取最新抽卡记录
    for banner in GACHA_TYPE:
        remoteLogs = await getSingleTypeLogs(logUrl, banner)
        if remoteLogs:
            newLogs[banner] = remoteLogs
            if not uidGot:
                # 从记录中获取一次 UID
                uidGot = newLogs[banner][0]["uid"]
    msg = str(uidGot) if uidGot else "获取最新抽卡记录失败！"
    logger.info(
        "刷新 UID{} 的抽卡记录耗时 {}s".format(
            (uidGot if uidGot else "未知"), round(time() - start, 3)  # type: ignore
        )
    )
    return {"msg": msg, "logs": newLogs}


async def mergeLogs(locLogs: Dict, newLogs: Dict, config: Dict, qq: str) -> Dict:
    """
    本地记录数据与新增记录数据合并

    * ``param locLogs: Dict`` 本地记录数据
    * ``param newLogs: Dict`` 新增记录数据
    * ``param config: Dict`` 配置文件
    * ``param qq: str`` 目标 QQ
    - ``return: Dict`` 合并后的记录数据，格式为``{"uid": "123456789", "msg": "文字消息", "logs": {}]``
    """
    msgList, logs = [], {}  # 消息列表、待写入记录
    for banner in GACHA_TYPE:
        locItems, newItems = locLogs.get(banner, []), newLogs.get(banner, [])
        # 本地记录同步至待写入记录
        if locItems:
            logs[banner] = locItems
        # 本地记录与最新记录相同，跳过
        if locItems == newItems:
            continue
        # UID 不同，立即单独展示最新记录
        if len(locItems) and len(newItems) and locItems[0]["uid"] != newItems[0]["uid"]:
            logger.info(
                f"{GACHA_TYPE[banner]}({banner}) 中发现 UID 不同（{locItems[0]['uid']}!={newItems[0]['uid']}），跳过合并"
            )
            return {
                "uid": newItems[0]["uid"],
                "msg": "新增与缓存数据 UID 不一致\n跳过合并，单独展示新增记录..",
                "logs": newLogs,
            }
        # 本地记录与最新记录对比合并
        tempList, locItemsSimp = [], [[i["time"], i["name"]] for i in locItems]
        for i in range(len(newItems)):
            newItem = [newItems[i]["time"], newItems[i]["name"]]
            if newItem not in locItemsSimp:
                # 新增记录暂存
                tempList.append(newItems[i])
        if len(tempList):
            # 新增记录同步至待写入记录，保证新增数据在最前
            msgList.append(f"新增 {len(tempList)} 条{GACHA_TYPE[banner]}记录..")
            tempList.extend(locItems)
            logs[banner] = tempList
    # 无记录跳过后续缓存更改
    if not logs:
        return {"msg": "未发现任何记录.."}
    # 保存合并后的记录数据
    uid = logs[list(logs.keys())[0]][0]["uid"]
    cache = LOCAL_DIR / f"gachalogs-{uid}.json"
    config.update(
        {
            # "url": initUrl,
            # "cookie": args,
            "logs": str(cache),
            "time": int(time()),
            # "game_biz": role["game_biz"],
            "game_uid": uid,
            # "region": role["region"],
        }
    )
    res, _ = await logsHelper(cache, logs)
    if not res.isdigit():
        msgList.append(res)
    res = await configHelper(qq, config)
    if res.get("error"):
        msgList.append(res["error"])
    return {"uid": uid, "msg": "\n".join(msgList), "logs": logs}


async def getFullGachaLogs(config: Dict, qq: str, force: bool) -> Dict:
    """
    抽卡记录数据获取入口，可根据配置获取最新完整抽卡记录

    * ``param config: Dict`` 配置数据
    * ``param qq: str`` 目标 QQ
    * ``param force: bool`` 是否强制更新抽卡记录
    - ``return: Dict`` 抽卡记录数据，格式为``{"uid": "123456789", "msg": "文字消息", "logs": {}]``
    """
    # 读取抽卡记录缓存
    uid, locLogs = await logsHelper(config["logs"]) if config["logs"] else ("无记录", {})
    # msg = uid if not uid.isdigit() else ""
    if (not config["url"]) or (  # 缺少有效链接
        (not force) and (int(time()) - config["time"] < EXPIRE_SEC)  # 有缓存、未要求强制更新
    ):
        timeStr = strftime("%m-%d %H:%M", localtime(config["time"]))
        timeTip = f"这是 {timeStr} 创建的缓存.." if config["time"] else "暂无本地记录！"
        logger.info(f"返回 QQ{qq} 于 {timeStr} 生成的抽卡记录缓存")
        return {"uid": uid, "msg": timeTip, "logs": locLogs}
    # 获取最新抽卡记录
    newLogsRes = await getAllTypeLogs(config["url"])
    if not str(newLogsRes["msg"]).isdigit():
        return {"msg": newLogsRes["msg"]}
    # 合并数据
    return await mergeLogs(locLogs, newLogsRes["logs"], config, qq)
