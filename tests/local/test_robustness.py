"""Checks for damaged input and failure handling: decryption, parser, save log, state guard, server.
Run: python tests/local/test_robustness.py"""
import copy
import glob
import http.client
import json
import os
import shutil
import stat
import struct
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish, latest_run, need, playthrough  # noqa: E402

import dd2  # noqa: E402
import dd2_decrypt  # noqa: E402
import dd2_mapdata  # noqa: E402
import dd2_parse  # noqa: E402
import dd2_server  # noqa: E402
import dd2_session  # noqa: E402

PORT = 8791  # never the real map's 8642


def quietly(fn, *a):
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a)


def raises(fn, *a):
    try:
        quietly(fn, *a)
    except Exception as e:
        return e
    return None


def slots():
    """the slot saves of the newest refresh run, oldest save first"""
    copy = os.path.join(latest_run(), "win64_save")
    return [os.path.basename(p)[:-4] for p in sorted(glob.glob(os.path.join(copy, "data*Slot.bin")), key=os.path.getmtime)]


def state_of(slot):
    dec = os.path.join(latest_run(), "decrypted")
    records = {r.get("$type"): r for r in json.load(open(os.path.join(dec, slot + ".json"), encoding="utf-8"))}
    quests = json.load(open(os.path.join(dec, slot + ".quests.json"), encoding="utf-8"))
    return records, quests, dd2_mapdata.compute_state(records, quests, slot, slot)


