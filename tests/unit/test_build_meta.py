"""When the map data must be built (first start, interrupted build) or rebuilt (game update), and that a build never
clears a folder that is a link to somewhere else. Run: python tests/unit/test_build_meta.py"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import dd2_build  # noqa: E402


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def main():
    check(dd2_build.STEPS == ["Reading game files", "Items and quests", "Map tiles", "Dungeon maps", "Map data"],
          "five build steps")
    with tempfile.TemporaryDirectory() as data:
        meta, static = os.path.join(data, "gamedata", "meta.json"), os.path.join(data, "map", "data", "static.json")
        check(dd2_build.needs_setup(data), "an empty data folder needs the build")
        write(static, {})
        check(dd2_build.needs_setup(data), "map data without meta.json (an interrupted build) needs the build again")
        write(meta, {"buildid": "1", "built": "2026-01-01T00:00:00"})
        check(dd2_build.needs_setup(data), "map data from a tracker without a data format number needs the build again")
        write(meta, {"buildid": "1", "built": "2026-01-01T00:00:00", "format": dd2_build.DATA_FORMAT - 1})
        check(dd2_build.needs_setup(data), "map data in an older data format needs the build again")
        write(meta, {"buildid": "1", "built": "2026-01-01T00:00:00", "format": dd2_build.DATA_FORMAT})
        check(not dd2_build.needs_setup(data), "a finished build in the current format needs nothing")
        check(dd2_build.outdated(data, "2"), "another game build id: outdated")
        check(not dd2_build.outdated(data, "1"), "the same build id: up to date")
        check(not dd2_build.outdated(data, None), "an unknown game build id: not called outdated")
        write(meta, {"buildid": None, "built": "2026-01-01T00:00:00"})
        check(not dd2_build.outdated(data, "2"), "a build made without a build id: not called outdated")

        target, link = os.path.join(data, "real"), os.path.join(data, "linked")
        os.makedirs(target)
        write(os.path.join(target, "keep.json"), {})
        made = subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True).returncode == 0
        if made:
            try:
                dd2_build._clear(link)
                refused = False
            except RuntimeError:
                refused = True
            check(refused and os.path.exists(os.path.join(target, "keep.json")), "a linked folder is never cleared")
            os.rmdir(link)
        own = os.path.join(data, "own")
        write(os.path.join(own, "x.json"), {})
        dd2_build._clear(own)
        check(not os.path.exists(own), "a plain folder is cleared")
        dd2_build._clear(os.path.join(data, "absent"))
        check(True, "clearing a folder that doesn't exist is fine")
    finish()


if __name__ == "__main__":
    main()
