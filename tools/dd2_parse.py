"""Parse a decrypted DD2 save payload (output of dd2_decrypt.py) into named JSON.

Format follows kvasszn/ree-save-editor src/save/types.rs; names come from its rszdd2.json
(class hash -> name/fields; field hash = murmur3(field_name, 0xffffffff)).

usage: python dd2_parse.py <assets_dir> <in.dec> <out.json>
"""
import json
import os
import struct
import sys

from dd2_decrypt import murmur3_32

FT = {-1: "Array", 0: "Unknown", 1: "Enum", 2: "Boolean", 3: "S8", 4: "U8", 5: "S16", 6: "U16", 7: "S32",
      8: "U32", 9: "S64", 10: "U64", 11: "F32", 12: "F64", 13: "C8", 14: "C16", 15: "String", 16: "Struct",
      17: "Class"}
SIZED_FMT = {"Boolean": "?", "S8": "b", "U8": "B", "S16": "h", "U16": "H", "S32": "i", "U32": "I", "S64": "q",
             "U64": "Q", "F32": "f", "F64": "d", "C8": "B", "C16": "H"}
ENUM_FMT = {1: "b", 2: "h", 4: "i", 8: "q"}
NATURAL_SIZE = {"Boolean": 1, "S8": 1, "U8": 1, "C8": 1, "S16": 2, "U16": 2, "C16": 2, "S32": 4, "U32": 4, "F32": 4,
                "S64": 8, "U64": 8, "F64": 8}
# some DLC-added structs sit behind far more padding than 32 bytes: NPCSaveStrayPawnPast's ?a1bad783 (112 bytes) gets
# 4, 36, 68 or 100 bytes, depending on its position in a 128-byte window
WIDE_PADDING = 256


class TypeNames:
    def __init__(self, rsz_path, names_path=None):
        self.classes = {}
        self.fields = {}
        for h, info in json.load(open(rsz_path, encoding="utf-8")).items():
            ch = int(h, 16)
            self.classes[ch] = info["name"]
            self.fields[ch] = {murmur3_32(f["name"].encode("utf-8"), 0xFFFFFFFF): (f["name"], f["original_type"], f["align"])
                               for f in info["fields"]}
        if names_path:
            # newer dump: take class/field names from it, but keep alignment only for fields the base dump
            # also knows (save padding of DLC-added fields doesn't follow the declared alignment)
            for h, info in json.load(open(names_path, encoding="utf-8")).items():
                ch = int(h, 16)
                self.classes[ch] = info["name"]
                base = self.fields.get(ch, {})
                for f in info["fields"]:
                    fh = murmur3_32(f["name"].encode("utf-8"), 0xFFFFFFFF)
                    align = base[fh][2] if fh in base else None
                    base[fh] = (f["name"], f["original_type"], align)
                self.fields[ch] = base
        self.all_fields = {fh for fs in self.fields.values() for fh in fs}

    def cls(self, h):
        return self.classes.get(h, f"?{h:08x}")

    def field(self, class_hash, field_hash):
        return self.fields.get(class_hash, {}).get(field_hash, (f"?{field_hash:08x}", None, None))


