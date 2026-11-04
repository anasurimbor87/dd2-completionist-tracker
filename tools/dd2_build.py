"""Builds what the map needs from the installed game into a data folder: the game tables (gamedata/), the map tiles,
the dungeon maps and the map data (map/data/static.json). The first start and the rebuild after a game update run
build_all; `dd2.py gamedata` and `dd2.py map` run the parts on their own and reuse tiles and dungeon maps already
built. Reads the game read-only; writes only inside the data folder."""
import datetime
import json
import os
import shutil

import dd2_gamedata
import dd2_map
import dd2_mapdata
import ree_pak
import ree_rsz

STEPS = ["Reading game files", "Items and quests", "Map tiles", "Dungeon maps", "Map data"]
# the shape of the built data; raise it whenever a change to the tools changes what the build writes, so every copy
# built by an older tracker is built again on its next start (1: the first public version)
DATA_FORMAT = 1


def _meta_path(data_dir):
    return os.path.join(data_dir, "gamedata", "meta.json")


def _static_path(data_dir):
    return os.path.join(data_dir, "map", "data", "static.json")


def _write_json(path, obj, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".new", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, **kw)
    os.replace(path + ".new", path)


def _clear(path):
    """remove a file or folder this build will make again; never one that links elsewhere (its target is not ours)"""
    if os.path.islink(path) or os.path.isjunction(path):
        raise RuntimeError(f"refusing to clear {path}: it is a link to another folder")
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def needs_setup(data_dir):
    """True until a build in the current data format has finished: meta.json is written last, so an interrupted
    build counts as none, and data built by an older tracker counts as none either"""
    if not os.path.exists(_static_path(data_dir)):
        return True
    try:
        with open(_meta_path(data_dir), encoding="utf-8") as f:
            return json.load(f).get("format") != DATA_FORMAT
    except (OSError, ValueError, AttributeError):
        return True


def outdated(data_dir, build_id):
    """True when the game's build id is known and differs from the one the map data was built from"""
    try:
        with open(_meta_path(data_dir), encoding="utf-8") as f:
            built = json.load(f).get("buildid")
    except (OSError, ValueError):
        return False
    return bool(build_id and built and str(built) != str(build_id))


def game_files(game_dir, assets):
    return ree_pak.GameFiles(game_dir, os.path.join(assets, "lists")), ree_rsz.Registry(os.path.join(assets, "rszdd2_dlc.json"))


def build_gamedata(game_dir, assets, data_dir):
    dd2_gamedata.build(game_dir, assets, os.path.join(data_dir, "extracted"), os.path.join(data_dir, "gamedata"))


def build_map(game_dir, assets, data_dir, progress=lambda step, name: None, files=None):
    """tiles and dungeon maps (each only when missing), then the map data; returns the map data"""
    gf, reg = files or game_files(game_dir, assets)
    map_dir = os.path.join(data_dir, "map")
    tiles = os.path.join(map_dir, "tiles")
    progress(2, STEPS[2])
    if not os.path.exists(os.path.join(tiles, "field.json")):
        dd2_map.build_tiles(gf, reg, tiles)
    progress(3, STEPS[3])
    dungeon_dir = os.path.join(map_dir, "dungeons")
    floors_json = os.path.join(dungeon_dir, "floors.json")
    if not os.path.exists(floors_json):
        floors = dd2_map.build_dungeons(gf, reg, dungeon_dir, dd2_mapdata.area_names(gf, reg))
        _write_json(floors_json, floors, indent=1)
    with open(floors_json, encoding="utf-8") as f:
        floors = json.load(f)
    progress(4, STEPS[4])
    static = dd2_mapdata.build_static(gf, reg, os.path.join(data_dir, "gamedata"), os.path.join(data_dir, "extracted"),
                                      floors, map_dir)
    _write_json(_static_path(data_dir), static, separators=(",", ":"))
    return static


def build_all(game_dir, assets, data_dir, progress, build_id):
    """everything from scratch (the first start, or after a game update); meta.json last marks it finished"""
    for p in (_meta_path(data_dir), _static_path(data_dir), os.path.join(data_dir, "extracted"),
              os.path.join(data_dir, "map", "tiles"), os.path.join(data_dir, "map", "dungeons")):
        _clear(p)
    progress(0, STEPS[0])
    files = game_files(game_dir, assets)
    progress(1, STEPS[1])
    build_gamedata(game_dir, assets, data_dir)
    static = build_map(game_dir, assets, data_dir, progress, files)
    _write_json(_meta_path(data_dir), {"buildid": build_id, "format": DATA_FORMAT,
                                       "built": datetime.datetime.now().isoformat(timespec="seconds")}, indent=1)
    return static
