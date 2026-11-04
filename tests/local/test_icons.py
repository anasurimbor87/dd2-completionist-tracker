"""Checks for the map icons: the stylized badges drawn by the page (BADGE in map/app.js) cover every icon it uses.
Run: python tests/local/test_icons.py"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, need  # noqa: E402


def main():

    app = open(os.path.join(ROOT, "map", "app.js"), encoding="utf-8").read()
    static = json.load(open(need("map", "data", "static.json"), encoding="utf-8"))
    badge_block = re.search(r"const BADGE = \{(.*?)\n\};", app, re.S).group(1)
    badges = set(re.findall(r"^\s+(\w+): \{ fill:", badge_block, re.M))
    loot = set(re.findall(r'"(\w+)"', re.search(r"const LOOT_ICON = \{([^}]*)\}", app).group(1)))  # the quoted values
    legend = set(re.findall(r'"(\w+)"', re.search(r"const LEGEND_ICON = \{([^}]*)\}", app).group(1)))
    check(len(badges) >= 19 and len(loot) == 8, f"badges and loot icons read ({len(badges)} badges, {len(loot)} loot icons)")

    needed = {
        "loot layers": loot,
        "gathering kinds": {g["k"] for g in static["gather"]},
        "services": {s["kind"] for s in static["services"]},
        "campsites and Riftstones": {r["k"] for r in static["rest"]},
        "layer list": legend,
        "entrances": {"entrance"},
        "chests with gear": {"gear"},
    }
    fills = dict(re.findall(r'^\s+(\w+): \{ fill: "(#[0-9a-f]{6})"', badge_block, re.M))
    check(len({fills.get("chest"), fills.get("gear"), fills.get("dlc"), fills.get("beetle"), fills.get("ducat")}) == 5,
          f"chests, chests with gear, Dark Arisen caches, beetles and Ducats differ in colour ({fills.get('chest')}, "
          f"{fills.get('gear')}, {fills.get('dlc')}, {fills.get('beetle')}, {fills.get('ducat')})")
    gear_chests = [e for e in static["loot"] if e["c"] == "chest"
                   and any(static["items"].get(str(i), {}).get("gear") for i, _ in e["it"])]
    check(len(gear_chests) == 238, f"238 chests hold gear ({len(gear_chests)})")
    for what, names in needed.items():
        check(names <= badges, f"every icon of the {what} has a badge ({sorted(names - badges) or sorted(names)})")
    for name in badges:
        fn = re.search(rf"^\s+{name}: \{{ fill: \"#[0-9a-f]{{6}}\"(?:, ink: \"#[0-9a-f]{{6}}\")?, draw: (\w+) \}}", badge_block, re.M)
        if not fn or not re.search(rf"^function {fn.group(1)}\(", app, re.M):
            check(False, f"badge {name} has a colour and a drawing function")
    check(not os.path.exists(os.path.join(ROOT, "map", "icons")) and "icons/icons" not in app,
          "no leftovers of the game-icon sprites")

    finish()


if __name__ == "__main__":
    main()
