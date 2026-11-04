"""The player's choices that outlive a restart (DATA_DIR/settings.json): which Steam account to read and where the
game is when Steam doesn't say. A missing or damaged file counts as no choices."""
import json
import os

import dd2_paths


def _path():
    return os.path.join(dd2_paths.DATA_DIR, "settings.json")


def load():
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(updates):
    data = dict(load(), **updates)
    tmp = _path() + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, _path())
    return data
