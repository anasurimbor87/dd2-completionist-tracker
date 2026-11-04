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
const later = (current) => Object.keys(a.quests).filter((id) => ctx.timelineLaterMain(a.quests, a.phases, current, id));
console.log(JSON.stringify({ ...ctx.phaseTimeline(a.quests, a.phases, a.results, a.statuses, a.closed),
  laterMains: { none: later(null), first: later(0), second: later(1) } }));
"""

# ids like the game's: 1xxxx main quests, 11010.. the hidden phase steps, 2xxxx side quests, 3xxxx world quests
# phase quest, the main quest whose end ends it; like the game's, the last phase ends with an untitled step
PHASES = [[11010, 10010], [11020, 10030], [11030, 10099]]
QUESTS = {
    "10010": {"t": "Main One", "o": 0, "opens": None, "ends": []},
    "10020": {"t": "Main Mid", "o": 1, "opens": [10010, 0], "ends": []},
    "10030": {"t": "Main Two", "o": 2, "opens": [10020, 0], "ends": []},
    "10040": {"t": "Main Outside The Tree", "opens": None, "ends": []},  # no story order: where it goes is unknown
    "11010": {"t": "", "o": 0, "opens": None, "ends": []},
    "20030": {"t": "Done Early", "o": 1, "opens": None, "ends": [[11010, 0, 10010]]},
    "20070": {"t": "Missed Early", "o": 1, "opens": None, "ends": [[11010, 0, 10010]]},
    "20080": {"t": "Running Early", "o": 1, "opens": None, "ends": [[11010, 0, 10010], [11020, 0, 10030]]},
    "20085": {"t": "Overtaken", "o": 1, "opens": None, "ends": [[11010, 0, 10010]]},
    "30005": {"t": "Early Side Closer", "o": 0, "opens": None, "ends": [[11010, 0, 10010]]},
    "20040": {"t": "Open Now", "o": 1, "opens": [10010, 0], "ends": [[11020, 0, 10030]]},
    "20090": {"t": "Opens Later", "o": 2, "opens": [10020, 0], "ends": [[11020, 0, 10030]]},
    # finishing a main quest is sure to happen: closes in the phase that main quest belongs to, before its end
    "20060": {"t": "Closed By Main", "o": 1, "opens": None, "ends": [[10020, 0, 10020]]},
    "30010": {"t": "Side Closer", "o": 1, "opens": None, "ends": [[11020, 0, 10030]]},
    # sure to close at phase 2's end, sooner if you finish a side quest that can only be done in phase 1
    "20055": {"t": "Late Or Via Side", "o": 1, "opens": None, "ends": [[11020, 0, 10030], [30005, 0, 30005]]},
    # only a side quest that never closes can close it: no point of no return, but it can be missed
    "20120": {"t": "Only Side Closed", "o": 5, "opens": None, "ends": [[20391, 1, 20390]]},
    # its own other outcome (a hidden step of its own) is how it ends, not something that closes it
    "20390": {"t": "Never Closing Side", "o": 4, "opens": None, "ends": [[20391, 1, 20390]]},
    "20005": {"t": "Forever", "o": 0, "opens": None, "ends": []},
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


def states(group):
    return {q["id"]: q["status"] for q in group}


def main():
    gone = [11010, 0, 10010]
    t = run({"10010": 0, "11010": 0}, {"20030": "Complete", "20080": "Progressing", "20085": "Progressing"},
            {"20070": gone, "20085": gone, "30005": gone})
    check("error" not in t, f"the timeline runs ({t.get('error')})")
    phases = t.get("phases", [])
    check(t.get("current") == 1 and len(phases) == 3, f"the first phase is over, the second is current ({t.get('current')})")
    first = states(phases[0]["quests"]) if phases else {}
    check(first == {"20030": "done", "20070": "missed", "20080": "active", "20085": "passed", "30005": "missed"},
          f"phase 1's missables with their states; a started quest the story moved past is 'passed' ({first})")
    second = states(phases[1]["quests"]) if len(phases) > 1 else {}
    check(second == {"20040": "open", "20090": "later", "20060": "open", "30010": "open", "20055": "open"},
          f"phase 2: open now, opens later, closed by a main quest of phase 2, closed at the end ({second})")
    check(phases and phases[0]["main"] == 10010 and phases[1]["main"] == 10030, "each phase names the main quest that ends it")
    check([q["id"] for q in phases[1]["quests"]] == ["20060", "20055", "20040", "30010", "20090"] if len(phases) > 1 else False,
          "quests are in story order, ties by title")
    side = states(t.get("side", []))
    check(side == {"20120": "open"}, f"a quest only a side quest can close has a group of its own ({side})")
    always = sorted(q["id"] for q in t.get("always", []))
    check(always == ["20005", "20390"], f"only side quests that never close stand apart, main quests are left out ({always})")
    check(not any(q["id"] == "11010" for p in phases for q in p["quests"]) and "11010" not in always, "untitled steps are left out")

    fresh = run({}, {}, {})
    check(fresh.get("current") is None, "without quest results there is no current phase")
    early = [q["id"] for q in fresh.get("phases", [{}])[0].get("quests", [])]
    check("20055" in early, f"while the side quest that closes it can still be done, a quest counts in that side quest's phase ({early})")
    over = run({"10010": 0, "11010": 0, "10030": 0, "11020": 0, "11030": 0}, {}, {})
    check(over.get("current") == 3, "after the last phase the story is over")

    later = t.get("laterMains", {})
    check(later.get("none") == ["10020", "10030"] and later.get("first") == ["10020", "10030"],
          f"before the story starts and in phase 1, the main quests of phase 2 are later story quests ({later})")
    check(later.get("second") == [], f"in phase 2 no main quest is a later one ({later.get('second')})")
    finish()


if __name__ == "__main__":
    main()
