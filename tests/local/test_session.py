"""Checks for the save log diff. Run: python tests/local/test_session.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish, latest_run, playthrough  # noqa: E402

import dd2_mapdata  # noqa: E402
import dd2_session  # noqa: E402



def state_of(dec_dir, slot):
    records = {r.get("$type"): r for r in json.load(open(os.path.join(dec_dir, slot + ".json"), encoding="utf-8"))}
    quests = json.load(open(os.path.join(dec_dir, slot + ".quests.json"), encoding="utf-8"))
    return dd2_mapdata.compute_state(records, quests, slot, slot)


def main():
    exp = playthrough("saves")
    if not exp:
        finish()
    dec = os.path.join(latest_run(), "decrypted")
    slots = (exp["older"], exp["newer"], exp["other_run"])
    old, new, other_run = (dd2_session.snapshot(state_of(dec, s)) for s in slots)
    entry = dd2_session.diff(old, new)
    n = exp["looted_between"]

    check(len(entry["looted"]) == n, f"{n} objects newly looted between the two saves ({len(entry['looted'])})")
    check(any(q[0] == exp["completed_between"] and q[2] == "Complete" for q in entry["quests"]),
          f"quest {exp['completed_between']} completed")
    check(entry["items"].get(exp["gained_between"], 0) > 0, f"item {exp['gained_between']} gained")
    check(entry["gold"] == new["gold"] - old["gold"], "gold change matches")
    check(dd2_session.same_run(old, new), "the two saves are the same playthrough")
    check(not dd2_session.same_run(other_run, new), "the other save is a different playthrough")
    check(not dd2_session.diff(new, new)["looted"] and not dd2_session.diff(new, new)["quests"], "no changes against itself")

    # what the live server does on each save
    older, newer, other = (state_of(dec, s) for s in slots)
    with tempfile.TemporaryDirectory() as work:
        check(dd2_session.record(work, older) is None, "the first save only sets the starting point")
        check(dd2_session.record(work, older) is None, "the same save read twice adds nothing")
        logged = dd2_session.record(work, newer)
        check(logged is not None and len(logged["looted"]) == n, f"the next save is logged with its {n} looted spots")
        check(dd2_session.record(work, other).get("new_run"), "switching to another playthrough is marked")
        log = dd2_session.read_log(work)
        check([bool(e.get("new_run")) for e in log] == [True, False], "the log reads newest first")

    finish()


if __name__ == "__main__":
    main()
