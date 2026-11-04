"""Achievements from this PC's Steam files and saves: the schema has all of Dragon's Dogma 2's achievements, the
counting ones get their goals, and a save's records give the progress. Run: python tests/local/test_achievements.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish, latest_run, playthrough, skip, slot_records  # noqa: E402

import dd2_achievements  # noqa: E402
import dd2_steam  # noqa: E402

COLLECTOR, PHILANTHROPIST, TOURIST = 28, 29, 46


def main():
    steam = dd2_steam.steam_path()
    schema = dd2_achievements.schema(steam)
    if not schema:
        skip("needs Steam's achievement schema for Dragon's Dogma 2 (appcache/stats)")
    check(sorted(schema) == list(range(1, 61)), f"60 achievements with ids 1 to 60 ({len(schema)})")
    check(all(a["n"] and a["d"] for a in schema.values()), "each has a name and a text")
    check(sum(a["hidden"] for a in schema.values()) >= 5, "the story achievements are hidden")
    rows = {a["id"]: a for a in dd2_achievements.achievements(schema, {}, {})}
    goals = {i: a["goal"] for i, a in rows.items() if "goal" in a}
    check(goals == {COLLECTOR: 80, PHILANTHROPIST: 50, TOURIST: 50}, f"three achievements count up to a goal ({goals})")
    accounts = dd2_steam.save_accounts(steam)
    times = dd2_achievements.unlocked(steam, accounts[0][0]) if accounts else None
    check(times is not None and all(1 <= i <= 60 for i in times), f"Steam's unlocks for the account ({len(times or {})})")

    exp = playthrough("achievements")
    if exp:
        dec = os.path.join(latest_run(), "decrypted")
        records = dd2_achievements.records(slot_records(dec, exp["slot"]))
        counts = {str(i): r[1] for i, r in records.items() if r[1]}
        check(counts == exp["counts"], f"{exp['slot']}: progress counts {exp['counts']} ({counts})")
        unlocked = sorted(i for i, r in records.items() if r[0])
        check(unlocked == exp["unlocked"], f"{exp['slot']}: achievements the save records as unlocked ({unlocked})")
    finish()


if __name__ == "__main__":
    main()
