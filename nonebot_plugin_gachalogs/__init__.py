from pathlib import Path
from traceback import format_exc
from typing import Dict

from nonebot import on_command, on_notice
from nonebot.adapters import Bot as rBot
from nonebot.adapters import Event as rEvent
from nonebot.log import logger
from nonebot.rule import Rule
from nonebot.typing import T_State

try:
    from nonebot.adapters.onebot.v11 import ActionFailed, Bot, Message, MessageSegment
    from nonebot.adapters.onebot.v11.event import (
        GroupMessageEvent,
        MessageEvent,
        NoticeEvent,
    )
except ImportError:
    from nonebot.adapters.cqhttp import ActionFailed, Bot, Message, MessageSegment  # type: ignore
    from nonebot.adapters.cqhttp.event import GroupMessageEvent, MessageEvent, NoticeEvent  # type: ignore

from .__meta__ import SAFE_GROUP
from .data_export import gnrtGachaFile
from .data_render import gnrtGachaInfo, gnrtGachaArchieve
from .data_source import (
    checkAuthKey,
    configHelper,
    getFullGachaLogs,
    logsHelper,
    updateLogsUrl,
)


async def _OFFLINE_FILE(bot: "rBot", event: "rEvent") -> bool:
    if isinstance(event, NoticeEvent):
        if event.notice_type == "offline_file":  # type: ignore
            if hasattr(event, "user_id") and hasattr(event, "file"):
                filename = str(event.file.get("name", "")).lower()  # type: ignore
                if any(filename.endswith(t) for t in ["json", "xlsx"]) or (
                    filename.startswith("gachalogs-") and filename.endswith(".json.bak")
                ):
                    return True
    return False


mainMatcher = on_command("抽卡记录", aliases={"ckjl"}, priority=5)
aMatcher = on_command("抽卡成就", aliases={"ckcj"}, priority=5)
eMatcher = on_command("抽卡记录导出", aliases={"logexp", "ckjldc"}, priority=5)
dMatcher = on_command("抽卡记录删除", aliases={"logdel", "ckjlsc"}, priority=5)
fMatcher = on_notice(rule=Rule(_OFFLINE_FILE))


@mainMatcher.handle()
async def mainInit(bot: Bot, event: MessageEvent, state: T_State):
    # 处理触发同时传入参数
    qq = str(event.get_user_id())
    args = (
        str(state["_prefix"]["command_arg"]).strip()
        if "command_arg" in list(state.get("_prefix", {}))
        else str(event.get_plaintext()).strip()
    ).split(" ")
    args = [arg.strip() for arg in args if ("[CQ:" not in arg) and arg]  # 阻止 CQ 码入参
    state["force"] = any(arg in ["-f", "--force", "刷新"] for arg in args)
    logger.debug(f"QQ{qq} {'' if state['force'] else '未'}要求刷新\n触发传入参数：{args}")
    # 检查当前消息来源是否安全
    unsafe = isinstance(event, GroupMessageEvent) and (event.group_id not in SAFE_GROUP)  # type: ignore
    # 读取配置数据
    cfg = await configHelper(qq)
    if cfg.get("error"):
        if any(s in " ".join(args) for s in ["https://", "stoken", "login_ticket"]):
            # 无缓存、触发时可能存在有效输入，跳过下一步输入
            state["args"] = " ".join(args)
        elif unsafe:
            # 无缓存、触发时无输入、来源不安全，结束响应
            await mainMatcher.finish("请在私聊中重试此命令添加抽卡记录链接或米游社 Cookie！")
        elif args:
            # 无缓存、触发时可能存在无效输入、来源安全，等待下一步输入
            state["prompt"] = "参数无效，请输入抽卡记录链接或米游社 Cookie："
        else:
            # 无缓存、触发时无输入、来源安全，等待下一步输入
            state["prompt"] = cfg["error"] + "请输入抽卡记录链接或米游社 Cookie："
    else:
        renewUrl, _ = await updateLogsUrl(cfg["url"], cfg["cookie"])
        if not renewUrl.startswith("https://"):
            # 有缓存、自动更新链接失败，等待下一步输入
            cfg["url"] = ""
            state["prompt"] = renewUrl + "请重新输入链接或 Cookie："
        else:
            # 有缓存、自动更新链接成功，跳过下一步输入
            cfg["url"] = state["args"] = renewUrl
            state["argsAuto"] = True
        state["config"] = cfg


