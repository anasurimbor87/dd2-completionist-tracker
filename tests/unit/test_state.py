"""compute_state on a made-up save (tests/fixtures/save_records.json, quests.json, quest_tree.json).
Run: python tests/unit/test_state.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish, fixture, fixture_records  # noqa: E402

import dd2_mapdata  # noqa: E402


def main():
    records, quests, tree = fixture_records(), fixture("quests.json"), fixture("quest_tree.json")
    s = dd2_mapdata.compute_state(records, quests, "2026-01-01 10:00:00", "data001Slot", None, tree)
    check(s["day"] == 3 and s["gold"] == 1000 and s["rift"] == 50, f"day, gold, Rift Crystals ({s['day']}, {s['gold']}, {s['rift']})")
    check(s["results"] == {"1": 0, "11010": 0}, f"ended quests and their results ({s['results']})")
    check(s["quests"].get("1") == {"status": "Complete", "task": 2}, f"the quest log ({s['quests']})")
    check(set(s["closed"]) == {"4", "5"}, f"the story has closed quests 4 and 5 ({s.get('closed')})")
    check(s["camps_found"] == [0, 2] and s["camp_last"] == 2, f"campsites 0 and 2 found ({s['camps_found']})")
    check(s["inventory"].get("10") == {"you": 2, "storage": 5} and s["inventory"].get("11") == {"main pawn": 1},
          f"items by owner ({s['inventory']})")
    check("gear" not in s and "equipped" not in s, "the state no longer carries worn gear")
    check(dd2_mapdata.check_records(records, quests) is None, "the made-up save passes the record guard")
    check("results" not in dd2_mapdata.compute_state(records, dict(quests, contexts=[]), "x", "s"),
          "without quest contexts there are no results")
    finish()


if __name__ == "__main__":
    main()
