import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Set, Tuple, Union

from httpx import AsyncClient, NetworkError
from nonebot.log import logger
from nonebot.utils import run_sync

from .__meta__ import GACHA_TYPE, LOCAL_DIR
from .data_render import gnrtGachaInfo
from .data_source import configHelper, logsHelper


@run_sync
def analysisData(data: Dict[str, Any]) -> Tuple[int, str, Literal["inner", "uigf"]]:
    """
    分析导入数据

    * ``param data: Dict[str, Any]`` 导入数据，由 ``getFileData()`` 返回
    - ``return: Tuple[int, str, Literal["inner", "uigf"]]`` 最新抽卡记录时间戳、抽卡记录归属 UID、导入数据格式
    """

    timestamp, uid, format = 0.0, "", ""
    standardKeys = [
        # "uid",  # v2.2 非必需，但官方返回
        "gacha_type",
        # "item_id",  # v2.2 非必需，但官方返回
        # "count",  # v2.2 非必需，但官方返回
        "time",  # v2.2 非必需，但插件必需
        "name",
        # "lang",  # v2.2 非必需，但官方返回
        "item_type",
        "rank_type",  # v2.2 非必需，但插件必需
        "id",
    ]

    # 内部格式验证
    if all(k.isdigit() for k in data.keys()):
        format = "inner"
        for k in data.keys():
            assert isinstance(data[k], list)
            for log in data[k]:
                assert isinstance(log, dict) and all(
                    isinstance(k, str) and isinstance(v, str) for k, v in log.items()
                )
                assert all(k in log.keys() for k in standardKeys)
                uid = uid or log["uid"]
                assert uid and uid.isdigit() and log["uid"] == uid
                assert log["id"].isdigit()
                _timestamp = datetime.strptime(
                    log["time"], "%Y-%m-%d %H:%M:%S"
                ).timestamp()
                timestamp = max(timestamp, _timestamp)
    # UIGF 格式验证
    elif data.get("info") and data.get("list"):
        uid, format = data["info"]["uid"], "uigf"
        standardKeys.append("uigf_gacha_type")
        assert uid and uid.isdigit()
        assert isinstance(data["list"], list)
        for log in data["list"]:
            assert isinstance(log, dict) and all(
                isinstance(k, str) and isinstance(v, str) for k, v in log.items()
            )
            assert all(k in log.keys() for k in standardKeys)
            assert log.get("uid", uid) == uid
            assert log["id"].isdigit()
            _timestamp = datetime.strptime(log["time"], "%Y-%m-%d %H:%M:%S").timestamp()
            timestamp = max(timestamp, _timestamp)
    else:
        raise ValueError("抽卡记录导入文件格式错误！")

    if uid[0] not in ["1", "2", "5"]:
        raise ValueError(f"抽卡记录拥有者 UID{uid} 所属服务器暂未支持")

    return int(timestamp), uid, format


async def getFileData(url: str) -> Dict:
    """获取链接对应文件的 JSON 数据"""

    async with AsyncClient() as client:
        try:
            res = await client.get(url, timeout=10.0)
            return res.json()
        except NetworkError as e:
            logger.opt(exception=e).error(f"记录导入文件下载出错 {url}")
            return {"error": f"[{e.__class__.__name__}] 可能由于网络问题未能获取文件"}
        except json.JSONDecodeError as e:
            logger.opt(exception=e).error(f"记录导入文件解析出错 {url}")
            return {"error": f"[{e.__class__.__name__}] 可能由于文件不是合法的 JSON"}


