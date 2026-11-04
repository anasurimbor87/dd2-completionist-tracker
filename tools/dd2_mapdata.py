"""Data for the save map: static.json (game data, built once) and live state (from the current save)."""
import collections
import json
import os
import re
import struct
import uuid

import dd2_achievements
import dd2_loot
import dd2_map
import dd2_parse
import dd2_party
import dd2_phases
import ree_msg
import ree_rsz

KEY_LOCATIONS = ["natives/stm/appsystem/quest/userdata/questuniquekeylocationdata.user.3",
                 "natives/stm/appsystem/ch/ch100/userdata/uniquekeylocationdata.user.3"]
AREA_NAME_FILES = ["displocalareanamedata", "contents0014displocalareanamedata"]
AREA_MSGS = ["aiareaname", "aiareaname_end", "ailocalareaname", "ailocalareaname_end"]
SEEKERS_TOKEN = 167  # gimmick id of Gm82_036
BEETLE_ITEM = 398  # Golden Trove Beetle: eating one adds 0.15 kg of carry weight (gimmick dd2_loot.BEETLE_GIMMICK)
DEST_CHARACTER = 2  # app.QuestLogResource.DestinationType: Area 0, LocalArea 1, Character 2, Free 3
NO_CHARA = 260732951  # the first app.CharacterID (ch300000): the default of a destination's _CharaID
# the game map's icons: fixed ones, and ones that appear once found (campsites, the small Riftstones)
MAP_ICONS = {"natives/stm/appsystem/gui/userdata/mapicondata.user.3": False,
             "natives/stm/appsystem/gui/userdata/autocollectmapicondata.user.3": True,
             "natives/stm/appsystem/gui/userdata/contents0014mapicondata.user.3": False,  # Dark Arisen (Norgan)
             "natives/stm/appsystem/gui/userdata/contents0014autocollectmapicondata.user.3": True}
ICON_MSGS = AREA_MSGS + ["ui0414_00"]
# app.MapIconType values (unnamed in the dumps); entrance icons' _MapArea is the dungeon's UI area
ICON_RIFTSTONE, ICON_CAMP, ICON_ENTRANCE = 8, 23, 32
TOWN_ICONS = {67: 250, 68: 150, 69: 120}  # cities, villages, outposts -> radius (world units) of their place


def _category(gimmick):
    if gimmick.startswith("gm80"):
        return "chest"
    if gimmick.startswith("gm82"):
        return "item"
    if gimmick.startswith("gm83"):
        return "dlc"
    return "other"


# "gatehr" is the game's own spelling of some folders; only rows whose gimmick has a yield table are kept
GATHER_FOLDERS = ("/gather/", "/gatehr/", "/ore/", "/lherb/", "/flower/", "/berry/", "/plant/", "/herbs/", "/potato/",
                  "/herb/")
# the campfire gimmicks under the (base game) campsite icons, one per icon; their _ParamId is the fire type
# (app.CampSaveData.LastSleepFireType). 476 sits under the two Battahl icons 198/199/475 leave out.
CAMP_FIRES = (198, 199, 475, 476)
SPAWN_CLUSTER = 60.0  # world units: placements of one species closer than this become one spawn spot


def _manualset_rows(gf, ex, reg):
    npc, medals, gather, enemies, fires, beetles = {}, [], [], [], [], []
    for name in gf.listed("appdata/generate/manualset/"):
        try:
            roots = ree_rsz.parse_user(dd2_loot._read_cached(gf, ex, name), reg)
        except Exception:
            continue
        path = name.split("manualset/")[1]
        for root in roots:
            t = (root or {}).get("_Table") or {}
            for r in (t.get("_NpcSetInfo") or {}).get("_BasicRowDatas", []):
                if r:
                    npc.setdefault(r["_CharaID"], r["_ManualPos"])
            for row, r in enumerate((t.get("_GimmickSetInfo") or {}).get("_BasicRowDatas", [])):
                if not r:
                    continue
                x, y, z = r["_ManualPos"]
                if r["_GimmickID"] in CAMP_FIRES:
                    fires.append({"file": path, "row": row, "x": x, "z": z,
                                  "fire": r["_Container"]["_GimmickSetting"]["_ParamId"]})
                if r["_GimmickID"] == SEEKERS_TOKEN:
                    medals.append({"id": uuid.UUID(r["_ManualSetGuid"]).bytes_le.hex(), "x": x, "y": y, "z": z, "file": path})
                elif r["_GimmickID"] == dd2_loot.BEETLE_GIMMICK:  # in gather folders and item folders alike; one-time
                    beetles.append({"id": uuid.UUID(r["_ManualSetGuid"]).bytes_le.hex(), "x": x, "y": y, "z": z, "file": path})
                elif any(k in name for k in GATHER_FOLDERS):
                    gather.append({"g": r["_GimmickID"], "x": x, "y": y, "z": z, "file": path})
            for r in (t.get("_EnemySetInfo") or {}).get("_BasicRowDatas", []):
                if r:
                    x, y, z = r["_ManualPos"]
                    enemies.append({"chara": r["_CharaID"], "x": x, "y": y, "z": z, "file": path})
    return npc, medals, gather, enemies, fires, beetles


