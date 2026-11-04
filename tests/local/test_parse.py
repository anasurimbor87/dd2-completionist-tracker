"""Checks for the save parser: every record of every save copy parses, including app.NPCManager (its DLC-added struct
field a1bad783 sits behind up to 100 bytes of padding). Run: python tests/local/test_parse.py"""
import glob
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, need, skip  # noqa: E402

import dd2_parse  # noqa: E402


def main():
    need("assets", "rszdd2.json")
    names = dd2_parse.load_names(os.path.join(ROOT, "assets"))

    seen = set()
    for f in sorted(glob.glob(os.path.join(ROOT, "work", "*", "decrypted", "data*Slot.bin.dec"))):
        data = open(f, "rb").read()
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        _root, records = dd2_parse.parse_records(data, names)
        label = os.path.basename(f)[:-8]
        bad = [r.get("$type") for r in records if dd2_parse._has_error(r)]
        check(not bad, f"{label}: all {len(records)} records parse ({bad})")
        npc = next((r for r in records if (r.get("$type") or "").startswith("app.NPCManager")), {})
        # a fixed list of 100 slots; unused ones are empty objects
        pasts = [p for p in (npc.get("_NPCStrayPawnPasts") or {}).get("Dismisses") or [] if isinstance(p, dict) and p.get("$type")]
        check(bool(pasts) and all(isinstance(p, dict) and "Refresh" in p for p in pasts),  # Refresh follows the struct
              f"{label}: every dismissed pawn reads past the padded struct ({len(pasts)})")
    if not seen:
        skip("needs a decrypted save under work/ (run dd2.py refresh)")
    check(True, f"{len(seen)} distinct saves checked")

    finish()


if __name__ == "__main__":
    main()
