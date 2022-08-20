from pathlib import Path

from httpx import stream  # AsyncClient
from nonebot import get_driver

cfg = get_driver().config

# 安全群组
SAFE_GROUP = (
    list(cfg.gachalogs_safe_group) if hasattr(cfg, "gachalogs_safe_group") else []
)

# 缓存过期秒数
EXPIRE_SEC = int(cfg.gacha_expire_sec) if hasattr(cfg, "gacha_expire_sec") else 3600

# 本地缓存目录
LOCAL_DIR = (
    (Path(cfg.resources_dir) / "gachalogs")
    if hasattr(cfg, "resources_dir")
    else (Path() / "data" / "gachalogs")
)
if not LOCAL_DIR.exists():
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

# 绘图字体
# auto download font use httpx AsyncClient
# async with AsyncClient() as client:
#     font_content = await client.get("", timeout=10)
#     with open(PIL_FONT, "wb") as f:
#         f.write(font_content.content)
PIL_FONT = (
    (Path(cfg.gachalogs_font))
    if hasattr(cfg, "gachalogs_font")
    else (LOCAL_DIR / "LXGW-Bold.ttf")
)
if not PIL_FONT.exists():
    with stream("GET", "https://cdn.monsterx.cn/bot/LXGW-Bold.ttf", verify=False) as r:
        with open(PIL_FONT, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
PIE_FONT = (
    (Path(cfg.gachalogs_pie_font))
    if hasattr(cfg, "gachalogs_pie_font")
    else (LOCAL_DIR / "LXGW-Bold-minipie.ttf")
)
if not PIE_FONT.exists():
    with stream(
        "GET", "https://cdn.monsterx.cn/bot/LXGW-Bold-minipie.ttf", verify=False
    ) as r:
        with open(PIE_FONT, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)

# 抽卡链接地址
ROOT_URL = "https://hk4e-api.mihoyo.com/event/gacha_info/api/getGachaLog"
ROOT_OVERSEA_URL = ROOT_URL.replace("hk4e-api", "hk4e-api-os")
# 米游社 API 地址
TOKEN_API = "https://api-takumi.mihoyo.com/auth/api/getMultiTokenByLoginTicket"
ROLE_API = "https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByStoken"
POOL_API = "https://webstatic.mihoyo.com/hk4e/gacha_info/cn_gf01/gacha/list.json"
AUTHKEY_API = "https://api-takumi.mihoyo.com/binding/api/genAuthKey"
# 米游社请求验证
CLIENT_SALT = "dWCcD2FsOUXEstC5f9xubswZxEeoBOTc"
CLIENT_VERSION = "2.28.1"
CLIENT_TYPE = "2"

# 卡池类型
GACHA_TYPE_FULL = {
    "100": "新手祈愿",
    "200": "常驻祈愿",
    "301": "角色活动祈愿",
    "302": "武器活动祈愿",
    "400": "角色活动祈愿-2",
}
GACHA_TYPE_EXCL = ["400"]
GACHA_TYPE = {
    key: value for key, value in GACHA_TYPE_FULL.items() if key not in GACHA_TYPE_EXCL
}
