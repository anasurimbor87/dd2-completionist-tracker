"""World map for the DD2 save viewer: tile pyramid from the game's menu map textures + static marker data.

Field map (app.MapTexListData, UIArea 0): 8x8 grid of 4096 px textures, each covering 1024 world units,
grid origin at world (-4096, -4096); grid row grows with world z (map up = world -z).
Leaflet CRS.Simple: one z0 tile (256 px) covers the whole 8192-unit grid -> latlng = [-(z + 4096) / 32, (x + 4096) / 32].

usage: python dd2_map.py tiles <game_dir> <assets_dir> <out_dir>
"""
import json
import os
import re
import sys

from PIL import Image

import ree_pak
import ree_rsz
import ree_tex

TEX_EXT = ".251211553"
MAP_LISTS = ["natives/stm/appdata/map/menumaptexlistdata.user.3",
             "natives/stm/appdata/map/contents0014menumaptexlistdata.user.3"]  # DLC list overrides
MAX_ZOOM = 6  # 2 px per world unit; the browser upscales beyond that
GRID = 8


def map_params(gf, reg):
    out = []
    for n in MAP_LISTS:
        root = ree_rsz.parse_user(gf.read(n), reg)[0]
        out.append(next(v for v in root.values() if isinstance(v, list)))
    return out


def field_tiles(gf, reg):
    tiles, field = {}, None
    for params in map_params(gf, reg):
        f = next(p for p in params if p["UIArea"] == 0)
        field = field or {k: f[k] for k in ("BasePosX", "BasePosZ", "DispRangeX", "DispRangeZ", "TexRange", "TexSize")}
        for i, pf in enumerate(f["PrefabList"]):
            if not pf or not pf.get("Path") or "mapbg_0" in pf["Path"]:
                continue
            text = gf.read("natives/stm/" + pf["Path"].lower() + ".18").decode("utf-16-le", errors="ignore")
            tex = sorted(set(re.findall(r"[A-Za-z0-9_/]+\.tex", text)))
            if tex:
                tiles[i] = "natives/stm/" + tex[0].lower() + TEX_EXT
    return field, tiles


def build_tiles(gf, reg, out_dir, quality=85):
    field, tiles = field_tiles(gf, reg)
    z3 = {}  # source tile index -> 256 px image (one z3 tile per source tile)
    for i, tex in sorted(tiles.items()):
        img = ree_tex.read_tex(gf.read(tex)).convert("RGB")
        col, row = i % GRID, i // GRID
        for z in range(MAX_ZOOM, 2, -1):
            n = 2 ** (z - 3)  # z tiles per source tile edge
            scaled = img.resize((256 * n, 256 * n), Image.LANCZOS) if img.width != 256 * n else img
            for ty in range(n):
                for tx in range(n):
                    d = os.path.join(out_dir, str(z), str(col * n + tx))
                    os.makedirs(d, exist_ok=True)
                    scaled.crop((tx * 256, ty * 256, tx * 256 + 256, ty * 256 + 256)).save(
                        os.path.join(d, f"{row * n + ty}.jpg"), quality=quality)
            if z == 3:
                z3[i] = scaled
        print(f"  tile {i:2} done")
    # z2..z0: compose from the z3 tiles
    for z in (2, 1, 0):
        per = 2 ** (3 - z)  # source tiles per z tile edge
        for ty in range(2 ** z):
            for tx in range(2 ** z):
                canvas = Image.new("RGB", (256 * per, 256 * per), (24, 22, 20))
                used = False
                for sy in range(per):
                    for sx in range(per):
                        i = (ty * per + sy) * GRID + tx * per + sx
                        if i in z3:
                            canvas.paste(z3[i], (sx * 256, sy * 256))
                            used = True
                if used:
                    d = os.path.join(out_dir, str(z), str(tx))
                    os.makedirs(d, exist_ok=True)
                    canvas.resize((256, 256), Image.LANCZOS).save(os.path.join(d, f"{ty}.jpg"), quality=quality)
    with open(os.path.join(out_dir, "field.json"), "w") as f:
        json.dump({"field": field, "tiles": {str(k): v for k, v in tiles.items()}, "max_zoom": MAX_ZOOM}, f, indent=1)


DUNGEON_MAX_PX = 640


def floor_label(n):
    return f"{n + 1}F" if n >= 0 else f"B{-n}"


