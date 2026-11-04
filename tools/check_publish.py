"""Leak guard: refuses files that would put personal data or game files into the public repository.

usage: python tools/check_publish.py            every file git would publish (tracked + not ignored)
       python tools/check_publish.py --staged   only the files staged for the next commit (the pre-commit hook)

Checks each file for paths under a user's folder (C:\\Users\\<name>\\...), e-mail addresses (GitHub no-reply,
noreply@anthropic.com and example domains are fine), Steam account ids of this PC, private strings (character names
and the like, listed under "private_strings" in the ignored tests/local/expectations.json), file types that only
come from the game, images, and files over 5 MB. Exit code 1 if anything is found.
"""
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_BYTES = 5 * 1024 * 1024
USER_PATH = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+(?!<)[^\\/\s\"'<>`]+")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_OK = re.compile(r"(@users\.noreply\.github\.com|^noreply@anthropic\.com|@example\.(org|com|net))$", re.I)
GAME_SUFFIXES = (".pak", ".user.3", ".scn.21", ".msg.24")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".dds")
ALLOWED_IMAGES = {"docs/screenshot.jpg": 1024 * 1024}  # the README's one screenshot, kept small; no other image


def scan(paths, root, private, account_ids):
    """One problem string per finding in the given files (relative to root); empty = clean."""
    problems = []
    ids = [str(a) for a in account_ids]
    for rel in paths:
        full = os.path.join(root, rel)
        low = rel.lower()
        if low.endswith(GAME_SUFFIXES) or ".tex." in low:
            problems.append(f"{rel}: a game file type")
            continue
        if low.endswith(IMAGE_SUFFIXES):
            limit = ALLOWED_IMAGES.get(rel.replace("\\", "/"))
            if limit is None:
                problems.append(f"{rel}: an image (map images come from the game)")
            elif os.path.getsize(full) >= limit:
                problems.append(f"{rel}: the README screenshot must stay under {limit // 1024} KB")
            continue
        try:
            size = os.path.getsize(full)
        except OSError:
            continue  # deleted since git listed it
        if size > MAX_BYTES:
            problems.append(f"{rel}: larger than 5 MB ({size} bytes)")
            continue
        with open(full, "rb") as f:
            text = f.read().decode("utf-8", errors="ignore")
        for m in USER_PATH.finditer(text):
            problems.append(f"{rel}: user path {m.group(0)!r}")
        for m in EMAIL.finditer(text):
            if not EMAIL_OK.search(m.group(0)):
                problems.append(f"{rel}: e-mail address {m.group(0)!r}")
        for s in private:
            if s and s in text:
                problems.append(f"{rel}: private string {s!r}")
        for a in ids:
            if re.search(rf"(?<!\d){a}(?!\d)", text):
                problems.append(f"{rel}: Steam account id {a}")
    return problems


def _private_strings():
    path = os.path.join(ROOT, "tests", "local", "expectations.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("private_strings", [])


def usable_ids(ids):
    """account ids worth searching for: Steam's userdata\\0 (no account) or a short folder name would match any
    number in the code"""
    return [a for a in ids if a >= 100000]


def account_ids(steam):
    """every Steam account of this PC (each userdata folder), whether it has DD2 saves or not"""
    if not steam:
        return []
    return usable_ids(sorted({int(os.path.basename(d)) for d in glob.glob(os.path.join(glob.escape(steam), "userdata", "*"))
                              if os.path.basename(d).isdigit()}))


def _steam_path():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import dd2_steam
        return dd2_steam.steam_path()
    except ImportError:
        return None


def git_files(staged, cwd=ROOT):
    """the files the next commit holds (staged: added, copied, modified, renamed) or all files git would publish"""
    cmd = (["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged
           else ["git", "ls-files", "--cached", "--others", "--exclude-standard"])
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def main():
    problems = scan(git_files("--staged" in sys.argv), ROOT, _private_strings(), account_ids(_steam_path()))
    for p in problems:
        print(p)
    print(f"check_publish: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
