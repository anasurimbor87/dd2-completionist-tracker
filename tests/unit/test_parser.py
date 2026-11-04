"""The save record parser on made-up records written by tests/unit/rszwriter.py (classes from tests/fixtures/names.json).
Run: python tests/unit/test_parser.py"""
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, load_json  # noqa: E402

import dd2_parse  # noqa: E402
import rszwriter  # noqa: E402

NAMES = os.path.join(ROOT, "tests", "fixtures", "names.json")


def main():
    names = load_json(NAMES)
    type_names = dd2_parse.TypeNames(NAMES)
    records = [
        {"$type": "test.ItemSaveData", "_Count": 7, "_Id": 4000000000, "_Name": "Ser Test", "_Flag": True,
         "_Child": {"$type": "test.TagData", "_Tag": 5}, "_Tags": []},
        {"$type": "test.ItemSaveData", "_Count": -3, "_Id": 1, "_Name": "", "_Flag": False,
         "_Child": {"$type": "test.TagData", "_Tag": 0},
         "_Tags": [{"$type": "test.TagData", "_Tag": 11}, {"$type": "test.TagData", "_Tag": 12}]},
    ]
    data = rszwriter.write_records("test.RootSaveData", records, names)
    with contextlib.redirect_stdout(io.StringIO()):
        root, recs = dd2_parse.parse_records(data, type_names)
    check(root == "test.RootSaveData" and len(recs) == 2, f"two records under the root ({root}, {len(recs)})")
    first, second = recs + [{}] * (2 - len(recs))
    check(first.get("_Count") == 7 and first.get("_Name") == "Ser Test" and first.get("_Flag") is True,
          f"S32, String and Boolean read back ({first})")
    check(first.get("_Id") == 4000000000 and second.get("_Count") == -3, "U32 above 2^31 and a negative S32 read back")
    check(first.get("_Child", {}).get("_Tag") == 5, "a nested class reads back")
    check([t.get("_Tag") for t in second.get("_Tags", [])] == [11, 12] and first.get("_Tags") == [],
          "arrays of classes read back, empty or not")
    check(second.get("_Name") == "", "an empty string reads back")
    check(not any(dd2_parse._has_error(r) for r in recs), "no parse errors")
    finish()


if __name__ == "__main__":
    main()
