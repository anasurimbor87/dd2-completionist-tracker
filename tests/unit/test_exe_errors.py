"""The exe has no console of its own: a start-up problem must stay readable until the player presses Enter, and a
second double-click while the tracker runs opens the running one instead of failing. Run: python tests/unit/test_exe_errors.py"""
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import dd2  # noqa: E402
import dd2_server  # noqa: E402


def run(fn):
    waited, out = [], io.StringIO()
    code = "returned"
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            dd2.run_command(fn, wait=lambda prompt: waited.append(prompt))
        except SystemExit as e:
            code = e.code
    return code, waited, out.getvalue()


def main():
    def no_save():
        sys.exit("No Dragon's Dogma 2 save found in Steam's userdata folder.")
    code, waited, text = run(no_save)
    check(code == 1 and waited and "No Dragon's Dogma 2 save found" in text, "a start-up message stays until Enter")

    def crash():
        raise ValueError("something unexpected")
    code, waited, text = run(crash)
    check(code == 1 and waited and "something unexpected" in text, "an unexpected error is shown and waits too")

    code, waited, _text = run(lambda: None)
    check(code == "returned" and not waited, "a normal end doesn't wait")
    code, waited, _text = run(lambda: sys.exit(0))
    check(code == 0 and not waited, "a clean exit doesn't wait")

    opened = []
    text = dd2_server.port_taken(8642, True, opener=opened.append)
    check(opened == ["http://127.0.0.1:8642/"] and "already running" in text,
          "a second start opens the running tracker in the browser")
    opened = []
    text = dd2_server.port_taken(8642, False, opener=opened.append)
    check(not opened and "8642" in text, "without --open it only says the port is taken")
    finish()


if __name__ == "__main__":
    main()