def _camp_order(fires):
    """campfires in the order the save numbers campsites (app.CampSaveData.DiscoverBits, LastSleepIndex).

    Not documented anywhere; it is the order that fits both save files on disk: by the area number in the path
    (dng_06, ..., editfield_40, ..., editfield_166), then path, then row. With it, the last sleep spot of the
    current save is a fire of the recorded type 1000, and every found campsite of both playthroughs lies within
    60 m of loot the player has passed."""
    def area_number(f):
        m = re.search(r"_(\d+)/", f["file"])
        return int(m.group(1)) if m else 9999
    return sorted(fires, key=lambda f: (area_number(f), f["file"], f["row"]))


def map_icons(gf, reg):
    """The game map's icons (Riftstones, campsites, towns, dungeon entrances, shops...) with English names."""
    msg = {}
    for f in ICON_MSGS:
        msg.update(ree_msg.english_by_guid(gf.read(f"natives/stm/message/ui/{f}.msg.24")))
    out = []
    for path, found in MAP_ICONS.items():
        for p in ree_rsz.parse_user(gf.read(path), reg)[0]["_Params"]:
            if p["_IsDisable"]:
                continue
            x, y, z = p["_Pos"]
            out.append({"type": p["_IconType"], "name": msg.get(p["_DispNameId"], ""), "x": x, "y": y, "z": z,
                        "area": p["_MapArea"], "main": p["_IsMainEntrance"], "found": found})
    return out


ORE_WORDS = re.compile(r"Ore\b|Stone\b|Crystal|Quartz|Jasper|Sapphire|Ruby|Emerald|Diamond|Opal|Amethyst|Agate|Gem")
REMAINS_WORDS = re.compile(r"Bone|Fang|Horn|Hide|Pelt|Scale|Claw|Feather|Sinew|Talon|Tusk|Skull")


def _gather_kind(yields, items):
    """the icon of a gathering spot: ore (ores, gems), remains (bones, horns, hides) or herb (everything else)"""
    names = [items.get(str(i), {}).get("name", "") for i, _ in yields]
    if any(ORE_WORDS.search(n) for n in names):
        return "ore"
    if any(REMAINS_WORDS.search(n) for n in names):
        return "remains"
    return "herb"


