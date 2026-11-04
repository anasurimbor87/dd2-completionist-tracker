"""The server's setup and account endpoints: only this PC may start a build, set the game folder or switch the Steam
account (a phone in LAN mode may still re-read the save), and page files and built map files come from their own
folders. Run: python tests/unit/test_server_setup.py"""
import http.client
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import dd2_server  # noqa: E402

PORT = 8793  # never the real map's 8642


class FakeLive:
    def __init__(self, log_dir):
        self.state = {"version": 3, "status": "ok"}
        self.log_dir = log_dir
        self.calls = []

    def manual_refresh(self):
        self.calls.append("refresh")

    def start_build(self):
        self.calls.append("build")
        return True

    def set_game_dir(self, text):
        self.calls.append(("game", text))
        return None if text == "good" else "No DD2.exe in that folder"

    def switch_account(self, account):
        self.calls.append(("account", account))
        return account == 1

    def public_state(self):
        return dict(self.state, setup={"needed": False}, accounts=[])


def request(method, path, body=None, port=PORT):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    data = json.dumps(body).encode() if body is not None else None
    c.request(method, path, body=data, headers={"Host": f"127.0.0.1:{port}", "Content-Type": "application/json"})
    r = c.getresponse()
    out = r.status, r.read()
    c.close()
    return out


def serve(live, page, built, admin_from, port):
    httpd = dd2_server.make_server(live, page, port, map_dir=built, admin_from=admin_from)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    with tempfile.TemporaryDirectory() as tmp:
        page, built = os.path.join(tmp, "page"), os.path.join(tmp, "built")
        for folder, name, text in ((page, "app.js", "page"), (built, "tiles/x.jpg", "generated"), (built, "data/static.json", "{}")):
            path = os.path.join(folder, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
        live = FakeLive(tmp)
        httpd = serve(live, page, built, ("127.0.0.1", "::1"), PORT)
        try:
            check(request("POST", "/api/setup/build", {})[0] == 200 and "build" in live.calls, "this PC may start a build")
            status, body = request("POST", "/api/setup/game-dir", {"path": "elsewhere"})
            check(status == 400 and json.loads(body).get("error") == "No DD2.exe in that folder", "a folder without the game is refused")
            check(request("POST", "/api/setup/game-dir", {"path": "good"})[0] == 200, "the game folder is taken")
            check(request("POST", "/api/account", {"id": 1})[0] == 200 and request("POST", "/api/account", {"id": 2})[0] == 404,
                  "switching to an account with saves works, to one without is 404")
            check(request("POST", "/api/account", {"id": "x"})[0] == 400, "a malformed account id is 400")
            check(request("GET", "/tiles/x.jpg")[1] == b"generated" and request("GET", "/app.js")[1] == b"page",
                  "map tiles come from the data folder, page files from the program")
            check(request("GET", "/data/static.json")[1] == b"{}", "the map data comes from the data folder")
            state = json.loads(request("GET", "/api/state")[1])
            check("setup" in state and "accounts" in state, "the state carries the setup and the accounts")
        finally:
            httpd.shutdown()
            httpd.server_close()

        # a phone in LAN mode: not this PC
        live = FakeLive(tmp)
        httpd = serve(live, page, built, (), PORT + 1)
        try:
            check(request("POST", "/api/setup/build", {}, PORT + 1)[0] == 403, "a phone can't start a build")
            check(request("POST", "/api/account", {"id": 1}, PORT + 1)[0] == 403, "a phone can't switch accounts")
            check(request("POST", "/api/setup/game-dir", {"path": "good"}, PORT + 1)[0] == 403, "a phone can't set the game folder")
            check(request("POST", "/api/refresh", None, PORT + 1)[0] in (200, 500) and live.calls == ["refresh"],
                  "a phone can still re-read the save, and nothing else ran")
        finally:
            httpd.shutdown()
            httpd.server_close()
    finish()


if __name__ == "__main__":
    main()
