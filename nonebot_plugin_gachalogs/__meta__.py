from typing import Dict, Union
from nonebot import get_driver
from pathlib import Path

try:
    localDir = Path(get_driver().config.resources_dir) / "gachalogs"
    assert localDir.exists()
except (AssertionError, AttributeError):
    localDir = Path() / "data" / "gachalogs"
    if not localDir.exists():
        localDir.mkdir(parents=True, exist_ok=True)

try:
    expireSec = get_driver().config.gacha_expire_sec
    assert isinstance(expireSec, int)
except (AssertionError, AttributeError):
    expireSec = 60 * 60


def getMeta(need: str) -> Union[str, Dict, Path]:
    gachaTypeDontIndex = ["400"]
    gachaTypeDictFull = {
        "100": "新手祈愿",
        "200": "常驻祈愿",
        "301": "角色活动祈愿",
        "302": "武器活动祈愿",
        "400": "角色活动祈愿-2",
    }
    gachaTypeDict = {
        key: value
        for key, value in gachaTypeDictFull.items()
        if key not in gachaTypeDontIndex
    }
    basicUrl = "https://hk4e-api.mihoyo.com/event/gacha_info/api/getGachaLog"
    basicUrlOversea = basicUrl.replace("hk4e-api", "hk4e-api-os")
    gachaMeta = {
        "gachaTypeDictFull": gachaTypeDictFull,
        "gachaTypeDict": gachaTypeDict,
        "basicUrl": basicUrl,
        "basicUrlOversea": basicUrlOversea,
        "localDir": localDir,
        "expireSec": expireSec,
    }
    return gachaMeta[need]


def getCOSMeta() -> Dict:
    cfg = get_driver().config
    Name = cfg.cos_bucket_name if hasattr(cfg, "cos_bucket_name") else ""
    Region = cfg.cos_bucket_region if hasattr(cfg, "cos_bucket_region") else ""
    secretId = cfg.cos_secret_id if hasattr(cfg, "cos_secret_id") else ""
    secretKey = cfg.cos_secret_key if hasattr(cfg, "cos_secret_key") else ""
    cosMeta = {
        "bucketName": Name,
        "bucketRegion": Region,
        "secretId": secretId,
        "secretKey": secretKey,
    }
    return cosMeta
