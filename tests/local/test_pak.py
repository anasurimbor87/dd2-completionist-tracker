"""The PAK reader on the installed game: plain, compressed, chunked and the one resource-encrypted entry.
Run: python tests/local/test_pak.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish, need, skip  # noqa: E402

import dd2_paths  # noqa: E402
import dd2_steam  # noqa: E402
import ree_pak  # noqa: E402

ENCRYPTED = "natives/stm/appsystem/item/itemshopdata/itemshopadditionaldata.user.3"  # the only one in the game
QUEST_TREE = "natives/stm/appsystem/quest/userdata/questtree.user.3"


def main():
    steam = dd2_steam.steam_path()
    game = dd2_steam.find_game_dir(steam) if steam else None
    if not game:
        skip("needs Dragon's Dogma 2 installed through Steam")
    need("assets", "lists")
    gf = ree_pak.GameFiles(game, os.path.join(dd2_paths.assets_dir(), "lists"))
    data = gf.read(ENCRYPTED)
    check(data[:4] == b"USR\x00" and len(data) > 64, f"the encrypted shop table decrypts to a user file ({data[:4]!r}, {len(data)} bytes)")
    tree = gf.read(QUEST_TREE)
    check(tree[:4] == b"USR\x00", "the quest tree reads")
    tex = next(n for n in gf.listed("natives/stm/gui/") if n.endswith(".tex.251211553"))
    check(gf.read(tex)[:4] == b"TEX\x00", f"a texture reads ({tex})")
    encrypted = [h for p in gf.paks for h, (_o, _c, _d, attr) in p.entries.items()
                 if (attr >> 16) & 0xFF and (attr >> 24) & 0xF != 1 and attr & 0xF]
    check(len(encrypted) == 1 and encrypted[0] == ree_pak.path_hash(ENCRYPTED),
          f"exactly one resource-encrypted entry, the shop table ({len(encrypted)})")
    finish()


if __name__ == "__main__":
    main()