def build_dungeons(gf, reg, out_dir, names):
    """Crop every dungeon floor map (menu map entries with IsDungeon) to its opaque area and save it as PNG.

    Returns floors: world rectangle of the crop, image path/size, name. The texture spans the entry's DispRange.
    """
    os.makedirs(out_dir, exist_ok=True)
    floors, seen = [], set()
    for params in reversed(map_params(gf, reg)):  # DLC list first, so its versions win
        for p in params:
            if not p["IsDungeon"] or not p["PrefabList"] or not p["PrefabList"][0]:
                continue
            key = (p["UIArea"], p["LocalArea"], p["FloorNo"])
            if key in seen:
                continue
            seen.add(key)
            try:
                text = gf.read("natives/stm/" + p["PrefabList"][0]["Path"].lower() + ".18").decode("utf-16-le", errors="ignore")
                tex = sorted(set(re.findall(r"[A-Za-z0-9_/]+\.tex", text)))
                img = ree_tex.read_tex(gf.read("natives/stm/" + tex[0].lower() + TEX_EXT))
            except (FileNotFoundError, IndexError, ValueError) as e:
                print(f"  skip dungeon {key}: {e}")
                continue
            box = img.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox()
            if not box:
                continue
            pad = img.width // 64
            box = (max(0, box[0] - pad), max(0, box[1] - pad), min(img.width, box[2] + pad), min(img.height, box[3] + pad))
            crop = img.crop(box)
            scale = min(1.0, DUNGEON_MAX_PX / max(crop.size))
            if scale < 1:
                crop = crop.resize((max(1, round(crop.width * scale)), max(1, round(crop.height * scale))), Image.LANCZOS)
            name = f"{p['UIArea']}_{p['LocalArea']}_{p['FloorNo']}.webp"
            crop.save(os.path.join(out_dir, name), quality=82, method=4)
            sx, sz = p["DispRangeX"] / img.width, p["DispRangeZ"] / img.height
            floors.append({
                "ui": p["UIArea"], "local": p["LocalArea"], "floor": p["FloorNo"], "label": floor_label(p["FloorNo"]),
                "name": names.get(p["LocalArea"]) or "",
                "x0": p["BasePosX"] + box[0] * sx, "z0": p["BasePosZ"] + box[1] * sz,
                "x1": p["BasePosX"] + box[2] * sx, "z1": p["BasePosZ"] + box[3] * sz,
                "img": "dungeons/" + name, "w": crop.width, "h": crop.height,
            })
    return floors


def to_crs(x, z, field):
    """world -> Leaflet CRS.Simple [lat, lng] of the field map"""
    return [-(z - field["BasePosZ"]) * 256 / field["DispRangeZ"], (x - field["BasePosX"]) * 256 / field["DispRangeX"]]


INSET_SCALE = 2.5  # dungeon maps are drawn larger than the world map scale
INSET_MAX, INSET_MIN, GAP, MARGIN = 22.0, 5.0, 1.5, 6.0


def layout_insets(groups, field, content):
    """Place each dungeon's floor maps in the margin around the world map, on the side nearest to the dungeon.

    groups: [{"key", "cx", "cz", "floors": [{"w_world", "h_world"}...]}]; content: (lng0, lat0, lng1, lat1) of the
    world map content. Sets floor["bounds"] = [[lat_bottom, lng_left], [lat_top, lng_right]].
    """
    lng0, lat0, lng1, lat1 = content  # lat0 top (0), lat1 bottom (negative)
    sides = {"left": [], "right": [], "top": [], "bottom": []}
    for g in groups:
        lat, lng = to_crs(g["cx"], g["cz"], field)
        g["lat"], g["lng"] = lat, lng
        d = {"left": lng - lng0, "right": lng1 - lng, "top": lat0 - lat, "bottom": lat - lat1}
        side = min(d, key=d.get)
        vertical = side in ("left", "right")
        sizes = []
        for f in g["floors"]:
            w, h = f["w_world"] / 32 * INSET_SCALE, f["h_world"] / 32 * INSET_SCALE
            s = min(1.0, INSET_MAX / max(w, h))
            w, h = w * s, h * s
            s = max(1.0, INSET_MIN / max(w, h))
            sizes.append((w * s, h * s))
        if vertical:
            g["w"], g["h"] = max(w for w, _ in sizes), sum(h for _, h in sizes) + GAP * (len(sizes) - 1)
        else:
            g["w"], g["h"] = sum(w for w, _ in sizes) + GAP * (len(sizes) - 1), max(h for _, h in sizes)
        g["sizes"], g["vertical"] = sizes, vertical
        sides[side].append(g)

    for side, gs in sides.items():
        vertical = side in ("left", "right")
        gs.sort(key=lambda g: -g["lat"] if vertical else g["lng"])
        lanes = []  # each lane: [offset from content edge, extent, cursor]
        for g in gs:
            along, size, across = (-g["lat"], g["h"], g["w"]) if vertical else (g["lng"], g["w"], g["h"])
            start = along - size / 2
            lo, hi = (-lat0 - 40, -lat1 + 40) if vertical else (lng0 - 40, lng1 + 40)
            placed = False
            for lane in lanes:
                pos = max(start, lane[2] + GAP)
                if pos + size <= hi and across <= lane[1]:
                    lane[2] = pos + size
                    placed = True
                    break
            if not placed:
                offset = (lanes[-1][0] + lanes[-1][1] + GAP * 2) if lanes else MARGIN
                width = max(across, 14.0)
                pos = max(start, lo)
                lanes.append([offset, width, pos + size])
                lane = lanes[-1]
            offset = lane[0]
            # top-left corner of the group in CRS units
            if side == "left":
                left, top = lng0 - offset - g["w"], -pos
            elif side == "right":
                left, top = lng1 + offset, -pos
            elif side == "top":
                left, top = pos, lat0 + offset + g["h"]
            else:
                left, top = pos, lat1 - offset
            cur = 0.0
            for f, (w, h) in zip(g["floors"], g["sizes"]):
                if g["vertical"]:
                    fl, ft = left, top - cur
                    cur += h + GAP
                else:
                    fl, ft = left + cur, top
                    cur += w + GAP
                f["bounds"] = [[ft - h, fl], [ft, fl + w]]


def main():
    if len(sys.argv) != 5 or sys.argv[1] != "tiles":
        sys.exit(__doc__)
    game_dir, assets, out = sys.argv[2:]
    gf = ree_pak.GameFiles(game_dir, os.path.join(assets, "lists"))
    reg = ree_rsz.Registry(os.path.join(assets, "rszdd2_dlc.json"))
    build_tiles(gf, reg, out)


if __name__ == "__main__":
    main()
