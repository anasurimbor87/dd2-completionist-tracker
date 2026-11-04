"""The Quests tab's story timeline (map/timeline.js, run in node): each missable quest sits under the point of no
return that closes it, with its state; quests that never close are listed apart. Made-up quests only.
Run: python tests/unit/test_timeline.py"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, skip  # noqa: E402

HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const ctx = {};
vm.runInNewContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const a = JSON.parse(fs.readFileSync(0, "utf8"));
console.log(JSON.stringify(ctx.phaseTimeline(a.quests, a.phases, a.results, a.statuses, a.closed)));
"""

PHASES = [[11010, 1], [11020, 2]]  # phase quest, the main quest whose end ends it
QUESTS = {
    "1": {"t": "Main One", "o": 0, "opens": None, "ends": []},
    "2": {"t": "Main Two", "o": 2, "opens": [1, 0], "ends": []},
    "11010": {"t": "", "o": 0, "opens": None, "ends": []},
    "3": {"t": "Done Early", "o": 1, "opens": None, "ends": [[11010, 0, 1]]},
    "7": {"t": "Missed Early", "o": 1, "opens": None, "ends": [[11010, 0, 1]]},
    "8": {"t": "Running Early", "o": 1, "opens": None, "ends": [[11010, 0, 1], [11020, 0, 2]]},
    "4": {"t": "Open Now", "o": 1, "opens": [1, 0], "ends": [[11020, 0, 2]]},
    "9": {"t": "Opens Later", "o": 3, "opens": [2, 0], "ends": [[11020, 0, 2]]},
    "6": {"t": "Closed By Side", "o": 1, "opens": None, "ends": [[30, 0, 30]]},
    "30": {"t": "Side Closer", "o": 1, "opens": None, "ends": []},
    "5": {"t": "Forever", "o": 0, "opens": None, "ends": []},
}


def run(results, statuses, closed):
    node = shutil.which("node")
    if not node:
        skip("node is not installed")
    harness = os.path.join(os.environ.get("TEMP", "."), "dd2_timeline_harness.js")
    with open(harness, "w", encoding="utf-8") as f:
        f.write(HARNESS)
    args = {"quests": QUESTS, "phases": PHASES, "results": results, "statuses": statuses, "closed": closed}
    proc = subprocess.run([node, harness, os.path.join(ROOT, "map", "timeline.js")], input=json.dumps(args),
                          capture_output=True, text=True)
    if proc.returncode:
        return {"error": proc.stderr.strip()[-300:]}
    return json.loads(proc.stdout)


def main():
    t = run({"1": 0, "11010": 0}, {"3": "Complete", "8": "Progressing"}, {"7": [11010, 0, 1]})
    check("error" not in t, f"the timeline runs ({t.get('error')})")
    phases = t.get("phases", [])
    check(t.get("current") == 1 and len(phases) == 2, f"the first phase is over, the second is current ({t.get('current')})")
    first = {q["id"]: q["status"] for q in phases[0]["quests"]} if phases else {}
    check(first == {"3": "done", "7": "missed", "8": "active"}, f"phase 1's missables with their states ({first})")
    second = {q["id"]: q["status"] for q in phases[1]["quests"]} if len(phases) > 1 else {}
    check(second == {"4": "open", "9": "later", "6": "open"}, f"phase 2: open now, opens later, closed by a side quest ({second})")
    check(phases and phases[0]["main"] == 1 and phases[1]["main"] == 2, "each phase names the main quest that ends it")
    check([q["id"] for q in phases[1]["quests"]] == ["6", "4", "9"] if len(phases) > 1 else False,
          "quests are in story order, ties by title")
    always = [q["id"] for q in t.get("always", [])]
    check(sorted(always) == ["1", "2", "30", "5"], f"titled quests that never close stand apart ({always})")
    check(not any(q["id"] == "11010" for p in phases for q in p["quests"]) and "11010" not in always, "untitled steps are left out")

    fresh = run({}, {}, {})
    check(fresh.get("current") is None, "without quest results there is no current phase")
    over = run({"1": 0, "11010": 0, "2": 0, "11020": 0}, {}, {})
    check(over.get("current") == 2, "after the last phase the story is over")
    finish()


if __name__ == "__main__":
    main()
