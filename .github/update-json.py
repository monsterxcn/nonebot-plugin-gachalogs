import os
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List

import oss2
from httpx import AsyncClient

SNAP_REPO_RAW = "https://github.com/DGP-Studio/Snap.Metadata/raw/main/"
SNAP_GACHA_EVENT = SNAP_REPO_RAW + "Genshin/CHS/GachaEvent.json"
GSMT_REPO_RAW = "https://github.com/monsterxcn/nonebot-plugin-gsmaterial/raw/main/"
ID_NAME_TABLE = GSMT_REPO_RAW + "data/gsmaterial/item-alias.json"

OSS_KEY_ID = os.getenv("OSS_KEY_ID")
OSS_KEY_SECRET = os.getenv("OSS_KEY_SECRET")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT")
OSS_BUCKET = os.getenv("OSS_BUCKET")
OSS_JSON_PATH = os.getenv("OSS_JSON_PATH")


async def update() -> None:
    async with AsyncClient(follow_redirects=True) as client:
        gacha_events_json: List[Dict[str, Any]] = (
            await client.get(SNAP_GACHA_EVENT)
        ).json()
        id_name_table: Dict[Dict[str, List[str]]] = (
            await client.get(ID_NAME_TABLE)
        ).json()

    translation_map, gacha_events = {}, []

    for id, names in id_name_table.items():
        translation_map[int(id)] = names[0]

    for event in gacha_events_json:
        up_orange_list = [translation_map[num] for num in event["UpOrangeList"]]
        up_purple_list = [translation_map[num] for num in event["UpPurpleList"]]
        event.update({"UpOrangeList": up_orange_list, "UpPurpleList": up_purple_list})
        gacha_events.append(event)

    assert gacha_events
    Path("GachaEvent.json").write_text(
        json.dumps(gacha_events, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    auth = oss2.Auth(OSS_KEY_ID, OSS_KEY_SECRET)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET)
    bucket.put_object_from_file(OSS_JSON_PATH, Path("GachaEvent.json"))


asyncio.run(update())
