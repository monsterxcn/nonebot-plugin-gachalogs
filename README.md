<h1 align="center">Nonebot Plugin GachaLogs</h1></br>


<p align="center">🤖 用于统计及导出原神祈愿记录的 Nonebot2 插件</p></br>


<p align="center"><b>现已支持祈愿历史记录链接自动更新！</b></p></br>


<p align="center">
  <a href="https://github.com/monsterxcn/nonebot-plugin-gachalogs/actions">
    <img src="https://img.shields.io/github/workflow/status/monsterxcn/nonebot-plugin-gachalogs/Build%20distributions?style=flat-square" alt="actions">
  </a>
  <a href="https://raw.githubusercontent.com/monsterxcn/nonebot-plugin-gachalogs/master/LICENSE">
    <img src="https://img.shields.io/github/license/monsterxcn/nonebot-plugin-gachalogs?style=flat-square" alt="license">
  </a>
  <a href="https://pypi.python.org/pypi/nonebot-plugin-gachalogs">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-gachalogs?style=flat-square" alt="pypi">
  </a>
  <img src="https://img.shields.io/badge/python-3.7.3+-blue?style=flat-square" alt="python"><br />
</p></br>


## 安装方法


如果你正在使用 2.0.0.beta1 以上版本 NoneBot，推荐使用以下命令安装：


```bash
# 从 nb_cli 安装
python3 -m nb plugin install nonebot-plugin-gachalogs

# 或从 PyPI 安装
python3 -m pip install nonebot-plugin-gachalogs
```


<details><summary><i>在 NoneBot 2.0.0.alpha16 上使用此插件</i></summary></br>


在过时的 NoneBot 2.0.0.alpha16 上 **可能** 仍有机会体验此插件！不过，千万不要通过 NoneBot 脚手架或 PyPI 安装，低版本仅支持通过 Git 手动安装。

以下命令仅作参考：


```bash
# 进入 Bot 根目录
cd /path/to/bot
# 安装依赖
# source venv/bin/activate
python3 -m pip install matplotlib Pillow xlsxwriter
# 安装插件
git clone https://github.com/monsterxcn/nonebot-plugin-gachalogs.git
cd nonebot_plugin_gachalogs
cp -r nonebot_plugin_gachalogs /path/to/bot/plugins/
cp -r data/gachalogs /path/to/bot/data/
```


</details>


