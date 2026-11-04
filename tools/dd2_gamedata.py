"""Build lookup tables (quests, items) from DD2 game files.

usage: python dd2_gamedata.py <game_dir> <assets_dir> <extract_dir> <out_dir>
"""
import glob
import json
import os
import sys

import dd2_loot
import dd2_mapdata
import dd2_phases
import ree_msg
import ree_pak
import ree_rsz

EXTRACT = [
    "appsystem/quest/userdata/questlog/", "message/questlog/",
    "message/ui/itemname", "message/ui/itemdetail", "appsystem/item/itemdata/",
]


def extract(gf, out_dir, substrings):
    for sub in substrings:
        for name in gf.listed(sub):
            dst = os.path.join(out_dir, name.replace("/", os.sep))
            if os.path.exists(dst):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(gf.read(name))


def build_quests(ex, reg):
    msgs = {}
    for path in glob.glob(os.path.join(ex, "natives/stm/message/questlog/*.msg.24")):
        msgs.update(ree_msg.english_by_guid(open(path, "rb").read()))
    quests = {}
    for path in sorted(glob.glob(os.path.join(ex, "natives/stm/appsystem/quest/userdata/questlog/*_log.user.3"))):
        for root in ree_rsz.parse_user(open(path, "rb").read(), reg):
            if not root or root.get("$type") != "app.QuestLogResource":
                continue
            qid = root["_QuestId"]
            tasks = []
            for t in root.get("_TaskList", []):
                if not isinstance(t, dict):
                    continue
                dests = [{"type": d["_DestType"], "key_location": d["_KeyLocation"], "area": d["_Area"],
                          "local_area": d["_LocalArea"], "chara": d["_CharaID"], "text": msgs.get(d.get("_MsgId"), "")}
                         for d in t.get("_Destinations", []) if d]
                tasks.append({"text": msgs.get(t.get("_BaseMsg"), ""), "detail": msgs.get(t.get("_DetailMsg"), ""),
                              "timed": t.get("_IsTimed", False), "destinations": dests})
            quests[qid] = {"title": msgs.get(root["_Title"], ""), "summary": msgs.get(root["_Summary"], ""),
                           "tasks": tasks, "timed": any(t["timed"] for t in tasks), "file": os.path.basename(path)}
    return quests


def build_items(ex, reg):
    msg_dir = os.path.join(ex, "natives/stm/message/ui")
    names, details = {}, {}
    for path in glob.glob(os.path.join(msg_dir, "itemname*.msg.24")):
        names.update(ree_msg.english_by_name(open(path, "rb").read()))
    for path in glob.glob(os.path.join(msg_dir, "itemdetail*.msg.24")):
        details.update(ree_msg.english_by_name(open(path, "rb").read()))
    items = {}
    for path in sorted(glob.glob(os.path.join(ex, "natives/stm/appsystem/item/itemdata/*.user.3"))):
        kind = os.path.basename(path).split(".")[0]
        for root in ree_rsz.parse_user(open(path, "rb").read(), reg):
            for p in (root or {}).get("_Params", []):
                if not isinstance(p, dict) or "_Id" not in p:
                    continue
                entry = items.setdefault(p["_Id"], {"id": p["_Id"]})
                entry.setdefault("sources", []).append(kind)
                entry.update({k.lstrip("_"): v for k, v in p.items() if not k.startswith("$")})
    for iid, entry in items.items():
        entry["name"] = names.get(f"item_name_{iid}", "")
        entry["detail"] = details.get(f"item_detail_{iid}", "")
    return items


def build_places(gf, reg):
    """Named local areas (towns, dungeons, landmarks) with their world rectangles from the menu map data."""
    places, _rects = dd2_mapdata._places(gf, reg)
    return places


def build_shop_items(ex, reg):
    sold = set()

    def walk(node, in_sell):
        if isinstance(node, dict):
            if in_sell and isinstance(node.get("_ItemId"), int):
                sold.add(node["_ItemId"])
            for k, v in node.items():
                walk(v, in_sell or k == "_BuyParams")  # _BuyParams = what the player can buy
        elif isinstance(node, list):
            for v in node:
                walk(v, in_sell)

    for path in glob.glob(os.path.join(ex, "natives/stm/appsystem/item/itemshopdata/*shop*data.user.3")):
        walk(ree_rsz.parse_user(open(path, "rb").read(), reg), False)
    return sold


