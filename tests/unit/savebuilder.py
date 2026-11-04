"""Builds made-up DD2 save files for the tests: a DSSS v2 container with the Mandarin cipher (and raw Deflate), the
exact inverse of tools/dd2_decrypt.py. The cipher is a key stream XOR, so encrypting is the same stream applied to
the plain bytes. Test code only: the tools never write saves."""
import struct
import zlib

import dd2_decrypt as d


def build_save(body, account_id, deflate=True):
    key = account_id & 0xFFFFFFFF
    if deflate:
        packer = zlib.compressobj(wbits=-15)
        comp = packer.compress(body) + packer.flush()
        payload = struct.pack("<QIIQ", len(comp) + 0x10, 1, len(comp), len(body)) + comp
    else:
        payload = body
    n = len(payload)

    # the block schedule of dd2_decrypt.mandarin_decrypt
    state = d.DD2_SEED_ENC
    sizes = []
    for _ in range((1 if n & 0x3FFF else 0) + (n >> 14)):
        sizes.append((state & 7) + 1)
        state = d.splitmix_next(state)
    blocks, left = [], n
    for b in sizes:
        blocks.append(b)
        if left <= b * 0x4000:
            break
        left -= b * 0x4000
    state = (state + (~key & d.M64)) & d.M64

    out, pos = bytearray(), 0
    for b in blocks:
        size = b * 0x4000
        aes_key, iv = bytearray(16), bytearray(16)
        for j in range(16):
            state = d.splitmix_next(state)
            aes_key[j] = state & 0xFF
            iv[j] = (state >> 8) & 0xFF
        meta = bytearray(0x210)  # per-block metadata the reader skips; XORed with the stream like the real one
        for j in range(0x210):
            state = d.splitmix_next(state)
            meta[j] ^= state & 0xFF
        out += meta + d.aes128_ofb(bytes(aes_key), bytes(iv), payload[pos:pos + size].ljust(size, b"\0"))
        pos += size

    flags = d.FLAG_MANDARIN | (d.FLAG_DEFLATE if deflate else 0)
    raw = struct.pack("<4sII", b"DSSS", 2, flags) + bytes(4) + bytes(out) + struct.pack("<Q", n)
    return raw + struct.pack("<I", d.murmur3_32(raw, 0xFFFFFFFF))
