"""Where the tracker's files live.

APP_DIR holds the code and the page (map/index.html, app.js, ...): the repository when run from source, the unpacked
bundle when frozen into an exe. DATA_DIR is where everything is written: the program's folder (portable: next to the
exe, or the repository), or DD2_DATA_DIR when set. Nothing is ever written to the game or the Steam save folder."""
import os
import sys
import tempfile

FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = getattr(sys, "_MEIPASS", None) if FROZEN else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.abspath(os.environ.get("DD2_DATA_DIR")
                           or (os.path.dirname(sys.executable) if FROZEN else APP_DIR))


def page_dir():
    """the page's own files (index.html, app.js, style.css, vendor/)"""
    return os.path.join(APP_DIR, "map")


def map_out_dir():
    """map files built from the game: tiles/, dungeons/, data/static.json"""
    return os.path.join(DATA_DIR, "map")


def assets_dir():
    """the pinned third-party data (assets.lock.json): bundled with the exe, fetched next to the code from source;
    it stays there when DD2_DATA_DIR moves the data elsewhere"""
    return os.path.join(APP_DIR, "assets")


def check_writable():
    """None when DATA_DIR can be written, else a message for the player"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with tempfile.TemporaryFile(dir=DATA_DIR):
            pass
        return None
    except OSError:
        return (f"Can't write to {DATA_DIR}. Move the DD2 Completionist Tracker folder somewhere you can write to, "
                f"such as your Documents folder, and start it again.")
