"""Story phases and cutoffs on a made-up quest tree (tests/fixtures/quest_tree.json): quest 1 is the main quest whose
end also ends phase quest 11010; quests 4 and 5 close with that phase, quest 6 with quest 2.
Run: python tests/unit/test_phases_unit.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish, fixture  # noqa: E402

import dd2_phases  # noqa: E402


def main():
    tree = fixture("quest_tree.json")
    check(dd2_phases.holds({"or": [[1, 0], [2, 0]]}, {2: 0}), "an or holds with one leaf")
    check(not dd2_phases.holds({"and": [[1, 0], [2, 0]]}, {2: 0}), "an and needs both leaves")
    check(not dd2_phases.holds([1, 0], {1: 1}), "a leaf needs its exact result")
    after_main = {1: 0, 11010: 0}
    check(set(dd2_phases.closed(tree, after_main, {})) == {"4", "5"}, "finishing quest 1 closes quests 4 and 5")
    check(dd2_phases.closed(tree, after_main, {})["5"] == [11010, 0, 1], "the closing end is shown as the main quest")
    check("5" not in dd2_phases.closed(tree, after_main, {"5": "Complete"}), "completed quests are never closed")
    check("4" not in dd2_phases.closed(tree, after_main, {"4": "Impossible"}), "failed quests are not closed again")
    check(set(dd2_phases.closed(tree, {2: 0}, {})) == {"5", "6"}, "finishing quest 2 closes quests 5 and 6")
    check(dd2_phases.closed(tree, {}, {}) == {}, "nothing is closed at the start")
    order = dd2_phases._story_order({q: n["opens"] for q, n in ((int(k), v) for k, v in tree["quests"].items())})
    check(order[1] == 0 and order[2] == 1 and order[3] == 1, f"story order: an or waits for its earliest part ({order})")
    finish()


if __name__ == "__main__":
    main()