@mainMatcher.got("args", prompt=Message.template("{prompt}"))
async def mainGot(bot: Bot, event: MessageEvent, state: T_State):
    qq = str(event.get_user_id())
    isCached = isinstance(state.get("config"), Dict)
    args = (  # got 获取的参数应为 Message 类型，将 str 类型视为触发时传入参数
        str(state["args"])
        if isinstance(state.get("args"), str)
        else str(event.get_plaintext()).strip()
    )
    cfg = state.get(
        "config",
        {
            "url": "",
            "cookie": "",
            "logs": "",
            "time": 0,
            "game_biz": "hk4e_cn",
            "game_uid": "",
            "region": "",
        },
    )
    logger.debug(f"{'已' if isCached else '无'}配置 QQ{qq} got 传入参数：{args}\n初始化配置数据：{cfg}")
    # 根据输入更新配置数据，configHelper 将判断是否写入新的配置
    if "https://" in args:
        # 输入链接
        if not state.get("argsAuto", False):
            # 非自动更新的链接需要检验
            urlState = await checkAuthKey(args, skipFmt=False)
            if urlState.startswith("https://"):
                cfg["url"] = urlState
            elif isCached:
                # 有缓存、自动更新链接失败、输入链接验证失败，重置缓存的抽卡记录链接
                cfg["url"], cfg["force"] = "", True
            else:
                await mainMatcher.finish(urlState, at_sender=True)
        cfg = await configHelper(qq, cfg)
        logger.debug(f"QQ{qq} 由 URL 生成的配置：\n{cfg}")
    elif any(x in args for x in ["stoken", "login_ticket"]):
        # 输入 Cookie
        initUrl, initData = await updateLogsUrl(str(cfg["url"]), args)
        if initData:
            # 获取到初始化数据一定是有效 Cookie，但角色数据可能由于网络原因为空
            cfg["cookie"] = initData["cookie"]
            if initData.get("role"):
                cfg.update(
                    {
                        "game_biz": initData["role"]["game_biz"],
                        "game_uid": initData["role"]["game_uid"],
                        "region": initData["role"]["region"],
                    }
                )
        if initUrl.startswith("https://"):
            cfg["url"] = initUrl
        elif isCached:
            # 有缓存、自动更新链接失败、输入 Cookie 验证失败，重置缓存的抽卡记录链接
            cfg["url"], cfg["force"] = "", True
        else:
            await mainMatcher.finish(initUrl, at_sender=True)
        cfg = await configHelper(qq, cfg)
        logger.debug(f"QQ{qq} 由 Cookie 生成的配置：\n{cfg}")
    elif isCached:
        # 输入无效，有缓存
        cfg["url"], cfg["force"] = "", True
        cfg = await configHelper(qq, cfg)
    else:
        # 输入无效，无缓存
        await mainMatcher.finish("无法提取有效的链接或 Cookie。", at_sender=True)
    # 获取数据、生成图片、发送消息，至此只有新增数据才会更新配置数据、记录数据
    data = await getFullGachaLogs(cfg, qq, state["force"])
    if data.get("msg"):
        await mainMatcher.send(data["msg"], at_sender=True)
    if not data.get("logs", {}):
        await mainMatcher.finish()
    imgB64 = await gnrtGachaInfo(data["logs"], data["uid"])
    await mainMatcher.finish(MessageSegment.image(imgB64))


@aMatcher.handle()
async def gachaAchievement(bot: Bot, event: MessageEvent, state: T_State):
    qq = event.get_user_id()
    # 读取配置数据
    cfg = await configHelper(qq)
    if cfg.get("error"):
        await aMatcher.finish(cfg["error"], at_sender=True)
    # 生成抽卡成就
    uid, logs = await logsHelper(cfg["logs"])
    if not logs:
        await aMatcher.finish()
    imgB64 = await gnrtGachaArchieve(logs, uid)
    await aMatcher.finish(MessageSegment.image(imgB64))


