"""The Windows program ships Python, cryptography (with OpenSSL), Pillow and PyInstaller's bootloader: their licence
texts go into licenses/ next to the exe (packaging/licences.py). Run: python tests/unit/test_licences.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "packaging"))
import licences  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as dest:
        copied, missing = licences.collect(dest, ("cryptography", "pillow", "no-such-package"))
        names = sorted(os.listdir(dest))
        text = {n: open(os.path.join(dest, n), encoding="utf-8", errors="replace").read() for n in names}
        check(any(n.startswith("python") and "PYTHON SOFTWARE FOUNDATION" in t.upper() for n, t in text.items()),
              f"Python's licence is included ({names})")
        check(any(n.startswith("cryptography") and "Apache License" in t for n, t in text.items()),
              "cryptography's Apache licence is included")
        check(any(n.startswith("pillow") for n in names), "Pillow's licence is included")
        check(missing == ["no-such-package"], f"a package that isn't installed is reported, not skipped silently ({missing})")
        check(len(copied) == len(names), "every copied file is listed")
    finish()


if __name__ == "__main__":
    main()