ENHANCE_FILES = ["weaponenhancedata", "exweaponenhancedata", "armorenhancedata", "exarmorenhancedata"]
ENHANCE_STATS = ("_PhysicalAttack", "_MagicAttack", "_PhysicalDefence", "_MagicDefence", "_Weight")
# species defaults only: enemyitemdropdata holds one-off tables for specific placements (quest enemies etc.)
DROP_FILES = ["enemydefaultitemdropdata", "contents0014enemydefaultitemdropdata"]
# Dark Arisen monsters have no default table; theirs are in this other format (groups, DefaultRate per element)
EXTENDED_DROP_FILE = "natives/stm/appsystem/item/itemdropdata/contents0014enemyextendeditemdropdata.user.3"
NORMAL_DROP_TABLE = 0  # other table types (100/101, 110/111) are special drops, e.g. pickpocketing
KILL_REGION = 0  # tables of _RegionNo > 0 drop when that body part breaks (Minotaur horns: 100%)


def _roll_chances(entries, rate_key, id_key):
    """item id -> chance per roll in one table: an item listed several times counts with all its entries; item 0
    ("nothing") counts towards the total"""
    total = sum(e[rate_key] for e in entries) or 1
    out = {}
    for e in entries:
        out[e[id_key]] = out.get(e[id_key], 0) + e[rate_key] / total
    out.pop(0, None)
    return out


def _at_least_once(p, lots):
    """chance that at least one roll gives the item; lots = [(number of rolls, weight)] (the _LotList: a Hobgoblin
    rolls once in 60% of kills and not at all in 40%)"""
    total = sum(w for _n, w in lots)
    if not total:
        return p
    return sum(w / total * (1 - (1 - min(p, 1.0)) ** n) for n, w in lots)


def _percent(c):
    return max(1, round(100 * c)) if c > 0 else 0


def build_enhance(ex, reg):
    """item id -> style (app.EnhanceType) -> list of steps; stats are per-step gains."""
    out = {}
    for name in ENHANCE_FILES:
        path = os.path.join(ex, f"natives/stm/appsystem/item/itemdata/{name}.user.3")
        for p in ree_rsz.parse_user(open(path, "rb").read(), reg)[0]["_Params"]:
            mats = [[p[f"_NeedItemId{i}"], p[f"_NeedItemNum{i}"]] for i in (0, 1) if p[f"_NeedItemId{i}"] > 0]
            step = {"no": p["_EnhanceNo"], "money": p["_NeedMoney"], "mats": mats}
            step.update({k.lstrip("_"): p[k] for k in ENHANCE_STATS if p.get(k)})
            out.setdefault(str(p["_ItemId"]), {}).setdefault(str(p["_Type"]), []).append(step)
    for styles in out.values():
        for steps in styles.values():
            steps.sort(key=lambda s: s["no"])
    return out


def build_enhance_styles(gf):
    names = ree_msg.english_by_name(gf.read("natives/stm/message/ui/ui041101.msg.24"))
    # app.EnhanceType: 0 Vernworth, 1 Battahl, 2 Elf, 3 Dragon (shown as Dwarven), 4 Unlimit
    styles = {str(i): names.get(f"ui041101_TypeName{i}", "") for i in range(5)}
    styles.setdefault("1", "Battahli")
    return {k: v or {"1": "Battahli", "4": "Unlimited"}.get(k, f"Style {k}") for k, v in styles.items()}


def build_character_names(gf, enums, enums_dlc):
    """character id (unsigned, as in the data files) -> display name, for monsters and NPCs.

    The pre-DLC enum stores signed values; the post-DLC dump (REasy format, a list) unsigned ones and adds DLC characters.
    """
    ids = {}
    for k, v in enums["app.CharacterID"].items():
        if not k.lstrip("-").isdigit():
            ids[int(v) & 0xFFFFFFFF] = k
    for e in enums_dlc.get("app.CharacterID", []):
        ids.setdefault(int(e["value"]) & 0xFFFFFFFF, e["name"])
    msgs = {}
    for n in sorted(x for x in gf.names.values() if x.endswith(".msg.24") and ("enemyname" in x or "charactername" in x)):
        try:
            msgs.update(ree_msg.english_by_name(gf.read(n)))
        except FileNotFoundError:
            pass  # DLC bundles that are not installed
    out = {}
    for cid, name in ids.items():
        text = msgs.get(f"Mes_{name}") or msgs.get(f"Mes_{name.split('_')[0]}")
        if text:
            out[str(cid)] = text
    return out


