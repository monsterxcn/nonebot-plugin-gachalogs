import os
import csv
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List

import oss2
from httpx import AsyncClient

SNAP_REPO_RAW = "https://github.com/DGP-Studio/Snap.Metadata/raw/main/"
SNAP_GACHA_EVENT = SNAP_REPO_RAW + "Genshin/CHS/GachaEvent.json"
SNAP_CHEAT_TABLE = SNAP_REPO_RAW + "CheatTable/CHS/AvatarAndWeapon.csv"

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
        cheat_table_content = (await client.get(SNAP_CHEAT_TABLE)).content

    cheat_table_csv = csv.reader(
        cheat_table_content.decode(encoding="utf-8").splitlines()
    )
    translation_map, gacha_events = {}, []

    for row in cheat_table_csv:
        translation_map[int(row[0])] = row[1]

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