async def getImportTarget(
    qq: str, uid: str, isSuperuser: bool
) -> Tuple[Optional[Path], str, Dict[str, Any]]:
    """
    获取导入目标初始配置

    * ``param qq: str`` 导入动作触发 QQ
    * ``param uid: str`` 抽卡数据归属 UID
    * ``param isSuperuser: bool`` 导入动作触发 QQ 是否为超级用户
    - ``return: Tuple[Optional[Path], str, Dict[str, Any]]`` 导入目标本地记录文件、导入目标 QQ、导入目标初始配置（出错时返回 ``{"error": "}``）
    """

    configKey, config = qq, (await configHelper(qq))

    # 非超级用户只能新增或更新自己
    if not isSuperuser:
        # 没有抽卡记录配置视为新增
        if config.get("error"):
            config = {
                "url": "",
                "cookie": "",
                "logs": "",
                "time": 0,
                "game_biz": "hk4e_cn",
                "game_uid": uid,
                "region": "cn_gf01" if uid[0] in ["1", "2"] else "cn_qd01",
            }
        if uid != config["game_uid"]:
            config = {
                "error": f"QQ{qq} 已经有 UID{config['game_uid']} 的抽卡记录，不能导入属于 UID{uid} 的抽卡记录"
            }
    # 超级用户可以新增或更新自己，也可以更新别人
    else:
        # 超级用户没有抽卡记录配置 / 导入记录归属 UID 与抽卡记录配置不符
        if config.get("error") or uid != config["game_uid"]:
            # 先找一遍当前 UID 是否属于别人
            allConfig = await configHelper("0")
            for k, v in allConfig.items():
                if v["game_uid"] == uid:
                    # 导入记录归属 UID 属于别人 -> 更新别人
                    configKey, config = k, v
                    break
            # 当前 UID 不属于别人，即 L136 未修改 configKey
            if configKey == qq:
                # 超级用户没有抽卡记录配置 -> 新增自己
                if config.get("error"):
                    config = {
                        "url": "",
                        "cookie": "",
                        "logs": "",
                        "time": 0,
                        "game_biz": "hk4e_cn",
                        "game_uid": uid,
                        "region": "cn_gf01" if uid[0] in ["1", "2"] else "cn_qd01",
                    }
                # 导入记录归属 UID 与抽卡记录配置不符 -> 拒绝导入
                else:
                    config = {
                        "error": (
                            f"QQ{qq} 已经有 UID{config['game_uid']} 的抽卡记录，"
                            f"如需导入 UID{uid} 的抽卡记录请选择以下方式之一：\n"
                            f"1. 请 UID{uid} 的用户使用自己的 QQ 导入当前文件。"
                            f"2. 请 UID{uid} 的用户使用 Bot 成功查询一次「抽卡记录」，"
                            "之后再由你导入当前文件。"
                        )
                    }
        # 导入记录归属 UID 与抽卡记录配置相符 -> 更新自己
        else:
            pass

    file = Path(config["logs"]) if config.get("logs") else None
    return file, configKey, config


async def revertLogs(
    inner: Dict, config: Dict, qq: str, uid: str, timestamp: int
) -> Tuple[Dict[str, list], Dict[str, str]]:
    """
    恢复抽卡数据（内部格式抽卡数据）

    * ``param inner: Dict`` 内部格式抽卡数据
    * ``param config: Dict`` 导入目标配置
    * ``param qq: str`` 导入目标 QQ
    * ``param uid: str`` 抽卡数据归属 UID
    * ``param timestamp: int`` 抽卡数据时间戳
    - ``return: Tuple[Dict[str, list], Dict[str, str]]`` 内部格式抽卡数据、导入结果（``{"error": "", "msg": ""}``）
    """

    config["logs"] = config["logs"] or str(LOCAL_DIR / f"gachalogs-{uid}.json")
    config["time"] = timestamp

    # 写入 gachalogs-{uid}.json
    res, _ = await logsHelper(config["logs"], inner)
    if not res.isdigit():
        return {}, {"error": res}
    # 写入 config.json
    res = await configHelper(qq, config)
    if res.get("error"):
        return {}, res

    return inner, {"msg": f"成功恢复 QQ{qq} 的抽卡记录！"}


