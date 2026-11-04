"""Third-party data the tools need (type dumps, enum dumps, the game's file list), pinned in assets.lock.json to a
commit of its upstream repository and checked by SHA-256. Release ZIPs ship these files; runs from source fetch them
with `dd2.py fetch-assets`. Nothing is ever taken from a moving branch."""
import hashlib
import json
import os
import urllib.request

RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"


def load_lock(path):
    """the list of pinned files: name (path under assets/), repo, commit, path (in the repo), sha256, licence"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)["files"]


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def missing(lock, assets_dir):
    """names of the pinned files that are absent or differ from their pinned hash"""
    return [e["name"] for e in lock
            if not os.path.exists(os.path.join(assets_dir, e["name"])) or _sha256(os.path.join(assets_dir, e["name"])) != e["sha256"]]


def fetch(lock, assets_dir, opener=urllib.request.urlopen):
    """download the missing files; a file whose hash differs from the lock is refused (ValueError) and not kept"""
    written = []
    todo = set(missing(lock, assets_dir))
    for e in lock:
        if e["name"] not in todo:
            continue
        final = os.path.join(assets_dir, e["name"])
        os.makedirs(os.path.dirname(final), exist_ok=True)
        part = final + ".part"
        h = hashlib.sha256()
        try:
            with opener(RAW.format(**e), timeout=60) as src, open(part, "wb") as dst:
                for block in iter(lambda: src.read(1 << 20), b""):
                    h.update(block)
                    dst.write(block)
            if h.hexdigest() != e["sha256"]:
                raise ValueError(f"{e['name']}: SHA-256 {h.hexdigest()} differs from the pinned {e['sha256']} "
                                 f"({e['repo']} at {e['commit'][:10]})")
            os.replace(part, final)
        finally:
            if os.path.exists(part):
                os.remove(part)
        written.append(e["name"])
    return written
