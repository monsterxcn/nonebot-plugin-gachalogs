from pathlib import Path
from typing import Dict

from nonebot import on_command
from nonebot.log import logger
from nonebot.typing import T_State

try:
    from nonebot.adapters.onebot.v11 import ActionFailed, Bot, Message, MessageSegment
    from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
except ImportError:
    from nonebot.adapters.cqhttp import ActionFailed, Bot, Message, MessageSegment  # type: ignore
    from nonebot.adapters.cqhttp.event import GroupMessageEvent, MessageEvent  # type: ignore

from .__meta__ import SAFE_GROUP
from .data_export import gnrtGachaFile
from .data_render import gnrtGachaInfo
from .data_source import (
    checkAuthKey,
    configHelper,
    getFullGachaLogs,
    logsHelper,
    updateLogsUrl,
)

mainMatcher = on_command("抽卡记录", aliases={"ckjl"}, priority=5)
eMatcher = on_command("抽卡记录导出", aliases={"logexp", "ckjldc"}, priority=5)
dMatcher = on_command("抽卡记录删除", aliases={"logdel", "ckjlsc"}, priority=5)


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
    logger.debug(f"QQ{qq} {'' if state['force'] else 'dont '}need flash\nargs: {args}")
    # 检查当前消息是否安全
    unsafe = isinstance(event, GroupMessageEvent) and (event.group_id not in SAFE_GROUP)  # type: ignore
    # 读取配置数据
    cfg = await configHelper(qq)
    if cfg.get("error"):
        # 无缓存，等待下一步输入
        if any(
            s in arg for arg in args for s in ["https://", "stoken", "login_ticket"]
        ):
            state["args"] = " ".join(args)
        elif unsafe:
            await mainMatcher.finish("请在私聊中重试此命令添加抽卡记录链接或米游社 Cookie！")
        elif args:
            state["prompt"] = "参数无效，请输入抽卡记录链接或米游社 Cookie："
        else:
            state["prompt"] = cfg["error"] + "请输入抽卡记录链接或米游社 Cookie："
    else:
        renewUrl, _ = await updateLogsUrl(cfg["url"], cfg["cookie"])
        if "https://" not in renewUrl:
            # 有缓存，自动更新链接失败，等待下一步输入
            cfg["url"] = ""
            state["prompt"] = renewUrl + "请重新输入链接或 Cookie："
        else:
            # 有缓存，自动更新链接成功，跳过下一步输入
            state["args"] = renewUrl
            state["argsAuto"] = True
        state["config"] = cfg


@mainMatcher.got("args", prompt=Message.template("{prompt}"))
async def mainGot(bot: Bot, event: MessageEvent, state: T_State):
    qq = str(event.get_user_id())
    isCached = isinstance(state.get("config"), Dict)
    args = (
        str(state["args"])
        if isinstance(state.get("args"), str)
        else str(event.get_plaintext()).strip()
    )
    logger.debug(f"QQ{qq} [{'cached' if isCached else 'not cached'}] got args: {args}")
    # 根据输入准备新增数据
    if "https://" in args:
        logger.debug(
            f"QQ{qq} {'auto ' if state.get('argsAuto', False) else ''}input url: {args}"
        )
        # 输入链接（包含 有缓存，自动更新链接成功 的情况）
        if not state.get("argsAuto", False):
            # 非自动更新的链接需要检验
            urlState = await checkAuthKey(args, skipFmt=False)
            if "https://" in urlState:
                args = urlState
            elif isCached:
                # 有缓存、自动更新链接失败、输入链接验证失败，删除已经过期的抽卡记录链接缓存
                state["config"]["url"] = ""
                _ = await configHelper(qq, state["config"])
            else:
                await mainMatcher.finish(urlState, at_sender=True)
        state["config"] = {
            "url": args,
            "cookie": state.get("config", {}).get("cookie", ""),
            "logs": state.get("config", {}).get("logs", ""),
            "time": state.get("config", {}).get("time", 0),
            "game_biz": state.get("config", {}).get("game_biz", ""),
            "game_uid": state.get("config", {}).get("game_uid", ""),
            "region": state.get("config", {}).get("region", ""),
        }
        logger.debug(f"QQ{qq} new config by url:\n{str(state['config'])}")
    elif any(x in args for x in ["stoken", "login_ticket"]):
        # 输入 Cookie
        initUrl, role = await updateLogsUrl("", args)
        if "https://" not in initUrl:
            if isCached:
                # 有缓存、自动更新链接失败、输入 Cookie 验证失败，删除已经过期的抽卡记录链接缓存
                state["config"]["url"] = ""
                _ = await configHelper(qq, state["config"])
            else:
                await mainMatcher.finish(initUrl, at_sender=True)
        state["config"] = {
            "url": initUrl,
            "cookie": args,
            "logs": state.get("config", {}).get("logs", ""),
            "time": state.get("config", {}).get("time", 0),
            "game_biz": role["game_biz"],
            "game_uid": role["game_uid"],
            "region": role["region"],
        }
        logger.debug(f"QQ{qq} new config by cookie:\n{str(state['config'])}")
    elif isCached:
        # 输入无效，有缓存
        state["config"]["url"] = ""
        _ = await configHelper(qq, state["config"])
    else:
        # 输入无效，无缓存
        await mainMatcher.finish("无法提取有效的链接或 Cookie。", at_sender=True)
    # 常规流程：获取数据、生成图片、发送消息
    data = await getFullGachaLogs(state["config"], qq, state["force"])
    if data.get("msg"):
        await mainMatcher.send(data["msg"], at_sender=True)
    if not data.get("logs", {}):
        await mainMatcher.finish()
    imgB64 = await gnrtGachaInfo(data["logs"], data["uid"])
    await mainMatcher.finish(
        MessageSegment.image(imgB64) if "base64" in imgB64 else imgB64
    )


