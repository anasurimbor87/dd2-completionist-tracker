"""Checks for story phases and quest cutoffs (dd2_phases, gamedata/quest_tree.json).
Run: python tests/local/test_phases.py"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, latest_run, need, playthrough  # noqa: E402

import dd2_mapdata  # noqa: E402
import dd2_phases  # noqa: E402
import dd2_session  # noqa: E402
import ree_rsz  # noqa: E402

GAOLED, SOVRAN, MONSTER_CULLING, DISAS_PLOT, UNSETTLING, CAGED, FEAST = 10030, 10080, 10090, 10100, 10110, 10120, 10140
GODSWAY, LEGACY, ARISENS_SHADOW, NAMELESS, REGENTKIN, OXCART, READVENT = 10170, 10200, 10130, 20220, 20390, 20480, 30100
FEAST_CLOSES = {"The Stolen Throne", "The Caged Magistrate", "The Arisen's Shadow", "The Ornate Box", "Readvent of Calamity",
                "Masked Correspondence"}


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return json.load(f)


def main():

    tree, titles = load(need("gamedata", "quest_tree.json")), load(need("gamedata", "quests.json"))
    node = lambda q: tree["quests"][str(q)]
    check(tree["phases"] == [[11010, GAOLED], [11020, SOVRAN], [11030, FEAST], [11040, LEGACY], [11050, 10220]],
          "five phases, ending with Gaoled Awakening, Seat of the Sovran, Feast of Deception, Legacy and the last step")
    check(len(tree["quests"]) == 118, f"118 of the 120 titled quests are in the tree ({len(tree['quests'])})")
    check(node(FEAST)["opens"] == {"and": [[MONSTER_CULLING, 0], [UNSETTLING, 0]]},
          "Feast of Deception opens after Monster Culling and An Unsettling Encounter")
    check(node(READVENT)["opens"] == {"or": [[DISAS_PLOT, 0], [MONSTER_CULLING, 0], [CAGED, 0]]},
          "Readvent of Calamity opens after any of Disa's Plot, Monster Culling, The Caged Magistrate")
    check(node(OXCART)["ends"] == [[11040, 0, LEGACY], [READVENT, 0, READVENT]],
          "Oxcart Courier closes with Legacy's phase or with Readvent of Calamity")
    check(node(ARISENS_SHADOW)["ends"] == [[11030, 0, FEAST]], "The Arisen's Shadow closes with Feast of Deception")
    check([e[2] for e in node(NAMELESS)["ends"]] == [REGENTKIN, REGENTKIN],
          "The Nameless Village: the untitled helper 20391 shows as The Regentkin's Resolve")
    check(all(not n["ends"] for q, n in tree["quests"].items() if int(q) >= 40000), "Dark Arisen quests have no cutoffs")
    order = [node(q)["o"] for q in (READVENT, FEAST, GODSWAY, LEGACY)]
    check(order == sorted(order) and len(set(order)) == 4,
          f"story order: Readvent of Calamity, Feast of Deception, A New Godsway, Legacy ({order})")
    feast = {titles[q]["title"] for q, n in tree["quests"].items() if any(e[2] == FEAST for e in n["ends"])}
    check(feast >= FEAST_CLOSES and len(feast) == 8, f"Feast of Deception ends eight quests ({sorted(feast)})")

    static = load("map", "data", "static.json")
    check(static.get("phases") == tree["phases"] and static["quests"][str(OXCART)].get("ends") == node(OXCART)["ends"],
          "the map data carries the phases and each quest's cutoffs (rebuild with dd2.py map if not)")

    # what closes what
    res = {11010: 0, 11020: 0, 11030: 0, FEAST: 0}
    closed = dd2_phases.closed(tree, res, {})
    check(closed.get(str(ARISENS_SHADOW)) == [11030, 0, FEAST], "after the Feast's phase The Arisen's Shadow is closed")
    check({titles[q]["title"] for q in closed} == FEAST_CLOSES | {"Vocation Frustration", "Brothers Brave and Timid"},
          f"without a quest log, the Feast closes its eight quests ({len(closed)})")
    check(str(ARISENS_SHADOW) not in dd2_phases.closed(tree, res, {str(ARISENS_SHADOW): "Complete"}),
          "a completed quest is never closed")
    check(dd2_phases.closed(tree, {READVENT: 0}, {}).get(str(OXCART)) == [READVENT, 0, READVENT],
          "finishing Readvent of Calamity closes Oxcart Courier")
    check(not dd2_phases.closed(tree, {READVENT: 1}, {}), "another result of Readvent of Calamity closes nothing")
    check(dd2_phases.holds({"and": [[1, 0], [2, 0]]}, {1: 0}) is False and dd2_phases.holds({"or": [[1, 0], [2, 0]]}, {1: 0}),
          "AND needs every part, OR one")

    # data the reader doesn't understand is refused, not guessed
    def refused(fn, *args):
        try:
            fn(*args)
        except ValueError:
            return True
        return False
    bad_end = {"_QuestID": 1, "_EndConditionParam": {"_Operator": 1, "_ConditionArray": [
        {"$type": "app.quest.condition.ScenarioConditionParam.CheckScenario", "_QuestID": 2, "_ResultNo": 0, "_Logic": 1}]}}
    check(refused(dd2_phases._end_leaves, bad_end), "a 'not ended' end condition is refused")
    two_paths = {"_QuestID": 1, "_PrevTransitions": [{"_ElementArray": []}, {"_ElementArray": []}]}
    check(refused(dd2_phases._opens, two_paths), "several prerequisite lists are refused")
    check(refused(ree_rsz.parse_scn_instances, b"USR\x00" + bytes(60), None), "a non-scene file is refused as a scene")

    # a real save: its phase, and what finishing Feast of Deception would close in it
    dec = os.path.join(latest_run(), "decrypted")
    exp = playthrough("phases")
    slot = exp["slot"] if exp else sorted(os.path.basename(p)[:-5] for p in os.listdir(dec)
                                         if p.startswith("data") and p.endswith("Slot.json"))[-1]
    records = {r.get("$type"): r for r in load(dec, slot + ".json")}
    quests = load(dec, slot + ".quests.json")
    state = dd2_mapdata.compute_state(records, quests, "x", slot, None, tree)
    if exp:
        phase = next(i for i, (p, _) in enumerate(tree["phases"]) if str(p) not in state["results"]) + 1
        check(phase == exp["phase"], f"{slot} is in story phase {exp['phase']} ({phase})")
        check(state["closed"] == exp["closed"], f"closed quests: {exp['closed']} ({state['closed']})")
        statuses = {q: v["status"] for q, v in state["quests"].items()}
        after_feast = {int(q): r for q, r in state["results"].items()} | {11030: 0, FEAST: 0}
        left = {titles[q]["title"] for q in dd2_phases.closed(tree, after_feast, statuses)}
        check(left == set(exp["feast_would_close"]), f"finishing the Feast now would close {sorted(left)}")
    check("results" not in dd2_mapdata.compute_state(records, dict(quests, contexts=[]), "x", "s", None, tree),
          "without quest contexts there are no results (the phase would read as the first)")

    # the save log notes what a save closed
    later = copy.deepcopy(state)
    later["saved"] = "y"
    later["closed"] = {str(ARISENS_SHADOW): [11030, 0, FEAST], str(OXCART): [READVENT, 0, READVENT]}
    later["quests"][str(OXCART)] = {"status": "Progressing", "task": 0}
    entry = dd2_session.diff(dd2_session.snapshot(state), dd2_session.snapshot(later))
    check(entry["closed"] == [[FEAST, [ARISENS_SHADOW], []], [READVENT, [], [OXCART]]],
          f"the log groups closed quests by the quest whose end closed them ({entry['closed']})")
    old = dd2_session.snapshot(state)
    old.pop("closed")
    check(dd2_session.diff(old, dd2_session.snapshot(later))["closed"] == [],
          "a snapshot from before closed quests were recorded logs none")
    check(not dd2_session._unchanged({"closed": entry["closed"]}), "a save that only closed quests is still logged")

    finish()


if __name__ == "__main__":
    main()
