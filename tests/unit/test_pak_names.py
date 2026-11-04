"""The PAK file-name index cache follows the lists' content, not their dates: unzipping a new version over an old
folder can leave a list older than the cache. Run: python tests/unit/test_pak_names.py"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import ree_pak  # noqa: E402

OLD, NEW = "natives/stm/made/up/old.user.3", "natives/stm/made/up/new.user.3"


def main():
    with tempfile.TemporaryDirectory() as lists:
        path = os.path.join(lists, "DD2_STM.list")
        with open(path, "w", encoding="utf-8") as f:
            f.write(OLD + "\n")
        names = ree_pak.GameFiles._load_names(lists)
        check(names.get(ree_pak.path_hash(OLD)) == OLD, "the list is indexed")
        with open(path, "w", encoding="utf-8") as f:
            f.write(NEW + "\n")
        past = time.time() - 3600
        os.utime(path, (past, past))  # older than the cache, as after unzipping an update
        names = ree_pak.GameFiles._load_names(lists)
        check(names.get(ree_pak.path_hash(NEW)) == NEW and ree_pak.path_hash(OLD) not in names,
              "a changed list is indexed again even when its date is older than the cache")
        check(ree_pak.GameFiles._load_names(lists) == names, "an unchanged list reuses the cache")
    finish()


if __name__ == "__main__":
    main()
