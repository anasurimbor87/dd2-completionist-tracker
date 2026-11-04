"""Shared helpers for the test scripts. Each script runs on its own (python tests/run.py runs them all):
check() per assertion, finish() at the end, skip() when the inputs a script needs are missing.

Local tests (tests/local) read real game data and saves. Values that hold for one playthrough only (slot names,
counts, character names) live in tests/local/expectations.json, which is never committed: without it those checks are
left out and the script says so with a NOTE line."""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
EXPECTATIONS = os.path.join(ROOT, "tests", "local", "expectations.json")

_failures = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        _failures.append(msg)


def finish():
    print(f"\n{len(_failures)} failure(s)")
    sys.exit(1 if _failures else 0)


def skip(reason):
    print(f"SKIP {reason}")
    sys.exit(0)


def note(text):
    print(f"NOTE {text}")


def expected(section):
    """this playthrough's values for one test (tests/local/expectations.json), or None"""
    if not os.path.exists(EXPECTATIONS):
        return None
    with open(EXPECTATIONS, encoding="utf-8") as f:
        return json.load(f).get(section)


def playthrough(section):
    """expected(section), with a NOTE when it is missing"""
    exp = expected(section)
    if exp is None:
        note(f"checks of one playthrough left out (no '{section}' in tests/local/expectations.json)")
    return exp


def need(*parts):
    """ROOT/<parts>, or skip the script when it doesn't exist"""
    path = os.path.join(ROOT, *parts)
    if not os.path.exists(path):
        skip(f"needs {'/'.join(parts)} (built by dd2.py gamedata / dd2.py map, or a dd2.py refresh run)")
    return path


def latest_run():
    """the newest work/<timestamp> folder of dd2.py refresh with decrypted saves, or skip"""
    runs = sorted(d for d in glob.glob(os.path.join(ROOT, "work", "[0-9][0-9][0-9][0-9]-*"))
                  if os.path.isdir(os.path.join(d, "decrypted")))
    if not runs:
        skip("needs a decrypted save under work/ (run dd2.py refresh)")
    return runs[-1]


def load_json(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return json.load(f)


def slot_records(dec_dir, slot):
    """the records of one decrypted slot save, by type"""
    return {r.get("$type"): r for r in load_json(dec_dir, slot + ".json")}


def fixture(name):
    """tests/fixtures/<name>: made-up data only (no game files, no game text)"""
    return load_json(ROOT, "tests", "fixtures", name)


def fixture_records():
    """the made-up save of tests/fixtures/save_records.json, by type (as dd2_parse would give it)"""
    return {r["$type"]: r for r in fixture("save_records.json")}
