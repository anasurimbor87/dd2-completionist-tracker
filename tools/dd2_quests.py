"""Extract quest state records from decrypted DD2 slot payloads.

Locates app.QuestContext.SaveData and app.QuestLogManager.QuestLogInfo.QuestLogSaveData records by their
class header and parses each record on its own, so unparsed Dark Arisen fields elsewhere don't matter.

usage: python dd2_quests.py <assets_dir> <out_dir> <slot.dec> [<slot.dec> ...]
"""
import json
import os
import struct
import sys

from dd2_parse import Reader, load_names

QUEST_CONTEXT = (9, 0x02C80F81)  # app.QuestContext.SaveData
QUEST_LOG = (7, 0x45DD9864)  # app.QuestLogManager.QuestLogInfo.QuestLogSaveData


def find_records(data, names, header):
    pat = struct.pack("<II", *header)
    out, i = [], data.find(pat)
    while i != -1:
        r = Reader(data, names)
        r.p = i
        try:
            rec = r.cls()
            rec["$offset"] = i
            out.append(rec)
        except Exception as e:
            print(f"  skip record at {i:#x}: {type(e).__name__}: {e}")
        i = data.find(pat, i + 1)
    return out


def extract(data, names, enums):
    quest_ids = enums["app.QuestDefine.ID"]
    log_status = enums["app.QuestLogManager.QuestStatus"]
    contexts = find_records(data, names, QUEST_CONTEXT)
    logs = find_records(data, names, QUEST_LOG)
    for c in contexts:
        c["IDName"] = quest_ids.get(str(c["ID"]), "?")
    for l in logs:
        l["QuestIdName"] = quest_ids.get(str(l["QuestId"]), "?")
        l["StatusName"] = log_status.get(str(l["Status"]), "?")
    return {"contexts": contexts, "log": logs}


def load_enums(assets):
    with open(os.path.join(assets, "enumsdd2.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    assets, out_dir = sys.argv[1], sys.argv[2]
    names = load_names(assets)
    enums = load_enums(assets)

    for path in sys.argv[3:]:
        q = extract(open(path, "rb").read(), names, enums)
        contexts, logs = q["contexts"], q["log"]
        name = os.path.basename(path).split(".")[0]
        print(f"== {name}: {len(contexts)} quest contexts, {len(logs)} quest log records")
        with open(os.path.join(out_dir, f"{name}.quests.json"), "w", encoding="utf-8") as f:
            json.dump({"contexts": contexts, "log": logs}, f, indent=1)


if __name__ == "__main__":
    main()
