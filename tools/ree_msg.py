"""RE Engine .msg reader (DD2 uses .msg.24). Ported from dtlnor/REMSG_Converter (REMSG.py, REWString.py)."""
import struct
import uuid

KEY = [0xCF, 0xCE, 0xFB, 0xF8, 0xEC, 0x0A, 0x33, 0x66, 0x93, 0xA9, 0x1D, 0x93, 0x50, 0x39, 0x5F, 0x09]
ENGLISH = 1


def decrypt_pool(raw):
    out = bytearray(raw)
    prev = 0
    for i, cur in enumerate(raw):
        out[i] = cur ^ prev ^ KEY[i & 0xF]
        prev = cur
    return bytes(out)


def _align8(p):
    return (p + 7) & ~7


def read_msg(data):
    """Return a list of entries: {guid, name, text: [per language]}."""
    version, magic, _hdr = struct.unpack_from("<I4sQ", data, 0)
    if magic != b"GMSG":
        raise ValueError("not a GMSG file")
    if version <= 15:
        raise ValueError(f"msg version {version} not handled")
    entry_count, attr_count, lang_count = struct.unpack_from("<III", data, 16)
    p = _align8(28)
    data_offset, _unkn, _lang_off, _attr_off, _attr_name_off = struct.unpack_from("<5Q", data, p)
    p += 40
    entry_offsets = struct.unpack_from(f"<{entry_count}Q", data, p)
    attr_types = struct.unpack_from(f"<{attr_count}i", data, _attr_off)

    pool = decrypt_pool(data[data_offset:])

    def string_at(off):
        start = off - data_offset
        end = start
        while pool[end : end + 2] != b"\x00\x00":
            end += 2
        return pool[start:end].decode("utf-16-le", errors="replace")

    entries = []
    for eo in entry_offsets:
        guid = uuid.UUID(bytes_le=data[eo : eo + 16])
        _sound, _hash, name_off, attr_off = struct.unpack_from("<IIQQ", data, eo + 16)
        langs = struct.unpack_from(f"<{lang_count}Q", data, eo + 40)
        attrs = {}
        for i, t in enumerate(attr_types):
            (v,) = struct.unpack_from("<q" if t == 0 else "<d" if t == 1 else "<Q", data, attr_off + 8 * i)
            attrs[i] = string_at(v) if t == 2 else v
        entries.append({"guid": str(guid), "name": string_at(name_off),
                        "text": [string_at(o) if o else "" for o in langs], "attrs": attrs})
    return entries


def english_by_name(data):
    return {e["name"]: e["text"][ENGLISH] for e in read_msg(data)}


def english_by_guid(data):
    return {e["guid"]: e["text"][ENGLISH] for e in read_msg(data)}
