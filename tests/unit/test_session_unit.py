"""The save log on two made-up saves: what changed between them, and how the live server records it.
Run: python tests/unit/test_session_unit.py"""
import copy
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish, fixture, fixture_records  # noqa: E402

import dd2_mapdata  # noqa: E402
import dd2_session  # noqa: E402

SEEN = "a0000000000000000000000000000003"


def states():
    records, quests = fixture_records(), fixture("quests.json")
    older = dd2_mapdata.compute_state(records, quests, "2026-01-01 10:00:00", "data001Slot")
    later = copy.deepcopy(records)
    for r in later["app.ContextDBMSSaveData"]["DBSaveData"]["Records"]:
        ctx = {c["$type"]: c for c in r["Contexts"] if c}  # real saves hold empty context slots too
        if ctx.get("app.UniqueIDContext", {}).get("UniqueID", {}).get("_RowID") == SEEN:
            ctx["app.GmItemContext"]["_IsPick"] = True
    later["app.ItemManager.GameSaveData"]["MoneySave"]["_Gold"] += 250
    later["app.TimeManager.TimeSaveData"]["InGameElapsedSeconds"] += 600
    newer = dd2_mapdata.compute_state(later, quests, "2026-01-01 10:30:00", "data001Slot")
    return older, newer


def main():
    older, newer = states()
    d = dd2_session.diff(dd2_session.snapshot(older), dd2_session.snapshot(newer))
    check(d["looted"] == [SEEN] and d["gold"] == 250, f"diff: the newly looted spot and the gold change ({d['looted']}, {d['gold']})")
    check(dd2_session.same_run(dd2_session.snapshot(older), dd2_session.snapshot(newer)), "both saves are one playthrough")
    check("upgrades" not in d, "the Log no longer records smithing upgrades")
    check(not any(k.startswith("gear") for k in dd2_session.snapshot(newer)), "snapshots carry no worn-gear levels")
    with tempfile.TemporaryDirectory() as work:
        check(dd2_session.record(work, older) is None, "the first save only sets the starting point")
        entry = dd2_session.record(work, newer)
        check(entry is not None and entry["looted"] == [SEEN], "the next save is logged")
        check(len(dd2_session.read_log(work)) == 1, "the log holds one entry")
        check(dd2_session.record(work, newer) is None, "the same save read again adds nothing")
    finish()


if __name__ == "__main__":
    main()
