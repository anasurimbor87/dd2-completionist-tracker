"""Checks for the farming map data (map/data/static.json). Run: python tests/local/test_farming.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, need  # noqa: E402


def main():
    s = json.load(open(need("map", "data", "static.json"), encoding="utf-8"))
    items = s["items"]
    mats = s.get("materials") or []
    check(len(mats) > 50 and mats == sorted(set(mats)) and all("sold" in items.get(str(m), {}) for m in mats),
          f"the Materials tab's list: smithing materials, sorted, each with its shop flag ({len(mats)})")
    check("enhance" not in s and not any("thief" in it for it in items.values()),
          "no upgrade cost tables and no Thief flags in the map data")
    name_of = lambda i: items.get(str(i), {}).get("n", "")

    gather = s.get("gather", [])
    check(len(gather) > 2000, f"gathering spots present ({len(gather)})")
    check(all(g.get("yields") for g in gather), "every gathering spot has yields")
    check(any(name_of(i) == "Cinnamon Bark" for g in gather for i, _ in g.get("yields", [])),
          "Cinnamon Bark can be gathered somewhere")

    spawns = s.get("spawns", [])
    check(len(spawns) > 500, f"monster spawn spots present ({len(spawns)})")
    check(any(sp["n"] == "Hobgoblin" for sp in spawns), "Hobgoblins have spawn spots (Slate-Colored Horn source)")
    check(sum(sp["count"] for sp in spawns) > 8000, "spawn spots cover all monster placements")
    drops = s.get("enemy_drops", {})
    hob = next((sp for sp in spawns if sp["n"] == "Hobgoblin"), {})
    horn = [c for ch in hob.get("ch", []) for i, c in drops.get(ch, {}).get("kill", []) if name_of(i) == "Slate-Colored Horn"]
    # 60% chance of one drop roll per kill, 60% horn per roll: 36% per kill (some variants always roll: 60%)
    check(horn and min(horn) == 36, f"Slate-Colored Horn per Hobgoblin kill: 36% ({horn})")
    mino = next((sp for sp in spawns if sp["n"] == "Minotaur"), {})
    md = drops.get(mino.get("ch", [""])[0], {})
    check(any(name_of(i) == "Minotaur Horn" and c == 71 for i, c in md.get("kill", []))
          and any(name_of(i) == "Minotaur Horn" and c == 100 for i, c in md.get("parts", [])),
          "Minotaur Horn: 71% per kill (2 or 3 rolls of 40%), 100% when a horn breaks")
    base_hob = [ch for sp in spawns if sp["n"] == "Hobgoblin" and not sp.get("d") for ch in sp["ch"]]
    brine = next((k for k, v in items.items() if v.get("n") == "Brinebeast Fragment"), None)
    check(brine and not any(int(brine) == i for ch in base_hob[:20] for i, _ in drops.get(ch, {}).get("kill", []))
          and all("Dark Arisen" in r[0] for r in s["drops"].get(brine, [])),
          "Brinebeast Fragment comes only from Dark Arisen variants, not from every Hobgoblin")
    check(max(c for g in gather for i, c in g["yields"] if name_of(i) == "Cinnamon Bark") == 100,
          "an item listed twice in one table counts twice (Cinnamon Bark 100%, was shown as 50%)")

    services = s.get("services", [])
    smiths = [x for x in services if x["kind"] == "smith"]
    check(len(smiths) >= 9, f"smiths present ({len(smiths)})")
    roderick = [x for x in smiths if "Roderick" in x.get("name", "") or "Roderick" in x.get("place", "")]
    check(bool(roderick) and roderick[0]["style"] == 0, "Roderick's Smithy is a Vermundian smith")
    check(all("x" in x and "z" in x for x in services), "every service has a position")

    finish()


if __name__ == "__main__":
    main()