def build_gather_yields(gf, reg):
    """gimmick id -> [[item id, chance % per visit], ...] from the gimmick default drop tables (gathering spots, ore,
    plants): the rolls of the _LotList applied to each table's chance per roll, best table per item."""
    out = {}
    for n in ("gimmickdefaultitemdropdata", "contents0014gimmickdefaultitemdropdata"):
        for p in ree_rsz.parse_user(gf.read(f"natives/stm/appsystem/item/itemdropdata/{n}.user.3"), reg)[0]["_Params"]:
            lots = [(l["_Num"], l["_Rate"]) for l in p.get("_LotList") or []]
            best = {}
            for table in p["_TableList"]:
                for item, per_roll in _roll_chances(table["_ItemList"], "_Rate", "_Id").items():
                    best[item] = max(best.get(item, 0), _at_least_once(per_roll, lots))
            best = {i: _percent(c) for i, c in best.items() if c > 0}
            if best:
                out.setdefault(str(p["_GimmickId"]), sorted(([i, c] for i, c in best.items()), key=lambda x: -x[1]))
    return out


SHOP_KINDS = {"app.NpcShopWeaponShopParam": "smith", "app.NpcShopDragonforgeParam": "dragonforge",
              "app.NpcShopInnParam": "inn", "app.NpcShopOxcartParam": "oxcart", "app.NpcShopItemParam": "shop"}
SHOP_FILES = ["natives/stm/appsystem/talk/resource/npcmonologue/npctalkshopdata.user.3",
              "natives/stm/appsystem/talk/resource/npcmonologue/contents0014npctalkshopuserdata.user.3"]


def build_services(gf, reg, chara_names):
    """NPC services: smiths with their smithing style (app.EnhanceType), the Dragonforged, inns, oxcarts, item shops."""
    out, seen = [], set()

    def walk(node):
        if isinstance(node, dict):
            kind = SHOP_KINDS.get(node.get("$type"))
            if kind and (kind, node["_CharaID"]) not in seen:
                seen.add((kind, node["_CharaID"]))
                out.append({"kind": kind, "chara": node["_CharaID"], "name": chara_names.get(str(node["_CharaID"]), ""),
                            "shop": node.get("_ShopID"), "style": node.get("_EnhancementType")})
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for n in SHOP_FILES:
        walk(ree_rsz.parse_user(gf.read(n), reg))
    return out


