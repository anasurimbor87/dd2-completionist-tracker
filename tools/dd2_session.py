"""Save log: what changed from one game save to the next (work/session_log.jsonl, newest last)."""
import json
import os

LOG_NAME = "session_log.jsonl"
SNAPSHOT_NAME = "last_snapshot.json"
COUNTED_OWNERS = ("you", "storage", "main pawn")
GROWING = ("you", "main pawn")  # hired pawns come and go: their growth is not yours


def snapshot(state):
    """The parts of a live state (dd2_mapdata.compute_state) that the log compares."""
    inventory = {}
    for item, owners in state.get("inventory", {}).items():
        n = sum(owners.get(w, 0) for w in COUNTED_OWNERS)
        if n:
            inventory[item] = n
    party = {}
    for m in state.get("party", []):
        if m["who"] in GROWING:
            party[m["who"]] = {"level": m["level"], "ranks": {str(j): r for j, r in m["vocations"]},
                               "learned": {str(s): lv for s, lv in m["learned"].items()}, "augments": list(m["augments_known"])}
    return {
        "saved": state.get("saved"), "slot": state.get("slot"), "day": state.get("day"), "elapsed": state.get("elapsed"),
        "gold": state.get("gold") or 0, "rift": state.get("rift") or 0, "player": state.get("player"),
        "looted": sorted(k for k, v in state.get("loot", {}).items() if v == "looted"),
        "quests": {q: v["status"] for q, v in state.get("quests", {}).items()},
        "inventory": inventory, "party": party,
        "closed": {q: e[2] for q, e in state["closed"].items()} if "closed" in state else None,
        "achievements": sorted([a["id"], a["n"]] for a in state["achievements"] if a["unlocked"]) if "achievements" in state else None,
        "achievements_from": state.get("achievements_from"),
    }


def _growth(older, newer):
    """level-ups, vocation rank-ups, new skills (or skill levels) and augments of you and your main pawn"""
    out = []
    for who in GROWING:
        a, b = (older.get("party") or {}).get(who), (newer.get("party") or {}).get(who)
        if not a or not b:  # snapshots from before the party was recorded
            continue
        if b["level"] > a["level"]:
            out.append([who, "level", a["level"], b["level"]])
        for job, rank in sorted(b["ranks"].items(), key=lambda kv: int(kv[0])):
            if rank > a["ranks"].get(job, 1):
                out.append([who, "rank", int(job), a["ranks"].get(job, 1), rank])
        for skill, lv in sorted(b["learned"].items(), key=lambda kv: int(kv[0])):
            if lv > a["learned"].get(skill, 0):
                out.append([who, "skill", int(skill), lv])
        out += [[who, "augment", aug] for aug in b["augments"] if aug not in a["augments"]]
    return out


def _closed(older, newer):
    """[[quest whose end closed them, [quests not started], [quests already started]], ...] for quests the story closed
    since the older save; nothing if either snapshot is from before closed quests were recorded"""
    if older.get("closed") is None or newer.get("closed") is None:
        return []
    by_event = {}
    for q, event in sorted(newer["closed"].items(), key=lambda kv: int(kv[0])):
        if q not in older["closed"]:
            by_event.setdefault(event, ([], []))[q in newer["quests"]].append(int(q))
    return [[event, fresh, started] for event, (fresh, started) in sorted(by_event.items())]


def _achievements(older, newer):
    """[[id, name], ...] of achievements unlocked since the older save; nothing if either snapshot is from before
    achievements were recorded, or if one has Steam's unlocks and the other only the save's own"""
    if older.get("achievements") is None or newer.get("achievements") is None:
        return []
    if older.get("achievements_from") != newer.get("achievements_from"):  # Steam's list against the save's flags
        return []
    before = {a[0] for a in older["achievements"]}
    return [a for a in newer["achievements"] if a[0] not in before]


