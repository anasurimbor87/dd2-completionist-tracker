"""Checks for the Golden Trove Beetles on the map (loot of kind "beetle", taken state from the save).
Run: python tests/local/test_beetles.py"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, latest_run, need, playthrough, slot_records  # noqa: E402

import dd2_loot  # noqa: E402
import dd2_mapdata  # noqa: E402

BEETLE = dd2_mapdata.BEETLE_ITEM


def load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return json.load(f)


def main():

    static = load(need("map", "data", "static.json"))
    beetles = [l for l in static["loot"] if l["c"] == "beetle"]
    check(len(beetles) == 78 and len({b["id"] for b in beetles}) == 78, f"78 beetle spots, each its own placement ({len(beetles)})")
    check(all(b["it"] == [[BEETLE, 1]] for b in beetles), "each holds one Golden Trove Beetle")
    check(not any(i == BEETLE for g in static["gather"] for i, _ in g["yields"]), "no beetle is left among the gathering spots")
    check(static["items"][str(BEETLE)]["n"] == "Golden Trove Beetle", "item 398 is the Golden Trove Beetle")

    dec = os.path.join(latest_run(), "decrypted")
    ids = {b["id"] for b in beetles}
    for path in sorted(glob.glob(os.path.join(dec, "data*Slot.json"))):
        slot = os.path.basename(path)[: -len(".json")]
        records = slot_records(dec, slot)
        state = dd2_loot.loot_state(records)
        # herbs and ore regrow: a gathering spot with nothing left must not count as looted
        db = records["app.ContextDBMSSaveData"]["DBSaveData"]["Records"]
        gen = records.get("app.GenerateManager.GenerateSaveData2") or {}
        never = {u["_RowID"] for u in gen.get("_NeverGenerateIDs", [])}
        wrong = 0
        for r in db:
            ctx = {c["$type"]: c for c in r.get("Contexts", []) if c}
            uid = ctx.get("app.UniqueIDContext", {}).get("UniqueID", {}).get("_RowID")
            gather, gm = ctx.get("app.GatherContext"), ctx.get("app.GimmickContext", {}).get("_GimmickId")
            if uid and gather and gm != dd2_loot.BEETLE_GIMMICK and gather.get("_Num") == 0:
                picked = ctx.get("app.GmItemContext", {}).get("_IsPick") or uid in never
                wrong += (state.get(uid) == "looted") != bool(picked)
        check(wrong == 0, f"{slot}: emptied herb and ore spots keep their own state ({wrong} wrong)")

    exp = playthrough("beetles")
    if exp:
        for slot, taken in exp["taken"].items():
            state = dd2_loot.loot_state(slot_records(dec, slot))
            got = sum(1 for i in ids if state.get(i) == "looted")
            check(got == taken, f"{slot}: {taken} beetles taken ({got})")
        for slot, held_n in exp["held"].items():
            inv = slot_records(dec, slot)["app.ItemManager.GameSaveData"]["ItemStorageSaves"]
            held = sum(s["_Num"] for s in inv if s["_ItemId"] == BEETLE)
            check(held == held_n, f"{slot}: {held_n} taken beetles still carried or stored, not eaten ({held})")

    finish()


if __name__ == "__main__":
    main()
