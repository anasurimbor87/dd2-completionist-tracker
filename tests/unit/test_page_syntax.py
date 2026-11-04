"""The page script parses (node --check). Run: python tests/unit/test_page_syntax.py"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, skip  # noqa: E402


def main():
    node = shutil.which("node")
    if not node:
        skip("node is not installed")
    proc = subprocess.run([node, "--check", os.path.join(ROOT, "map", "app.js")], capture_output=True, text=True)
    check(proc.returncode == 0, f"map/app.js parses {proc.stderr.strip()}")
    finish()


if __name__ == "__main__":
    main()
