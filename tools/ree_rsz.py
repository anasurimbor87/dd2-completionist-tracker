"""Minimal RE Engine RSZ reader for .user files (DD2 .user.3), based on seifhassine/REasy rsz_file.py.

parse_user(data, registry) -> list of root objects; object references are resolved into nested dicts.
parse_scn_instances(data, registry) -> the flat instance list of a scene (.scn.21); references stay ("$ref", index).
"""
import json
import struct
import uuid

PRIM = {"Bool": "?", "S8": "b", "U8": "B", "S16": "h", "U16": "H", "S32": "i", "U32": "I", "S64": "q", "U64": "Q",
        "F32": "f", "F64": "d", "C8": "B", "C16": "H"}
VEC = {"Vec2": 2, "Float2": 2, "Vec3": 3, "Float3": 3, "Vec4": 4, "Float4": 4, "Quaternion": 4, "Position": 3,
       "Point": 2, "Size": 2, "Range": 2}


class Registry:
    def __init__(self, path):
        raw = json.load(open(path, encoding="utf-8"))
        self.by_hash = {int(h, 16): v for h, v in raw.items()}
        self.by_name = {v["name"]: v for v in raw.values()}


class RszReader:
    def __init__(self, data, reg):
        self.d, self.reg = data, reg

    def _align(self, p, a):
        return p if a <= 1 else (p + a - 1) // a * a

    def _string(self, p):
        p = self._align(p, 4)
        (n,) = struct.unpack_from("<I", self.d, p)
        s = self.d[p + 4 : p + 4 + n * 2].decode("utf-16-le", errors="replace").rstrip("\x00")
        return s, p + 4 + n * 2

    def _value(self, f, p):
        t, size, align = f["type"], f["size"], f["align"]
        if t in ("String", "Resource"):
            return self._string(p)
        p = self._align(p, align)
        if t in ("Object", "UserData"):
            return ("$ref", struct.unpack_from("<i", self.d, p)[0]), p + 4
        if t in PRIM:
            return struct.unpack_from("<" + PRIM[t], self.d, p)[0], p + size
        if t in ("Guid", "GameObjectRef", "Uri"):
            return str(uuid.UUID(bytes_le=self.d[p : p + 16])), p + size
        if t in VEC:
            ft = "d" if t == "Position" else "f"
            return list(struct.unpack_from(f"<{VEC[t]}{ft}", self.d, p)), p + size
        if t == "Struct":
            sub = self.reg.by_name.get(f["original_type"])
            if sub and sub["fields"]:
                obj, q = self.fields(sub, p)
                return obj, max(q, p + size) if size else q
        return self.d[p : p + size].hex(), p + size

    def fields(self, info, p):
        obj = {"$type": info["name"]}
        for f in info["fields"]:
            if f["array"]:
                p = self._align(p, 4)
                (n,) = struct.unpack_from("<I", self.d, p)
                p += 4
                vals = []
                for _ in range(n):
                    v, p = self._value(f, p)
                    vals.append(v)
                obj[f["name"]] = vals
            else:
                obj[f["name"]], p = self._value(f, p)
        return obj, p


def _rsz_block(data, rsz_off, reg):
    """the RSZ block at rsz_off: (root object indices, instances with unresolved references, external user data)"""
    _m, version, obj_count, inst_count, ud_count, _res, inst_off, data_off, ud_off = struct.unpack_from(
        "<IIIIIIQQQ", data, rsz_off)
    objects = struct.unpack_from(f"<{obj_count}i", data, rsz_off + 48)
    infos = [struct.unpack_from("<II", data, rsz_off + inst_off + 8 * i) for i in range(inst_count)]
    userdata = {}  # instance id -> referenced external .user path
    for i in range(ud_count):
        inst_id, _h, str_off = struct.unpack_from("<IIQ", data, rsz_off + ud_off + 16 * i)
        end = rsz_off + str_off
        while data[end : end + 2] != b"\x00\x00":
            end += 2
        userdata[inst_id] = {"$userdata": data[rsz_off + str_off : end].decode("utf-16-le")}
    userdata_ids = set(userdata)

    r = RszReader(data, reg)
    p = rsz_off + data_off
    instances = [None] * inst_count
    for idx, (type_hash, _crc) in enumerate(infos):
        if idx == 0 or idx in userdata_ids or type_hash == 0:
            continue
        info = reg.by_hash.get(type_hash)
        if info is None:
            raise ValueError(f"instance {idx}: unknown type {type_hash:#010x}")
        instances[idx], p = r.fields(info, p)
    return objects, instances, userdata


def parse_user(data, reg):
    magic, _res_count, _ud_count, _info_count, _res_tbl, _ud_tbl, rsz_off, _r = struct.unpack_from("<4s3I3QQ", data, 0)
    if magic != b"USR\x00":
        raise ValueError("not a USR file")
    objects, instances, userdata = _rsz_block(data, rsz_off, reg)

    def resolve(v, depth=0):
        if isinstance(v, tuple) and v and v[0] == "$ref":
            i = v[1]
            if i in userdata:
                return userdata[i]
            return resolve(instances[i], depth + 1) if 0 < i < len(instances) and instances[i] is not None else None
        if isinstance(v, dict):
            return {k: resolve(x, depth) for k, x in v.items()}
        if isinstance(v, list):
            return [resolve(x, depth) for x in v]
        return v

    return [resolve(("$ref", o)) for o in objects]


def parse_scn_instances(data, reg):
    """all instances of a scene (game objects, their components and the objects these hold), in file order"""
    if data[:4] != b"SCN\x00":
        raise ValueError("not a SCN file")
    rsz_off = struct.unpack_from("<Q", data, 56)[0]  # header <4s5I5Q: the last field is the RSZ block's offset
    return _rsz_block(data, rsz_off, reg)[1]