def same_run(older, newer):
    """True if newer continues older's playthrough: completed quests stay completed and loot stays looted."""
    done = lambda s: {q for q, st in s["quests"].items() if st == "Complete"}
    if not done(older) <= done(newer):
        return False
    lost = set(older["looted"]) - set(newer["looted"])
    return len(lost) <= max(5, len(older["looted"]) // 10)


def diff(older, newer):
    looted = sorted(set(newer["looted"]) - set(older["looted"]))
    quests = [[q, older["quests"].get(q), st] for q, st in sorted(newer["quests"].items()) if older["quests"].get(q) != st]
    items = {}
    for item in set(older["inventory"]) | set(newer["inventory"]):
        d = newer["inventory"].get(item, 0) - older["inventory"].get(item, 0)
        if d:
            items[item] = d
    return {"saved": newer["saved"], "prev_saved": older["saved"], "day": newer["day"],
            "days": (newer["day"] or 0) - (older["day"] or 0), "gold": newer["gold"] - older["gold"],
            "rift": newer["rift"] - older["rift"], "looted": looted, "quests": quests, "items": items,
            "growth": _growth(older, newer), "closed": _closed(older, newer), "achievements": _achievements(older, newer)}


def _unchanged(entry):
    return not any(entry.get(k) for k in ("looted", "quests", "items", "growth", "closed", "achievements", "gold", "rift",
                                          "days"))


def _write_atomic(path, text):
    """write via a temporary file: a crash or a closed console window mid-write never leaves half a file"""
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)


def _read_entries(path):
    """log entries oldest first; a damaged line (cut off by a crash) is skipped"""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _append(work_dir, entry):
    path = os.path.join(work_dir, LOG_NAME)
    lead = ""
    if os.path.exists(path) and os.path.getsize(path):
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            lead = "" if f.read(1) == b"\n" else "\n"  # never glue onto a cut-off line
    with open(path, "a", encoding="utf-8") as f:
        f.write(lead + json.dumps(entry, ensure_ascii=False) + "\n")


def _save_snapshot(work_dir, snap):
    _write_atomic(os.path.join(work_dir, SNAPSHOT_NAME), json.dumps(snap))


def _load_snapshot(work_dir):
    try:
        with open(os.path.join(work_dir, SNAPSHOT_NAME), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):  # missing or damaged: start over from this save
        return None


def record(work_dir, state):
    """Compare a new live state with the last recorded save; append a log entry if it is a new save.

    - same playthrough, later: what changed (nothing is logged if nothing did)
    - same playthrough, earlier (an older save or "restart from last checkpoint" was loaded): a "reloaded" marker
    - anything else: a "new_run" marker"""
    snap = snapshot(state)
    prev = _load_snapshot(work_dir)
    if prev and prev["saved"] == snap["saved"]:
        return None
    entry = None
    if prev:
        if same_run(prev, snap):
            entry = diff(prev, snap)
        elif same_run(snap, prev):
            entry = {"saved": snap["saved"], "reloaded": True, "day": snap["day"], "prev_saved": prev["saved"],
                     "prev_day": prev["day"]}
        else:
            entry = {"saved": snap["saved"], "new_run": True, "day": snap["day"]}
        if _unchanged(entry) and not entry.get("reloaded") and not entry.get("new_run"):
            entry = None
        else:
            _append(work_dir, entry)
    _save_snapshot(work_dir, snap)
    return entry


def backfill(work_dir, snapshots):
    """Rebuild the log from older save copies: keep the latest playthrough, oldest first."""
    snaps = sorted({s["saved"]: s for s in snapshots}.values(), key=lambda s: s["saved"])
    if not snaps:
        return []
    chain = [snaps[-1]]
    for s in reversed(snaps[:-1]):
        if same_run(s, chain[0]):
            chain.insert(0, s)
    entries = [e for e in (diff(a, b) for a, b in zip(chain, chain[1:])) if not _unchanged(e)]
    _write_atomic(os.path.join(work_dir, LOG_NAME), "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    _save_snapshot(work_dir, chain[-1])
    return entries


def quest_start_days(work_dir):
    """quest id -> in-game day of the first logged save that shows the quest (current playthrough only).

    The day is that of the save, so the quest started on that day or a little earlier. Quests that were already in the
    quest log when the log began have no entry."""
    days = {}
    for e in _read_entries(os.path.join(work_dir, LOG_NAME)):
        if e.get("new_run"):
            days = {}
            continue
        for q, before, _after in e.get("quests", []):
            if before is None:
                days.setdefault(q, e["day"])
    return days


def read_log(work_dir, limit=100):
    return list(reversed(_read_entries(os.path.join(work_dir, LOG_NAME))[-limit:]))
