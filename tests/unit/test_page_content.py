"""The page's name, notice and tabs: DD2 Completionist Tracker with the vibe-coded footer, a Materials tab, and no
upgrade planner or Thief tips left. Run: python tests/unit/test_page_content.py"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish  # noqa: E402

FOOTER = "Vibe-coded fan project, not affiliated with Capcom."


def main():
    html = open(os.path.join(ROOT, "map", "index.html"), encoding="utf-8").read()
    js = open(os.path.join(ROOT, "map", "app.js"), encoding="utf-8").read()
    title = re.search(r"<title>(.*?)</title>", html)
    h1 = re.search(r"<h1>(.*?)</h1>", html)
    check(title and title.group(1) == "DD2 Completionist Tracker" and h1 and h1.group(1) == "DD2 Completionist Tracker",
          f"title and heading name the tracker ({title and title.group(1)}, {h1 and h1.group(1)})")
    check(FOOTER in html, "the footer says it is a vibe-coded fan project, not affiliated with Capcom")
    check('id="tab-mat"' in html and 'id="pane-mat"' in html and ">Materials<" in html, "a Materials tab")
    for gone in ('id="tab-up"', 'id="pane-up"', 'id="gear-thief"', 'id="near-tip"'):
        check(gone not in html, f"{gone} is gone from the page")
    for gone in ("renderUpgrades", "upgradePlan", "betterThanEquipped", "Thief", "STATE.equipped", "STATIC.enhance",
                 "STATE.gear", "e.upgrades"):
        check(gone not in js, f"{gone} is gone from app.js")
    check("function renderMaterials(" in js and '["materials", renderMaterials]' in js, "renderMaterials runs on each state")
    check(re.search(r'^const REPO_URL = "[^"]*";', js, re.M) is not None, "the repository link is one constant")
    # achievements: their own tab, drawn on every state, unlocked ones in the Log
    check('id="tab-ach"' in html and 'id="pane-ach"' in html and ">Achievements<" in html, "an Achievements tab")
    check('["achievements", renderAchievements]' in js and "Achievement unlocked:" in js, "achievements are drawn and logged")
    check("STATE.achievements_from" in js, "the page knows whether the list came from Steam or only from the save")
    server = open(os.path.join(ROOT, "tools", "dd2_server.py"), encoding="utf-8").read()
    check('state["achievements_from"]' in server, "the server says where the achievements came from")
    # the story timeline: its logic file loads before the page script, replaces the old phase card, ships in the exe
    scripts = re.findall(r'<script src="([^"]+)"></script>', html)
    check("timeline.js" in scripts and scripts.index("timeline.js") < scripts.index("app.js"), f"timeline.js loads before app.js ({scripts})")
    check("function timelineCard(" in js and "function phaseCard(" not in js and "phaseTimeline(" in js,
          "the Quests tab opens with the story timeline")
    check('id="tl-spoilers"' in js and 'id="q-missable"' in js, "a spoiler switch for later phases and a missable filter")
    spec = open(os.path.join(ROOT, "packaging", "tracker.spec"), encoding="utf-8").read()
    check('"timeline.js"' in spec, "the exe bundles timeline.js")
    # the setup box doesn't redraw under the player's typing; once the folder is taken the field must let go,
    # or the build's progress would stay frozen on screen
    submit = re.search(r'post\("/api/setup/game-dir".*?\n  \}\);', js, re.S)
    check(submit is not None and 'if (res.ok) $("game-dir").blur()' in submit.group(0),
          "a taken game folder releases the field so the progress shows")
    finish()


if __name__ == "__main__":
    main()
