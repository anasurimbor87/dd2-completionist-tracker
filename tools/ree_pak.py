"""Read-only RE Engine PAK reader (DD2, PAK v4.x incl. the 0x40 remap table added in TU 3.2).

Based on seifhassine/REasy (MIT; file_handlers/pak/pakfile.py and utils.py at commit 103397a, the commit pinned in
assets.lock.json) and kagenocookie/RE-Engine-Lib (MIT; REE-Lib/Pak/PakFile.cs). Each part below names its
counterpart.

usage: python ree_pak.py <game_dir> <list_dir> <out_dir> <path-substring> [...]
       extracts every listed file whose path contains one of the substrings (case-insensitive)
"""
import glob
import hashlib
import os
import pickle
import struct
import sys
import zlib
from compression import zstd

from dd2_decrypt import murmur3_32

# header feature flags (REasy pakfile.py: PAK_FLAG_*; RE-Engine-Lib PakFile.cs: PakFeatureFlags)
FLAG_EXTRA_DATA, FLAG_ENCRYPTED_TABLE, FLAG_EXTRA_INT, FLAG_CHUNKS, FLAG_REMAP = 4, 8, 16, 32, 64

# RSA-style keys of the entry table and of encrypted resources (REasy pakfile._decrypt_key, _decrypt_resource)

TABLE_MODULUS = int.from_bytes(bytes([
    0x7D, 0x0B, 0xF8, 0xC1, 0x7C, 0x23, 0xFD, 0x3B, 0xD4, 0x75, 0x16, 0xD2, 0x33, 0x21, 0xD8, 0x10,
    0x71, 0xF9, 0x7C, 0xD1, 0x34, 0x93, 0xBA, 0x77, 0x26, 0xFC, 0xAB, 0x2C, 0xEE, 0xDA, 0xD9, 0x1C,
    0x89, 0xE7, 0x29, 0x7B, 0xDD, 0x8A, 0xAE, 0x50, 0x39, 0xB6, 0x01, 0x6D, 0x21, 0x89, 0x5D, 0xA5,
    0xA1, 0x3E, 0xA2, 0xC0, 0x8C, 0x93, 0x13, 0x36, 0x65, 0xEB, 0xE8, 0xDF, 0x06, 0x17, 0x67, 0x96,
    0x06, 0x2B, 0xAC, 0x23, 0xED, 0x8C, 0xB7, 0x8B, 0x90, 0xAD, 0xEA, 0x71, 0xC4, 0x40, 0x44, 0x9D,
    0x1C, 0x7B, 0xBA, 0xC4, 0xB6, 0x2D, 0xD6, 0xD2, 0x4B, 0x62, 0xD6, 0x26, 0xFC, 0x74, 0x20, 0x07,
    0xEC, 0xE3, 0x59, 0x9A, 0xE6, 0xAF, 0xB9, 0xA8, 0x35, 0x8B, 0xE0, 0xE8, 0xD3, 0xCD, 0x45, 0x65,
    0xB0, 0x91, 0xC4, 0x95, 0x1B, 0xF3, 0x23, 0x1E, 0xC6, 0x71, 0xCF, 0x3E, 0x35, 0x2D, 0x6B, 0xE3]), "little")
RES_MODULUS = int.from_bytes(bytes([
    0x13, 0xD7, 0x9C, 0x89, 0x88, 0x91, 0x48, 0x10, 0xD7, 0xAA, 0x78, 0xAE, 0xF8, 0x59, 0xDF, 0x7D,
    0x3C, 0x43, 0xA0, 0xD0, 0xBB, 0x36, 0x77, 0xB5, 0xF0, 0x5C, 0x02, 0xAF, 0x65, 0xD8, 0x77, 0x03]), "little")
RES_EXPONENT = int.from_bytes(bytes([
    0xC0, 0xC2, 0x77, 0x1F, 0x5B, 0x34, 0x6A, 0x01, 0xC7, 0xD4, 0xD7, 0x85, 0x2E, 0x42, 0x2B, 0x3B,
    0x16, 0x3A, 0x17, 0x13, 0x16, 0xEA, 0x83, 0x30, 0x30, 0xDF, 0x3F, 0xF4, 0x25, 0x93, 0x20, 0x01]), "little")


