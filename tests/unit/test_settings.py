"""The player's saved choices (DATA_DIR/settings.json): read back, merged on save, a damaged file counts as empty.
Run: python tests/unit/test_settings.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import dd2_paths  # noqa: E402
import dd2_settings  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as tmp:
        dd2_paths.DATA_DIR = tmp
        check(dd2_settings.load() == {}, "no settings file: no choices")
        dd2_settings.save({"account_id": 222})
        dd2_settings.save({"game_dir": "D:\Games\Dragons Dogma 2"})
        check(dd2_settings.load() == {"account_id": 222, "game_dir": "D:\Games\Dragons Dogma 2"}, "choices merge and read back")
        with open(os.path.join(tmp, "settings.json"), "w") as f:
            f.write('{"account_id": 2')
        check(dd2_settings.load() == {}, "a damaged file counts as no choices")
        check(not os.path.exists(os.path.join(tmp, "settings.json.new")), "no temporary file is left behind")
    finish()


if __name__ == "__main__":
    main()
