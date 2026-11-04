# DD2 Completionist Tracker: open-source readiness (sub-project 1 of 4)

Date: 2026-11-03. Status: draft for review.

The private "DD2 Save Tools" become a public GitHub project, **DD2 Completionist Tracker**. This spec covers only
making it publishable and installable by other players. The later sub-projects get their own specs:
2. quest tracker with story phases and points of no return, 3. achievements, 4. more collectibles.

## Positioning

A completionist tracker for Dragon's Dogma 2 on PC (Steam) that needs **no mods**: it only reads your save files,
never writes to them, and shows the result in a browser on the same PC or a phone. In-game alternatives exist
(REFramework mods: Arisen's Ledger, Clairvoyance, Map Markers and Collectables by Raze); the README links them for
players who prefer an overlay. Nothing found tracks achievements or reads the save from outside the game.

## Decisions taken

| Topic | Decision |
|---|---|
| Name | DD2 Completionist Tracker |
| Vibe-coded notice | Box at the top of the README and a line in the page footer |
| Thief-specific tips | Removed completely (Nearby tip, Thief filter, "Thief can use it", report gear scoring) |
| Upgrade planner | Removed (Upgrades tab, cost tables, smithing lines in the Log) |
| Material lookup | Kept, as a new "Materials" tab |
| Distribution | ZIP in GitHub Releases, built by GitHub Actions; tests on every push; run from source still possible; no code signing for now |
| Licence | GPL-3.0 (the save reader is a port of kvasszn/ree-save-editor, GPL-3.0) |
| UI language | English |

## 1. Product changes

### Name and notices

- Window title, page heading and launcher: "DD2 Completionist Tracker" (`DD2 Completionist Tracker.exe`; from
  source `DD2 Completionist Tracker.cmd`, phone variant `DD2 Completionist Tracker (phone).cmd`).
- README top box:
  > **Vibe-coded project.** Almost all of this code was written by an AI coding assistant (Claude Code), directed and
  > play-tested by a human player. Not every line has been reviewed by a person. The tool only reads your saves and
  > never writes to them, but use it at your own risk.
- README and page footer: "Vibe-coded fan project, not affiliated with Capcom." plus a link to the repository.
  The README adds that Dragon's Dogma is a trademark of Capcom and that the tool ships no game files.

### Removed

| What | Where |
|---|---|
| Upgrades tab (gear list, levels, styles, next-step costs, totals) | `map/index.html` `tab-up`/`pane-up`; `map/app.js` `renderUpgrades`, `upgradePlan`, `matLine` |
| Closest unique upgrade for your Thief | `map/app.js` Nearby tip (`near-tip`) and its helper |
| Thief filter and "Thief can use it" | `map/app.js` `gear-thief`, item sub-line; `tools/dd2_mapdata.py` `THIEF`, item field `thief` |
| Smithing upgrades in the Log | `tools/dd2_session.py` `_upgrades` and the `upgrades` entry key; `map/app.js` log rendering of it |
| Report: gear scoring and upgrade report | `tools/dd2_report.py` `score`, the Thief parts of `gear_report`, `upgrade_report` |
| Worn-gear levels and styles in the state | `tools/dd2_mapdata.py` `_enhancement` and the state field `gear` (read only by the planner and `_upgrades`) |

The "Unique gear" tab stays (unique items are collectibles) without the Thief filter. The report keeps its unique-gear
and loot sections. Smith labels on the map keep using `gamedata/enhance_styles.json`.

### New: Materials tab (replaces Upgrades)

- A searchable list of all smithing materials (the item ids used by `gamedata/enhance.json`; the table stays for this
  list only), sorted by name, each with how many you carry, store and your main pawn carries.
- Clicking a material opens the existing material card (`showMaterial`): monsters that drop it with chances, shops
  that sell it, and buttons to show its monster spawn spots, gathering spots and unlooted world spots.
- The Find box keeps finding materials, gatherable items and monsters as today.

### Generalised

- LAN mode text: explains both cases (network "Private": allow in the Windows prompt; network "Public": allow
  public networks in the prompt or switch the network to "Private") instead of stating how this PC is set.
- No name, slot or value of the author's playthrough appears in code, tests or docs (see section 5).

### Unchanged

The map with all layers and dungeon insets, Quests (phases, cutoffs, timed banner), Unique gear, Party, Nearby,
Log, LAN/phone mode, the save watcher and backups, and the CLI commands `refresh`, `quests`, `report`, `gamedata`,
`map`, `serve`, `backfill-log`.

## 2. Repository

- The repository is created in place (`Documents/DD2-SaveTools`) with `git init`; the folder name on disk does not
  matter. Proposed GitHub name: `dd2-completionist-tracker`.
- `.gitignore` is an allowlist: ignore everything (`/*`), then re-include `dd2.py`, `tools/`, `tests/`, `docs/`,
  `map/` (minus generated `map/tiles/`, `map/dungeons/`, `map/data/`, `map/build/`), `.github/`, the launchers,
  `README.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`, `CONTRIBUTING.md`, `requirements.txt`, `assets.lock.json`.
  Always ignored: `work/`, `assets/`, `extracted/`, `gamedata/`, `refs/`, `.venv/`, `__pycache__/`,
  `tests/local/expectations.json`, `settings.json`.
- `LICENSE`: GPL-3.0. `THIRD_PARTY_NOTICES.md`: ree-save-editor (GPL-3.0; save format, cipher, `rszdd2.json`,
  `enumsdd2.json`), REasy (MIT; RSZ reading, post-DLC type dump, enums, file list), RE-Engine-Lib (MIT; PAK),
  REMSG_Converter (MIT; msg), Leaflet 1.9.4 (BSD-2-Clause), qrcode-generator 1.4.4 (MIT).
- PAK reader provenance: `tools/ree_pak.py` names Ekey/REE.PAK.Tool as a source; that project has no licence. Each
  part is checked against RE-Engine-Lib and REasy (both MIT). Parts found only in Ekey's code are rewritten from the
  MIT sources, and the header credits only those. `refs/` (copies of upstream sources) is never committed.
- Commit identity: the repository's local `user.email` is set to the GitHub no-reply address before the first commit,
  so no private e-mail address ends up in the public history.
- Pre-publish check, `tools/check_publish.py`: scans every file `git ls-files` would publish for Steam account ids
  (the `userdata/<id>` folders on this PC), absolute user paths (`C:\Users\<name>`), e-mail addresses, and strings
  listed in the ignored `tests/local/expectations.json` (character names and the like). Also fails on any file over
  5 MB or any file type that can only come from the game (`.pak`, `.tex.*`, `.user.3`, `.msg.*`, tiles).

## 3. Third-party data

- `assets.lock.json` lists five files, each with source repository, commit SHA, path, SHA-256 and licence:
  - ree-save-editor `assets/dd2/rszdd2.json` and `assets/dd2/enumsdd2.json`;
  - REasy `resources/data/dumps/rszdd2.json` (stored as `rszdd2_dlc.json`), `resources/data/enums/dd2_enums.json`
    (as `enumsdd2_dlc.json`), `resources/data/lists/DD2_STM.list`.
- `dd2.py fetch-assets` downloads them from `raw.githubusercontent.com` at the pinned commits into `assets/` and
  refuses a file whose SHA-256 differs. The release ZIP already contains them, so players need no download.
- The Ekey and reelib file lists are dropped. Acceptance check: rebuilding `gamedata/` and `map/data/static.json`
  with the REasy list alone gives byte-identical output to the current build. If REasy's list misses files we use,
  the missing paths are added through a small list of our own (paths only, no game content), not through Ekey's list.
- `name_index.pickle` stays a local cache, rebuilt when the lists change.

## 4. First run and runtime

- Data folder: next to the program (the folder holding the exe, or the repository root when run from source).
  Everything written goes there: `assets/` (source runs only), `extracted/`, `gamedata/`, generated map files,
  `work/`, `settings.json`. Static page files are served from the bundle, generated map files from the data folder.
- Discovery (read-only): Steam path from the registry, the game from Steam's library folders, saves from
  `userdata/<id>/2054970/remote/win64_save`. With several accounts that have DD2 saves, the one with the newest save
  is used; the side panel shows which account is read and offers the others. The choice is stored in
  `settings.json`. CLI: `--account <id>`.
- The server starts even without built data. The page then shows a setup screen: "Building the map from your game
  files", with steps (reading game files, items and quests, map tiles, dungeon maps) and progress, reported through
  the existing state polling. The build runs in a background thread; an error is shown with a "Try again" button.
- If the game is not found, the setup screen asks for the game folder; the server accepts it only if it contains
  `DD2.exe` and stores it in `settings.json`.
- Game updates: the build records Steam's build id (`steamapps/appmanifest_2054970.acf`, `buildid`) in
  `gamedata/meta.json`. A different build id at start shows a banner "The game was updated: rebuild the map data"
  with a button; the map keeps working with the old data until then.
- The new actions (rebuild, choose account, set game folder) are POST requests under the server's existing host and
  origin checks; with `--lan` they are refused from other devices.

## 5. Tests

- `tests/unit/`: run anywhere (GitHub Actions, cloud sessions, contributors) with synthetic fixtures in
  `tests/fixtures/`, made-up ids and names only, no game text:
  - cipher: a synthetic payload encrypted in the test with a made-up account id, then read back by `dd2_decrypt`;
    damaged files (hash mismatch, short payload) are rejected;
  - save parser on hand-made record trees; loot state including the beetle rule; story phases (`holds`, `closed`,
    story order) on a small made-up quest tree; session diffs; `compute_state` on a small save;
  - `fetch-assets` hash check (with a local fake file), `check_publish.py` on a planted path and e-mail;
  - `node --check map/app.js`.
- `tests/local/`: today's tests against real game data and saves. Each skips with a clear message when the game,
  built data or saves are missing. Values from one playthrough (taken beetles, ranks, names) move to the ignored
  `tests/local/expectations.json`; checks of game data that hold for everyone (78 beetles, 238 gear chests) stay.
- One runner: `python tests/run.py [unit|local|all]`, exit code non-zero on any failure.

## 6. Release and CI

- `.github/workflows/ci.yml`: on push and pull request, `windows-latest`, runs `tests/run.py unit`.
- `.github/workflows/release.yml`: on a `v*` tag, `windows-latest`: fetch assets, run unit tests, build with PyInstaller
  in one-folder mode, add the page, assets and licence texts, zip as `DD2-Completionist-Tracker-<version>.zip` with a
  `.sha256` file, publish a GitHub Release. Python version: the newest one PyInstaller supports, pinned to the same
  version in both workflow files; `requirements.txt` pins `cryptography`, `pillow` and (for builds) `pyinstaller`.
- The README explains the SmartScreen warning ("More info", "Run anyway") and how to check the SHA-256.

## 7. Documentation

- `README.md` for players: what it is, the vibe-coded box, download and start, what each tab and layer shows, FAQ
  (SmartScreen, phone and firewall, game updates, several Steam accounts, "is my save safe"), alternatives (the three
  in-game mods), licence and credits.
- `docs/FORMAT.md`: the save and game-file notes now in the README (container, cipher, parser rules, quest tree,
  phases, campsites, loot ids, map transform).
- `CONTRIBUTING.md`: running from source, the test runner, the fixture rule (no game files or game text in the
  repository), the pre-publish check.

## 8. Publishing steps (each needs the owner's explicit OK)

1. The owner names the GitHub account and confirms the repository name; the GitHub CLI is installed or the empty
   repository is created on the website.
2. `check_publish.py` passes; the owner sees the full file list of the first commit.
3. First push. Then tag `v1.0.0`; the release workflow builds and publishes the ZIP.

## Out of scope

Steam Deck / Linux, code signing, auto-update, translations, and sub-projects 2 to 4.

## Acceptance

- A fresh folder with the release ZIP unpacked (tested on this PC, on a port other than 8642) starts, builds the map
  from the installed game, and shows the newest save, with the changes above and nothing else changed.
- `git ls-files` contains no game-derived file and no personal data; `check_publish.py` passes.
- `tests/run.py unit` passes on GitHub Actions; `tests/run.py all` passes on this PC.
- The owner's running copy keeps working (same port, same `work/` log) after the change.

## Risks

- Antivirus false positives on the unsigned exe: one-folder mode, builds only by GitHub Actions, SHA-256 published.
- Upstream files change or move: pinned commits; bumping them is a deliberate change with a rebuild check.
- First build time on slow disks: progress is shown per step; the build can be resumed by "Try again".
- REasy's file list may lack paths the Ekey list had: covered by the byte-identical rebuild check.
