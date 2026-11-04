# PyInstaller build of DD2 Completionist Tracker, one-folder mode (fewer antivirus false positives than one file).
# Run from the repository root after `python dd2.py fetch-assets`:  pyinstaller packaging/tracker.spec
# The result is dist/DD2 Completionist Tracker/: the exe, its _internal/ folder (Python, the page under map/, the pinned
# assets/), the phone launcher, the licence texts and the README. Everything the tracker writes goes next to the exe.
import glob
import os
import sys

sys.path.insert(0, SPECPATH)
import licences  # noqa: E402

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
NAME = "DD2 Completionist Tracker"

page = [(os.path.join(ROOT, "map", f), "map") for f in ("index.html", "timeline.js", "app.js", "style.css")]
page += [(p, os.path.join("map", "vendor")) for p in glob.glob(os.path.join(ROOT, "map", "vendor", "*"))]
assets = [(os.path.join(ROOT, "assets", f), "assets") for f in ("rszdd2.json", "enumsdd2.json", "rszdd2_dlc.json",
                                                                 "enumsdd2_dlc.json")]
assets += [(os.path.join(ROOT, "assets", "lists", "DD2_STM.list"), os.path.join("assets", "lists"))]
for src, _dst in assets:
    if not os.path.exists(src):
        raise SystemExit(f"{src} is missing: run `python dd2.py fetch-assets` first")

a = Analysis(
    [os.path.join(ROOT, "dd2.py")],
    pathex=[os.path.join(ROOT, "tools")],
    datas=page + assets,
    hiddenimports=["dd2_server", "dd2_map", "dd2_mapdata", "dd2_party", "dd2_phases", "dd2_session", "ree_msg",
                   "ree_rsz", "ree_tex"],
    excludes=["tkinter", "unittest", "pydoc", "test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NAME, console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)

# files players open themselves sit next to the exe, not inside _internal/
out = os.path.join(DISTPATH, NAME)
_copied, _missing = licences.collect(os.path.join(out, "licenses"))
if _missing:
    raise SystemExit(f"licence texts missing for bundled packages: {', '.join(_missing)}")
for f in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"):
    with open(os.path.join(ROOT, f), "rb") as src, open(os.path.join(out, f), "wb") as dst:
        dst.write(src.read())
with open(os.path.join(out, NAME + " (phone).cmd"), "w", newline="\r\n") as f:
    f.write('@echo off\nrem Like the exe, but also reachable from phones and tablets on your home network while this window '
            'is open.\ncd /d "%~dp0"\n"' + NAME + '.exe" serve --open --lan\npause\n')
