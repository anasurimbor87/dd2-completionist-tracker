"""Loot placements (chests, item pickups, ...) from DD2 game data, and their state in a parsed save.

build_loot(gf, reg, extract_dir) -> list of placements with items; loot_state(save_records) -> guid -> state
Placement GUID (GenerateRowData._ManualSetGuid) == save UniqueID._RowID (raw bytes_le).
"""
import os
import re
import uuid

import ree_rsz

CATALOGS = ["natives/stm/appsystem/catalog/maincontents/userdata/gimmickcatalogdata.user.3",
            "natives/stm/appsystem/catalog/maincontents/userdata/gimmickcatalogdata_contents_0014.user.3"]
BEETLE_GIMMICK = 161  # Gm82_080: a Golden Trove Beetle (item 398), gathered once rather than picked up
# Gm83_169: a Norgan Ducat (item 711) lying in Norgan; its gimmick data names no item, so build_loot doesn't see it.
# Like a Seeker's Token it has no pick-up flag in the save: a taken one is listed in _NeverGenerateIDs.
DUCAT_GIMMICK, DUCAT_ITEM = 894, 711


def _read_cached(gf, ex, name):
    dst = os.path.join(ex, name.replace("/", os.sep))
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(gf.read(name))
    with open(dst, "rb") as f:
        return f.read()


def _collect_items(node, out):
    # parameter classes differ per gimmick; collect every {ItemId, ItemNum} pair found in them
    if isinstance(node, dict):
        if "ItemId" in node and isinstance(node["ItemId"], int) and node["ItemId"] > 0:
            out.append((node["ItemId"], node.get("ItemNum", 1)))
        for k, v in node.items():
            if k != "ItemId":
                _collect_items(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_items(v, out)


def gimmick_params(gf, reg, ex):
    """gimmick id -> {"prefab", "params": {ParamId: [(item, num)]}}"""
    prefabs = {}
    for cat in CATALOGS:
        for root in ree_rsz.parse_user(_read_cached(gf, ex, cat), reg):
            for c in root.get("GimmickCatalogDataList", []):
                if c and c.get("GimmickPrefab"):
                    prefabs[c["gimmickId"]] = c["GimmickPrefab"]["Path"]
    tables = {}

    def table(user_path):
        if user_path not in tables:
            name = "natives/stm/" + user_path.lower() + ".3"
            params = {}
            try:
                for root in ree_rsz.parse_user(_read_cached(gf, ex, name), reg):
                    for p in (root or {}).get("Params", []):
                        if p and "ParamId" in p:
                            items = []
                            _collect_items(p, items)
                            params[p["ParamId"]] = items
            except (FileNotFoundError, ValueError):
                pass
            tables[user_path] = params
        return tables[user_path]

    out = {}
    for gid, pfb in prefabs.items():
        try:
            data = gf.read("natives/stm/" + pfb.lower() + ".18")
        except FileNotFoundError:
            continue
        text = data.decode("utf-16-le", errors="ignore")
        gm = sorted(set(re.findall(r"AppSystem/Gimmick/UserData/[A-Za-z0-9_]+_GmData\.user", text, re.I)))
        params = {}
        for g in gm:
            params.update(table(g))
        out[gid] = {"prefab": pfb, "gmdata": gm, "params": params}
    return out


def build_loot(gf, reg, ex):
    gparams = gimmick_params(gf, reg, ex)
    loot = []
    for name in gf.listed("appdata/generate/manualset/"):
        if "/gimmick" not in name:
            continue
        try:
            roots = ree_rsz.parse_user(_read_cached(gf, ex, name), reg)
        except Exception:
            continue
        area = name.split("manualset/")[1]
        for root in roots:
            rows = (((root or {}).get("_Table") or {}).get("_GimmickSetInfo") or {}).get("_BasicRowDatas", [])
            for row in rows:
                if not row:
                    continue
                gid = row["_GimmickID"]
                pid = row["_Container"]["_GimmickSetting"]["_ParamId"]
                items = gparams.get(gid, {}).get("params", {}).get(pid)
                if not items:
                    continue
                loot.append({
                    "guid": row["_ManualSetGuid"],
                    "row_id": uuid.UUID(row["_ManualSetGuid"]).bytes_le.hex(),
                    "gimmick_id": gid,
                    "gimmick": os.path.basename(gparams[gid]["prefab"]).split(".")[0],
                    "param_id": pid,
                    "items": items,
                    "pos": row["_ManualPos"],
                    "file": area,
                })
    return loot


def loot_state(records):
    """row_id -> 'looted' | 'seen' from parsed save records (dict by $type)."""
    state = {}
    db = records.get("app.ContextDBMSSaveData", {}).get("DBSaveData", {}).get("Records", [])
    for r in db:
        ctx = {c["$type"]: c for c in r.get("Contexts", []) if c}
        uid = ctx.get("app.UniqueIDContext", {}).get("UniqueID", {}).get("_RowID")
        if not uid:
            continue
        picked = ctx.get("app.GmItemContext", {}).get("_IsPick")
        # a beetle's GatherContext._Num (beetles left) drops to 0 once taken; only for beetles, as herbs and ore regrow
        if ctx.get("app.GimmickContext", {}).get("_GimmickId") == BEETLE_GIMMICK:
            picked = ctx.get("app.GatherContext", {}).get("_Num") == 0
        state[uid] = "looted" if picked else state.get(uid, "seen")
    gen = records.get("app.GenerateManager.GenerateSaveData2") or records.get("app.GenerateManager.GenerateSaveData") or {}
    for u in gen.get("_NeverGenerateIDs", []):
        state[u["_RowID"]] = "looted"
    return state
