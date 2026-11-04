# Contributing

Thanks for looking. This is a small, vibe-coded project (see the README); issues and pull requests are welcome.

## Run from source

Windows with Python 3.14 and Dragon's Dogma 2 installed through Steam:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python dd2.py fetch-assets
```

Then double-click `DD2 Completionist Tracker.cmd`; the first start builds the map from your game files. The command
line has more (`.venv\Scripts\python dd2.py` lists it): `build`, `map`, `refresh`, `report`, `backfill-log`, ...
Set `DD2_DATA_DIR` to build or serve into another folder, and use another port (`dd2.py serve 8652`) for a second
copy next to the one you play with.

## Tests

```
.venv\Scripts\python tests\run.py unit    # made-up data only: runs anywhere, also on GitHub Actions
.venv\Scripts\python tests\run.py local   # your installed game and saves; skips what is missing
.venv\Scripts\python tests\run.py all
```

Local tests check values of one playthrough (slot names, counts, names) only when `tests\local\expectations.json`
exists. That file is ignored by git: keep your own there.

## Rules for the repository

- **No game files and no game text.** Map images, item names, quest texts and anything else extracted from the game
  stay on each player's PC; test fixtures are made up (`tests/fixtures/`).
- **Nothing personal.** No Steam account ids, user folder paths, e-mail addresses or character names.
- `tools/check_publish.py` checks both. Install it as a pre-commit hook:

  ```
  printf '#!/bin/sh\nexec .venv/Scripts/python.exe tools/check_publish.py --staged\n' > .git/hooks/pre-commit
  ```

  It also reads `private_strings` (names to keep out) from `tests\local\expectations.json`.
- Third-party data is pinned in `assets.lock.json`; see "Bumping a pinned file" in `docs/FORMAT.md`.

## Releases

Push a tag `vX.Y.Z`. GitHub Actions (`.github/workflows/release.yml`) runs the unit tests, builds the one-folder exe
with PyInstaller and publishes the ZIP with its SHA-256.