def _cluster_spawns(rows, names):
    """merge placements of one species (and one dungeon floor) that lie within SPAWN_CLUSTER of each other"""
    cells, spots = {}, []
    for r in rows:
        name = names.get(str(r["chara"]), "Unknown monster")
        key = (name, tuple(r["d"]) if r.get("d") else None)
        cx, cz = int(r["x"] // SPAWN_CLUSTER), int(r["z"] // SPAWN_CLUSTER)
        spot = None
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for s in cells.get((key, cx + dx, cz + dz), []):
                    if (s["x"] - r["x"]) ** 2 + (s["z"] - r["z"]) ** 2 <= SPAWN_CLUSTER ** 2:
                        spot = s
                        break
                if spot:
                    break
            if spot:
                break
        if spot is None:
            spot = {"n": name, "x": r["x"], "y": r["y"], "z": r["z"], "count": 0, "ch": set()}
            if r.get("d"):
                spot["d"] = r["d"]
            cells.setdefault((key, cx, cz), []).append(spot)
            spots.append(spot)
        spot["count"] += 1
        spot["ch"].add(str(r["chara"] & 0xFFFFFFFF))  # character ids: variants of one monster drop different things
    for spot in spots:
        spot["ch"] = sorted(spot["ch"])
    return spots


def area_names(gf, reg):
    """local area id -> display name"""
    msg = {}
    for f in AREA_MSGS:
        msg.update(ree_msg.english_by_guid(gf.read(f"natives/stm/message/ui/{f}.msg.24")))
    names = {}
    for f in AREA_NAME_FILES:
        root = ree_rsz.parse_user(gf.read(f"natives/stm/appsystem/gui/userdata/{f}.user.3"), reg)[0]
        for p in next(v for v in root.values() if isinstance(v, list)):
            if msg.get(p["MsgId"]):
                names[p["AreaId"]] = msg[p["MsgId"]]
    return names


def _places(gf, reg):
    names = area_names(gf, reg)
    places, rects, seen = [], {}, set()
    for params in dd2_map.map_params(gf, reg):
        for p in params:
            if p["LocalArea"] < 0:
                continue
            rect = (p["BasePosX"], p["BasePosZ"], p["DispRangeX"], p["DispRangeZ"])
            rects[p["LocalArea"]] = rect
            name = names.get(p["LocalArea"])
            if name and (name, rect) not in seen:
                seen.add((name, rect))
                places.append({"name": name, "x": rect[0], "z": rect[1], "w": rect[2], "h": rect[3],
                               "dungeon": p["IsDungeon"]})
    return places, rects


def place_of(x, z, places, surface=True):
    """Name of the smallest area around the position, else "near <nearest area>" within 500 m. A surface spot is never
    *in* a dungeon area (those lie beneath it, and are smaller than towns), but can be near one."""
    around = [p for p in places if not (surface and p.get("dungeon"))]
    inside = [p for p in around if p["x"] <= x <= p["x"] + p["w"] and p["z"] <= z <= p["z"] + p["h"]]
    if inside:
        return min(inside, key=lambda p: p["w"] * p["h"])["name"]
    near = min(places, key=lambda p: (p["x"] + p["w"] / 2 - x) ** 2 + (p["z"] + p["h"] / 2 - z) ** 2, default=None)
    if near and ((near["x"] + near["w"] / 2 - x) ** 2 + (near["z"] + near["h"] / 2 - z) ** 2) ** 0.5 < 500:
        return "near " + near["name"]
    return ""


UNDERGROUND_FILES = ("content/dng", "content/rdl", "content/nrd", "content/spot")
PROVING_GROUNDS = 6000  # UI areas 6000+nn: the Dark Arisen proving grounds, placements in content/rdl_0nn


def _end_names(gf):
    """Dark Arisen proving grounds: AI area messages Situation_END_0nn -> name; END_0nn is the dungeon rdl_0nn (UI area 6000+nn)"""
    out = {}
    for f in AREA_MSGS:
        for e in ree_msg.read_msg(gf.read(f"natives/stm/message/ui/{f}.msg.24")):
            m = re.match(r"Situation_END_0*(\d+)_\d+$", e["name"])
            text = e["text"][ree_msg.ENGLISH]
            if m and text and "#Rejected#" not in text:
                out.setdefault(6000 + int(m.group(1)), text)
    return out


def _entrances_by_area(icons):
    """dungeon UI area -> entrance icons, main entrance first, duplicates (same spot) dropped"""
    out = {}
    for i in sorted((i for i in icons if i["type"] == ICON_ENTRANCE), key=lambda i: not i["main"]):
        ents = out.setdefault(i["area"], [])
        if all((e["x"] - i["x"]) ** 2 + (e["z"] - i["z"]) ** 2 > 25 for e in ents):
            ents.append(i)
    return out


def build_dungeons(gf, reg, floors, places, kl_entrances, icon_entrances, entry_lists, field, content, map_dir):
    from PIL import Image

    end_names = _end_names(gf)
    groups = {}
    for f in floors:
        groups.setdefault(f["ui"], {"key": f["ui"], "floors": []})["floors"].append(f)
    for g in groups.values():
        g["floors"].sort(key=lambda f: -f["floor"])  # top floor first
        x0 = min(f["x0"] for f in g["floors"]); x1 = max(f["x1"] for f in g["floors"])
        z0 = min(f["z0"] for f in g["floors"]); z1 = max(f["z1"] for f in g["floors"])
        g["rect"] = (x0, z0, x1, z1)
        g["cx"], g["cz"] = (x0 + x1) / 2, (z0 + z1) / 2
        icons = icon_entrances.get(g["key"], [])
        name = (next((f["name"] for f in g["floors"] if f["name"]), "") or end_names.get(g["key"], "")
                or next((i["name"] for i in icons if i["name"]), ""))
        if not name:
            near = place_of(g["cx"], g["cz"], places, surface=False)
            name = ("Cave " + near) if near.startswith("near ") else (near or "Unnamed cave")
        g["name"] = name
        if icons:  # the game map's own entrance icons
            g["entrances"], g["entrance_known"] = [[i["x"], i["z"]] for i in icons], True
        else:
            ent = [k for k in kl_entrances if x0 <= k[0] <= x1 and z0 <= k[2] <= z1]
            g["entrances"] = [[ent[0][0], ent[0][2]] if ent else [g["cx"], g["cz"]]]
            g["entrance_known"] = bool(ent)
        g["entrance"] = g["entrances"][0]
        for f in g["floors"]:
            f["w_world"], f["h_world"] = f["x1"] - f["x0"], f["z1"] - f["z0"]

    masks = {}

    def opaque(f, x, z):
        if f["img"] not in masks:
            # fully opaque crops are stored without alpha
            masks[f["img"]] = Image.open(os.path.join(map_dir, f["img"])).convert("RGBA").getchannel("A")
        m = masks[f["img"]]
        px = int((x - f["x0"]) / f["w_world"] * m.width)
        pz = int((z - f["z0"]) / f["h_world"] * m.height)
        return 0 <= px < m.width and 0 <= pz < m.height and m.getpixel((px, pz)) > 40

    # 1) which dungeon floors a placement could be on (opaque on the floor map, from a dungeon-type file)
    candidates = []
    for entry, path in [(e, e.get("file", "")) for entries in entry_lists for e in entries]:
        if not (path.startswith(UNDERGROUND_FILES) or "/dungeon" in path):
            continue
        x, z = entry["x"], entry["z"]
        # Dark Arisen proving grounds overlap other dungeons on the map: rdl_0nn placements belong to UI area 6000+nn
        # and nothing else does
        m = re.match(r"content/rdl_0*(\d+)/", path)
        proving = PROVING_GROUNDS + int(m.group(1)) if m else None
        hits = [(g, f) for g in groups.values() for f in g["floors"]
                if (g["key"] == proving if proving else g["key"] < PROVING_GROUNDS or g["key"] >= PROVING_GROUNDS + 1000)
                and f["x0"] <= x <= f["x1"] and f["z0"] <= z <= f["z1"] and opaque(f, x, z)]
        if hits:
            g = min({id(g): g for g, _ in hits}.values(), key=lambda g: (g["rect"][2] - g["rect"][0]) * (g["rect"][3] - g["rect"][1]))
            candidates.append((entry, g, [f for gg, f in hits if gg is g]))
    # 2) overlapping floors: split by height; floor order (FloorNo) follows the height order of its placements
    by_group = {}
    for entry, g, fs in candidates:
        by_group.setdefault(g["key"], []).append((entry, g, fs))
    for items in by_group.values():
        single = {}
        for entry, g, fs in items:
            if len(fs) == 1:
                single.setdefault(fs[0]["floor"], []).append(entry["y"])
        med = {fl: sorted(ys)[len(ys) // 2] for fl, ys in single.items()}
        for entry, g, fs in items:
            if len(fs) == 1:
                f = fs[0]
            else:
                known = [f for f in fs if f["floor"] in med]
                f = min(known, key=lambda f: abs(med[f["floor"]] - entry["y"])) if known else max(fs, key=lambda f: f["floor"])
            entry["d"] = [g["key"], g["floors"].index(f)]

    dd2_map.layout_insets(list(groups.values()), field, content)
    out = []
    for g in groups.values():
        out.append({"ui": g["key"], "name": g["name"], "entrance": g["entrance"], "entrances": g["entrances"],
                    "entrance_known": g["entrance_known"],
                    "floors": [{"label": f["label"], "img": f["img"], "bounds": f["bounds"],
                                "x0": f["x0"], "z0": f["z0"], "x1": f["x1"], "z1": f["z1"]} for f in g["floors"]]})
    return out


def build_static(gf, reg, gd_dir, ex, floors=None, map_dir=None):
    def j(name):
        with open(os.path.join(gd_dir, name + ".json"), encoding="utf-8") as f:
            return json.load(f)
    quests, items, loot, shop = j("quests"), j("items"), j("loot"), set(j("shop_items"))
    field, _tiles = dd2_map.field_tiles(gf, reg)
    places, rects = _places(gf, reg)
    icons = map_icons(gf, reg)
    named = {p["name"] for p in places}
    for i in icons:  # towns and villages have no area rectangle of their own: a square around their map icon
        r = TOWN_ICONS.get(i["type"])
        if r and i["name"] and i["name"] not in named:
            named.add(i["name"])
            places.append({"name": i["name"], "x": i["x"] - r, "z": i["z"] - r, "w": 2 * r, "h": 2 * r,
                           "dungeon": False, "town": True})
    npc, medals, gather_rows, enemy_rows, fires, beetles = _manualset_rows(gf, ex, reg)
    chara_names, yields, enemy_drops = j("chara_names"), j("gather_yields"), j("enemy_drops")
    gather = [dict(g, yields=yields[str(g["g"])], k=_gather_kind(yields[str(g["g"])], items))
              for g in gather_rows if str(g["g"]) in yields]
    kl, entrances = {}, []
    for n in KEY_LOCATIONS:
        for u in ree_rsz.parse_user(gf.read(n), reg)[0]["_UniqueKeyLocations"]:
            kl[u["_KeyLocationID"]] = u["_Position"]
            if u["_IsGuidanceDNG"]:
                entrances.append(u["_Position"])

    seen_rows = set()  # a few placements are listed twice (normal and quest variant of one file)
    loot = [l for l in loot if not (l["row_id"] in seen_rows or seen_rows.add(l["row_id"]))]
    # unique: gear lying at no more than two spots (variant rows of one spot count once), not sold, not dropped
    spots = collections.defaultdict(set)
    for l in loot:
        for i, _ in l["items"]:
            spots[i].add((round(l["pos"][0]), round(l["pos"][2])))
    dropped = {int(k) for k in j("drops")}
    # every item that can lie in the world, plus all gear (unique gear, chests holding gear)
    used = {i for l in loot for i, _ in l["items"]} | {int(k) for k, v in items.items() if "EquipCategory" in v}
    used |= {i for g in gather for i, _ in g["yields"]}
    used |= {i for ds in enemy_drops.values() for i, _ in ds["kill"] + ds["parts"]}
    used |= {int(k) for k, v in items.items() if v.get("name")}  # anything that can show up in the save log
    out_items = {}
    for i in used:
        it = items.get(str(i), {})
        gear = "EquipCategory" in it
        out_items[i] = {
            "n": it.get("name") or f"Unidentified spoils #{i}",
            "gear": gear, "slot": it.get("EquipCategory"), "lv": it.get("Lv"),
            "atk": it.get("PhysicalAttack", 0) + it.get("MagicAttack", 0),
            "def": it.get("PhysicalDefence", 0) + it.get("MagicDefence", 0),
            "wt": it.get("Weight"),
            "dlc": any(s.startswith("ex") for s in it.get("sources", [])),
            "unique": gear and i not in shop and i not in dropped and len(spots[i]) <= 2,
            "gold": it.get("name") == "1 G",
        }
    out_loot = []
    for l in loot:
        x, y, z = l["pos"]
        out_loot.append({"id": l["row_id"], "c": _category(l["gimmick"]), "g": l["gimmick"], "x": x, "y": y, "z": z,
                         "it": l["items"], "p": place_of(x, z, places), "file": l["file"]})
    for b in beetles:  # loot of their own kind: looted state, rings, Hide looted, Nearby and Find all apply
        out_loot.append(dict(b, c="beetle", g="gm82_080", it=[[BEETLE_ITEM, 1]], p=place_of(b["x"], b["z"], places)))
    for m in medals:
        m["p"] = place_of(m["x"], m["z"], places)

    def resolve(d):
        if d["key_location"] in kl:
            return kl[d["key_location"]]
        if d["local_area"] in rects:
            r = rects[d["local_area"]]
            return [r[0] + r[2] / 2, 0, r[1] + r[3] / 2]
        # only "Character" destinations name a character; the others carry the field's default (the first
        # character id, one NPC in Vernworth Castle), which once put 38% of all objectives on that spot
        if d["type"] == DEST_CHARACTER and d["chara"] != NO_CHARA and d["chara"] in npc:
            return npc[d["chara"]]
        return None  # base-game key locations (ids below 3456) are not in the readable data

    tree = j("quest_tree")
    out_quests = {}
    for qid, q in quests.items():
        tasks = []
        for t in q["tasks"]:
            dests = []
            for d in t["destinations"]:
                pos = resolve(d)
                if pos:
                    dests.append([pos[0], pos[2], d["text"]])
            tasks.append({"t": t["text"], "timed": t["timed"], "d": dests})
        out_quests[qid] = {"t": q["title"], "s": q["summary"], "timed": q["timed"], "tasks": tasks}
        node = tree["quests"].get(qid)
        if node:  # when it opens, what closes it, its place in the story (dd2_phases)
            out_quests[qid].update(opens=node["opens"], ends=node["ends"], o=node["o"])
    # the Materials tab lists everything smiths use, with where to find it
    enhance = j("enhance")
    materials = {m for styles in enhance.values() for steps in styles.values() for s in steps for m, _ in s["mats"]}
    for m in materials - set(out_items):
        it = items.get(str(m), {})
        out_items[m] = {"n": it.get("name") or f"Item #{m}", "gear": False}
    for m in materials:
        out_items[m]["sold"] = m in shop
    dungeons = []
    if floors:
        cols = {int(i) % dd2_map.GRID for i in _tiles}
        rows = {int(i) // dd2_map.GRID for i in _tiles}
        cell = 256 / dd2_map.GRID
        content = (min(cols) * cell, -min(rows) * cell, (max(cols) + 1) * cell, -(max(rows) + 1) * cell)
        dungeons = build_dungeons(gf, reg, floors, places, entrances, _entrances_by_area(icons),
                                  [out_loot, medals, gather, enemy_rows], field, content, map_dir)
    spawns = _cluster_spawns(enemy_rows, chara_names)
    by_ui = {d["ui"]: d for d in dungeons}
    for e in out_loot + medals + gather + spawns:
        e.pop("file", None)
        e.pop("chara", None)
        if e.get("d"):  # the dungeon's place name is better than a nearby surface name
            d = by_ui[e["d"][0]]
            e["p"] = f"{d['name']}, {d['floors'][e['d'][1]]['label']}"
        elif "p" not in e:
            e["p"] = place_of(e["x"], e["z"], places)

    services = []
    for s in j("services"):
        pos = npc.get(s["chara"])
        if pos:  # NPC position from its placement row; NPCs on schedules may also be elsewhere
            services.append({"kind": s["kind"], "name": s["name"], "style": s["style"], "x": pos[0], "z": pos[2],
                             "place": place_of(pos[0], pos[2], places)})
    # campsites (with their number in the save, from the campfire under the icon) and Riftstones
    rest = [{"k": "camp", "n": "Campsite", "x": i["x"], "z": i["z"]} for i in icons if i["type"] == ICON_CAMP]
    for number, f in enumerate(_camp_order(fires)):
        camp = min((r for r in rest if r["k"] == "camp"), key=lambda r: (r["x"] - f["x"]) ** 2 + (r["z"] - f["z"]) ** 2)
        if (camp["x"] - f["x"]) ** 2 + (camp["z"] - f["z"]) ** 2 < 15 ** 2:
            camp.update(i=number, fire=f["fire"])
    rest += [{"k": "rift", "n": i["name"] or "Riftstone", "x": i["x"], "z": i["z"]} for i in icons if i["type"] == ICON_RIFTSTONE]
    for r in rest:
        r["p"] = place_of(r["x"], r["z"], places)
    return {"field": field, "places": places, "items": out_items, "loot": out_loot, "medals": medals,
            "quests": out_quests, "materials": sorted(materials), "styles": j("enhance_styles"), "drops": j("drops"),
            "dungeons": dungeons, "gather": gather, "spawns": spawns, "enemy_drops": enemy_drops,
            "services": services, "rest": rest, "vocations": j("vocations"), "phases": tree["phases"]}


def _position(raw_hex):
    if isinstance(raw_hex, str) and len(raw_hex) >= 48:
        return list(struct.unpack("<3d", bytes.fromhex(raw_hex[:48])))
    return None


# records the live state is built from: if one of them parses only partly, the state would show wrong loot,
# gear or quests without any sign of it, so the state is refused instead
STATE_RECORDS = ("app.GameSystem.GameSaveData", "app.ItemManager.GameSaveData", "app.ContextDBMSSaveData",
                 "app.GenerateManager.GenerateSaveData2", "app.GenerateManager.GenerateSaveData",
                 "app.TimeManager.TimeSaveData", "app.CampSaveData")
REQUIRED_RECORDS = ("app.GameSystem.GameSaveData", "app.ItemManager.GameSaveData", "app.ContextDBMSSaveData")


def check_records(records, quest_json):
    """Raise ValueError if the save could not be read well enough to build a trustworthy state."""
    missing = [t for t in REQUIRED_RECORDS if t not in records]
    broken = [t for t in STATE_RECORDS if t in records and dd2_parse._has_error(records[t])]
    if missing or broken:
        raise ValueError(f"save records not readable: {', '.join(missing + broken)}")
    log_rec = next((r for t, r in records.items() if (t or "").startswith("app.QuestLogManager.SaveData")), None)
    in_save = len(log_rec.get("RecordList") or []) if log_rec else None
    if in_save is not None and in_save != len(quest_json.get("log", [])):
        raise ValueError(f"quest log: {in_save} entries in the save, {len(quest_json.get('log', []))} read")


PLAYER = 2891076981  # app.CharacterID ch000000_00 (unsigned)
MAIN_PAWN = 2283028347  # ch100000_00
STORAGE = 65535


def _owner(chara):
    return {PLAYER: "you", MAIN_PAWN: "main pawn", STORAGE: "storage"}.get(chara, "pawn")


def inventory_of(storages):
    """item id (str) -> owner -> count, for you, your main pawn, the storage and other pawns"""
    inv = {}
    for s in storages:
        if not s["_ItemId"]:
            continue
        bucket = inv.setdefault(str(s["_ItemId"]), {})
        who = _owner(s["_CharaId"])
        bucket[who] = bucket.get(who, 0) + s["_Num"]
    return inv


def compute_state(records, quest_json, saved_at, slot_name, vocations=None, quest_tree=None):
    """vocations: gamedata/vocations.json, for the party (you and your pawns); quest_tree: gamedata/quest_tree.json,
    for the quests the story has closed; each is left out without its table"""
    game = records.get("app.GameSystem.GameSaveData", {})
    time_rec = records.get("app.TimeManager.TimeSaveData", {})
    item_rec = records.get("app.ItemManager.GameSaveData", {})
    storages = item_rec.get("ItemStorageSaves", [])
    state = {
        "inventory": inventory_of(storages),
        "saved": saved_at,
        "slot": slot_name,
        "day": (time_rec.get("Inside") or {}).get("InGameDay"),
        "elapsed": time_rec.get("InGameElapsedSeconds"),  # rises within a playthrough: tells earlier saves from later
        "gold": (item_rec.get("MoneySave") or {}).get("_Gold"),
        "rift": (item_rec.get("MoneySave") or {}).get("_Rim"),
        "player": _position(game.get("StartPosition")),
        "loot": dd2_loot.loot_state(records),
        "quests": {str(l["QuestId"]): {"status": l["StatusName"], "task": l["CurrentTaskIndex"]}
                   for l in quest_json.get("log", [])},
        "owned": sorted({s["_ItemId"] for s in storages if s["_ItemId"]}),
    }
    camp = records.get("app.CampSaveData", {})
    words = camp.get("DiscoverBits") or []  # 64-bit words, bit n = campsite number n (see _camp_order)
    state["camps_found"] = [64 * w + b for w, word in enumerate(words) for b in range(64) if word >> b & 1]
    state["camp_last"] = camp.get("LastSleepIndex")
    state["records"] = dd2_achievements.records(records)  # achievement progress and unlocks in this save
    if vocations:
        state["party"] = dd2_party.party(records, vocations)
    contexts = quest_json.get("contexts") or []
    if contexts:  # without them every quest would look not ended: the story phase would read as the first one
        results = {c["ID"]: c["ResultNo"] for c in contexts}
        state["results"] = {str(q): r for q, r in results.items() if r >= 0}
        if quest_tree:
            state["closed"] = dd2_phases.closed(quest_tree, results, {q: v["status"] for q, v in state["quests"].items()})
    return state
