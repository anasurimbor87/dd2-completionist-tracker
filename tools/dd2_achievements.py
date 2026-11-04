"""Achievements: names and texts from Steam's local achievement schema, unlock times from Steam's stats for the
account, progress counts from the save (app.GlobalUserDataManager.SaveData.SaveGameRecordDataList, one record per
achievement id: _IsUnlock, _Count).

Everything is read at run time from the player's own Steam folder and save (read-only); no achievement text ships with
the tracker. Without Steam's files the save's own unlock flags are used, with numbered names."""
import os
import re
import struct

APPID = "2054970"
RECORDS = "app.GlobalUserDataManager.SaveData"


def read_kv(path):
    """Steam's binary KeyValues file as nested dicts, or None when it can't be read"""
    try:
        with open(path, "rb") as f:
            data = f.read()
        return _kv(data, 0)[0]
    except (OSError, ValueError, IndexError, struct.error):
        return None


def _kv(d, i):
    out = {}
    while i < len(d):
        t = d[i]
        i += 1
        if t in (8, 11):  # end of a section (11: end of the file in some versions)
            return out, i
        j = d.index(b"\0", i)
        name = d[i:j].decode("utf-8", "replace")
        i = j + 1
        if t == 0:
            v, i = _kv(d, i)
        elif t == 1:
            j = d.index(b"\0", i)
            v = d[i:j].decode("utf-8", "replace")
            i = j + 1
        elif t in (2, 3, 4, 6):  # int32, float32, pointer, color: 4 bytes
            v = struct.unpack_from("<f" if t == 3 else "<i", d, i)[0]
            i += 4
        elif t in (7, 10):  # uint64, int64
            v = struct.unpack_from("<Q" if t == 7 else "<q", d, i)[0]
            i += 8
        else:
            raise ValueError(f"KeyValues type {t} at {i}")
        out[name] = v
    return out, i


def _bits(schema_kv):
    """(stat block, bit, achievement dict) for every achievement of the schema"""
    app = (schema_kv or {}).get(APPID) or {}
    for block, stat in (app.get("stats") or {}).items():
        if isinstance(stat, dict):
            for bit, ach in (stat.get("bits") or {}).items():
                if isinstance(ach, dict) and str(ach.get("name", "")).isdigit():
                    yield block, bit, ach


def _english(v):
    return v.get("english", "") if isinstance(v, dict) else (v or "")


def schema(steam):
    """{achievement id: {"n": name, "d": text, "hidden": bool}} from Steam's local schema, or None"""
    if not steam:
        return None
    kv = read_kv(os.path.join(steam, "appcache", "stats", f"UserGameStatsSchema_{APPID}.bin"))
    if kv is None:
        return None
    out = {}
    for _block, _bit, ach in _bits(kv):
        disp = ach.get("display") or {}
        out[int(ach["name"])] = {"n": _english(disp.get("name")), "d": _english(disp.get("desc")),
                                 "hidden": str(disp.get("hidden", "0")) == "1"}
    return out or None


def unlocked(steam, account_id):
    """{achievement id: unlock time (unix)} for the account from Steam's stats, or None without the files"""
    if not steam:
        return None
    stats_dir = os.path.join(steam, "appcache", "stats")
    kv = read_kv(os.path.join(stats_dir, f"UserGameStats_{account_id}_{APPID}.bin"))
    sch = read_kv(os.path.join(stats_dir, f"UserGameStatsSchema_{APPID}.bin"))
    if kv is None or sch is None:
        return None
    cache = kv.get("cache") or {}
    out = {}
    for block, bit, ach in _bits(sch):
        t = ((cache.get(block) or {}).get("AchievementTimes") or {}).get(bit)
        if t:
            out[int(ach["name"])] = t
    return out


def records(by_type):
    """{achievement id: [unlocked in this save, count]} from the save, for records with something in them"""
    out = {}
    for r in (by_type.get(RECORDS) or {}).get("SaveGameRecordDataList") or []:
        if isinstance(r, dict) and (r.get("_IsUnlock") or r.get("_Count")):
            out[r["_RecordID"]] = [bool(r.get("_IsUnlock")), r.get("_Count") or 0]
    return out


def achievements(schema_map, times, save_records):
    """one row per achievement: id, n, d, hidden, unlocked, at (unix time or None), count, and goal when the text
    names a number to reach ("Collected 80 Seeker's Tokens")"""
    ids = sorted(schema_map) if schema_map else sorted(i for i in save_records if i > 0)
    rows = []
    for i in ids:
        info = (schema_map or {}).get(i) or {"n": f"Achievement {i}", "d": "", "hidden": False}
        unlock, count = save_records.get(i, [False, 0])
        at = (times or {}).get(i)
        row = {"id": i, "n": info["n"], "d": info["d"], "hidden": info["hidden"],
               "unlocked": bool(at) if times is not None else unlock, "at": at, "count": count}
        m = re.search(r"\b(\d+)\b", info["d"])
        if m and int(m.group(1)) >= 2:
            row["goal"] = int(m.group(1))
        rows.append(row)
    return rows
