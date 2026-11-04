"""Writes made-up save record trees in the layout tools/dd2_parse.py reads (field hash, type, value), for the field
types Class, Array of classes, S32, U32, Boolean and String. names: a type dump like tests/fixtures/names.json, whose
fields' original_type is one of those type names. Test code only."""
import struct

import dd2_decrypt

FT = {"Array": -1, "Boolean": 2, "S32": 7, "U32": 8, "String": 15, "Class": 17}


def _hash(text):
    return dd2_decrypt.murmur3_32(text.encode("utf-8"), 0xFFFFFFFF)


class _Writer:
    def __init__(self, names):
        self.out = bytearray()
        self.classes = {info["name"]: (int(h, 16), info["fields"]) for h, info in names.items()}

    def align(self, a):
        self.out += bytes(-len(self.out) % a)

    def u32(self, v):
        self.out += struct.pack("<I", v)

    def i32(self, v):
        self.out += struct.pack("<i", v)

    def cls(self, obj):
        class_hash, fields = self.classes[obj["$type"]]
        self.u32(len(fields))
        self.u32(class_hash)
        for f in fields:
            ftype = f["original_type"]
            self.u32(_hash(f["name"]))
            self.i32(FT[ftype])
            self.value(ftype, obj[f["name"]])
            self.align(4)

    def value(self, ftype, v):
        if ftype == "Class":
            return self.cls(v)
        self.align(4)
        if ftype == "Array":  # member type, member size, length, array type 1 (classes)
            self.i32(FT["Class"])
            self.u32(0)
            self.u32(len(v))
            self.i32(1)
            for item in v:
                self.cls(item)
        elif ftype == "String":
            text = v.encode("utf-16le") + b"\0\0"
            self.u32(len(text) // 2)
            self.out += text
        elif ftype == "Boolean":
            self.u32(1)
            self.out += bytes([1 if v else 0])
        else:
            self.u32(4)
            self.out += struct.pack("<i" if ftype == "S32" else "<I", v)


def write_records(root_class, records, names):
    w = _Writer(names)
    root_hash, root_fields = w.classes[root_class]
    w.u32(0x12345678)  # root hash (not read)
    w.u32(1)
    w.u32(root_hash)
    w.u32(_hash(root_fields[0]["name"]))
    w.i32(FT["Array"])
    w.align(4)
    w.i32(FT["Class"])
    w.u32(0)
    w.u32(len(records))
    w.i32(1)
    for r in records:
        w.cls(r)
    return bytes(w.out)
