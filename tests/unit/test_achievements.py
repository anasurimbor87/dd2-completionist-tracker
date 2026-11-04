"""Achievements (tools/dd2_achievements.py): names from Steam's local schema, unlock times from Steam's per-account
stats, progress counts from the save. Made-up Steam files and records only. Run: python tests/unit/test_achievements.py"""
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import dd2_achievements  # noqa: E402

APP = "2054970"


def kv(obj):
    """Steam's binary KeyValues: 0 = section, 1 = string, 2 = int32, 8 = end of section"""
    out = bytearray()
    for k, v in obj.items():
        key = k.encode("utf-8") + b"\0"
        if isinstance(v, dict):
            out += b"\0" + key + kv(v)
        elif isinstance(v, str):
            out += b"\1" + key + v.encode("utf-8") + b"\0"
        else:
            out += b"\2" + key + struct.pack("<i", v)
    return bytes(out) + b"\x08"


def bit(name, title, desc, hidden=0):
    return {"name": name, "display": {"name": {"english": title}, "desc": {"english": desc}, "hidden": str(hidden)}}


SCHEMA = {APP: {"stats": {
    "1": {"bits": {"1": bit("1", "First Steps", "Walked a bit."), "2": bit("2", "Coin Collector", "Collected 80 test coins.")},
          "type": "ACHIEVEMENTS"},
    "2": {"bits": {"0": bit("32", "Secret Ending", "Saw the secret ending.", hidden=1), "4": bit("36", "Friendly", "Befriended 50 people.")},
          "type": "ACHIEVEMENTS"},
}, "version": 3, "gamename": "Made Up"}}
STATS = {"cache": {"crc": 1, "PendingChanges": 0, "1": {"data": 6, "AchievementTimes": {"1": 1700000000}},
                   "2": {"data": 16, "AchievementTimes": {"4": 1700000500}}}}
RECORDS = {"app.GlobalUserDataManager.SaveData": {"SaveGameRecordDataList": [
    {"_RecordID": 0, "_IsUnlock": False, "_Count": 0, "_ProgressBitFlag": 0},
    {"_RecordID": 1, "_IsUnlock": True, "_Count": 0, "_ProgressBitFlag": 0},
    {"_RecordID": 2, "_IsUnlock": False, "_Count": 15, "_ProgressBitFlag": 0},
    {"_RecordID": 36, "_IsUnlock": False, "_Count": 9, "_ProgressBitFlag": 0},
]}}


def main():
    with tempfile.TemporaryDirectory() as steam:
        stats = os.path.join(steam, "appcache", "stats")
        os.makedirs(stats)
        with open(os.path.join(stats, f"UserGameStatsSchema_{APP}.bin"), "wb") as f:
            f.write(kv(SCHEMA))
        with open(os.path.join(stats, f"UserGameStats_12345678_{APP}.bin"), "wb") as f:
            f.write(kv(STATS))

        schema = dd2_achievements.schema(steam)
        check(sorted(schema) == [1, 2, 32, 36], f"four achievements, ids from the bits' names ({sorted(schema)})")
        check(schema[2] == {"n": "Coin Collector", "d": "Collected 80 test coins.", "hidden": False}, f"name and text ({schema.get(2)})")
        check(schema[32]["hidden"] is True, "hidden achievements are marked")
        times = dd2_achievements.unlocked(steam, 12345678)
        check(times == {1: 1700000000, 36: 1700000500}, f"unlock times by id, the second block's bit 4 is id 36 ({times})")
        check(dd2_achievements.unlocked(steam, 999) is None, "no stats file for an account: None")
        check(dd2_achievements.schema(os.path.join(steam, "nowhere")) is None, "no schema: None")

        records = dd2_achievements.records(RECORDS)
        check(records == {1: [True, 0], 2: [False, 15], 36: [False, 9]}, f"the save's unlocks and counts ({records})")
        check(dd2_achievements.records({}) == {}, "a save without game records has none")

        rows = {a["id"]: a for a in dd2_achievements.achievements(schema, times, records)}
        check(sorted(rows) == [1, 2, 32, 36], "one row per achievement")
        check(rows[1]["unlocked"] and rows[1]["at"] == 1700000000 and not rows[2]["unlocked"], "unlocked from Steam, with the time")
        check(rows[2]["count"] == 15 and rows[2]["goal"] == 80, f"progress from the save, goal from the text ({rows[2]})")
        check(rows[36]["unlocked"] and rows[36].get("goal") == 50, "an unlocked counting achievement keeps its goal")
        check("goal" not in rows[1] and "goal" not in rows[32], "achievements without a number in the text have no goal")

        no_steam = {a["id"]: a for a in dd2_achievements.achievements(None, None, records)}
        check(no_steam[1]["unlocked"] and no_steam[1]["n"] == "Achievement 1" and no_steam[2]["count"] == 15,
              "without Steam's files: unlocks from the save and numbered names")
    finish()


if __name__ == "__main__":
    main()