def test_decrypt(tmp):
    src = os.path.join(latest_run(), "win64_save", slots()[-1] + ".bin")
    raw = open(src, "rb").read()
    _dir, account = dd2.find_save_dir()
    check(raises(dd2_decrypt.process, src, account, tmp) is None, "a real save still decrypts")
    for cut in (0.25, 0.5, 0.99):
        p = os.path.join(tmp, f"cut{cut}.bin")
        open(p, "wb").write(raw[: int(len(raw) * cut)])
        t0 = time.time()
        e = raises(dd2_decrypt.process, p, account, tmp)
        check(isinstance(e, ValueError) and time.time() - t0 < 5, f"a save cut at {cut:.0%} is refused at once ({e})")
    p = os.path.join(tmp, "flipped.bin")
    bad = bytearray(raw)
    bad[len(bad) // 2] ^= 0xFF
    open(p, "wb").write(bad)
    check(isinstance(raises(dd2_decrypt.process, p, account, tmp), ValueError), "a save with one damaged byte is refused")


def test_parser():
    names = dd2_parse.load_names(os.path.join(ROOT, "assets"))
    data = struct.pack("<iIIi", 8, 0, 0xFFFFFFFF, 0) + bytes(64)  # U32 array, member size 0, absurd length
    r = dd2_parse.Reader(data, names)
    t0 = time.time()
    try:
        r.array()
        e = None
    except ValueError as err:
        e = err
    check(e is not None and time.time() - t0 < 1, "an array of zero-size elements is refused instead of looping")


def test_session(tmp):
    exp = playthrough("saves")
    if not exp:
        return
    work = os.path.join(tmp, "log")
    os.makedirs(work)
    n, quest = exp["looted_between"], exp["completed_between"]
    _r6, _q6, s006 = state_of(exp["older"])
    _r9, _q9, s009 = state_of(exp["newer"])
    with open(os.path.join(work, dd2_session.SNAPSHOT_NAME), "w") as f:
        f.write('{"saved": "2026-10-17 03:2')  # cut off mid-write
    check(raises(dd2_session.record, work, dict(s006, saved="A")) is None, "a damaged snapshot counts as missing")
    entry = dd2_session.record(work, dict(s009, saved="B"))
    check(entry and len(entry["looted"]) == n, "the next save is logged normally")
    with open(os.path.join(work, dd2_session.LOG_NAME), "a") as f:
        f.write('{"saved": "cut')  # a crash mid-append
    check(len(dd2_session.read_log(work)) == 1 and dd2_session.quest_start_days(work) == {quest: s009["day"]},
          "a damaged log line is skipped")
    reloaded = dd2_session.record(work, dict(s006, saved="C"))  # the older save loaded and saved again
    check(reloaded and reloaded.get("reloaded") and not reloaded.get("new_run"),
          f"loading an earlier save of the same playthrough is marked as such ({reloaded})")
    log = dd2_session.read_log(work)
    check(len(log) == 2 and log[0].get("reloaded"), "the entry after a damaged line is readable")
    check(dd2_session.quest_start_days(work) == {quest: s009["day"]}, "quest start days survive the reload")
    check(dd2_session.record(work, dict(s006, saved="D")) is None and len(dd2_session.read_log(work)) == 2,
          "a save with nothing new adds no entry")


def test_state_guard():
    for slot in slots():
        records, quests, _s = state_of(slot)
        check(raises(dd2_mapdata.check_records, records, quests) is None, f"{slot}: a complete save passes the guard")
    records, quests, _s = state_of(slots()[-1])
    broken = dict(records)
    broken["app.ContextDBMSSaveData"] = dict(records["app.ContextDBMSSaveData"], **{"$error": "ValueError: test"})
    check(isinstance(raises(dd2_mapdata.check_records, broken, quests), ValueError), "a partly parsed loot record is refused")
    check(isinstance(raises(dd2_mapdata.check_records, records, {"log": quests["log"][:-1]}), ValueError),
          "a quest log read incompletely is refused")


class FakeLive:
    def __init__(self, log_dir):
        self.state = {"version": 5, "status": "error", "error": "RuntimeError: test"}
        self.log_dir = log_dir
        self.refreshed = 0

    def manual_refresh(self):
        self.refreshed += 1


def request(method, path, host=f"127.0.0.1:{PORT}", origin=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=3)
    c.putrequest(method, path, skip_host=True)
    c.putheader("Host", host)
    if origin:
        c.putheader("Origin", origin)
    c.endheaders()
    r = c.getresponse()
    body = r.read()
    headers = r.getheaders()
    c.close()
    return r.status, body, headers


def test_server(tmp):
    map_dir = os.path.join(ROOT, "map")
    live = FakeLive(tmp)
    httpd = dd2_server.make_server(live, map_dir, PORT)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        status, body, _h = request("GET", "/api/state?since=5")
        reply = json.loads(body)
        check(reply.get("unchanged") and reply.get("error") == "RuntimeError: test", "an unchanged reply carries the error")
        status, body, _h = request("GET", "/api/state?since=5&x=2")
        check(json.loads(body).get("unchanged"), "since= is read as a query parameter")
        status, body, _h = request("GET", "/api/state?since=abc")
        check(json.loads(body).get("version") == 5 and "unchanged" not in json.loads(body), "a bad since= gets the full state")
        check(request("GET", "/api/state", host="evil.example")[0] == 403, "a foreign Host header is refused")
        check(request("POST", "/api/refresh", origin="http://evil.example")[0] == 403 and live.refreshed == 0,
              "a POST from another web page is refused")
        status, _b, _h = request("POST", "/api/refresh")
        check(live.refreshed == 1 and status == 500, "a refresh that ends in an error answers 500")
        for p in ("/CON", "/nul.txt", "/tiles/COM1", "/C%4FN"):
            check(request("GET", p)[0] == 404, f"Windows device name {p} is not served")
        check(request("GET", "/api/statefoo")[0] == 404, "unknown API paths are 404")
        status, _b, headers = request("GET", "/index.html")
        cc = [v for k, v in headers if k.lower() == "cache-control"]
        check(status == 200 and cc == ["no-cache"], f"pages are revalidated, one Cache-Control header ({cc})")
        _s, _b, headers = request("GET", "/api/log")
        check([v for k, v in headers if k.lower() == "cache-control"] == ["no-store"], "API answers are not stored")
        try:
            second = dd2_server.make_server(live, map_dir, PORT)
            second.server_close()
            taken = False
        except OSError:
            taken = True
        check(taken, "a second server can't bind the same port")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_live(tmp):
    save = os.path.join(tmp, "save")
    os.makedirs(save)
    open(os.path.join(save, "data001Slot.bin"), "wb").write(b"x")
    live = dd2_server.Live(ROOT, save, 0, os.path.join(ROOT, "assets"), tag="test_robustness")
    other = dd2_server.Live(ROOT, save, 0, os.path.join(ROOT, "assets"), tag="test_robustness")
    check(live.version > 10 ** 12 and other.version != 1, "versions don't restart at 1 with the server")
    calls = []

    def flaky(reason):
        calls.append(reason)
        if len(calls) == 1:
            raise RuntimeError("the game holds the file")
        live.state = {"version": live.version + 1, "status": "ok"}

    live._refresh = flaky
    dd2_server.SETTLE_SECONDS, dd2_server.RETRY_SECONDS = 0, 0.3
    quietly(live.check)
    check(live.state["status"] == "error" and "holds the file" in live.state["error"], "a failed read shows as an error")
    quietly(live.check)
    check(len(calls) == 1, "no retry storm right after a failure")
    time.sleep(0.35)
    quietly(live.check)
    check(len(calls) == 2 and live.state["status"] == "ok", "a failed read is retried without a new game save")
    quietly(live.check)
    quietly(live.manual_refresh)
    check(len(calls) == 2, "nothing is re-read while the folder is unchanged")
    check("<save folder>" in live.public(RuntimeError(f"cannot open {save}\\data001Slot.bin")), "errors don't show local paths")

    # backups: interrupted copies, rotation leaves other folders alone, read-only files can be deleted
    backups = os.path.join(tmp, "backups")
    live.backup_dir = backups
    os.makedirs(os.path.join(backups, "keep this"))
    for i in range(31):
        os.makedirs(os.path.join(backups, f"2026-01-{i + 1:02d}_000000"))
    ro = os.path.join(save, "readonly.bin")
    open(ro, "wb").write(b"r")
    os.chmod(ro, stat.S_IREAD)
    quietly(live._backup, save, "2026-02-01_000000")
    stamps = sorted(d for d in os.listdir(backups) if dd2_server.STAMP.match(d))
    check(len(stamps) == 30 and "keep this" in os.listdir(backups) and stamps[-1] == "2026-02-01_000000",
          "rotation keeps 30 backups and leaves other folders alone")
    dd2_server._rmtree(os.path.join(backups, "2026-02-01_000000"))
    check(not os.path.exists(os.path.join(backups, "2026-02-01_000000")), "a backup with a read-only file can be removed")
    os.chmod(ro, stat.S_IWRITE)
    shutil.rmtree(os.path.join(ROOT, "work", "test_robustness"), ignore_errors=True)
    shutil.rmtree(os.path.join(ROOT, "work", "test_robustness_backups"), ignore_errors=True)


def main():
    need("assets", "rszdd2.json")
    with tempfile.TemporaryDirectory() as tmp:
        test_decrypt(tmp)
        test_parser()
        test_session(tmp)
        test_state_guard()
        test_server(tmp)
        test_live(tmp)
    finish()


if __name__ == "__main__":
    main()
