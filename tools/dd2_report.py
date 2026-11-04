"""Readable report from a parsed DD2 slot save + game data tables (gamedata/*.json)."""
import collections
import json
import math
import os

import dd2_loot
import dd2_mapdata

SLOTS = {0: "weapon", 1: "sub weapon", 2: "head", 3: "body", 4: "legs", 5: "cloak", 6: "ring"}
VERNWORTH = (520.0, -1000.0)  # centre of twn01_* placements


def load_gamedata(gd_dir):
    def j(name):
        with open(os.path.join(gd_dir, name + ".json"), encoding="utf-8") as f:
            return json.load(f)
    return j("quests"), {int(k): v for k, v in j("items").items()}, j("loot"), j("places"), set(j("shop_items"))


def where(entry, places):
    x, _, z = entry["pos"]
    name = dd2_mapdata.place_of(x, z, places)
    if name and not name.startswith("near "):
        return name
    # map orientation verified on the menu map: world -z is north, +x is east
    dx, dz = x - VERNWORTH[0], -(z - VERNWORTH[1])
    compass = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((math.degrees(math.atan2(dx, dz)) % 360 + 22.5) // 45) % 8]
    far = f"{math.hypot(dx, dz) / 1000:.1f} km {compass} of Vernworth"
    return f"{name}, {far}" if name else far


def gear_report(records, items, loot, places, shop_items):
    state = dd2_loot.loot_state(records)
    owned = {s["_ItemId"] for s in records["app.ItemManager.GameSaveData"]["ItemStorageSaves"] if s["_ItemId"]}

    placements = collections.defaultdict(list)
    for l in loot:
        for iid, _n in l["items"]:
            placements[iid].append(l)

    lines = []
    lines.append("## Unique gear (≤2 placements, not sold in shops)\n")
    rows, seen_rows = [], set()
    for iid, pls in placements.items():
        it = items.get(iid)
        if not it or not it.get("name") or "EquipCategory" not in it or iid in shop_items or len(pls) > 2:
            continue
        for l in pls:
            key = (iid, round(l["pos"][0]), round(l["pos"][2]))  # same spot listed in several layer files
            if key not in seen_rows:
                seen_rows.add(key)
                rows.append((it, l, state.get(l["row_id"], "not visited")))
    for slot in sorted({r[0]["EquipCategory"] for r in rows}):
        lines.append(f"### {SLOTS.get(slot, f'other ({slot})')}")
        for it, l, st in sorted((r for r in rows if r[0]["EquipCategory"] == slot), key=lambda r: (r[0].get("Lv") or 0, r[0]["name"])):
            have = " (owned)" if it["id"] in owned else ""
            dlc = " [DLC]" if any(s.startswith("ex") for s in it.get("sources", [])) else ""
            lines.append(f"- [{st:11}] {it['name']}{dlc}{have} – Lv{it.get('Lv')} wt {it.get('Weight')}"
                         f" – {where(l, places)} @ ({l['pos'][0]:.0f}, {l['pos'][2]:.0f})")
        lines.append("")
    seen = [l for l in loot if state.get(l["row_id"]) == "seen" and l["gimmick"].startswith("gm80")]
    lines.append(f"## Chests you passed but didn't loot: {len(seen)}\n")
    for l in sorted(seen, key=lambda l: where(l, places))[:60]:
        names = ", ".join(items.get(i, {}).get("name", str(i)) for i, _ in l["items"])
        lines.append(f"- {where(l, places)} @ ({l['pos'][0]:.0f}, {l['pos'][2]:.0f}): {names}")
    return "\n".join(lines)


def quest_report(quest_json, quests):
    lines = ["## Quests\n"]
    for l in quest_json["log"]:
        q = quests.get(str(l["QuestId"]), {})
        lines.append(f"- {l['StatusName']:11} {q.get('title', l['QuestId'])}")
    return "\n".join(lines) + "\n"