def build_drops(gf, ex, reg, chara_names):
    """Monster drops per character id (base and Dark Arisen variants of one monster can drop different things):
      enemy_drops: chara id -> {"kill": [[item, % per kill]], "parts": [[item, % when the part breaks]]}
      drops:       item id -> [[monster name, best % per kill (0 = parts only), [chara ids], % from parts,
                                lowest % per kill among the variants]]
    """
    kill, parts, dlc = {}, {}, set()  # dlc: Dark Arisen variants, labelled as such (a Norgan Hobgoblin drops other things)

    def add(target, chara, item, chance):
        d = target.setdefault(chara & 0xFFFFFFFF, {})  # some files store character ids signed
        d[item] = max(d.get(item, 0), chance)

    for name in DROP_FILES:
        path = os.path.join(ex, f"natives/stm/appsystem/item/itemdropdata/{name}.user.3")
        if not os.path.exists(path):
            continue
        for p in ree_rsz.parse_user(open(path, "rb").read(), reg)[0]["_Params"]:
            lots = [(l["_Num"], l["_Rate"]) for l in p.get("_LotList") or []]
            if name.startswith("contents0014"):
                dlc.add(p["_CharaId"] & 0xFFFFFFFF)
            for table in p["_TableList"]:
                if table["_Type"] != NORMAL_DROP_TABLE:
                    continue
                for item, per_roll in _roll_chances(table["_ItemList"], "_Rate", "_Id").items():
                    if table["_RegionNo"] == KILL_REGION:
                        add(kill, p["_CharaId"], item, _at_least_once(per_roll, lots))
                    else:
                        add(parts, p["_CharaId"], item, per_roll)
    # Dark Arisen: DefaultRate as the element's weight within its table (group rules are not modelled: approximate)
    for t in ree_rsz.parse_user(gf.read(EXTENDED_DROP_FILE), reg)[0]["TableDataList"]:
        if t["Type"] != NORMAL_DROP_TABLE or t["CharaID"] & 0xFFFFFFFF in kill:
            continue
        dlc.add(t["CharaID"] & 0xFFFFFFFF)
        lots = [(l["LotteryCount"], l["Weight"]) for l in t["LotteryCountDataList"]]
        elements = [e for e in t["TableElementList"] if not e["IsNotUse"]]
        for item, per_roll in _roll_chances(elements, "DefaultRate", "ItemID").items():
            add(kill, t["CharaID"], item, _at_least_once(per_roll, lots))

    enemy_drops, by_name = {}, {}
    for chara in set(kill) | set(parts):
        who = chara_names.get(str(chara))
        if not who:
            continue
        if chara in dlc:
            who += " (Dark Arisen)"
        k = {i: _percent(c) for i, c in kill.get(chara, {}).items() if c > 0}
        b = {i: _percent(c) for i, c in parts.get(chara, {}).items() if c > 0}
        enemy_drops[str(chara)] = {"kill": sorted(([i, c] for i, c in k.items()), key=lambda x: -x[1]),
                                   "parts": sorted(([i, c] for i, c in b.items()), key=lambda x: -x[1])}
        for item in set(k) | set(b):
            row = by_name.setdefault((item, who), [who, 0, [], 0, None])
            row[1], row[3] = max(row[1], k.get(item, 0)), max(row[3], b.get(item, 0))
            if item in k:  # variants of one monster differ (a Hobgoblin rolls in 60% or in all kills)
                row[4] = k[item] if row[4] is None else min(row[4], k[item])
            row[2].append(str(chara))
    drops = {}
    for (item, _who), row in by_name.items():
        drops.setdefault(str(item), []).append(row)
    for rows in drops.values():
        rows.sort(key=lambda r: (-r[1], -r[3]))
    return drops, enemy_drops


JOB_MENU = "natives/stm/appsystem/gui/jobmenu/"
JOB_RANKS = "natives/stm/appsystem/ch/common/human/userdata/parameter/jobrankparameter.user.3"
# app.PersonalityDefine.PersonalityID name -> number of its text in personality.msg
PERSONALITY_TEXT = {"Kind": "00", "Cool": "01", "Simple": "02", "Frank": "03"}


