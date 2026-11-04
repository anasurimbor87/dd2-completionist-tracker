"""Checks for the Hard-mode safety data: campsites, Riftstones, town names, real dungeon entrances, timed quests.
Run: python tests/local/test_hardmode.py"""
import collections
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, latest_run, need, playthrough, slot_records  # noqa: E402

import dd2_mapdata  # noqa: E402
import dd2_session  # noqa: E402

EVERY_ROSE = "30050"


def write_log(work, entries):
    with open(os.path.join(work, dd2_session.LOG_NAME), "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def main():
    s = json.load(open(need("map", "data", "static.json"), encoding="utf-8"))

    rest = s.get("rest", [])
    rifts = [r for r in rest if r["k"] == "rift"]
    camps = [r for r in rest if r["k"] == "camp"]
    check(len(rifts) == 109, f"109 Riftstones: 75 in the base game, 34 in Norgan ({len(rifts)})")
    check(any(r["n"] == "Grand Riftstone of Norgan" for r in rifts), "the Dark Arisen icons are read")
    check(all("Riftstone" in r["n"] for r in rifts), "every Riftstone has its name")
    grand = [r for r in rifts if r["n"] == "Grand Riftstone of Vermund"]
    check(bool(grand) and "Vernworth" in grand[0]["p"], f"the Grand Riftstone of Vermund is in Vernworth ({grand[0]['p'] if grand else '-'})")
    check(len(camps) == 109, f"109 campsites: 84 in the base game, 25 in Norgan ({len(camps)})")
    near_fire = (-713, -1506)  # a campfire placement in editfield_87
    check(any(abs(c["x"] - near_fire[0]) < 20 and abs(c["z"] - near_fire[1]) < 20 for c in camps),
          "a campsite icon sits on a known campfire placement")

    # campsite numbers (app.CampSaveData bits): campfires of all three kinds in area-number order
    numbered = {c["i"]: c for c in camps if "i" in c}
    check(len(numbered) == 84, f"the 84 base-game campsites have a number, Norgan's don't ({len(numbered)})")
    check(sorted(numbered) == list(range(84)), "numbers 0-83 without gaps or doubles")
    last = numbered.get(24, {})
    check(last.get("fire") == 1000 and last.get("p") == "near Mt. Alles Tunnel",
          f"#24 (fire type 1000) is at Mt. Alles Tunnel ({last.get('p')}, {last.get('fire')})")
    exp = playthrough("hardmode")
    if exp:
        dec = os.path.join(latest_run(), "decrypted")
        for slot, want in exp["camps"].items():
            state = dd2_mapdata.compute_state(slot_records(dec, slot), {"log": []}, "x", slot)
            check(state.get("camps_found") == want["found"] and ("last" not in want or state.get("camp_last") == want["last"]),
                  f"{slot}: campsites {want['found']} found, last slept at {want.get('last')} "
                  f"({state.get('camps_found')}, {state.get('camp_last')})")

    names = {p["name"] for p in s["places"]}
    check({"Bakbattahl", "Melve"} <= names, "Bakbattahl and Melve are named places")
    spots = s["loot"] + s["services"]
    check(any((e.get("p") or e.get("place")) == "Melve" for e in spots), "spots in Melve say Melve")

    by_ui = {d["ui"]: d for d in s["dungeons"]}
    check(by_ui.get(1000, {}).get("name") == "Waterfall Cave", f"dungeon 1000 is Waterfall Cave ({by_ui.get(1000, {}).get('name')})")
    # entrance icons (_MapArea = dungeon UI area) from the base game and Dark Arisen icon files
    with_ent = [d for d in s["dungeons"] if d.get("entrance_known")]
    check(len(with_ent) >= 110, f"at least 110 of 120 dungeons have their real entrance ({len(with_ent)}, was 11)")
    check(by_ui.get(7009, {}).get("name") == "Mordria Temple", f"Norgan caves get their names ({by_ui.get(7009, {}).get('name')})")

    # surface spots are not named after the dungeons beneath them
    field = [e for e in s["loot"] if not e.get("d")]
    dungeon_names = {p["name"] for p in s["places"] if p.get("dungeon")}
    check(not any(e["p"] in dungeon_names for e in field), "no surface spot carries a dungeon's name")
    check(not any(r["p"] in dungeon_names for r in rest), "no campsite or Riftstone carries a dungeon's name")

    # proving-ground loot stays in its own proving ground (Wyrmsblood Arena lies at y -12 under Dragonsbreath Tower)
    wyrm =[e for e in s["loot"] if e.get("d") and by_ui[e["d"][0]]["name"] == "Dragonsbreath Tower"
            and e["y"] < 100]
    check(not wyrm, f"no low-lying proving-ground loot drawn in Dragonsbreath Tower ({len(wyrm)})")

    # quests: only real positions (the default character of a destination once put 38% on one castle NPC)
    spots = collections.Counter((round(x), round(z)) for q in s["quests"].values() for t in q["tasks"] for x, z, _ in t["d"])
    check(spots.get((549, -759), 0) == 0, f"no quest objective at the default character's spot ({spots.get((549, -759), 0)})")
    check(any(len(d.get("entrances", [])) > 1 for d in s["dungeons"]), "dungeons with several entrances keep all of them")

    rose = s["quests"].get(EVERY_ROSE, {})
    check(rose.get("timed") and any(t["timed"] and "three days" in t["t"] for t in rose.get("tasks", [])),
          "Every Rose Has Its Thorn is timed: gather evidence within three days")

    with tempfile.TemporaryDirectory() as work:
        write_log(work, [
            {"saved": "a", "day": 3, "quests": [["20070", None, "Progressing"]]},
            {"saved": "b", "day": 5, "quests": [["20070", "Progressing", "Progressing"], ["30050", None, "Progressing"]]},
        ])
        check(dd2_session.quest_start_days(work) == {"20070": 3, "30050": 5}, "quest start days come from the first log entry that shows them")
        write_log(work, [
            {"saved": "a", "day": 3, "quests": [["20070", None, "Progressing"]]},
            {"saved": "b", "new_run": True, "day": 1},
            {"saved": "c", "day": 2, "quests": [["30050", None, "Progressing"]]},
        ])
        check(dd2_session.quest_start_days(work) == {"30050": 2}, "another playthrough starts the start days afresh")
    if exp:
        real = dd2_session.quest_start_days(os.path.join(ROOT, "work"))
        for quest, day in exp["quest_start_days"].items():
            check(real.get(quest) == day, f"the save log: quest {quest} first showed up on day {day} ({real.get(quest)})")

    finish()


if __name__ == "__main__":
    main()
