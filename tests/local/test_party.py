"""Checks for the Party tab data: vocation table, ranks, what to learn next, pawns and their quest knowledge.
Run: python tests/local/test_party.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish, latest_run, need, playthrough  # noqa: E402

import dd2_mapdata  # noqa: E402
import dd2_party  # noqa: E402
import dd2_session  # noqa: E402

THIEF = 4
PILFER, POISE = 49, 21


def state_of(dec_dir, slot, voc):
    records = {r.get("$type"): r for r in json.load(open(os.path.join(dec_dir, slot + ".json"), encoding="utf-8"))}
    quests = json.load(open(os.path.join(dec_dir, slot + ".quests.json"), encoding="utf-8"))
    return dd2_mapdata.compute_state(records, quests, slot, slot, voc)


def main():
    voc = json.load(open(need("gamedata", "vocations.json"), encoding="utf-8"))

    # the game's tables
    check(voc["jobs"][str(THIEF)]["n"] == "Thief" and len(voc["jobs"]) == 10, "10 vocations, job 4 is Thief")
    pilfer = voc["skills"].get(str(PILFER), {})
    check(THIEF in pilfer.get("jobs", []) and pilfer["levels"][0]["n"] == "Pilfer" and pilfer["levels"][0]["cost"] == 1100
          and pilfer["levels"][0]["rank"] == 5, "Pilfer: Thief skill, 1100 Discipline at rank 5")
    poise = voc["augments"].get(str(POISE), {})
    check(poise.get("n") == "Poise" and poise.get("rank") == 6 and poise.get("cost") == 1800, "Poise: augment at rank 6 for 1800")
    check(voc["specializations"].get("2") == "Chirurgeon" and voc["personalities"].get("1477799926") == "Kindhearted",
          "specialization 2 is Chirurgeon, personality Kind is Kindhearted")

    # rank edges: points needed per next rank 400, 800, 1600, ...
    steps = voc["jobs"][str(THIEF)]["ranks"]
    check(dd2_party.rank_of(0, steps) == (1, 0, 400), "0 points: rank 1, 400 to go")
    check(dd2_party.rank_of(399, steps)[0] == 1 and dd2_party.rank_of(400, steps)[:2] == (2, 0), "400 points reach rank 2")
    check(dd2_party.rank_of(8106, steps) == (5, 8106 - 5200, 4000), "8106 points: rank 5, 2906 into it, 4000 for rank 6")
    check(dd2_party.rank_of(sum(steps) + 50, steps) == (9, 50, None), "past the last step: rank 9, no next rank")

    exp = playthrough("party")
    if not exp:
        finish()
    state = state_of(os.path.join(latest_run(), "decrypted"), exp["slot"], voc)
    party = {m["who"] if m["who"] != "hired pawn" else m["name"]: m for m in state.get("party", [])}
    you, pawn = party.get("you", {}), party.get("main pawn", {})
    ey, ep, eh = exp["you"], exp["pawn"], exp["hired"]
    check(all(you.get(k) == ey[k] for k in ("name", "job", "rank", "dp", "points_to_next")),
          f"you: {ey['name']}, vocation {ey['job']} rank {ey['rank']}, {ey['dp']} Discipline, {ey['points_to_next']} to the next rank "
          f"({[you.get(k) for k in ('name', 'job', 'rank', 'dp', 'points_to_next')]})")
    check([x["n"] for x in you.get("skills", [])] == ey["skills"],
          f"equipped skills by their learned level ({[x['n'] for x in you.get('skills', [])]})")
    check([a["n"] for a in you.get("augments", [])] == ey["augments"], f"equipped augments {ey['augments']}")
    now = [x["n"] for x in you.get("next", {}).get("now", [])]
    check(set(ey["now_has"]) <= set(now) and not set(ey["now_lacks"]) & set(now), f"affordable now, not learned ones ({now})")
    later = [x["n"] for x in you.get("next", {}).get("rank", [])]
    check(set(ey["rank_has"]) <= set(later), f"at the next rank: {ey['rank_has']} ({later})")
    other = {x["n"] for x in you.get("next", {}).get("other", [])}
    check(set(ey["other_has"]) <= other, f"not bought with Discipline: {ey['other_has']}")
    check(all(pawn.get(k) == ep[k] for k in ep), f"main pawn: {ep}")
    hired = party.get(eh["name"], {})
    check(hired.get("owner") == eh["owner"] and eh["knows"] in hired.get("knows", []),
          f"hired pawn {eh['name']} (from {eh['owner']}) knows quest {eh['knows']}")

    # the save log notes growth
    old = dd2_session.snapshot(state)
    new = json.loads(json.dumps(old))
    new["party"]["you"]["level"] += 1
    new["party"]["you"]["ranks"][str(ey["job"])] = ey["rank"] + 1
    new["party"]["you"]["learned"][str(PILFER)] = 1
    new["party"]["you"]["augments"].append(POISE)
    growth = dd2_session.diff(old, new)["growth"]
    check(["you", "level", ey["level"], ey["level"] + 1] in growth and ["you", "rank", ey["job"], ey["rank"], ey["rank"] + 1] in growth
          and ["you", "skill", PILFER, 1] in growth and ["you", "augment", POISE] in growth,
          f"log growth: level, rank, skill, augment ({growth})")
    check(dd2_session.diff(old, old)["growth"] == [], "no growth against itself")
    legacy = dict(old)
    legacy.pop("party")
    check(dd2_session.diff(legacy, old)["growth"] == [], "an older snapshot without party data adds no growth lines")

    finish()


if __name__ == "__main__":
    main()
