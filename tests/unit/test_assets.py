"""Pinned third-party data (tools/dd2_assets.py): files land only when their SHA-256 matches the lock.
Run: python tests/unit/test_assets.py"""
import hashlib
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish  # noqa: E402

import dd2_assets  # noqa: E402

GOOD, BAD = b'{"made": "up"}', b'{"made": "up", "but": "changed"}'


def entry(name, data):
    return {"name": name, "repo": "someone/somerepo", "commit": "0" * 40, "path": "data/" + name.split("/")[-1],
            "sha256": hashlib.sha256(data).hexdigest(), "licence": "MIT"}


def main():
    served = {}

    def opener(url, timeout=None):
        served.setdefault("urls", []).append(url)
        return io.BytesIO(served["bodies"][url.rsplit("/", 1)[-1]])

    with tempfile.TemporaryDirectory() as tmp:
        lock = [entry("one.json", GOOD), entry("lists/two.list", GOOD)]
        served["bodies"] = {"one.json": GOOD, "two.list": GOOD}
        check(sorted(dd2_assets.missing(lock, tmp)) == ["lists/two.list", "one.json"], "absent files are missing")
        written = dd2_assets.fetch(lock, tmp, opener=opener)
        check(sorted(written) == ["lists/two.list", "one.json"], f"both files are written ({written})")
        check(open(os.path.join(tmp, "lists", "two.list"), "rb").read() == GOOD, "a file lands in its subfolder")
        check(served["urls"][0] == "https://raw.githubusercontent.com/someone/somerepo/" + "0" * 40 + "/data/one.json",
              f"files come from the pinned commit ({served['urls'][0]})")
        check(dd2_assets.missing(lock, tmp) == [] and dd2_assets.fetch(lock, tmp, opener=opener) == [],
              "files already in place are not fetched again")

        bad = [entry("three.json", GOOD)]
        served["bodies"]["three.json"] = BAD
        try:
            dd2_assets.fetch(bad, tmp, opener=opener)
            err = None
        except ValueError as e:
            err = str(e)
        check(err is not None and "three.json" in err, f"a changed file is refused by name ({err})")
        check(not any(n.startswith("three.json") for n in os.listdir(tmp)), "and leaves neither the file nor a .part")
        with open(os.path.join(tmp, "one.json"), "wb") as f:
            f.write(BAD)
        check(dd2_assets.missing(lock, tmp) == ["one.json"], "a file with the wrong hash counts as missing")

        path = os.path.join(tmp, "lock.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"files": lock}, f)
        check(dd2_assets.load_lock(path) == lock, "the lock file reads back")
    real = dd2_assets.load_lock(os.path.join(ROOT, "assets.lock.json"))
    names = {e["name"] for e in real}
    check(names == {"rszdd2.json", "enumsdd2.json", "rszdd2_dlc.json", "enumsdd2_dlc.json", "lists/DD2_STM.list"},
          f"the project's lock pins the five files ({sorted(names)})")
    check(all(len(e["commit"]) == 40 and len(e["sha256"]) == 64 and e["licence"] in ("MIT", "GPL-3.0") for e in real),
          "each with a full commit, a SHA-256 and its licence")
    finish()


if __name__ == "__main__":
    main()