## 使用须知


 - 初次使用 `抽卡记录` 命令时，要求输入祈愿历史记录链接或米游社通行证 Cookie。如果初次使用输入链接（只要回复的内容中含有即可，不必手动截取准确的链接），在该链接的 AuthKey 过期（24 小时）后需要重新输入链接或 Cookie 才能刷新数据。如果初次使用输入 Cookie，只要 Cookie 有效，后续使用时祈愿历史记录链接将自动更新，无需再次输入。
   
 - 插件使用米游社通行证 Cookie 来自动更新祈愿历史记录链接，该 Cookie 可在 [米游社通行证](https://user.mihoyo.com/#/login/) 登陆获取，并非一些教程中使用的 [米游社 BBS](https://bbs.mihoyo.com/) Cookie，其中需要包含 `stoken` `stuid` 或 `login_ticket`。
   
   此处提供一种获取该 Cookie 的简便方法：在桌面端浏览器 **隐身标签页** 中打开 https://user.mihoyo.com/ ，正常登陆米游社通行证账号；按下 F12 键，切换至「Console / 控制台」页面，在输入处（通常由蓝色「>」符号示意）输入 `document.cookie` 回车，控制台中出现的字符串即为插件需要的 Cookie。你也可以参考 [KimigaiiWuyi/GenshinUID#255](https://github.com/KimigaiiWuyi/GenshinUID/issues/255) 等其他教程获取米游社通行证 Cookie。
   
 - 一般来说，插件安装完成后无需设置环境变量，只需重启 Bot 即可开始使用。你也可以在 Nonebot2 当前使用的 `.env` 文件中参考 [.env.example](.env.example) 添加下表给出的环境变量，对插件进行更多配置。环境变量修改后需要重启 Bot 才能生效。
   
   | 环境变量 | 必需 | 默认 | 说明 |
   |:-------|:----:|:-----|:----|
   | `gachalogs_safe_group` | 否 | `[]` | 安全群组，只有在安全群组内才允许输入链接、Cookie 等内容 |
   | `gacha_expire_sec` | 否 | `3600` | 祈愿历史记录本地缓存过期秒数 |
   | `resources_dir` | 否 | `/path/to/bot/data/` | 插件缓存目录的父文件夹，包含 `gachalogs` 文件夹的上级文件夹路径 |
   | `gachalogs_font` | 否 | `/path/to/bot/data/gachalogs/LXGW-Bold.ttf` | 祈愿历史记录绘制字体 |
   | `gachalogs_pie_font` | 否 | `/path/to/bot/data/gachalogs/LXGW-Bold-minipie.ttf` | 祈愿历史记录绘制饼图字体 |
   
 - 在群组中发送米游社通行证 Cookie 等内容存在安全隐患，因此即使某些命令在群组中触发，处理结果最终也会通过私聊发送。如果用户未添加 Bot 为好友，私聊消息将发送失败。你也可以在环境变量中添加 `gachalogs_safe_group` 定义安全群组，允许在这些群组中直接发送敏感消息，如果大家不在意的话。
   
 - commit [`e2f38f3`](https://github.com/monsterxcn/nonebot-plugin-gachalogs/commit/e2f38f30379dac4f98f9314fa012a1272c2dcc95) 之后插件私聊文件发送功能不再依赖腾讯云 COS 转存，只需 go-cqhttp 支持 [上传私聊文件](https://docs.go-cqhttp.org/api/#%E4%B8%8A%E4%BC%A0%E7%A7%81%E8%81%8A%E6%96%87%E4%BB%B6) 接口。因此如果有私聊文件发送需求，务必保证 go-cqhttp 版本不低于 [v1.0.0-rc3](https://github.com/Mrs4s/go-cqhttp/releases/tag/v1.0.0-rc3)。
   
 - 使用 `抽卡记录导出` 命令生成的表格与 JSON 文件均符合 [统一可交换祈愿记录标准](https://github.com/DGP-Studio/Snap.Genshin/wiki/StandardFormat)（UIGF）格式，你可以尝试在其他支持此标准的工具中导入。导出的祈愿历史记录链接、米游社通行证 Cookie 在某些地方也许有用。
   
 - 插件运行后，会将用户的基本配置信息写入 `config.json` 文件，祈愿历史记录数据缓存于 `gachalogs-{uid}.json` 文件。使用 `抽卡记录删除` 命令默认只删除 `gachalogs-{uid}.json` 文件，如果需要连同指定用户在 `config.json` 文件中的配置一起删除，请使用附带参数 `全部` 等。记录、配置一旦删除将无法恢复，所以 `抽卡记录删除` 命令会要求重新发送附带删除操作确认参数的命令。你也可以在第一次发送命令时就确认删除操作，例如 `抽卡记录删除确认`。


## 命令说明


 - `抽卡记录` / `ckjl`
   
   返回一张祈愿历史记录统计图，样式与 https://genshin.voderl.cn/ 一致。
   
   | 可选附带参数 | 默认 | 说明 |
   |:-----------|:-----|:----|
   | `刷新` / `-f` / `--force` | 空 | 要求强制刷新最新祈愿历史记录，即使本地缓存未过期（结果默认缓存 1 小时） |
   | 祈愿历史记录链接 | 空 | 指定祈愿历史记录链接（仅初次使用、无法自动更新祈愿历史记录链接时生效） |
   | 米游社通行证 Cookie | 空 | 指定米游社通行证 Cookie（仅初次使用、无法自动更新祈愿历史记录链接时生效） |
   
   ![祈愿统计图](data/readme/result.png)
   
 - `抽卡记录导出` / `logexp` / `ckjldc`
   
   导出祈愿历史记录表格，通过可选附带参数指定导出祈愿历史记录 JSON 文件、祈愿历史记录链接或米游社通行证 Cookie。
   
   | 可选附带参数 | 默认 | 说明 |
   |:-----------|:-----|:----|
   | @某人 | **@自己** | 指定导出记录用户，仅 **Bot 管理员** 可导出其他用户的记录 |
   | `统一` / `标准` / `uigf` / `json` | 空 | 指定导出祈愿历史记录为 JSON 文件 |
   | `链接` / `地址` / `url` | 空 | 指定导出祈愿历史记录链接 |
   | `饼干` / `ck` / `cookie` | 空 | 指定导出米游社通行证 Cookie |
   
   ![导出示意图](data/readme/export.jpg)
   
 - `抽卡记录删除` / `logdel` / `ckjldc`
   
   删除本地祈愿历史记录缓存（不会影响 Cookie 等配置数据），通过可选附带参数指定删除全部数据。
   
   | 可选附带参数 | 默认 | 说明 |
   |:-----------|:-----|:----|
   | @某人 | **@自己** | 指定删除记录或配置的用户，仅 **Bot 管理员** 可删除其他用户的记录或配置 |
   | `强制` / `确认` / `force` / `-f` / `-y` | 空 | 删除操作确认 |
   | `全部` / `所有` / `配置` / `all` / `-a` / `config` / `-c` | 空 | 指定删除用户的 **配置和记录** 全部数据 |


## 特别鸣谢


[@nonebot/nonebot2](https://github.com/nonebot/nonebot2/) | [@Mrs4s/go-cqhttp](https://github.com/Mrs4s/go-cqhttp) | [@sunfkny/genshin-gacha-export](https://github.com/sunfkny/genshin-gacha-export) | [@voderl/genshin-gacha-analyzer](https://github.com/voderl/genshin-gacha-analyzer)


> 插件主要功能是从 [@sunfkny/genshin-gacha-export](https://github.com/sunfkny/genshin-gacha-export) 抄的，溜溜…
