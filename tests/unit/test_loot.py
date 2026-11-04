"""Loot state from a made-up save (tests/fixtures/save_records.json): picked, never generated again, only seen,
and the beetle rule (an emptied beetle spot is taken, an emptied herb spot is not). Run: python tests/unit/test_loot.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish, fixture_records  # noqa: E402

import dd2_loot  # noqa: E402

PICKED, NEVER, SEEN = "a0000000000000000000000000000001", "a0000000000000000000000000000002", "a0000000000000000000000000000003"
BEETLE, HERB = "a0000000000000000000000000000004", "a0000000000000000000000000000005"


def main():
    state = dd2_loot.loot_state(fixture_records())
    check(state.get(PICKED) == "looted" and state.get(NEVER) == "looted" and state.get(SEEN) == "seen",
          f"_IsPick, NeverGenerate, context only ({[state.get(x) for x in (PICKED, NEVER, SEEN)]})")
    check(state.get(BEETLE) == "looted" and state.get(HERB) == "seen",
          f"a beetle spot with _Num 0 is taken, a herb spot with _Num 0 is not ({state.get(BEETLE)}, {state.get(HERB)})")
    check(dd2_loot.loot_state({}) == {}, "a save without loot records has no loot state")
    finish()


if __name__ == "__main__":
    main()