class Reader:
    def __init__(self, data, names):
        self.d, self.p, self.n = data, 0, names
        self.stack = []  # (class name, field name) path, for error reports
        self.cur_class, self.remaining = None, 0
        self.trace = []  # recent (offset, path, type) entries

    def align(self, a):
        self.p = (self.p + a - 1) & ~(a - 1)

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def string(self):
        self.align(4)
        size = self.u32()
        s = self.d[self.p : self.p + size * 2].decode("utf-16le", errors="replace")
        self.p += size * 2
        return s.rstrip("\x00")

    def sized(self, ftype, size):
        if size > 1:
            # upstream uses (pos + size - 1) & !(size - 1), which only works for power-of-two sizes
            if size & (size - 1):
                self.p = self.odd_struct_start(self.p, min(size & -size, 16))
            else:
                self.align(min(size, 16))
        if ftype == "Enum":
            v = struct.unpack_from("<" + ENUM_FMT[size], self.d, self.p)[0]
        elif ftype == "Struct":
            v = self.d[self.p : self.p + size].hex()
        elif ftype == "Array":
            return self.array()
        else:
            v = struct.unpack_from("<" + SIZED_FMT[ftype], self.d, self.p)[0]
        self.p += size
        return v

    def field_header_ok(self, pos):
        if pos + 8 > len(self.d):
            return pos == len(self.d)
        first, second = struct.unpack_from("<Ii", self.d, pos)
        known = self.n.fields.get(self.cur_class)
        if self.remaining == 0:
            # last field of the class: next comes the parent's next field or the next array element's
            # class header (num_fields, class hash)
            if first < 1024 and ((second & 0xFFFFFFFF) == self.cur_class or (second & 0xFFFFFFFF) in self.n.classes):
                return True
            return first > 0xFFFF and second in FT and second != 0
        if second not in FT or second == 0:
            return False
        if known:
            # inside a known class the next field must be one of its fields, or a DLC-added (unknown) hash
            return first in known or (first > 0xFFFF and first not in self.n.all_fields)
        return first > 0xFFFF

    def field_header_strict(self, pos):
        """field_header_ok, and a field header's size must fit its type: for searches across long runs of zeros and data"""
        if pos + 12 > len(self.d) or not self.field_header_ok(pos):
            return pos + 12 > len(self.d) and self.field_header_ok(pos)
        first, second, size = struct.unpack_from("<IiI", self.d, pos)
        if self.remaining == 0 and first < 1024:
            return True  # class header of the next array element
        ftype = FT[second]
        if ftype in NATURAL_SIZE:
            return size == NATURAL_SIZE[ftype]
        if ftype == "Enum":
            return size in ENUM_FMT
        if ftype == "Struct":
            return 0 < size <= 4096
        if ftype == "Array":  # array header: member type, member size, length, array type (0 values, 1 classes)
            if pos + 24 > len(self.d):
                return False
            member, msize, length, kind = struct.unpack_from("<iIIi", self.d, pos + 8)
            return member in FT and member not in (0, -1) and msize <= 4096 and length < 1_000_000 and kind in (0, 1)
        return True

    def known_field_at(self, pos):
        """a field header of a field the current class is known to have, passing the strict checks"""
        if self.remaining == 0 or pos + 12 > len(self.d):
            return False
        first = struct.unpack_from("<I", self.d, pos)[0]
        return first in self.n.fields.get(self.cur_class, {}) and self.field_header_strict(pos)

    @staticmethod
    def odd_struct_start(p, align):
        # measured on thousands of via.Position values: structs whose size is not a power of two start at
        # their alignment, pushed into the upper half of a 32-byte window (offset % 32 >= 16)
        s = (p + align - 1) & ~(align - 1)
        return s + 16 if s % 32 < 16 else s

    def struct_field(self, size, declared_align):
        pow2 = size & (size - 1) == 0
        base = self.p
        if pow2:
            align = declared_align or min(size, 16)
            self.align(align)
            if declared_align or self.field_header_ok((self.p + size + 3) & ~3):
                return self.sized("Struct", size)
            starts = [base + k for k in range(0, 33, 4)]
        else:
            # alignment of DLC-added fields is unknown: try the declared one first, then the usual ones
            aligns = [a for a in (declared_align, 4, 8, 16) if a]
            starts = [self.odd_struct_start(base, a) for a in aligns] + [base + k for k in range(0, 33, 4)]
            if not declared_align:
                # the upper-half rule was measured on known structs; for unknown ones take the earliest start whose
                # end meets a field header (a later one can end on the field after next, swallowing a header), and
                # test headers strictly: the value's own bytes can look like one
                starts = sorted(set(starts))
        if not (pow2 or declared_align):
            # a known field of this class right after the value is far stronger evidence than a hash that merely is
            # missing from the dumps: a dismissed pawn's 112-byte struct behind 36 bytes of padding otherwise ended
            # early on a chance "header" (0x0001ffff, Enum, size 2) inside its own bytes
            for start in starts + list(range(base + 36, base + WIDE_PADDING, 4)):
                if self.known_field_at((start + size + 3) & ~3):
                    self.p = start
                    return self.raw(size)
        header_ok = self.field_header_ok if pow2 or declared_align else self.field_header_strict
        for start in starts:
            if header_ok((start + size + 3) & ~3):
                self.p = start
                return self.raw(size)
        for start in range(base + 36, base + WIDE_PADDING, 4):
            if self.field_header_strict((start + size + 3) & ~3):
                self.p = start
                return self.raw(size)
        self.p = starts[0]
        return self.raw(size)

    def raw(self, length):
        v = self.d[self.p : self.p + length].hex()
        self.p += length
        return v

    def value(self, ftype, declared_align=None):
        if ftype == "Array":
            return self.array()
        if ftype == "Class":
            return self.cls()
        if ftype == "String":
            return self.string()
        if ftype == "Unknown":
            raise ValueError(f"unknown field type at {self.p:#x}")
        self.align(4)
        size = self.u32()
        if ftype == "Struct":
            return self.struct_field(size, declared_align)
        return self.sized(ftype, size)

    def array(self):
        self.align(4)
        member_type = FT[self.i32()]
        member_size = self.u32()
        length = self.u32()
        array_type = self.i32()
        # a misparse can land on garbage: never loop over more elements than the bytes left could hold
        if length and array_type != 1 and member_type != "String" and member_size == 0:
            raise ValueError(f"array of {length} zero-size {member_type} elements at {self.p:#x}")
        if length > len(self.d) - self.p:
            raise ValueError(f"array length {length} exceeds the data left at {self.p:#x}")
        if array_type == 1:
            if self.u32() != 0xFFEEFFEE:
                self.p -= 4
            else:
                self.p += 4 * length
        out = []
        try:
            for _ in range(length):
                if array_type == 1:
                    out.append(self.cls())
                elif member_type == "String":
                    out.append(self.string())
                else:
                    out.append(self.sized(member_type, member_size))
        except Exception as e:
            # keep what was read so far; callers chain partial results up to the failing record
            out.append(getattr(e, "partial", None))
            e.partial = out
            raise
        self.align(4)
        return out

    def cls(self):
        class_start = self.p
        num_fields = self.u32()
        class_hash = self.u32()
        obj = {"$type": self.n.cls(class_hash)}
        for i in range(num_fields):
            start = self.p
            fh = self.u32()
            ftype = FT.get(self.i32(), "Unknown")
            name, otype, falign = self.n.field(class_hash, fh)
            self.cur_class, self.remaining = class_hash, num_fields - i - 1
            self.stack.append(f"{obj['$type']}@{class_start:#x}.{name}")
            self.trace.append((start, "/".join(self.stack[-3:]), ftype, otype))
            del self.trace[:-40]
            try:
                obj[name] = self.value(ftype, falign)
            except Exception as e:
                obj[name] = getattr(e, "partial", None)
                obj["$error"] = f"{type(e).__name__}: {e} at {self.p:#x} (field {name} @ {start:#x})"
                e.partial = obj
                raise
            self.stack.pop()
            self.align(4)
        return obj