@eMatcher.handle()
async def gachaExport(bot: Bot, event: MessageEvent, state: T_State):
    qq = event.get_user_id()
    unsafe = isinstance(event, GroupMessageEvent) and (event.group_id not in SAFE_GROUP)  # type: ignore
    # 提取导出目标 QQ 及导出方式
    target = {"qq": qq, "type": "xlsx"}
    for msgSeg in event.message:
        if msgSeg.type == "at":
            target["qq"] = msgSeg.data["qq"]
        elif msgSeg.type == "text":
            text = str(msgSeg.data["text"]).replace("ckjldc", "").lower()
            if any(x in text for x in ["饼干", "ck", "cookie"]):
                target["type"] = "cookie"
            elif any(x in text for x in ["链接", "地址", "url"]):
                target["type"] = "url"
            elif any(x in text for x in ["统一", "标准", "uigf", "json"]):
                target["type"] = "json"
    if target["qq"] != qq and qq not in bot.config.superusers:
        await eMatcher.finish("你没有权限导出该用户抽卡记录！")
    # 读取配置数据
    cfg = await configHelper(target["qq"])
    if cfg.get("error"):
        await eMatcher.finish(cfg["error"], at_sender=True)
    # 发送导出消息
    if target["type"] in ["cookie", "url"]:
        if not cfg[target["type"]]:
            await eMatcher.finish(f"没有找到 QQ{target['qq']} 的该配置", at_sender=True)
        elif not unsafe:
            await eMatcher.finish(cfg[target["type"]], at_sender=True)
        try:
            await bot.send_private_msg(user_id=int(qq), message=cfg[target["type"]])
            await eMatcher.finish()
        except ActionFailed:
            await eMatcher.finish("导不出来，因为发送悄悄话失败辣..", at_sender=True)
    # 发送导出文件
    fileInfo = await gnrtGachaFile(cfg, target["type"])  # type: ignore
    if fileInfo.get("error"):
        await eMatcher.finish(fileInfo["error"], at_sender=True)
    # 尝试发送文件
    try:
        locFile = Path(fileInfo["path"])
        assert locFile.exists()
        if isinstance(event, GroupMessageEvent) and not unsafe:
            await bot.upload_group_file(
                group_id=int(event.group_id),  # type: ignore
                file=str(locFile.resolve()),
                name=locFile.name,
            )
        else:
            await bot.upload_private_file(
                user_id=int(event.user_id),
                file=str(locFile.resolve()),
                name=locFile.name,
            )
        locFile.unlink()
    except ActionFailed:
        logger.error(f"QQ{qq} 导出文件 {fileInfo['path']} 发送出错 {format_exc()}")
        await eMatcher.finish("导不出来，因为文件发送出错辣..", at_sender=True)


@dMatcher.handle()
async def gachaDelete(bot: Bot, event: MessageEvent, state: T_State):
    # 提取目标 QQ 号、确认情况
    op, user, rmrf, comfirm = str(event.get_user_id()), "", "抽卡记录", False
    comfirmStrList = ["确认", "强制", "force", "-f", "-y"]
    deleteAllList = ["全部", "所有", "配置", "all", "-a", "config", "-c"]
    for msgSeg in event.message:
        if msgSeg.type == "at":
            user = msgSeg.data["qq"]
            break
        elif msgSeg.type == "text":
            maybeUser = msgSeg.data["text"].strip()
            if any(x in maybeUser for x in comfirmStrList):
                comfirm = True
                for x in comfirmStrList:
                    maybeUser = maybeUser.replace(x, "")
            if any(x in maybeUser for x in deleteAllList):
                rmrf = "全部配置"
                for x in deleteAllList:
                    maybeUser = maybeUser.replace(x, "")
            if maybeUser.strip().isdigit():
                user = maybeUser
                break
        else:
            continue
    user = user if user else op
    # 读取配置数据
    cfg = await configHelper(user)
    if cfg.get("error"):
        await dMatcher.finish(cfg["error"], at_sender=True)
    # 检查权限及确认情况
    if (op != user) and (op not in bot.config.superusers):
        await dMatcher.finish(f"你没有权限删除 QQ{user} 的{rmrf}！")
    if not comfirm:
        await dMatcher.finish(
            f"将要删除用户 {user} 的{rmrf}，确认无误请在刚刚的命令后附带「确认/强制/force/-f」之一重试！"
        )
    # 删除记录数据
    if cfg.get("logs"):
        delUid, _ = await logsHelper(cfg["logs"], {"delete": True})
        if not delUid.isdigit():
            await dMatcher.finish(delUid, at_sender=True)
        delTips = f"QQ{user}-UID{delUid}"
    elif rmrf == "抽卡记录":
        await dMatcher.finish(f"还没有 QQ{user} 的记录哦！", at_sender=True)
    else:
        delTips = f"QQ{user}"
    # 更新配置数据
    cfg.update({"logs": "", "time": 0, "game_uid": "", "region": "", "delete": rmrf})
    updateRes = await configHelper(user, cfg)
    if not updateRes:
        await dMatcher.finish(f"删除了 {delTips} 的{rmrf}缓存！", at_sender=True)
    else:
        await dMatcher.finish(updateRes["error"], at_sender=True)


@fMatcher.handle()
async def gotFile(bot: Bot, event: NoticeEvent, state: T_State):
    # [notice.offline_file]: {
    #     'time': 1661966162,
    #     'self_id': BOT_QQ,
    #     'post_type': 'notice',
    #     'notice_type': 'offline_file',
    #     'file': {
    #         'name': 'name.format',
    #         'size': 10127,
    #         'url': 'http://xxx.xx.xx.xxx/ftn_handler/73...a41c257b1'
    #     },
    #     'user_id': SENDER_QQ
    # }
    sender: int = event.user_id  # type: ignore
    fileInfo: Dict = event.file  # type: ignore
    logger.info(f"{sender} 发送了抽卡记录文件 {fileInfo}")
