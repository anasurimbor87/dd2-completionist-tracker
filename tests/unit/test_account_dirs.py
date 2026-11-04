"""Each Steam account keeps its own save log, save copies and backups: the first account the tracker read keeps
work/ itself (so an existing log carries over), every other account gets work/accounts/<id>/.
Run: python tests/unit/test_account_dirs.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import dd2_server  # noqa: E402

ROOT = os.path.join("C:", os.sep, "data")


def main():
    work = os.path.join(ROOT, "work")
    live, backups, log = dd2_server.account_dirs(ROOT, "live", 111111, 111111)
    check((live, backups, log) == (os.path.join(work, "live"), os.path.join(work, "backups"), work),
          "the first account keeps work/ as before")
    other = os.path.join(work, "accounts", "222222")
    live, backups, log = dd2_server.account_dirs(ROOT, "live", 222222, 111111)
    check((live, backups, log) == (os.path.join(other, "live"), os.path.join(other, "backups"), other),
          "another account gets its own log, copies and backups")
    live, backups, log = dd2_server.account_dirs(ROOT, "test", 111111, 111111)
    check((live, backups, log) == (os.path.join(work, "test"), os.path.join(work, "test_backups"), os.path.join(work, "test")),
          "a test server keeps its own folders")
    check(dd2_server.account_dirs(ROOT, "live", 5, None)[2] == work, "without a first account yet, work/ is used")
    finish()


if __name__ == "__main__":
    main()