def parse(data, names):
    r = Reader(data, names)
    top = []
    end = len(data) - 7
    while r.p + 4 <= len(data):
        h = r.u32()
        try:
            top.append({"$root_hash": f"{h:08x}", "value": r.cls()})
        except Exception as e:
            top.append({"$root_hash": f"{h:08x}", "$error": f"{type(e).__name__}: {e} at {r.p:#x}"})
            print(f"ERROR {type(e).__name__}: {e} at {r.p:#x}\n  path: {' / '.join(r.stack)}")
            for off, path, ft, ot in r.trace[-25:]:
                print(f"  {off:#08x} {ft:8} {ot or '':34} {path}")
            break
        if r.p >= end:
            break
    return top, r.p


HASH_VALUE_HASH = murmur3_32(b"HashValue", 0xFFFFFFFF)


def find_next_record(data, pos, names):
    # top-level records end with the fields VersionValue, HashValue (U32); the next record's class header
    # (num_fields, class hash) follows HashValue's value. Nested classes can end the same way, so also
    # require a known class whose name looks like a save record.
    marker = struct.pack("<IiI", HASH_VALUE_HASH, 8, 4)
    i = data.find(marker, pos)
    while i != -1:
        nxt = i + 16
        if i % 4 == 0 and nxt + 8 <= len(data):
            n, ch = struct.unpack_from("<II", data, nxt)
            name = names.classes.get(ch, "")
            if 0 < n < 512 and "SaveData" in name:
                return nxt
        i = data.find(marker, i + 1)
    return -1


def parse_records(data, names):
    """Parse the root record list element by element, resyncing to the next record after a failure."""
    r = Reader(data, names)
    r.u32()  # root hash
    r.u32()  # num_fields of the root manager class (1)
    root_type = r.n.cls(r.u32())
    r.u32()  # list field hash
    r.i32()  # Array
    r.align(4)
    r.i32()  # member type
    r.u32()  # member size
    length = r.u32()
    r.i32()  # array type
    records = []
    for i in range(length):
        start = r.p
        r.stack, r.trace = [], []
        try:
            rec = r.cls()
            rec["$offset"] = start
            records.append(rec)
        except Exception as e:
            rec = getattr(e, "partial", None) or {}
            rec["$offset"] = start
            records.append(rec)
            nxt = find_next_record(data, max(r.p - 16, start + 8), names)
            where = f"resync -> {nxt:#x}" if nxt != -1 else "no further record"
            print(f"  record {i} ({rec.get('$type')}) @ {start:#x}: {type(e).__name__}: {e}; {where}")
            if nxt == -1:
                break
            r.p = nxt
    return root_type, records


def load_names(assets_dir):
    dlc = os.path.join(assets_dir, "rszdd2_dlc.json")
    return TypeNames(os.path.join(assets_dir, "rszdd2.json"), dlc if os.path.exists(dlc) else None)


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    names = load_names(sys.argv[1])
    data = open(sys.argv[2], "rb").read()
    root_type, records = parse_records(data, names)
    ok = sum(not _has_error(r) for r in records)
    print(f"{root_type}: {len(records)} records, {ok} parsed without error")
    with open(sys.argv[3], "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)


def _has_error(node):
    if isinstance(node, dict):
        return "$error" in node or any(_has_error(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_error(v) for v in node)
    return False


if __name__ == "__main__":
    main()
