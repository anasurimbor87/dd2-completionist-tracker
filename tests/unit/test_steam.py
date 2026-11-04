"""Finding Steam, the game, its build id and the accounts with saves, on a made-up Steam folder.
Run: python tests/unit/test_steam.py"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import dd2_steam  # noqa: E402


def touch(path, text="", mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    if mtime:
        os.utime(path, (mtime, mtime))


def vdf(*libs):
    body = "".join(f'\t"{i}"\n\t{{\n\t\t"path"\t\t"{lib.replace(chr(92), chr(92) * 2)}"\n\t}}\n' for i, lib in enumerate(libs))
    return '"libraryfolders"\n{\n' + body + "}\n"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        steam, lib2 = os.path.join(tmp, "Steam"), os.path.join(tmp, "Library Two")
        game = os.path.join(lib2, "steamapps", "common", "Dragons Dogma 2")
        touch(os.path.join(steam, "steamapps", "libraryfolders.vdf"), vdf(steam, lib2))
        touch(os.path.join(game, "DD2.exe"))
        touch(os.path.join(game, "re_chunk_000.pak"))
        touch(os.path.join(lib2, "steamapps", "appmanifest_2054970.acf"),
              '"AppState"\n{\n\t"appid"\t\t"2054970"\n\t"buildid"\t\t"16520194"\n}\n')
        now = time.time()
        saves = lambda a: os.path.join(steam, "userdata", a, "2054970", "remote", "win64_save")
        touch(os.path.join(saves("111"), "data001Slot.bin"), mtime=now - 100)
        touch(os.path.join(saves("222"), "data005Slot.bin"), mtime=now)
        touch(os.path.join(saves("333"), "SS1_settings.bin"))  # an account that never saved a game
        os.makedirs(os.path.join(steam, "userdata", "0"))

        accounts = dd2_steam.save_accounts(steam)
        check(accounts and accounts[0][0] == 222, f"the account with the newest slot save comes first ({accounts})")
        check([a for a, _d, _t in accounts] == [222, 111], "an account without a DD2 save is left out")
        check(os.path.normpath(accounts[0][1]) == os.path.normpath(saves("222")), "each account comes with its save folder")
        check(dd2_steam.find_game_dir(steam) == os.path.normpath(game), "the game is found in the second library folder")
        check(dd2_steam.game_build_id(steam) == "16520194", "the build id is read from the app manifest")
        check(dd2_steam.valid_game_dir(f'"{game}\\"  ') == os.path.normpath(game), "quotes and a trailing backslash are fine")
        check(dd2_steam.valid_game_dir(lib2) is None, "a folder without DD2.exe is refused")
        check(dd2_steam.valid_game_dir("") is None, "an empty answer is refused")

        bare = os.path.join(tmp, "BareSteam")
        touch(os.path.join(bare, "steamapps", "libraryfolders.vdf"), vdf(bare))
        check(dd2_steam.game_build_id(bare) is None and dd2_steam.find_game_dir(bare) is None,
              "no game and no manifest: no build id, no game folder, no error")
        check(dd2_steam.save_accounts(bare) == [], "no userdata: no accounts")
        os.environ["DD2_STEAM_DIR"] = steam
        check(dd2_steam.steam_path() == steam, "DD2_STEAM_DIR overrides the registry")
    finish()


if __name__ == "__main__":
    main()