def path_hash(path):
    """REasy utils.filepath_hash: murmur3 of the lower-case path (low word) and the upper-case path (high word), UTF-16LE"""
    lo = murmur3_32(path.lower().encode("utf-16-le"), 0xFFFFFFFF)
    hi = murmur3_32(path.upper().encode("utf-16-le"), 0xFFFFFFFF)
    return hi << 32 | lo


def decrypt_table(table, enc_key):
    """REasy pakfile._decrypt_pak_entry_data: key = enc_key ** 65537 mod TABLE_MODULUS (_decrypt_key), then
    entry byte i ^= (i + key[i % 32] * key[i % 29]) & 0xFF"""
    key = pow(int.from_bytes(enc_key, "little"), 65537, TABLE_MODULUS).to_bytes(129, "little")
    # mask byte i = (i + key[i%32] * key[i%29]) mod 256, periodic in lcm(32, 29, 256) = 7424
    period = bytes((i + key[i % 32] * key[i % 29]) & 0xFF for i in range(7424))
    n = len(table)
    mask = (period * (n // 7424 + 1))[:n]
    return (int.from_bytes(table, "little") ^ int.from_bytes(mask, "little")).to_bytes(n, "little")


def decrypt_resource(buf):
    """REasy pakfile._decrypt_resource: an 8-byte size, then 128-byte blocks of (key, data); each yields 8 bytes,
    data // (key ** RES_EXPONENT mod RES_MODULUS). One entry of the game uses it (the shop table
    itemshopadditionaldata.user.3)."""
    size = struct.unpack_from("<Q", buf, 0)[0]
    out = bytearray()
    for o in range(8, 8 + (len(buf) - 8) // 128 * 128, 128):
        key = int.from_bytes(buf[o:o + 64], "little")
        data = int.from_bytes(buf[o + 64:o + 128], "little")
        mod = pow(key, RES_EXPONENT, RES_MODULUS)
        out += ((data // mod if mod else 0) & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "little")
    return bytes(out[:size])


class Pak:
    """one PAK file's entry table (REasy pakfile.PakFile.read_contents, _read_chunk_table; RE-Engine-Lib PakFile.cs)"""

    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        magic, major, minor, flags, count, _fp = struct.unpack("<IBBhiI", self.f.read(16))
        if magic != 0x414B504B or major != 4:
            raise ValueError(f"{path}: unsupported PAK {magic:#x} v{major}.{minor}")
        if flags & ~(FLAG_EXTRA_DATA | FLAG_ENCRYPTED_TABLE | FLAG_EXTRA_INT | FLAG_CHUNKS | FLAG_REMAP):
            raise ValueError(f"{path}: unknown PAK flags {flags:#x}")
        table = self.f.read(count * 48)
        if flags & FLAG_EXTRA_INT:
            self.f.seek(4, 1)
        if flags & FLAG_EXTRA_DATA:
            self.f.seek(9, 1)
        if flags & FLAG_REMAP:
            (n,) = struct.unpack("<q", self.f.read(8))
            self.f.seek(n * 16, 1)
        if flags:
            table = decrypt_table(table, self.f.read(128))
        self.block_size, self.chunks = 0, []
        if flags & FLAG_CHUNKS:
            self.block_size, n = struct.unpack("<ii", self.f.read(8))
            raw = self.f.read(n * 8)
            self.chunks = [((attr & 0x3FF) << 32 | off, attr >> 10) for off, attr in struct.iter_unpack("<II", raw)]
        self.entries = {}
        for lo, hi, off, csize, dsize, attr, _ck in struct.iter_unpack("<IIqqqqQ", table):
            self.entries[hi << 32 | lo] = (off, csize, dsize, attr)

    def read_hash(self, h):
        """one entry's bytes: stored, raw Deflate or Zstandard, encrypted, or chunked (REasy pakfile._read_entry_raw)"""
        off, csize, dsize, attr = self.entries[h]
        comp, enc, table_type = attr & 0xF, (attr >> 16) & 0xFF, (attr >> 24) & 0xF
        if table_type == 1:  # chunked: offset is a chunk index
            out, idx = bytearray(), off
            while len(out) < dsize:
                coff, clen = self.chunks[idx]
                self.f.seek(coff)
                data = self.f.read(clen)
                out += data if clen == self.block_size else zstd.decompress(data)
                idx += 1
            return bytes(out[:dsize])
        self.f.seek(off)
        if comp == 0:
            return self.f.read(dsize)
        data = self.f.read(csize)
        if enc:
            data = decrypt_resource(data)
        if comp == 1:
            return zlib.decompress(data, wbits=-15)
        if comp == 2:
            return zstd.decompress(data)
        raise ValueError(f"unknown compression {comp}")


class GameFiles:
    """All PAKs of a DD2 install; later PAKs (patches, DLC) override earlier ones."""

    def __init__(self, game_dir, list_dir=None):
        paths = [os.path.join(game_dir, "re_chunk_000.pak")]
        paths += sorted(glob.glob(os.path.join(game_dir, "re_chunk_000.pak.patch_*.pak")))
        paths += sorted(glob.glob(os.path.join(game_dir, "dlc", "*.pak")))
        self.paks = []
        for p in paths:
            if os.path.getsize(p) <= 16 + 128:
                continue  # empty patch placeholders
            self.paks.append(Pak(p))
        self.names = self._load_names(list_dir) if list_dir else {}

    @staticmethod
    def _load_names(list_dir):
        # hashing ~1M paths in pure Python takes about a minute; cache the index next to the lists
        lists = sorted(glob.glob(os.path.join(list_dir, "*.list")))
        if not lists:
            raise FileNotFoundError(f"no file list (*.list) in {list_dir}: run dd2.py fetch-assets")
        cache = os.path.join(list_dir, "name_index.pickle")
        # keyed by the lists' names and content: dates can't be trusted after unzipping an update over an old folder
        key = hashlib.sha256()
        for p in lists:
            key.update(os.path.basename(p).encode("utf-8") + b"\0")
            with open(p, "rb") as f:
                for block in iter(lambda: f.read(1 << 20), b""):
                    key.update(block)
        key = key.hexdigest()
        try:
            with open(cache, "rb") as f:
                cached = pickle.load(f)
            if isinstance(cached, dict) and cached.get("key") == key:
                return cached["names"]
        except (OSError, pickle.UnpicklingError, EOFError, AttributeError, KeyError):
            pass
        names = {}
        for lst in lists:
            for line in open(lst, encoding="utf-8", errors="replace"):
                line = line.strip().replace("\\", "/")
                if line:
                    names.setdefault(path_hash(line), line.lower())
        try:
            with open(cache + ".new", "wb") as f:
                pickle.dump({"key": key, "names": names}, f)
            os.replace(cache + ".new", cache)
        except OSError:
            pass  # a folder that can't be written: index again next time
        return names

    def find(self, h):
        for pak in reversed(self.paks):
            if h in pak.entries:
                return pak
        return None

    def read(self, path):
        h = path_hash(path)
        pak = self.find(h)
        if pak is None:
            raise FileNotFoundError(path)
        return pak.read_hash(h)

    def listed(self, substring):
        s = substring.lower()
        return sorted(n for h, n in self.names.items() if s in n and self.find(h))


def main():
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    game_dir, list_dir, out_dir = sys.argv[1:4]
    gf = GameFiles(game_dir, list_dir)
    print(f"{len(gf.paks)} paks, {sum(len(p.entries) for p in gf.paks)} entries, {len(gf.names)} known names")
    for sub in sys.argv[4:]:
        for name in gf.listed(sub):
            dst = os.path.join(out_dir, name.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(gf.read(name))
            print(f"  {name}")


if __name__ == "__main__":
    main()