def build_vocations(gf, reg, enums_dlc):
    """Vocations (rank steps), weapon skills per level and augments with name, text, Discipline cost and unlock rank;
    pawn specializations and personalities; pawn quest knowledge bits -> quest id."""
    msg = {}
    for n in gf.listed("message/ui/job"):  # job.msg (vocation names), jobNNact(_tu_end).msg (skills and augments)
        if n.endswith(".msg.24"):
            msg.update(ree_msg.english_by_guid(gf.read(n)))
    text = lambda g: msg.get(g, "").replace("\r\n", " ")
    ranks = {p["Job"]: p["RequiredNextPoints"] for p in ree_rsz.parse_user(gf.read(JOB_RANKS), reg)[0]["JobParams"]}
    jobs = {}
    for j in ree_rsz.parse_user(gf.read(JOB_MENU + "jobinformationdata.user.3"), reg)[0]["_Params"]:
        jobs[str(j["_JobID"])] = {"n": text(j["_JobNameText"]), "pawn": j["_EnablePawn"], "ranks": ranks.get(j["_JobID"], [])}
    skills = {}
    for s in ree_rsz.parse_user(gf.read(JOB_MENU + "customskillinformationdata.user.3"), reg)[0]["_Params"]:
        for p in s["_Params"]:
            sk = skills.setdefault(str(p["_SkillID"]), {"jobs": [], "levels": []})
            if s["_Job"] not in sk["jobs"]:
                sk["jobs"].append(s["_Job"])
            if all(x["lv"] != p["_Level"] for x in sk["levels"]):
                sk["levels"].append({"lv": p["_Level"], "n": text(p["_SkillName"]), "t": text(p["_SkillText"]),
                                     "cost": p["_Cost"], "rank": p["_UnlockRank"]})
    for sk in skills.values():
        sk["levels"].sort(key=lambda x: x["lv"])
    augments = {}
    for s in ree_rsz.parse_user(gf.read(JOB_MENU + "abilityinformationdata.user.3"), reg)[0]["_Params"]:
        for a in s["_Params"]:
            augments[str(a["_AbilityID"])] = {"job": s["_Job"], "n": text(a["_AbilityName"]), "t": text(a["_InfoText"]),
                                              "cost": a["_Cost"], "rank": a["_UnlockRank"]}
    enum = lambda name: {e["name"]: e["value"] for e in enums_dlc.get(name, [])}
    sub = ree_msg.english_by_name(gf.read("natives/stm/message/ui/subskill.msg.24"))
    # app.PawnDefine.SubSkillID n (0 = none) is the text Subskill_<n-1>_00
    specializations = {str(v): sub[f"Subskill_{v - 1:02}_00"] for v in enum("app.PawnDefine.SubSkillID").values()
                       if v and f"Subskill_{v - 1:02}_00" in sub}
    per = ree_msg.english_by_name(gf.read("natives/stm/message/ui/personality.msg.24"))
    personalities = {str(v): per[f"Personality_{PERSONALITY_TEXT[k]}"]
                     for k, v in enum("app.PersonalityDefine.PersonalityID").items() if k in PERSONALITY_TEXT}
    knowledge = {}
    for cat in ("1", "2", "3"):
        for name, value in enum(f"app.PawnKnowledge.QuestKnowledge.Category0{cat}").items():
            if value and name.startswith("qu"):
                knowledge.setdefault(cat, {})[str(value.bit_length() - 1)] = str(int(name[2:]))
    return {"jobs": jobs, "skills": skills, "augments": augments, "specializations": specializations,
            "personalities": personalities, "knowledge": knowledge}


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    build(*sys.argv[1:])


def build(game_dir, assets, ex, out):
    """every game table into out/<name>.json; ex caches the files extracted from the game's PAKs"""
    gf = ree_pak.GameFiles(game_dir, os.path.join(assets, "lists"))
    extract(gf, ex, EXTRACT + ["appsystem/item/itemshopdata/", "appsystem/item/itemdropdata/"])
    reg = ree_rsz.Registry(os.path.join(assets, "rszdd2_dlc.json"))
    with open(os.path.join(assets, "enumsdd2.json"), encoding="utf-8") as f:
        enums = json.load(f)
    with open(os.path.join(assets, "enumsdd2_dlc.json"), encoding="utf-8") as f:
        enums_dlc = json.load(f)
    os.makedirs(out, exist_ok=True)
    chara_names = build_character_names(gf, enums, enums_dlc)
    drops, enemy_drops = build_drops(gf, ex, reg, chara_names)
    quests = build_quests(ex, reg)
    tables = {
        "quests": {str(k): v for k, v in sorted(quests.items())},
        "quest_tree": dd2_phases.build_tree(gf, reg, {q for q, v in quests.items() if v["title"]}),
        "items": {str(k): v for k, v in sorted(build_items(ex, reg).items())},
        "places": build_places(gf, reg),
        "shop_items": sorted(build_shop_items(ex, reg)),
        "loot": dd2_loot.build_loot(gf, reg, ex),
        "enhance": build_enhance(ex, reg),
        "enhance_styles": build_enhance_styles(gf),
        "drops": drops,
        "enemy_drops": enemy_drops,
        "chara_names": chara_names,
        "gather_yields": build_gather_yields(gf, reg),
        "services": build_services(gf, reg, chara_names),
        "vocations": build_vocations(gf, reg, enums_dlc),
    }
    for name, table in tables.items():
        with open(os.path.join(out, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(table, f, ensure_ascii=False, indent=1)
        print(f"{name}: {len(table)} entries")


if __name__ == "__main__":
    main()