@eMatcher.handle()
async def gachaExport(bot: Bot, event: MessageEvent, state: T_State):
    qq = event.get_user_id()
    unsafe = isinstance(event, GroupMessageEvent) and (event.group_id not in SAFE_GROUP)  # type: ignore
    # 提取导出目标 QQ 及导出方式
    target = {"qq": "", "type": ""}
    for msgSeg in event.message:
        if msgSeg.type == "at" and not target["qq"]:
            target["qq"] = msgSeg.data["qq"]
        elif msgSeg.type == "text" and not target["type"]:
            text = msgSeg.data["text"].lower()
            if any(x in text for x in ["统一", "标准", "uigf", "json"]):
                target["type"] = "json"
            elif any(x in text for x in ["链接", "地址", "url"]):
                target["type"] = "url"
            elif any(x in text for x in ["饼干", "ck", "cookie"]):
                target["type"] = "cookie"
            else:
                target["type"] = "xlsx"
    if not target["qq"]:
        target["qq"] = qq
    elif target["qq"] != qq and qq not in bot.config.superusers:
        await eMatcher.finish("你没有权限导出该用户抽卡记录！")
    # 读取配置数据
    cfg = await configHelper(qq)
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
    except ActionFailed as e:
        logger.error(f"QQ{qq} 导出文件 {fileInfo['file']} 处理出错 {e}")
        await eMatcher.finish("导不出来，因为文件处理出错辣..", at_sender=True)


@dMatcher.handle()
async def gachaDelete(bot: Bot, event: MessageEvent, state: T_State):
    # 提取目标 QQ 号、确认情况
    op, user, comfirm = str(event.get_user_id()), "", False
    comfirmStrList = ["确认", "强制", "force", "-f", "-y"]
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
    elif not cfg.get("logs"):
        await dMatcher.finish(f"还没有 QQ{user} 的记录哦！", at_sender=True)
    # 检查权限及确认情况
    if (op != user) and (op not in bot.config.superusers):
        await dMatcher.finish(f"你没有权限删除 QQ{user} 的抽卡记录！")
    if not comfirm:
        await dMatcher.finish(
            f"将要删除用户 {user} 的抽卡记录，确认无误请在刚刚的命令后附带「确认/强制/force/-f」之一重试！"
        )
    # 删除记录数据
    delUid, _ = await logsHelper(cfg["logs"], {"delete": True})
    if not delUid.isdigit():
        await dMatcher.finish(delUid, at_sender=True)
    # 更新配置数据
    cfg["logs"] = ""
    updateRes = await configHelper(user, cfg)
    if not updateRes:
        await dMatcher.finish(f"删除了 QQ{user}-UID{delUid} 的抽卡记录缓存！", at_sender=True)
    else:
        await dMatcher.finish(updateRes["error"], at_sender=True)
