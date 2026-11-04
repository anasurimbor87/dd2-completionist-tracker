# DD2 Completionist Tracker: open-source readiness, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the private DD2 save tools into the publishable "DD2 Completionist Tracker": no personal or game-derived
data in git, Thief tips and upgrade planner removed, a Materials tab, a first-run map build, a GitHub Actions release ZIP.

**Architecture:** Python stdlib server + Leaflet page stay as they are. New small modules split out what the frozen
exe needs: `dd2_paths` (bundle vs. data folder), `dd2_steam` (discovery), `dd2_settings`, `dd2_build` (whole build
with progress), `dd2_assets` (pinned downloads), `check_publish` (leak guard). Tests become `tests/unit` (synthetic,
run anywhere) and `tests/local` (real game and saves, skip when absent), driven by `tests/run.py`.

**Tech Stack:** Python 3.14 (Windows), cryptography 50.0.2, Pillow 13.0.0, PyInstaller (one-folder), Leaflet 1.9.4,
GitHub Actions `windows-latest`.

**Spec:** `docs/superpowers/specs/2026-11-03-open-source-readiness-design.md`

## Global Constraints

- Read-only on the Steam save folder and the game folder, always. Builds write only into the data folder.
- Never stop or restart the owner's running map server on port 8642; test servers use port 8652 and tag `test`.
- Nothing game-derived (tiles, dungeon maps, `gamedata/`, `static.json`, `extracted/`, game text) and nothing personal
  (Steam account ids, `C:\Users\<name>` paths, e-mail addresses, character names) is ever committed.
  `tools/check_publish.py` runs as a pre-commit hook from Task 1 on.
- Third-party sources only: ree-save-editor (GPL-3.0), REasy (MIT), RE-Engine-Lib (MIT), REMSG_Converter (MIT),
  Leaflet 1.9.4 (BSD-2-Clause), qrcode-generator 1.4.4 (MIT). Nothing from Ekey/REE.PAK.Tool (no licence).
- Project licence GPL-3.0. UI text English. Name exactly "DD2 Completionist Tracker".
- Footer line exactly: "Vibe-coded fan project, not affiliated with Capcom." README box text verbatim from spec section 1.
- Pins: `cryptography==50.0.2`, `pillow==13.0.0`; PyInstaller pinned in `requirements-build.txt`.
- Edit scripts write `path + ".new"` and then `os.replace` (an interrupted write once truncated `app.js`).
- No push, repository creation or release without the owner's explicit OK in chat (Task 14).
- Tests follow the project's script style: `check(cond, msg)` per assertion, non-zero exit on any failure.

## Review Focus

- Several Steam accounts on one PC: the account whose newest `data*Slot.bin` is newest wins, an account folder
  without a DD2 save is ignored (test in Task 7).
- A game folder typed with quotes, a trailing backslash, or the library root instead of the game folder: accepted only
  when it (after stripping quotes and whitespace) contains `DD2.exe` (test in Task 7).
- A build interrupted by closing the window: `gamedata/meta.json` is written last, so a start without it needs setup
  again even when `map/data/static.json` exists (test in Task 7).
- A phone in LAN mode calling the new setup/account endpoints: refused with 403, `/api/refresh` still allowed
  (test in Task 10).
- The program unpacked into a folder it can't write (Program Files): a start-up message naming the folder and
  suggesting Documents, no traceback (test in Task 7).

---

### Task 1: Leak guard, test runner, repository bootstrap

**Files:**
- Create: `tools/check_publish.py`, `tests/testlib.py`, `tests/run.py`, `tests/unit/test_check_publish.py`, `.gitignore`
- Create (local only, not versioned): `.git/hooks/pre-commit`

**Interfaces:**
- Produces: `check_publish.scan(paths: list[str], root: str, private: list[str], account_ids: list[int]) -> list[str]`
  (one problem string per finding, empty = clean); `check_publish.main() -> int`.
- Produces: `testlib.ROOT: str` (repository root), `testlib.check(cond: bool, msg: str) -> None`,
  `testlib.finish() -> NoReturn` (prints failure count, exits 1 on failures), `testlib.skip(reason: str) -> NoReturn`
  (prints `SKIP <reason>`, exits 0), `testlib.expected(section: str) -> dict | None` (Task 2 fills it).
- Produces: `python tests/run.py [unit|local|all]` (default `unit`): runs each `tests/<kind>/test_*.py` as a
  subprocess with `sys.executable`, prints one line per script (`ok`, `FAIL`, `SKIP`), exits 1 if any failed.

