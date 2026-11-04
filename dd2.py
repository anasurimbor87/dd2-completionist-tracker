"""DD2 Completionist Tracker - reads Dragon's Dogma 2 saves, never writes them.

usage:
  .venv\\Scripts\\python dd2.py refresh   copy the Steam save folder, decrypt it, extract quest state
  .venv\\Scripts\\python dd2.py quests    print quest state of the latest refresh
  .venv\\Scripts\\python dd2.py gamedata  (re)build quest/item/loot tables from the game files (after game updates)
  .venv\\Scripts\\python dd2.py report    write work\\<latest>\\report.md (quests, unique gear, missed chests)
  .venv\\Scripts\\python dd2.py map       build the map (tiles + data) from the game files; run after gamedata
  .venv\\Scripts\\python dd2.py build     everything from scratch, as on the first start (game tables, tiles, dungeons, map data)
  .venv\\Scripts\\python dd2.py serve [port] [--open] [--lan] [--account <id>]   start the live map at http://127.0.0.1:8642/ (follows your saves);
                                                    --lan also serves it to phones on your home network
  .venv\\Scripts\\python dd2.py backfill-log   rebuild the save log (work\\session_log.jsonl) from the save copies on disk
  .venv\\Scripts\\python dd2.py fetch-assets [--to <dir>]   download the pinned third-party data (assets.lock.json)

Several Steam accounts with DD2 saves: the newest save wins; --account <id> (or the choice made on the page) picks one.
Never writes to the Steam save folder or the game; everything goes to the data folder (this one, or DD2_DATA_DIR).
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))

import dd2_build  # noqa: E402
import dd2_decrypt  # noqa: E402
import dd2_parse  # noqa: E402
import dd2_paths  # noqa: E402
import dd2_quests  # noqa: E402
import dd2_report  # noqa: E402
import dd2_settings  # noqa: E402
import dd2_steam  # noqa: E402

ROOT = dd2_paths.DATA_DIR  # everything written goes here
WORK = os.path.join(ROOT, "work")
ASSETS = dd2_paths.assets_dir()
ASSETS_LOCK = os.path.join(dd2_paths.APP_DIR, "assets.lock.json")
GAMEDATA = os.path.join(ROOT, "gamedata")


def _option(name):
    """the value after --name on the command line, or None"""
    args = sys.argv[2:]
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def find_save_dir():
    """(save folder, Steam account id): --account, else the account chosen on the page, else the newest save"""
    steam = dd2_steam.steam_path()
    accounts = dd2_steam.save_accounts(steam) if steam else []
    if not accounts:
        sys.exit("No Dragon's Dogma 2 save found in Steam's userdata folder. Start the game and save once.")
    asked = _option("--account")
    want = asked or dd2_settings.load().get("account_id")
    for account, save_dir, _t in accounts:
        if want is not None and str(want) == str(account):
            return save_dir, account
    if asked:
        sys.exit(f"Steam account {asked} has no DD2 saves; accounts with saves: {', '.join(str(a) for a, _d, _t in accounts)}")
    return accounts[0][1], accounts[0][0]


def game_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DD2.exe", "/NH"], capture_output=True, text=True).stdout
    return "DD2.exe" in out


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def refresh():
    if game_running():
        sys.exit("DD2.exe is running - close the game first.")
    save_dir, account_id = find_save_dir()
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    run_dir = os.path.join(WORK, stamp)
    copy_dir = os.path.join(run_dir, "win64_save")
    dec_dir = os.path.join(run_dir, "decrypted")
    shutil.copytree(save_dir, copy_dir)
    for name in os.listdir(copy_dir):
        if sha256(os.path.join(copy_dir, name)) != sha256(os.path.join(save_dir, name)):
            sys.exit(f"copy mismatch for {name}")
    print(f"copied {save_dir} -> {copy_dir} (hashes verified)")

    os.makedirs(dec_dir)
    slots = []
    for name in sorted(os.listdir(copy_dir)):
        if name.startswith("SS1_"):  # screenshot/settings-only files
            continue
        try:
            dd2_decrypt.process(os.path.join(copy_dir, name), account_id, dec_dir)
            if "Slot" in name:
                slots.append(os.path.join(dec_dir, name + ".dec"))
        except Exception as e:
            print(f"  FAILED {name}: {type(e).__name__}: {e}")

    names = dd2_parse.load_names(ASSETS)
    for dec in sorted(glob.glob(os.path.join(dec_dir, "*.dec"))):
        if os.path.basename(dec).startswith("data000"):  # pre-2026 normal save, superseded
            continue
        root_type, records = dd2_parse.parse_records(open(dec, "rb").read(), names)
        bad = sum(dd2_parse._has_error(r) for r in records)
        print(f"  {os.path.basename(dec)}: {root_type}, {len(records)} records ({bad} with parse errors)")
        with open(dec[: -len(".bin.dec")] + ".json", "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=1)

    sys.argv = ["dd2_quests", ASSETS, dec_dir] + slots
    dd2_quests.main()
    with open(os.path.join(WORK, "latest.txt"), "w") as f:
        f.write(stamp)
    print(f"done: {run_dir}")


def latest_dir():
    with open(os.path.join(WORK, "latest.txt")) as f:
        return os.path.join(WORK, f.read().strip())


def quests():
    run_dir = latest_dir()
    copy_dir = os.path.join(run_dir, "win64_save")
    files = sorted(glob.glob(os.path.join(run_dir, "decrypted", "*.quests.json")),
                   key=lambda p: os.path.getmtime(os.path.join(copy_dir, os.path.basename(p).split(".")[0] + ".bin")),
                   reverse=True)
    for path in files:
        q = json.load(open(path))
        name = os.path.basename(path).split(".")[0]
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(os.path.join(copy_dir, name + ".bin"))))
        print(f"== {name} (saved {mtime})")
        for l in q["log"]:
            print(f"   {l['QuestId']:6} {l['QuestIdName']:10} {l['StatusName']}")


def find_game_dir():
    game = dd2_steam.valid_game_dir(dd2_settings.load().get("game_dir", ""))
    steam = dd2_steam.steam_path()
    game = game or (dd2_steam.find_game_dir(steam) if steam else None)
    if not game:
        sys.exit("Dragon's Dogma 2 install not found. Start the tracker and enter the game folder on the page.")
    return game


def _progress(step, name):
    print(f"[{step + 1}/{len(dd2_build.STEPS)}] {name}...")


def gamedata():
    dd2_build.build_gamedata(find_game_dir(), ASSETS, ROOT)


def report():
    run_dir = latest_dir()
    dec_dir = os.path.join(run_dir, "decrypted")
    copy_dir = os.path.join(run_dir, "win64_save")
    slot = max(glob.glob(os.path.join(copy_dir, "data*Slot.bin")), key=os.path.getmtime)
    name = os.path.basename(slot)[: -len(".bin")]
    records = {r.get("$type"): r for r in json.load(open(os.path.join(dec_dir, name + ".json"), encoding="utf-8"))}
    quests_json = json.load(open(os.path.join(dec_dir, name + ".quests.json"), encoding="utf-8"))
    q, items, loot, places, shop = dd2_report.load_gamedata(GAMEDATA)
    saved = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(slot)))
    text = (f"# DD2 save report – {name} (saved {saved})\n\n" + dd2_report.quest_report(quests_json, q) + "\n"
            + dd2_report.gear_report(records, items, loot, places, shop) + "\n")
    out = os.path.join(run_dir, "report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {out}")


def build_map():
    static = dd2_build.build_map(find_game_dir(), ASSETS, ROOT, _progress)
    inside = sum(1 for e in static["loot"] + static["medals"] if e.get("d"))
    print(f"map data: {len(static['loot'])} loot spots, {len(static['medals'])} Seeker's Tokens, {len(static['quests'])} quests, "
          f"{len(static['dungeons'])} dungeon maps ({inside} spots inside them)")


def build():
    steam = dd2_steam.steam_path()
    dd2_build.build_all(find_game_dir(), ASSETS, ROOT, _progress, dd2_steam.game_build_id(steam) if steam else None)
    print(f"built into {ROOT}")


def serve():
    import dd2_server
    if game_running():
        print("note: the game is running; saves are only read, never written")
    args = sys.argv[2:]
    account = _option("--account")
    unknown = [a for a in args if a not in ("--open", "--lan", "--account", account) and not a.isdigit()]
    if unknown:
        sys.exit(f"unknown option(s) {' '.join(unknown)}; usage: dd2.py serve [port] [--open] [--lan] [--account <id>]")
    port = next((int(a) for a in args if a.isdigit() and a != account), 8642)
    if not 1024 <= port <= 65535:
        sys.exit(f"port {port}: use a number from 1024 to 65535")
    save_dir, account_id = find_save_dir()
    dd2_server.serve(ROOT, save_dir, account_id, ASSETS, port, open_browser="--open" in args, lan="--lan" in args,
                     page_dir=dd2_paths.page_dir(), steam=dd2_steam.steam_path())


def backfill_log():
    """Rebuild work/session_log.jsonl from every save copy on disk (refresh runs and backups)."""
    import tempfile
    import dd2_mapdata
    import dd2_server
    import dd2_session
    _save_dir, account_id = find_save_dir()
    names, enums = dd2_parse.load_names(ASSETS), dd2_quests.load_enums(ASSETS)
    vocations, quest_tree = dd2_server.load_table(ROOT, "vocations"), dd2_server.load_table(ROOT, "quest_tree")
    seen, snaps = set(), []
    # refresh runs and backups; not work\live, the running map server's own copy
    copies = [p for p in glob.glob(os.path.join(glob.escape(WORK), "*", "win64_save", "data*Slot.bin"))
              if os.path.basename(os.path.dirname(os.path.dirname(p))) != "live"]
    copies += glob.glob(os.path.join(glob.escape(WORK), "backups", "*", "data*Slot.bin"))
    with tempfile.TemporaryDirectory() as tmp:
        for path in copies:
            digest = sha256(path)
            if digest in seen:
                continue
            seen.add(digest)
            try:
                payload = dd2_decrypt.process(path, account_id, tmp)
                _root, records = dd2_parse.parse_records(payload, names)
                by_type = {r.get("$type"): r for r in records}
                quests = dd2_quests.extract(payload, names, enums)
                dd2_mapdata.check_records(by_type, quests)
            except Exception as e:  # a damaged copy must not put wrong numbers into the log
                print(f"  skipped {path}: {type(e).__name__}: {e}")
                continue
            saved = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path)))
            state = dd2_mapdata.compute_state(by_type, quests, saved, os.path.basename(path)[:-4], vocations, quest_tree)
            snaps.append(dd2_session.snapshot(state))
    entries = dd2_session.backfill(WORK, snaps)
    print(f"{len(seen)} distinct saves, {len(entries)} log entries written to {os.path.join(WORK, dd2_session.LOG_NAME)}")
    for e in entries:
        print(f"  {e['prev_saved']} -> {e['saved']}: {len(e['looted'])} looted, {len(e['quests'])} quest changes, gold {e['gold']:+}")


def fetch_assets():
    """the type dumps, enum dumps and file list the tools read, at the upstream commits pinned in assets.lock.json"""
    import dd2_assets
    args = sys.argv[2:]
    target = args[args.index("--to") + 1] if "--to" in args and args.index("--to") + 1 < len(args) else ASSETS
    lock = dd2_assets.load_lock(ASSETS_LOCK)
    todo = dd2_assets.missing(lock, target)
    if not todo:
        print(f"all {len(lock)} files are in place in {target}")
        return
    print(f"downloading {len(todo)} file(s) into {target}: {', '.join(todo)}")
    for name in dd2_assets.fetch(lock, target):
        print(f"  {name}: SHA-256 checked")


def run_command(fn, wait=input):
    """Run one command. The exe's console window closes as soon as the program ends, so a start-up problem (no save,
    a folder that can't be written, the port in use) or an unexpected error is shown until the player presses Enter."""
    try:
        fn()
        return
    except SystemExit as e:
        if e.code in (None, 0):
            raise
        print(e.code if isinstance(e.code, str) else f"Stopped (exit code {e.code}).")
    except KeyboardInterrupt:
        raise
    except Exception:
        traceback.print_exc()
    try:
        wait("\nPress Enter to close this window.")
    except EOFError:
        pass
    raise SystemExit(1)


if __name__ == "__main__":
    if dd2_paths.FROZEN and len(sys.argv) == 1:
        sys.argv += ["serve", "--open"]  # a double-click on the exe starts the tracker and opens it in the browser
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    commands = {"refresh": refresh, "quests": quests, "gamedata": gamedata, "report": report, "map": build_map, "serve": serve,
                "backfill-log": backfill_log, "fetch-assets": fetch_assets, "build": build}
    command = commands.get(cmd, lambda: sys.exit(__doc__))
    run_command(command) if dd2_paths.FROZEN else command()
