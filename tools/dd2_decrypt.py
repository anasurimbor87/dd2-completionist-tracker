"""Read-only decryptor for Dragon's Dogma 2 PC saves (RE Engine DSSS container, "Mandarin" cipher).

Ported from kvasszn/ree-save-editor (src/save/mod.rs, src/save/crypto/mandarin.rs).
Only reads the input files; writes decrypted payloads to the output directory.

usage: python dd2_decrypt.py <steam_account_id_or_id64> <out_dir> <save.bin> [<save.bin> ...]
"""
import os
import struct
import sys
import zlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

M64 = (1 << 64) - 1
DD2_SEED_ENC = 0x5EC646997D69AE1B

FLAG_BLOWFISH, FLAG_HAS_ID, FLAG_CITRUS, FLAG_DEFLATE, FLAG_MANDARIN = 0x1, 0x2, 0x4, 0x8, 0x10


def splitmix_next(state):
    # mirrors `state = SplitMix64::next_int(&mut state)`: the mixed output becomes the new state
    z = (state + 0x9E3779B97F4A7C15) & M64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
    return z ^ (z >> 31)


def murmur3_32(data, seed):
    c1, c2 = 0xCC9E2D51, 0x1B873593
    h = seed & 0xFFFFFFFF
    n = len(data) // 4
    for (k,) in struct.iter_unpack("<I", data[: n * 4]):
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << 13) | (h >> 19)) & 0xFFFFFFFF
        h = (h * 5 + 0xE6546B64) & 0xFFFFFFFF
    tail = data[n * 4 :]
    if tail:
        k = int.from_bytes(tail, "little")
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
    h ^= len(data)
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h


def aes128_ofb(key, iv, data):
    # OFB built on ECB: keystream block i = AES(block i-1); avoids the deprecated/removed modes.OFB
    ecb = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    stream = bytearray(len(data) + 16)
    block = iv
    for off in range(0, len(data), 16):
        block = ecb.update(block)
        stream[off : off + 16] = block
    n = len(data)
    return (int.from_bytes(data, "little") ^ int.from_bytes(stream[:n], "little")).to_bytes(n, "little")


def mandarin_decrypt(encrypted, decrypted_len, key, seed_enc=DD2_SEED_ENC):
    num_potential = (1 if decrypted_len & 0x3FFF else 0) + (decrypted_len >> 14)
    state = seed_enc
    block_sizes = []
    for _ in range(num_potential):
        block_sizes.append((state & 7) + 1)
        state = splitmix_next(state)

    num_real, left = 0, decrypted_len
    for b in block_sizes:
        num_real += 1
        if left <= b * 0x4000:
            break
        left -= b * 0x4000

    state = (state + (~key & M64)) & M64

    out = bytearray()
    pos, remaining = 0, decrypted_len
    for i in range(num_real):
        block_size = block_sizes[i] * 0x4000
        chunk = encrypted[pos : pos + block_size + 0x210]
        if len(chunk) != block_size + 0x210:
            raise ValueError(f"block {i}: out of bounds ({pos + block_size + 0x210} > {len(encrypted)})")

        aes_key, iv = bytearray(16), bytearray(16)
        for j in range(16):
            state = splitmix_next(state)
            aes_key[j] = state & 0xFF
            iv[j] = (state >> 8) & 0xFF

        meta = bytearray(chunk[:0x210])
        for j in range(0x210):
            state = splitmix_next(state)
            meta[j] ^= state & 0xFF
        # meta[0x200:0x208] holds a per-block checksum of unknown algorithm; the file hash above covers integrity

        data = aes128_ofb(bytes(aes_key), bytes(iv), chunk[0x210:])
        take = min(block_size, remaining)
        out += data[:take]
        remaining -= take
        pos += block_size + 0x210
    return bytes(out)


def process(path, key, out_dir):
    raw = open(path, "rb").read()
    name = os.path.basename(path)
    print(f"== {name} ({len(raw)} bytes)")

    if len(raw) < 32:
        raise ValueError(f"{name}: file too short ({len(raw)} bytes)")
    end_hash = struct.unpack_from("<I", raw, len(raw) - 4)[0]
    calc = murmur3_32(raw[:-4], 0xFFFFFFFF)
    print(f"  murmur3 file hash: stored={end_hash:#010x} calc={calc:#010x} {'OK' if end_hash == calc else 'MISMATCH'}")
    if end_hash != calc:
        # a half-written or damaged file: its trailer (and with it the length below) is garbage
        raise ValueError(f"{name}: file hash mismatch (half-written or damaged save file)")

    magic, version, flags = struct.unpack_from("<4sII", raw, 0)
    if magic != b"DSSS" or version != 2:
        raise ValueError(f"unexpected header {magic!r} v{version}")
    names = [n for f, n in ((FLAG_BLOWFISH, "BLOWFISH"), (FLAG_HAS_ID, "HAS_ID"), (FLAG_CITRUS, "CITRUS"),
                            (FLAG_DEFLATE, "DEFLATE"), (FLAG_MANDARIN, "MANDARIN")) if flags & f]
    print(f"  flags={flags:#x} {'|'.join(names)}")
    if flags & (FLAG_BLOWFISH | FLAG_HAS_ID | FLAG_CITRUS):
        raise ValueError("flag combination not handled by this script")

    offset = 16  # 12-byte header aligned up to 16 for Mandarin
    decrypted_len = struct.unpack_from("<Q", raw, len(raw) - 12)[0]
    encrypted = raw[offset : len(raw) - 4]
    print(f"  decrypted_len={decrypted_len}")
    if decrypted_len > len(raw):  # the Mandarin payload is never larger than the file (0.33-0.99 on real saves)
        raise ValueError(f"{name}: implausible payload length {decrypted_len} for a {len(raw)}-byte file")

    payload = mandarin_decrypt(encrypted, decrypted_len, key) if flags & FLAG_MANDARIN else encrypted

    if flags & FLAG_DEFLATE:
        comp_plus_0x10, unk_one, comp_size, decomp_size = struct.unpack_from("<QIIQ", payload, 0)
        print(f"  deflate header: comp+0x10={comp_plus_0x10} unk={unk_one} comp={comp_size} decomp={decomp_size}")
        body = zlib.decompress(payload[24 : 24 + comp_size], wbits=-15)
        print(f"  inflated {len(body)} bytes ({'size OK' if len(body) == decomp_size else 'SIZE MISMATCH'})")
        if len(body) != decomp_size:
            raise ValueError(f"{name}: inflated {len(body)} bytes, header says {decomp_size}")
    else:
        body = payload

    out_path = os.path.join(out_dir, name + ".dec")
    with open(out_path, "wb") as f:
        f.write(body)
    print(f"  wrote {out_path}")
    return body


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    key = int(sys.argv[1]) & 0xFFFFFFFF  # DD2 keys on the lower 32 bits of the SteamID64
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    for p in sys.argv[3:]:
        try:
            process(p, key, out_dir)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
