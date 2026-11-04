"""Norgan Ducats on the map (loot of kind "ducat"): every fixed placement of gimmick 894 (Gm83_169), one Ducat each.
Run: python tests/local/test_ducats.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish, need  # noqa: E402

import dd2_loot  # noqa: E402

DUCAT = dd2_loot.DUCAT_ITEM


def main():
    static = json.load(open(need("map", "data", "static.json"), encoding="utf-8"))
    ducats = [l for l in static["loot"] if l["c"] == "ducat"]
    check(len(ducats) == 140 and len({d["id"] for d in ducats}) == 140, f"140 Ducat spots, each its own placement ({len(ducats)})")
    check(all(d["it"] == [[DUCAT, 1]] for d in ducats), "each holds one Norgan Ducat")
    check(static["items"][str(DUCAT)]["n"] == "Norgan Ducat", "item 711 is the Norgan Ducat")
    check(not any(i == DUCAT for g in static["gather"] for i, _ in g["yields"]), "no Ducat is left among the gathering spots")
    others = [l for l in static["loot"] if l["c"] != "ducat" and any(i == DUCAT for i, _ in l["it"])]
    check(not others, f"no other loot spot holds a Ducat ({len(others)})")
    # Norgan has few named places (40 of the 408 Dark Arisen caches have no name either)
    named = sum(1 for d in ducats if d.get("p"))
    check(named >= 110, f"most Ducat spots have a place name ({named} of {len(ducats)})")
    finish()


if __name__ == "__main__":
    main()
