"""Finds Steam, Dragon's Dogma 2 and the accounts with DD2 saves. Read-only: it only lists folders and reads Steam's
small text files (libraryfolders.vdf, the app manifest)."""
import glob
import os
import re

APPID = "2054970"
GAME_FOLDER = "Dragons Dogma 2"


def steam_path():
    """DD2_STEAM_DIR when set (tests, unusual setups), else Steam's folder from the registry, else None"""
    if os.environ.get("DD2_STEAM_DIR"):
        return os.environ["DD2_STEAM_DIR"]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return winreg.QueryValueEx(k, "SteamPath")[0]
    except (ImportError, OSError):
        return None


def library_dirs(steam):
    """Steam's own folder and every library folder listed in libraryfolders.vdf"""
    libs = [os.path.normpath(steam)]
    try:
        with open(os.path.join(steam, "steamapps", "libraryfolders.vdf"), encoding="utf-8") as f:
            vdf = f.read()
    except OSError:
        return libs
    for p in re.findall(r'"path"\s+"([^"]+)"', vdf):
        p = os.path.normpath(p.replace("\\\\", "\\"))
        if p not in libs:
            libs.append(p)
    return libs


def _is_game_dir(d):
    return os.path.isfile(os.path.join(d, "DD2.exe")) and os.path.isfile(os.path.join(d, "re_chunk_000.pak"))


def find_game_dir(steam):
    for lib in library_dirs(steam):
        d = os.path.join(lib, "steamapps", "common", GAME_FOLDER)
        if _is_game_dir(d):
            return os.path.normpath(d)
    return None


def game_build_id(steam):
    """the game's build id from Steam's app manifest; it changes with every game update"""
    for lib in library_dirs(steam):
        try:
            with open(os.path.join(lib, "steamapps", f"appmanifest_{APPID}.acf"), encoding="utf-8") as f:
                m = re.search(r'"buildid"\s+"(\d+)"', f.read())
        except OSError:
            continue
        if m:
            return m.group(1)
    return None


def save_accounts(steam):
    """[(account id, save folder, mtime of its newest slot save)] for accounts with DD2 slot saves, newest first"""
    out = []
    for d in glob.glob(os.path.join(glob.escape(steam), "userdata", "*", APPID, "remote", "win64_save")):
        folder = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(d))))
        slots = glob.glob(os.path.join(glob.escape(d), "data*Slot.bin"))
        if folder.isdigit() and slots:
            out.append((int(folder), os.path.normpath(d), max(os.path.getmtime(s) for s in slots)))
    return sorted(out, key=lambda a: -a[2])


def valid_game_dir(text):
    """a game folder typed or pasted by the player (quotes, spaces, a trailing backslash are fine), or None"""
    d = (text or "").strip().strip('"').strip("'").strip()
    if not d:
        return None
    d = os.path.normpath(d)
    return d if _is_game_dir(d) else None
