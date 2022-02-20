import os
import sys

from nonebot import on_command
from nonebot.exception import FinishedException
from nonebot.log import logger
from nonebot.typing import T_State

try:
    from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent, Message,
                                             MessageEvent, MessageSegment,
                                             PrivateMessageEvent)
except ImportError:
    from nonebot.adapters.cqhttp import Bot, Message, MessageSegment
    from nonebot.adapters.cqhttp.event import (GroupMessageEvent, MessageEvent,
                                               PrivateMessageEvent)

from .data_export import exportGacha
from .data_render import gnrtGachaInfo
from .data_source import checkLogUrl, getCacheData, getGachaData
from .upload_cos import initCosClient, uploadFile

cosClient = initCosClient()

gMatcher = on_command("抽卡记录", aliases={"ckjl"}, priority=1)
eMatcher = on_command("抽卡记录导出", aliases={"gcexport", "ckjldc"}, priority=1)
# iMatcher = on_command("抽卡记录导入", aliases={"gcimport", "ckjldr"}, priority=1)
# fMatcher = on_notice("offline_file", priority=100)


@gMatcher.handle()
async def gachaHistory(bot: Bot, event: MessageEvent, state: T_State):
    q = event.get_user_id()
    s = event.get_plaintext().strip()
    c = await getCacheData(q)
    # 群聊用户不在缓存中且没有输入链接，结束会话
    if c["msg"] == "暂无本地抽卡记录！":
        if isinstance(event, GroupMessageEvent) and s in ["", "-f", "--force"]:
            c["msg"] += "请在私聊中使用「抽卡记录」命令添加抽卡记录链接！"
            await gMatcher.finish(Message(c["msg"]))
    # 检测到缓存的用户将缓存数据传递至 got 方法进一步判断
    else:
        state["cache"] = c
        state["url"] = c["data"]["url"]
    # 只在触发时判定用户是否要求强制刷新
    state["force"] = True if s in ["-f", "--force"] else False
    # 传递附加在首次触发命令的消息中的链接
    if s not in ["", "-f", "--force"]:
        state["url"] = s


# Message.template("{next}")
@gMatcher.got("url", prompt=("派蒙将从接下来你回复的内容中找出有效链接用于统计：\n\n"
                             "* webstatic.mihoyo.com/hk4e/.../#/log 在内即可"))
async def gachaHistoryRes(bot: Bot, event: MessageEvent, state: T_State):
    qq = event.get_user_id()
    # 已缓存用户特殊处理
    if "cache" not in state.keys():
        state["cache"] = {}
    else:
        # 不是缓存中的链接，则判定为需要强制刷新
        if state["url"] != state["cache"]["data"]["url"]:
            # 粗略判断输入是否合法，不合法继续使用缓存链接
            if "https" not in state["url"]:
                state["url"] = ""
            else:
                state["force"] = True
        # 检查缓存中的链接是否失效，发送提示信息
        else:
            expireCheck = await checkLogUrl(state["cache"]["data"]["url"])
            state["url"] = ""
            if "https" not in expireCheck:
                warnMag = "缓存的链接状态异常！回复链接以更新 / 回复其他内容忽略"
                await gMatcher.reject(Message(warnMag))
    # 常规流程，获取数据、生成图片、发送消息
    rt = await getGachaData(qq, state["url"], state["cache"], state["force"])
    if rt["msg"]:
        await gMatcher.send(Message(rt["msg"]))
    if not rt["data"].get("gachaLogs", ""):
        raise FinishedException
    try:
        imgB64 = await gnrtGachaInfo(rt["data"])
        await gMatcher.finish(MessageSegment.image(imgB64))
    except FinishedException:
        pass
    except Exception as e:
        logger.error("抽卡记录图片生成出错：" + str(sys.exc_info()[0]) + "\n" + str(e))
        await bot.send_private_msg(
            message=(f"[error] [genshin_export]\n由用户 {event.get_user_id()} 触发"
                     f"\n{str(sys.exc_info()[0])}\n{str(e)}"),
            user_id=int(list(bot.config.superusers)[0]),
        )


@eMatcher.handle()
async def gachaExport(bot: Bot, event: MessageEvent, state: T_State):
    s = [i.strip() for i in event.get_plaintext().split(" ")]
    q = event.get_user_id()
    # 处理输入的导出参数
    if not len(s):
        exUser = q
        outFmt = "xlsx"
    elif len(s) == 1:
        exUser = s[0] if s[0].isdigit() else q
        outFmt = "xlsx" if s[0].isdigit() else s[0]
    elif len(s) == 2:
        exUser = s[0] if s[0].isdigit() else s[1]
        outFmt = s[1] if s[0].isdigit() else s[0]
    else:
        await eMatcher.finish("指令格式错误！")
    if exUser != q and q not in bot.config.superusers:
        await eMatcher.finish("你没有权限导出该用户抽卡记录！")
    c = await getCacheData(exUser)
    # 用户不在缓存中，结束会话
    if c["msg"] == "暂无本地抽卡记录！":
        c["msg"] += "请在私聊中使用「抽卡记录」命令添加抽卡记录链接！"
        await gMatcher.finish(Message(c["msg"]))
    # 生成文件并尝试发送
    exData = await exportGacha(c["data"], outFmt)
    if not exData["file"]:
        await eMatcher.finish(Message(exData["msg"]))
    elif isinstance(event, GroupMessageEvent):
        try:
            await bot.upload_group_file(
                group_id=event.group_id,
                file=exData["file"],
                name=exData["file"].split(os.sep)[-1],
            )
        except Exception as e:
            logger.error(
                "发送抽卡记录导出群文件失败："
                + str(sys.exc_info()[0]) + "\n" + str(e)
            )
            exData["msg"] += "但是群文件上传失败，稍后再试吧！"
    elif isinstance(event, PrivateMessageEvent):
        if not cosClient:
            exData["msg"] += "但是因为未成功初始化腾讯云对象存储，无法发送文件！"
        else:
            exFileUrl = await uploadFile(cosClient, exData["file"])
            if exFileUrl:
                exData["msg"] += "派蒙已将文件上传至腾讯云 COS，有效期 1 小时，"
                exData["msg"] += f"请及时下载保存：\n{exFileUrl}"
            else:
                exData["msg"] += "但是上传文件失败，请稍后再试！"
    # 删除本地下载文件
    await eMatcher.send(Message(exData["msg"]))
    try:
        os.remove(exData["file"])
    except Exception:
        pass


# @iMatcher.handle()
# async def gachaImport(bot: Bot, event: MessageEvent, state: T_State):