- [ ] **Step 1: Write the failing test `tests/unit/test_check_publish.py`** with a temp folder holding planted files:

```python
problems = check_publish.scan(paths, tmp, private=["Brunhild"], account_ids=[12345678])
check(any("a.txt" in p and "user path" in p for p in problems), "a path under a user's folder is found")
check(any("b.txt" in p and "e-mail" in p for p in problems), "an e-mail address is found")
check(not any("c.txt" in p for p in problems), "the no-reply addresses and C:\\Users\\<name> are allowed")
check(any("d.txt" in p and "Brunhild" in p for p in problems), "a private string is found")
check(any("e.txt" in p and "12345678" in p for p in problems), "a Steam account id is found")
check(any("f.user.3" in p for p in problems) and any("g.jpg" in p for p in problems), "game file types and images are refused")
check(any("big.bin" in p and "5 MB" in p for p in problems), "files over 5 MB are refused")
check(check_publish.scan([clean], tmp, [], []) == [], "a clean file passes")
```

  Planted contents (built from string pieces, so the test file itself passes the scan): a.txt a path under
  `C:\Users\` with a made-up name; b.txt an address at a non-reserved domain; c.txt
  `1+x@users.noreply.github.com noreply@anthropic.com you@example.org C:\Users\<name>`; d.txt `Brunhild`; e.txt `userdata/12345678/`;
  empty `f.user.3` and `g.jpg`; `big.bin` of 5 MB + 1 byte.

- [ ] **Step 2: Run** `.venv\Scripts\python tests\unit\test_check_publish.py`. Expected: fails on the missing module.

- [ ] **Step 3: Implement `tools/check_publish.py`.** User path regex `[A-Za-z]:[\\/]+Users[\\/]+(?!<)[^\\/\s"'<>]+`;
  e-mail regex with an allowlist of `*@users.noreply.github.com` and `noreply@anthropic.com`; refused suffixes
  `.pak`, `.user.3`, `.scn.21`, `.msg.24`, any `.tex.` and images (`.png .jpg .jpeg .webp .gif .bmp .dds`);
  size limit 5 * 1024 * 1024 bytes. `main()` scans `git ls-files --cached --others --exclude-standard` (or, with
  `--staged`, `git diff --cached --name-only --diff-filter=AM`), private strings from
  `tests/local/expectations.json` key `private_strings` (missing file = none), account ids from
  `dd2_steam.save_accounts` when Task 7 exists, otherwise from the `userdata/*` folder names under Steam's path in the
  registry. Prints each problem; returns 1 if any.

- [ ] **Step 4: Implement `tests/testlib.py` and `tests/run.py`** per the Interfaces block. Run
  `.venv\Scripts\python tests\run.py unit`. Expected: `ok test_check_publish.py`, exit 0.

- [ ] **Step 5: Write `.gitignore`** as the allowlist from spec section 2 (ignore `/*`, re-include the listed paths,
  then ignore `map/tiles/ map/dungeons/ map/data/ map/build/ __pycache__/ tests/local/expectations.json settings.json`).

- [ ] **Step 6: Bootstrap the repository.** `git init -b main`; ask the owner for the GitHub account name, read its
  numeric id from `https://api.github.com/users/<name>`, set `git config user.name "<name>"` and
  `git config user.email "<id>+<name>@users.noreply.github.com"` locally. Write `.git/hooks/pre-commit` running
  `.venv/Scripts/python tools/check_publish.py --staged`.

- [ ] **Step 7: Commit** `.gitignore tools/check_publish.py tests/testlib.py tests/run.py tests/unit/ docs/superpowers/`
  with message `chore: leak guard, test runner, repository bootstrap`. Expected: the hook passes. Check
  `git show --stat HEAD` lists only those files.

### Task 2: Real-data tests move to `tests/local`

**Files:**
- Move: `tests/test_*.py` (9 scripts) to `tests/local/`
- Create (ignored): `tests/local/expectations.json`
- Modify: `tests/testlib.py` (`expected`)

**Interfaces:**
- Consumes: `testlib` from Task 1.
- Produces: `expectations.json` shape `{"private_strings": [str], "<section>": {...}}`, one section per script that
  checks playthrough values (`beetles`, `party`, `phases`, `session`, `robustness`, `hardmode`, `parse`).

- [ ] **Step 1: Move the scripts and switch them to `testlib`** (`ROOT`, `check`, `finish`). Each calls `skip(...)`
  first when its inputs are missing: game folder (via `dd2.py`'s discovery), `gamedata/`, `map/data/static.json`, or
  a decrypted save under `work/`.
- [ ] **Step 2: Move playthrough values into `expectations.json`.** Slot names, taken/held counts, names, ranks,
  Discipline, phase numbers, closed-quest counts go to their section; the script reads `expected("<section>")` and
  skips only those checks when it returns None. Checks that hold for every player stay literal (78 beetles, 238 gear
  chests, 5 phase quests). `private_strings` lists the character names and slot-specific strings.
- [ ] **Step 3: Run** `.venv\Scripts\python tests\run.py all`. Expected: all `ok` on this PC. Then rename
  `expectations.json` temporarily and rerun `local`: every script prints `ok` or `SKIP`, none `FAIL`.
- [ ] **Step 4: Run** `.venv\Scripts\python tools\check_publish.py`. Expected: no finding in `tests/`.
- [ ] **Step 5: Commit** `tests/` with message `test: real-data tests move to tests/local, playthrough values local`.

### Task 3: Unit tests on synthetic fixtures (safety net before refactors)

**Files:**
- Create: `tests/unit/savebuilder.py`, `tests/unit/rszwriter.py`, `tests/fixtures/names.json`,
  `tests/fixtures/quest_tree.json`, `tests/fixtures/save_records.json`
- Create: `tests/unit/test_cipher.py`, `test_parser.py`, `test_loot.py`, `test_phases_unit.py`, `test_session_unit.py`,
  `test_state.py`, `test_page_syntax.py`

**Interfaces:**
- Produces: `savebuilder.build_save(body: bytes, account_id: int, deflate: bool = True) -> bytes`: a DSSS v2 file
  (flags `0x10 | 0x08` with deflate, `0x10` without; Mandarin blocks built with `dd2_decrypt.splitmix_next` and
  `aes128_ofb`, the stream being symmetric; trailing `<Q decrypted_len>` and `<I murmur3>`).
- Produces: `rszwriter.write_records(root_class: str, records: list[dict], names: dict) -> bytes`, the inverse of
  `dd2_parse.parse_records` for field types Class, Array (of classes), S32, U32, Boolean, String; `names` is the
  `tests/fixtures/names.json` dump (made-up classes `test.RootSaveData`, `test.ItemSaveData` with made-up fields).

- [ ] **Step 1: Write the tests.** Assertions:

```python
# test_cipher.py
raw = savebuilder.build_save(body, 12345678)
check(dd2_decrypt.process(path, 12345678, out) == body, "a made-up save decrypts and inflates to its body")
check(raises(lambda: dd2_decrypt.process(flipped_byte_path, 12345678, out), "hash mismatch"), "a damaged file is refused")
check(raises(lambda: dd2_decrypt.process(short_path, 12345678, out), "too short"), "a 20-byte file is refused")
# test_parser.py
root, recs = dd2_parse.parse_records(rszwriter.write_records("test.RootSaveData", records, names), type_names)
check(root == "test.RootSaveData" and recs[0]["_Count"] == 7 and recs[0]["_Name"] == "Ser Test", "fields read back")
check(not any(dd2_parse._has_error(r) for r in recs), "no parse errors")
# test_loot.py (records from save_records.json, made-up GUIDs)
check(state[A] == "looted" and state[B] == "looted" and state[C] == "seen", "_IsPick, NeverGenerate, context only")
check(state[BEETLE] == "looted" and state[HERB] != "looted", "beetle with _Num 0 taken, herb with _Num 0 not")
# test_phases_unit.py (quest_tree.json: made-up quests 1..6, phase quest 11010 ends with main quest 1)
check(dd2_phases.holds({"or": [[1, 0], [2, 0]]}, {2: 0}), "or holds with one leaf")
check(not dd2_phases.holds({"and": [[1, 0], [2, 0]]}, {2: 0}), "and needs both")
check(set(dd2_phases.closed(tree, {1: 0}, {})) == {"4", "5"}, "finishing quest 1 closes 4 and 5")
check("5" not in dd2_phases.closed(tree, {1: 0}, {"5": "Complete"}), "completed quests are never closed")
# test_session_unit.py (two made-up states)
check(d["looted"] == [A] and d["gold"] == 250, "diff: looted spot and gold change")
# test_state.py
check(s["day"] == 3 and s["gold"] == 1000 and s["results"] == {"1": 0}, "compute_state on a made-up save")
# test_page_syntax.py
check(subprocess.run(["node", "--check", "map/app.js"]).returncode == 0, "app.js parses")
```

- [ ] **Step 2: Run** `.venv\Scripts\python tests\run.py unit`. Expected: the new scripts fail until the helpers and
  fixtures exist.
- [ ] **Step 3: Implement `savebuilder.py`, `rszwriter.py` and the fixtures.** The fixtures hold only made-up ids,
  names and GUIDs; `save_records.json` holds the minimal record set `compute_state` and `check_records` read.
- [ ] **Step 4: Run** `tests\run.py unit`. Expected: all `ok`.
- [ ] **Step 5: Commit** `tests/` with message `test: unit tests on synthetic saves, parser records and quest trees`.

### Task 4: Thief tips and upgrade planner leave the Python side

**Files:**
- Modify: `tools/dd2_mapdata.py` (remove `THIEF`, item field `thief`, `_enhancement`, state fields `gear` and
  `equipped`; static gets `"materials": [sorted ids]` instead of `"enhance"`)
- Modify: `tools/dd2_session.py` (remove `_upgrades` and the `upgrades` key, also from `_unchanged`)
- Modify: `tools/dd2_report.py` (remove `score`, `upgrade_report`, Thief parts of `gear_report`), `dd2.py` (`report`)
- Test: `tests/unit/test_session_unit.py`, `tests/local/test_session.py`, `tests/local/test_robustness.py`

**Interfaces:**
- Produces: static key `materials: list[int]` (every item id in `gamedata/enhance.json` step materials, ascending);
  `out_items[m]["sold"]` stays for those ids. State keys `gear` and `equipped` no longer exist.

- [ ] **Step 1: Add the failing checks** to `tests/unit/test_session_unit.py` and `tests/unit/test_state.py`:

```python
check("upgrades" not in d, "the Log no longer records smithing upgrades")
check("gear" not in s and "equipped" not in s, "the state no longer carries worn gear")
```

  Run `tests\run.py unit`. Expected: both FAIL.
- [ ] **Step 2: Remove the code** listed under Files; `dd2.py report` writes quests + unique gear + loot only.
- [ ] **Step 3: Run** `tests\run.py all`. Expected: all `ok`. `dd2.py report` writes a report without Thief or
  upgrade sections.
- [ ] **Step 4: Commit** with message `refactor: remove Thief tips and the upgrade planner (Python side)`.

### Task 5: Page: rename, footer, Materials tab, planner and Thief UI gone

**Files:**
- Modify: `map/index.html` (title and `h1` "DD2 Completionist Tracker"; tab `tab-mat`/`pane-mat` "Materials" replaces
  `tab-up`/`pane-up`; remove `near-tip` and `gear-thief`; footer line + repository link)
- Modify: `map/app.js` (remove `renderUpgrades`, `upgradePlan`, `matLine`, `betterThanEquipped`, the Nearby tip,
  "Thief can use it", "Currently wearing", the Log's upgrades lines; add `renderMaterials`)
- Modify: `map/style.css` (Materials list rows; drop rules only the planner used)
- Rebuild: `map/data/static.json` via `.venv\Scripts\python dd2.py map`

**Interfaces:**
- Consumes: `STATIC.materials` (Task 4), `STATE.inventory` (existing), `showMaterial(id, anchor)` (existing).
- Produces: `renderMaterials(): void`, registered in `applyState` as `["materials", renderMaterials]`; the
  repository link is the constant `REPO_URL` at the top of `app.js` (set in Task 14, `""` hides the link).

- [ ] **Step 1: Implement.** Materials tab: a search input (`mat-find`) and a list sorted by name; each row
  `<button data-mat=id>Name</button>` with "carried X, stored Y, pawn Z" (zeros left out, "none" if all zero); a click
  calls `showMaterial`. Footer: `<p class="foot-note">Vibe-coded fan project, not affiliated with Capcom.</p>`.
- [ ] **Step 2: Run** `tests\run.py all` (includes `node --check` and `test_icons`). Expected: all `ok`.
- [ ] **Step 3: Browser check on the test server** (`dd2.py serve 8652` with tag `test`): Materials lists items with
  counts; a click shows drops and the three buttons, and "Show N gathering spots" highlights them; Nearby has no tip;
  Unique gear has no Thief box; the Log renders older entries that still carry `upgrades` without errors; no console
  errors. Stop the test server afterwards.
- [ ] **Step 4: Commit** `map/` with message `feat: Materials tab, new name and footer; planner and Thief UI removed`.

### Task 6: Pinned third-party data and licence files

**Files:**
- Create: `tools/dd2_assets.py`, `assets.lock.json`, `LICENSE`, `THIRD_PARTY_NOTICES.md`, `requirements.txt`
- Modify: `dd2.py` (command `fetch-assets`)
- Test: `tests/unit/test_assets.py`

**Interfaces:**
- Produces: `dd2_assets.load_lock(path: str) -> list[dict]` (keys `name repo commit path sha256 licence`);
  `dd2_assets.fetch(lock: list[dict], assets_dir: str, opener=urllib.request.urlopen) -> list[str]` (names written;
  raises `ValueError` naming the file on a SHA-256 mismatch and leaves no partial file);
  `dd2_assets.missing(lock, assets_dir) -> list[str]`.

- [ ] **Step 1: Write the failing test** with a fake opener serving bytes: a matching file lands in `assets/`; a
  wrong one raises `ValueError` containing its name and leaves neither the file nor a `.part`; `missing` lists absent
  and hash-mismatched files.
- [ ] **Step 2: Run** `tests\unit\test_assets.py`. Expected: FAIL, module missing.
- [ ] **Step 3: Implement** `dd2_assets.py` (download to `name + ".part"`, verify, `os.replace`). Fill
  `assets.lock.json` with the five files of spec section 3: the current default-branch commit SHA of each upstream
  repository and the SHA-256 of the downloaded files, the lists under `lists/`.
- [ ] **Step 4: Add** `LICENSE` (GPL-3.0 text from gnu.org), `THIRD_PARTY_NOTICES.md` (spec section 2 list, each with
  its licence text or link and what we use), `requirements.txt` (`cryptography==50.0.2`, `pillow==13.0.0`).
- [ ] **Step 5: Run** `tests\run.py unit`; `dd2.py fetch-assets` into a temp folder (env `DD2_DATA_DIR` from Task 7, or
  a `--to <dir>` option). Expected: `ok`; five files with matching hashes.
- [ ] **Step 6: Commit** with message `feat: pinned third-party data, licence and notices`.

### Task 7: Paths, Steam discovery, settings, one builder

**Files:**
- Create: `tools/dd2_paths.py`, `tools/dd2_steam.py`, `tools/dd2_settings.py`, `tools/dd2_build.py`
- Modify: `dd2.py` (all commands use them; `gamedata` and `map` call `dd2_build`), `tools/dd2_gamedata.py`
  (`build(game_dir, assets, extract_dir, out_dir) -> None` next to `main()`)
- Test: `tests/unit/test_steam.py`, `tests/unit/test_build_meta.py`, `tests/unit/test_paths.py`

**Interfaces:**
- Produces: `dd2_paths.APP_DIR` (`sys._MEIPASS` when frozen, else repo root), `dd2_paths.DATA_DIR` (exe folder when
  frozen, env `DD2_DATA_DIR` if set, else repo root), `dd2_paths.page_dir() -> str` (`APP_DIR/map`),
  `dd2_paths.map_out_dir() -> str` (`DATA_DIR/map`), `dd2_paths.assets_dir() -> str` (`APP_DIR/assets` when frozen,
  else `DATA_DIR/assets`), `dd2_paths.check_writable() -> str | None` (message or None).
- Produces: `dd2_steam.steam_path() -> str | None` (env `DD2_STEAM_DIR` if set, else the registry's `SteamPath`); `dd2_steam.find_game_dir(steam: str) -> str | None`;
  `dd2_steam.game_build_id(steam: str) -> str | None` (`buildid` from `appmanifest_2054970.acf` in the game's library);
  `dd2_steam.save_accounts(steam: str) -> list[tuple[int, str, float]]` (account id, save dir, newest
  `data*Slot.bin` mtime; newest first; folders without a slot file left out); `dd2_steam.valid_game_dir(text: str) -> str | None`
  (strips quotes and whitespace, returns the normalised folder if it holds `DD2.exe`).
- Produces: `dd2_settings.load() -> dict`, `dd2_settings.save(updates: dict) -> dict` (atomic, `DATA_DIR/settings.json`).
- Produces: `dd2_build.STEPS = ["Reading game files", "Items and quests", "Map tiles", "Dungeon maps", "Map data"]`;
  `dd2_build.build_all(game_dir: str, assets: str, data_dir: str, progress: Callable[[int, str], None], build_id: str | None) -> None`
  (clears `extracted/`, `gamedata/meta.json`, tiles and dungeon outputs first; writes `gamedata/meta.json`
  `{"buildid": ..., "built": iso time}` last); `dd2_build.needs_setup(data_dir) -> bool` (meta.json or static.json
  missing); `dd2_build.outdated(data_dir, build_id) -> bool` (both known and different).

- [ ] **Step 1: Write the failing tests.** `test_steam.py` on a fake Steam tree in a temp folder:

```python
check(dd2_steam.save_accounts(steam)[0][0] == 222, "the account with the newest slot save comes first")
check(all(a != 333 for a, _d, _t in dd2_steam.save_accounts(steam)), "an account without a DD2 save is left out")
check(dd2_steam.find_game_dir(steam) == game, "the game is found in the second library folder")
check(dd2_steam.game_build_id(steam) == "16520194", "build id read from the app manifest")
check(dd2_steam.game_build_id(steam_without_manifest) is None, "no manifest: no build id, no error")
check(dd2_steam.valid_game_dir(f'"{game}\\"  ') == os.path.normpath(game), "quotes and a trailing backslash are fine")
check(dd2_steam.valid_game_dir(library_root) is None, "a folder without DD2.exe is refused")
```

  `test_build_meta.py`: `needs_setup` is True with `static.json` but no `meta.json`; False with both; `outdated` is
  True for `"1"` vs `"2"`, False when either is None. `test_paths.py`: with `DD2_DATA_DIR` set to a read-only temp
  folder, `check_writable()` returns a message naming the folder and containing "Documents".
- [ ] **Step 2: Run** `tests\run.py unit`. Expected: the three new scripts FAIL (modules missing).
- [ ] **Step 3: Implement the four modules** and switch `dd2.py` to them (`ROOT`/`WORK`/`ASSETS`/`GAMEDATA` come from
  `dd2_paths`; `find_save_dir` uses `save_accounts` and `--account <id>` / `settings.json`; `gamedata` and `map`
  call `dd2_build.build_all` with a console progress printer). `build_static` and the tile builders take their output
  folder from the caller.
- [ ] **Step 4: Run** `tests\run.py all`. Expected: all `ok`.
- [ ] **Step 5: Rebuild into a temp data folder** (`DD2_DATA_DIR=<temp>`, assets copied there): `dd2.py map` builds
  everything; `gamedata/*.json` and `map/data/static.json` are byte-identical to the current ones in the repo folder,
  and the tile and dungeon file hashes match. The owner's folder is untouched.
- [ ] **Step 6: Commit** with message `refactor: data folder, Steam discovery, settings and one build entry point`.

### Task 8: REasy file list alone

**Files:**
- Modify: `assets.lock.json` (only REasy's `DD2_STM.list` under `lists/`), `tools/ree_pak.py` (if a fallback list
  is needed)
- Create if needed: `tools/extra_paths.list` (paths only, one per line, with a comment line naming why)

- [ ] **Step 1: Build into a fresh temp data folder** whose `assets/lists/` holds only `DD2_STM.list`.
- [ ] **Step 2: Compare** `gamedata/*.json`, `static.json`, tile and dungeon hashes with Task 7's temp build.
  Expected: identical. If not: list the game paths the build read that the REasy list lacks
  (`GameFiles.read` misses), add exactly those to `tools/extra_paths.list`, load it in `GameFiles._load_names`, repeat
  until identical.
- [ ] **Step 3: Commit** with message `build: REasy file list only (plus N extra paths)`.

### Task 9: PAK reader provenance

**Files:**
- Modify: `tools/ree_pak.py`

- [ ] **Step 1: Compare each part** of `ree_pak.py` (`path_hash`, `decrypt_table`, `_cs_div`, `decrypt_resource`,
  `Pak`, `GameFiles`, the modulus and exponent constants) with RE-Engine-Lib `REE-Lib/Pak/` and REasy's PAK code at the
  pinned commits. Write the counterpart file and function next to each part as a comment.
- [ ] **Step 2: Rewrite** any part found only in Ekey's code from the MIT counterpart. If a part has no MIT
  counterpart, stop and report to the owner before going on.
- [ ] **Step 3: Header** names only RE-Engine-Lib and REasy. Delete the local `refs/ree` copy reference from comments.
- [ ] **Step 4: Run** `tests\run.py all` and repeat the Task 8 comparison. Expected: all `ok`, output identical.
- [ ] **Step 5: Commit** with message `refactor: PAK reader based on MIT sources only`.

### Task 10: First-run setup, account choice, game updates in the server and page

**Files:**
- Modify: `tools/dd2_server.py` (setup state, build thread, endpoints, two-root file serving), `map/app.js`,
  `map/index.html`, `map/style.css`
- Test: `tests/unit/test_server_setup.py`

**Interfaces:**
- Consumes: `dd2_build` (`STEPS`, `build_all`, `needs_setup`, `outdated`), `dd2_steam`, `dd2_settings`, `dd2_paths`.
- Produces: state key `setup`: `{"needed": bool, "running": bool, "step": int, "steps": [str], "error": str | None,
  "game_dir_missing": bool, "outdated": bool}`; state key `accounts: [{"id": int, "current": bool, "saved": str}]`.
- Produces endpoints (POST, JSON body): `/api/setup/build` `{}`; `/api/setup/game-dir` `{"path": str}` (400 with
  `{"error": "No DD2.exe in that folder"}` if invalid); `/api/account` `{"id": int}`. All three answer 403 unless
  `client_address[0] == "127.0.0.1"`, also in LAN mode.
- Produces: `/tiles/`, `/dungeons/`, `/data/` served from `dd2_paths.map_out_dir()`, everything else from
  `dd2_paths.page_dir()`. `Live` starts without `gamedata/`; the save watcher starts once the build is done.

- [ ] **Step 1: Write the failing test** with `make_server` on a free port and a fake `live` object:

```python
check(post("/api/setup/build", via="127.0.0.1").status == 200, "a local build request is taken")
check(post("/api/account", {"id": 1}, via=lan_ip, host=lan_host).status == 403, "a phone can't switch accounts")
check(post("/api/setup/game-dir", {"path": "x"}, via=lan_ip, host=lan_host).status == 403, "a phone can't set the game folder")
check(post("/api/refresh", via=lan_ip, host=lan_host).status in (200, 500), "a phone can still re-read the save")
check(post("/api/setup/game-dir", {"path": empty_dir}).json()["error"] == "No DD2.exe in that folder", "bad folder refused")
check(get("/tiles/x.jpg").body == b"generated" and get("/app.js").body == b"page", "two roots")
```

- [ ] **Step 2: Run** it. Expected: FAIL (endpoints missing).
- [ ] **Step 3: Implement the server side.** The build runs in one background thread at a time; progress updates
  `setup.step`; an exception sets `setup.error` (via `Live.public`, no local paths); success clears `needed`,
  bumps the state version and starts the watcher. At start: `check_writable()` failure prints its message and exits
  with code 2; `outdated` comes from `dd2_steam.game_build_id` vs `gamedata/meta.json`. `/api/account` switches
  `Live` to that account's save folder under its lock, resets the last-read signature, and stores the id with
  `dd2_settings.save({"account_id": id})`; `/api/setup/game-dir` stores `{"game_dir": path}`.
- [ ] **Step 4: Implement the page side.** While `setup.needed`: a full-panel setup screen ("Building the map from
  your game files", the steps with the current one marked, "Try again" on error, a folder field when
  `game_dir_missing`); the map loads once `needed` turns false. `setup.outdated`: banner "The game was updated: rebuild
  the map data" with a button. Several `accounts`: a select in the panel head ("Steam account").
- [ ] **Step 5: Run** `tests\run.py all`. Expected: all `ok`.
- [ ] **Step 6: Browser check** with `DD2_DATA_DIR=<empty temp>` on port 8652: the setup screen walks through all five
  steps and the map appears with the newest save; a fake older `buildid` in `meta.json` shows the banner. With
  `DD2_STEAM_DIR` pointing at a temp Steam folder holding two accounts (copies of the save folder), the account select
  appears, switching reads the other copy, and the game-folder field accepts the real game folder. Stop the server.
- [ ] **Step 7: Commit** with message `feat: first-run map build, Steam account choice, game update notice`.

### Task 11: Launchers, frozen entry point, PyInstaller build

**Files:**
- Create: `packaging/tracker.spec`, `requirements-build.txt`, `DD2 Completionist Tracker.cmd`,
  `DD2 Completionist Tracker (phone).cmd`
- Delete: `DD2 Map.cmd`, `DD2 Map (phone).cmd`
- Modify: `dd2.py` (frozen with no arguments = `serve --open`; `--lan` passes through)

**Interfaces:**
- Produces: one-folder build `dist/DD2 Completionist Tracker/` with `DD2 Completionist Tracker.exe` (console window),
  bundled `map/` page files, `assets/` (fetched), `LICENSE`, `THIRD_PARTY_NOTICES.md`, and
  `DD2 Completionist Tracker (phone).cmd` calling the exe with `--lan`.

- [ ] **Step 1: Install** the build requirement into `.venv` (`pip install -r requirements-build.txt`, PyInstaller pinned
  to the version installed).
- [ ] **Step 2: Build** `pyinstaller packaging/tracker.spec`. Expected: `dist/DD2 Completionist Tracker/` as above.
- [ ] **Step 3: Acceptance run.** Copy the folder to a new temp folder, start the exe with `serve 8652` (port argument):
  setup screen, full build, the newest save shown, Materials tab and footer present, `work/` created inside that
  folder, nothing written next to the repository. Stop it.
- [ ] **Step 4: Commit** with message `build: PyInstaller one-folder package and new launchers`.

### Task 12: GitHub Actions: tests and release

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/release.yml`

- [ ] **Step 1: `ci.yml`:** on `push` and `pull_request`, `windows-latest`, Python 3.14, Node available,
  `pip install -r requirements.txt`, `python tests/run.py unit`.
- [ ] **Step 2: `release.yml`:** on tags `v*`, `windows-latest`: install both requirement files, `python dd2.py
  fetch-assets`, `python tests/run.py unit`, `pyinstaller packaging/tracker.spec`, zip the folder as
  `DD2-Completionist-Tracker-${{ github.ref_name }}.zip`, write its SHA-256 to a `.sha256` file, create the Release
  with both files (`softprops/action-gh-release` pinned to a commit SHA). `permissions: contents: write` only here.
- [ ] **Step 3: Validate** both files with `actionlint` if it is installed, otherwise by reading them against the
  GitHub Actions workflow syntax reference; they first run for real in Task 14.
- [ ] **Step 4: Commit** with message `ci: unit tests on every push, release ZIP on version tags`.

### Task 13: Documentation and generalised texts

**Files:**
- Rewrite: `README.md`
- Create: `docs/FORMAT.md`, `CONTRIBUTING.md`
- Modify: `tools/dd2_server.py` (LAN hint lines)

- [ ] **Step 1: `README.md`** per spec section 7: the vibe-coded box (verbatim), what it is ("no mods, reads only your
  save"), download and first start, tabs and layers, FAQ (SmartScreen: "More info" then "Run anyway"; checking the
  SHA-256 with `certutil -hashfile <zip> SHA256`; phone and firewall for Private and Public networks; game updates;
  several Steam accounts; save safety), alternatives (Arisen's Ledger, Clairvoyance, Map Markers and Collectables by
  Raze, with links), "Dragon's Dogma is a trademark of Capcom; this tool ships no game files", licence and credits.
- [ ] **Step 2: `docs/FORMAT.md`:** the technical notes from today's README (save format, parser rules, quest tree and
  phases, campsites, loot ids, map transform, beetles), unchanged in substance.
- [ ] **Step 3: `CONTRIBUTING.md`:** run from source (`python -m venv .venv`, requirements, `dd2.py fetch-assets`,
  `dd2.py map`), `tests/run.py unit|local|all`, the rule "no game files or game text in the repository; fixtures are
  made up", the pre-commit leak guard.
- [ ] **Step 4: LAN hint** in `serve()`: both network cases, nothing about "this PC".
- [ ] **Step 5: Run** `tests\run.py all` and `tools\check_publish.py`. Expected: all `ok`, no findings.
- [ ] **Step 6: Commit** with message `docs: player README, format notes, contributing guide`.

### Task 14: Publish (every step needs the owner's explicit OK)

- [ ] **Step 1:** Ask the owner to confirm the account and the repository name `dd2-completionist-tracker`; set
  `REPO_URL` in `map/app.js` and the README links; commit.
- [ ] **Step 2:** Ask whether to install the GitHub CLI (`winget install GitHub.cli`, then the owner runs
  `! gh auth login`) or to create the empty public repository on the website.
- [ ] **Step 3:** Run `tools/check_publish.py`; show the owner `git ls-files` and `git log --stat`; wait for OK.
- [ ] **Step 4:** Add the remote and push `main`. Check the `ci.yml` run passes.
- [ ] **Step 5:** With the owner's OK, tag `v1.0.0` and push the tag. Check the release run, download the ZIP, verify
  its SHA-256, run the Task 11 acceptance on it.
- [ ] **Step 6:** Tell the owner to close and reopen their own launcher (now `DD2 Completionist Tracker.cmd`) and press
  Ctrl+F5; their `work/` log carries over.
