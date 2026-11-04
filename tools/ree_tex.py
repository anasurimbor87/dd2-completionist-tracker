"""RE Engine .tex reader (DD2 .tex.251211553, "Modern" serializer), mip 0 -> PIL image.

Header layout from kagenocookie/RE-Engine-Lib (REE-Lib/OtherFiles/TexFile.cs).
"""
import struct

from PIL import Image

# DXGI format -> (Pillow bcn decoder index, srgb); only block-compressed formats used by DD2 UI textures
BCN = {70: 1, 71: 1, 72: 1, 73: 2, 74: 2, 75: 2, 76: 3, 77: 3, 78: 3, 79: 4, 80: 4, 81: 4, 82: 5, 83: 5, 84: 5,
       94: 6, 95: 6, 96: 6, 97: 7, 98: 7, 99: 7}
RGBA8 = (27, 28, 29)


def read_tex(data):
    magic, version, width, height, depth, image_count, mip_header_size, fmt, swizzle, _cube, flags = \
        struct.unpack_from("<4sIHHHBBIiII", data, 0)
    if magic != b"TEX\x00":
        raise ValueError("not a TEX file")
    if swizzle != -1:
        raise ValueError(f"swizzled texture ({swizzle}) not supported")
    offset, pitch, size = struct.unpack_from("<QII", data, 40)
    raw = data[offset : offset + size]
    if fmt in BCN:
        # rows of 4x4 blocks can be padded to a larger pitch (e.g. the 1560 px item icon atlases): drop the padding
        row = (width + 3) // 4 * (8 if BCN[fmt] in (1, 4) else 16)
        if pitch > row:
            raw = b"".join(raw[r * pitch : r * pitch + row] for r in range((height + 3) // 4))
        return Image.frombytes("RGBA", (width, height), raw, "bcn", BCN[fmt])
    if fmt in RGBA8:
        return Image.frombytes("RGBA", (width, height), raw)
    raise ValueError(f"DXGI format {fmt} not supported")