async def mergeLogs(
    uigf: Dict, config: Dict, qq: str, uid: str, timestamp: int
) -> Tuple[Dict[str, list], Dict[str, str]]:
    """
    合并抽卡数据（UIGF 格式抽卡数据）

    * ``param uigf: Dict`` UIGF 格式抽卡数据
    * ``param config: Dict`` 导入目标配置
    * ``param qq: str`` 导入目标 QQ
    * ``param uid: str`` 抽卡数据归属 UID
    * ``param timestamp: int`` 抽卡数据时间戳
    - ``return: Tuple[Dict[str, list], Dict[str, str]]`` 内部格式抽卡数据、导入结果（``{"error": "", "msg": ""}``）
    """
    # TODO: 优化
    # 当前写的比较臃肿，主要基于以下思路：
    # 1. 导入和本地所有 id 非官方生成的都不可信任
    # 2. 无论本地记录还是要导入的 UIGF 格式数据，
    #    某时刻的数据只能是单抽或完整的十连
    # 3. 导入后按时间顺序将记录分别插入卡池单独的列表中
    # 4. 合并过程中所有记录的顺序均保证新数据在前，旧数据在后

    # UIGF 格式数据转换为中间态
    _list = sorted(uigf["list"], key=lambda i: int(i["id"]))
    _list.reverse()  # 新数据在前，旧数据在后
    uigfDict = {}
    for log in _list:
        # 所有由程序补全的 ID 均不信任，同时按官方返回补全部分字段
        log = {
            "uid": log.get("uid") or uid,  # v2.2 非必需，但官方返回
            "gacha_type": log["gacha_type"],
            "item_id": log.get("item_id") or "",  # v2.2 非必需，但官方返回
            "count": log.get("count") or "1",  # v2.2 非必需，但官方返回
            "time": log["time"],  # v2.2 非必需，但插件必需
            "name": log["name"],
            "lang": log.get("lang") or "zh-cn",  # v2.2 非必需，但官方返回
            "item_type": log["item_type"],
            "rank_type": log["rank_type"],  # v2.2 非必需，但插件必需
            "id": "" if str(log["id"]).startswith("1000") else log["id"],
        }
        # UIGF 格式数据分离为单抽和十连
        if log["time"] in uigfDict:
            uigfDict[log["time"]].append(log)
        else:
            uigfDict[log["time"]] = [log]
    try:
        assert all(
            len(subList) == 1 or len(subList) == 10 for subList in uigfDict.values()
        )
    except AssertionError:
        return {}, {"error": "UIGF 文件中某时刻的数据既非单抽也非十连，拒绝导入异常数据！"}

    # 内部格式数据转换为中间态
    _, _local = (await logsHelper(config["logs"])) if config["logs"] else ("", {})
    localDict = {}
    for _, logs in _local.items():
        for log in logs:
            # 所有由程序补全的 ID 均不信任
            if str(log["id"]).startswith("1000"):
                log["id"] = ""
            # 内部格式数据分离为单抽和十连
            if log["time"] in localDict:
                localDict[log["time"]].append(log)
            else:
                localDict[log["time"]] = [log]
    assert all(len(subList) == 1 or len(subList) == 10 for subList in localDict.values())

    # 合并中间态
    counters = {}
    for logsTime, logs in uigfDict.items():
        banner = "301" if logs[0]["gacha_type"] == "400" else logs[0]["gacha_type"]
        if logsTime not in localDict:
            localDict[logsTime] = logs
            counters[banner] = counters.get(banner, 0) + len(logs)

    # 中间态转换为内部格式数据
    merged = {}
    localDict = dict(
        sorted(
            localDict.items(),
            key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S"),
            reverse=True,
        )
    )
    for logsTime, logs in localDict.items():
        banner = "301" if logs[0]["gacha_type"] == "400" else logs[0]["gacha_type"]
        merged[banner] = merged.get(banner, [])
        merged[banner].extend(logs)

    config["logs"] = config["logs"] or str(LOCAL_DIR / f"gachalogs-{uid}.json")
    config["time"] = timestamp
    # 写入 gachalogs-{uid}.json
    res, _ = await logsHelper(config["logs"], merged)
    if not res.isdigit():
        return {}, {"error": res}
    # 写入 config.json
    res = await configHelper(qq, config)
    if res.get("error"):
        return {}, res

    addMsg = "\n".join(
        f"新增 {count} 条{GACHA_TYPE[banner]}记录.." for banner, count in counters.items()
    )
    return merged, {"msg": f"成功合并 QQ{qq} 的抽卡记录！\n{addMsg or '不过似乎没有新增记录..'}"}


async def importGachaFile(
    qq: str, file: Dict[str, str], superusers: Set[str]
) -> Dict[str, Union[str, bytes]]:
    """
    导入抽卡数据

    * ``param qq: str`` 发送者 QQ
    * ``param file: Dict[str, str]`` 导入文件数据
    * ``param superusers: Set[str]`` 超级用户集合
    - ``return: Dict[str, str]`` 导入结果，``{"error": "", "bak": "", "msg": "", "img": bytes}``
    """

    # 获取导入文件数据
    data = await getFileData(file["url"])
    # 文件数据获取出错返回错误消息
    if data.get("error"):
        return data

    # 分析导入数据
    try:
        timestamp, uid, format = await analysisData(data)
    except (AssertionError, AttributeError, KeyError, ValueError) as e:
        logger.opt(exception=e).error("导入的抽卡记录文件格式异常")
        return {"error": "导入的抽卡记录文件格式异常，请查看后台报错！"}

    # 决定导入的目标配置
    logsFile, targetQ, config = await getImportTarget(qq, uid, qq in superusers)
    # 导入不被允许返回错误消息
    if config.get("error"):
        return config

    result = {}

    # 创建本地记录备份
    if logsFile and logsFile.exists():
        backupPath = logsFile.with_suffix(".bak")
        backupPath.write_bytes(logsFile.read_bytes())
        result["bak"] = str(backupPath)

    # 内部格式文件 -> 恢复
    if format == "inner":
        logsData, actionRes = await revertLogs(data, config, targetQ, uid, timestamp)
    # UIGF 格式文件 -> 合并
    else:
        logsData, actionRes = await mergeLogs(data, config, targetQ, uid, timestamp)
    result.update(actionRes)
    if logsData:
        result["img"] = await gnrtGachaInfo(logsData, uid)

    return result
