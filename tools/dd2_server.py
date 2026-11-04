"""Local server for the save map: serves the page, the map files built from the game, and a live state built from the
newest save.

The watcher polls the Steam save folder; when the game writes a save it copies the folder (read-only access,
hash-verified copy), decrypts the newest slot and publishes a new state version. The page polls /api/state.
Without built map data (the first start, or after the player asks for a rebuild) the server builds it in the
background and the page shows the steps; the watcher starts once the build is done.
"""
import contextlib
import glob
import hashlib
import io
import json
import os
import re
import shutil
import socket
import stat
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

import dd2_build
import dd2_decrypt
import dd2_mapdata
import dd2_parse
import dd2_quests
import dd2_paths
import dd2_session
import dd2_settings
import dd2_steam

POLL_SECONDS = 3
SETTLE_SECONDS = 4  # the game writes several files per save; wait until the folder is quiet
RETRY_SECONDS = 15  # after a failed read, try again even if the save folder did not change
KEEP_BACKUPS = 30
GENERATED = ("/tiles/", "/dungeons/", "/data/")  # served from the data folder, everything else from the page folder
LOCAL_ONLY = ("/api/setup/build", "/api/setup/game-dir", "/api/account")  # never from another device
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")  # backup folder names; anything else in the folder is left alone
WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {f"{d}{i}" for d in ("COM", "LPT") for i in range(10)}


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _signature(save_dir):
    return tuple(sorted((os.path.basename(p), os.path.getmtime(p), os.path.getsize(p))
                        for p in glob.glob(os.path.join(glob.escape(save_dir), "*.bin"))))


def _rmtree(path):
    def clear_read_only(func, p, _exc):  # copies keep the save files' attributes; a read-only one can't be deleted
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onexc=clear_read_only)


def _write_atomic(path, text):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)


def load_table(root, name):
    """gamedata/<name>.json (built by dd2.py gamedata) or None: without vocations the page has no Party tab data,
    without quest_tree it doesn't know which quests the story has closed"""
    path = os.path.join(root, "gamedata", name + ".json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def account_dirs(root, tag, account, home):
    """(save copy folder, backup folder, log folder) of one Steam account: the first account the tracker read (home)
    keeps work/ itself, so an existing log carries over; every other account gets work/accounts/<id>/. Test servers
    (tag other than "live") keep their own folders and log."""
    base = os.path.join(root, "work")
    if home is not None and account != home:
        base = os.path.join(base, "accounts", str(account))
    live_dir = os.path.join(base, tag)
    backup_dir = os.path.join(base, "backups" if tag == "live" else tag + "_backups")
    return live_dir, backup_dir, base if tag == "live" else live_dir


class Live:
    def __init__(self, root, save_dir, account_id, assets, tag="live", steam=None):
        self.root, self.save_dir, self.account_id = root, save_dir, account_id
        self.assets, self.steam = assets, steam
        self.build_id = dd2_steam.game_build_id(steam) if steam else None
        self.setup = {"needed": dd2_build.needs_setup(root), "running": False, "step": 0, "steps": dd2_build.STEPS,
                      "error": None, "game_dir_missing": False, "outdated": dd2_build.outdated(root, self.build_id)}
        self.build_lock = threading.Lock()
        self.watching = False
        self.tag = tag
        self.home = dd2_settings.load().get("home_account") if tag == "live" else account_id
        if self.home is None:
            self.home = account_id
            dd2_settings.save({"home_account": account_id})
        self.live_dir, self.backup_dir, self.log_dir = account_dirs(root, tag, account_id, self.home)
        self.names = dd2_parse.load_names(assets)
        self.enums = dd2_quests.load_enums(assets)
        self.vocations = load_table(root, "vocations")
        self.quest_tree = load_table(root, "quest_tree")
        self.lock = threading.Lock()
        self.state = {"version": 0, "status": "starting"}
        # versions start at the clock, not at 1: a page left open across a server restart must never take the new
        # server's state for the one it already shows
        self.version = int(time.time() * 1000)
        self.ok_sig = None  # save folder signature of the last successful read
        self.failed_sig, self.failed_at = None, None

    def public_state(self):
        """the state the page sees: the save's state plus the build's progress and the Steam accounts with saves"""
        return dict(self.state, setup=dict(self.setup), accounts=self.accounts())

    def accounts(self):
        found = dd2_steam.save_accounts(self.steam) if self.steam else []
        return [{"id": a, "current": a == self.account_id, "saved": time.strftime("%Y-%m-%d %H:%M", time.localtime(t))}
                for a, _d, t in found]

    def game_dir(self):
        game = dd2_steam.valid_game_dir(dd2_settings.load().get("game_dir", ""))
        return game or (dd2_steam.find_game_dir(self.steam) if self.steam else None)

    def start_build(self):
        """build the map data in the background; False when one is running or the game folder is unknown"""
        with self.build_lock:
            if self.setup["running"]:
                return False
            game = self.game_dir()
            if not game:
                self.setup.update(game_dir_missing=True, needed=True)
                return False
            self.setup.update(running=True, needed=True, step=0, error=None, game_dir_missing=False)
        threading.Thread(target=self._build, args=(game,), daemon=True).start()
        return True

    def _build(self, game):
        try:
            dd2_build.build_all(game, self.assets, self.root, lambda step, _name: self.setup.update(step=step), self.build_id)
            self.vocations = load_table(self.root, "vocations")
            self.quest_tree = load_table(self.root, "quest_tree")
            self.ok_sig = None  # read the save again with the new tables
            self.setup.update(running=False, needed=False, outdated=False)
            print("[live] map data built")
            self.start_watching()
        except Exception as e:
            self.setup.update(running=False, error=self.public(e))
            print(f"[live] the map data could not be built: {self.public(e)}")

    def set_game_dir(self, text):
        """the folder the player entered: None when it holds the game (the build starts), else what's wrong"""
        game = dd2_steam.valid_game_dir(text)
        if not game:
            return "No DD2.exe in that folder"
        dd2_settings.save({"game_dir": game})
        self.start_build()
        return None

    def switch_account(self, account):
        """read another Steam account's saves from now on; False when it has none"""
        for a, save_dir, _t in dd2_steam.save_accounts(self.steam) if self.steam else []:
            if a == account:
                with self.lock:
                    self.save_dir, self.account_id = save_dir, a
                    self.live_dir, self.backup_dir, self.log_dir = account_dirs(self.root, self.tag, a, self.home)
                    self.ok_sig = self.failed_sig = self.failed_at = None
                dd2_settings.save({"account_id": a})
                return True
        return False

    def start_watching(self):
        if not self.watching:
            self.watching = True
            threading.Thread(target=self.watch, daemon=True).start()

    def public(self, e):
        """error text for the page (also seen by phones in LAN mode): without local folder names"""
        text = f"{type(e).__name__}: {e}"
        for path, label in ((self.save_dir, "<save folder>"), (self.root, "<toolkit folder>"), (os.path.expanduser("~"), "~")):
            text = text.replace(path, label).replace(path.replace("\\", "/"), label)
        return text

    def _copy(self):
        dst = os.path.join(self.live_dir, "win64_save")
        problem = None
        for _attempt in range(5):
            try:
                if os.path.exists(dst):
                    _rmtree(dst)
                shutil.copytree(self.save_dir, dst)
                if all(_sha256(os.path.join(dst, n)) == _sha256(os.path.join(self.save_dir, n)) for n in os.listdir(dst)):
                    return dst
                problem = "the save folder kept changing while copying"
            except OSError as e:  # a file held open by the game or a virus scanner, or deleted meanwhile
                problem = f"{type(e).__name__}: {e}"
            time.sleep(2)
        raise RuntimeError(f"could not copy the save folder ({problem})")

    def _backup(self, src, stamp):
        os.makedirs(self.backup_dir, exist_ok=True)
        final = os.path.join(self.backup_dir, stamp)
        if os.path.exists(final):
            return
        part = final + ".part"  # an interrupted copy never looks like a finished backup
        if os.path.exists(part):
            _rmtree(part)
        shutil.copytree(src, part)
        os.replace(part, final)
        for d in sorted(d for d in os.listdir(self.backup_dir) if STAMP.match(d))[:-KEEP_BACKUPS]:
            try:
                _rmtree(os.path.join(self.backup_dir, d))
            except OSError as e:
                print(f"[live] could not remove old backup {d}: {e}")

    def refresh(self, reason, sig=None):
        """Read the newest save and publish it. Returns False if the folder is unchanged since the last good read."""
        out = io.StringIO()
        try:
            # nothing is printed while the lock is held: a paused console must never stall the reading
            with self.lock, contextlib.redirect_stdout(out):
                sig = _signature(self.save_dir) if sig is None else sig
                if sig == self.ok_sig and self.state.get("status") == "ok":
                    return False
                self._refresh(reason)
                self.ok_sig = sig
                return True
        finally:
            text = out.getvalue()
            if text:
                print(text, end="")

    def _refresh(self, reason):
        t0 = time.time()
        copy = self._copy()
        slots = glob.glob(os.path.join(glob.escape(copy), "data*Slot.bin"))
        if not slots:
            raise RuntimeError("no slot save (data*Slot.bin) in the save folder")
        slot = max(slots, key=os.path.getmtime)
        mtime = os.path.getmtime(slot)
        # back up first: a save the tools can't read (say, after a game patch) is exactly the one worth keeping
        self._backup(copy, time.strftime("%Y-%m-%d_%H%M%S", time.localtime(mtime)))
        dec_dir = os.path.join(self.live_dir, "decrypted")
        os.makedirs(dec_dir, exist_ok=True)
        payload = dd2_decrypt.process(slot, self.account_id, dec_dir)
        _root, records = dd2_parse.parse_records(payload, self.names)
        by_type = {r.get("$type"): r for r in records}
        quests = dd2_quests.extract(payload, self.names, self.enums)
        dd2_mapdata.check_records(by_type, quests)
        saved = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
        state = dd2_mapdata.compute_state(by_type, quests, saved, os.path.basename(slot)[:-4], self.vocations,
                                          self.quest_tree)
        os.makedirs(self.log_dir, exist_ok=True)
        entry = dd2_session.record(self.log_dir, state)
        if entry:
            print(f"[live] logged save {entry['saved']}: {len(entry.get('looted', []))} looted, "
                  f"{len(entry.get('quests', []))} quest changes")
        state["quest_days"] = dd2_session.quest_start_days(self.log_dir)
        self.version += 1
        state.update({"version": self.version, "status": "ok", "reason": reason, "took": round(time.time() - t0, 1)})
        _write_atomic(os.path.join(self.live_dir, "state.json"), json.dumps(state))
        self.state = state  # replaced as a whole: request threads read it without the lock
        print(f"[live] state v{self.version} from {os.path.basename(slot)} saved {saved} ({state['took']}s, {reason})")

    def _failed(self, e, sig):
        self.failed_sig, self.failed_at = sig, time.time()
        self.state = dict(self.state, status="error", error=self.public(e))  # keeps the last good state's data
        print(f"[live] could not read the save: {self.public(e)} (trying again in {RETRY_SECONDS} s)")

    def check(self):
        """One step of the watch loop: read the save when the folder changed and settled, or retry after a failure."""
        sig = None
        try:
            sig = _signature(self.save_dir)
            if sig == self.ok_sig:
                return
            if sig == self.failed_sig and time.time() - self.failed_at < RETRY_SECONDS:
                return
            time.sleep(SETTLE_SECONDS)
            if _signature(self.save_dir) != sig:
                return  # still being written
            reason = "start" if self.ok_sig is None and self.failed_sig is None else (
                "retry" if sig == self.failed_sig else "save changed")
            self.refresh(reason, sig)
            self.failed_sig = self.failed_at = None
        except Exception as e:
            self._failed(e, sig)

    def manual_refresh(self):
        """the page's "Re-read save now": a no-op if nothing changed since the last good read; errors land in the state"""
        sig = None
        try:
            sig = _signature(self.save_dir)
            self.refresh("manual", sig)
            self.failed_sig = self.failed_at = None
        except Exception as e:
            self._failed(e, sig)

    def watch(self):
        while True:
            self.check()
            time.sleep(POLL_SECONDS)


def lan_addresses():
    """IPv4 addresses of this PC on the local network, the one with the default route first (no packets are sent)."""
    primary, others = None, set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # TEST-NET address: only picks the outgoing interface
            primary = s.getsockname()[0]
    except OSError:
        pass
    try:
        others.update(a for a in socket.gethostbyname_ex(socket.gethostname())[2] if not a.startswith("127."))
    except OSError:
        pass
    return ([primary] if primary else []) + sorted(others - {primary})


class _Server(ThreadingHTTPServer):
    # Windows lets a second program bind a port that SO_REUSEADDR (the http.server default) left shareable:
    # two map servers would then both run and fight over work\live. Bind exclusively instead.
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(live, page_dir, port, lan=False, urls=(), map_dir=None, admin_from=("127.0.0.1", "::1")):
    """The HTTP side. live needs .state, .log_dir and .manual_refresh(); with .public_state(), .start_build(),
    .set_game_dir() and .switch_account() also the setup and account endpoints. page_dir holds the page, map_dir the
    map files built from the game (the same folder when run from source). The setup and account endpoints answer only
    clients in admin_from (this PC), also in LAN mode."""
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"} | {urlsplit(u).netloc for u in urls}
    map_dir = map_dir or page_dir

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=page_dir, **kw)

        def log_message(self, *a):
            pass

        def end_headers(self):
            # revalidate everything (page, data, and map images after a rebuild); API answers are never stored
            self.send_header("Cache-Control", "no-store" if getattr(self, "is_api", False) else "no-cache")
            super().end_headers()

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode("utf-8")
            self.is_api = True
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _trusted(self):
            # only this PC's own addresses: a web page elsewhere (or a DNS rebinding trick) can't use the API
            if (self.headers.get("Host") or "").lower() not in allowed_hosts:
                return False
            origin = self.headers.get("Origin")
            return not origin or urlsplit(origin).netloc.lower() in allowed_hosts

        def do_GET(self):
            if not self._trusted():
                return self.send_error(403)
            url = urlsplit(self.path)
            if url.path == "/api/log":
                return self._json(dd2_session.read_log(live.log_dir))
            if url.path == "/api/info":
                return self._json({"lan": lan, "urls": list(urls)})
            if url.path == "/api/state":
                # read once: the watcher replaces it as a whole
                state = live.public_state() if hasattr(live, "public_state") else live.state
                since = parse_qs(url.query).get("since", [""])[0]
                if since.isascii() and since.isdigit() and int(since) == state.get("version"):
                    return self._json({"version": state.get("version"), "unchanged": True, "status": state.get("status"),
                                       "error": state.get("error"), "setup": state.get("setup"),
                                       "accounts": state.get("accounts")})
                return self._json(state)
            if url.path.startswith("/api/"):
                return self.send_error(404)
            # Windows device names (CON, NUL, COM1...) are not files: opening one would block or answer empty
            if any(unquote(p).split(".")[0].upper() in WINDOWS_DEVICES for p in url.path.split("/") if p):
                return self.send_error(404)
            self.directory = map_dir if url.path.startswith(GENERATED) else page_dir
            return super().do_GET()

        def _body(self):
            """the request's JSON object; always read first, as answering before the body arrived resets the
            connection on Windows. Bodies over 4 KB are not read: the connection closes after the answer."""
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if not 0 < length <= 4096:
                self.close_connection = length > 0
                return {}
            try:
                body = json.loads(self.rfile.read(length))
            except ValueError:
                return {}
            return body if isinstance(body, dict) else {}

        def do_POST(self):
            body = self._body()
            if not self._trusted():
                return self.send_error(403)
            path = urlsplit(self.path).path
            if path in LOCAL_ONLY:
                if self.client_address[0] not in admin_from:
                    return self.send_error(403)
                if path == "/api/setup/build":
                    return self._json({"started": live.start_build()})
                if path == "/api/setup/game-dir":
                    problem = live.set_game_dir(str(body.get("path") or ""))
                    return self._json({"error": problem} if problem else {"ok": True}, 400 if problem else 200)
                account = body.get("id")
                if not isinstance(account, int) or isinstance(account, bool):
                    return self._json({"error": "id must be a Steam account number"}, 400)
                return self._json({"ok": True}) if live.switch_account(account) else self._json({"error": "no saves"}, 404)
            if path != "/api/refresh":
                return self.send_error(404)
            live.manual_refresh()
            state = live.state
            return self._json({"version": state.get("version"), "status": state.get("status"), "error": state.get("error")},
                              200 if state.get("status") == "ok" else 500)

    return _Server(("0.0.0.0" if lan else "127.0.0.1", port), Handler)


def _disable_quick_edit():
    """A click into the console window (say, to copy the address) would pause all output, and the reading with it,
    until a key is pressed. Turn that off for this window only."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, (mode.value & ~0x0040) | 0x0080)  # QUICK_EDIT off, EXTENDED_FLAGS on
    except Exception:
        pass


def port_taken(port, open_browser, opener=webbrowser.open):
    """the message when the port is in use; most often the tracker is already running, so with --open the running one
    is opened in the browser instead"""
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        opener(url)
        return f"The tracker is already running (port {port} is in use): opened it in your browser. You can close this window."
    return f"Port {port} is already in use. Is the tracker already running? Close that window first."


def serve(root, save_dir, account_id, assets, port=8642, tag="live", open_browser=False, lan=False, page_dir=None,
          steam=None):
    problem = dd2_paths.check_writable()
    if problem:
        sys.exit(problem)
    live = Live(root, save_dir, account_id, assets, tag, steam)
    urls = [f"http://{a}:{port}/" for a in lan_addresses()] if lan else []
    try:
        httpd = make_server(live, page_dir or os.path.join(root, "map"), port, lan, urls, map_dir=os.path.join(root, "map"))
    except OSError:
        sys.exit(port_taken(port, open_browser))
    _disable_quick_edit()
    if live.setup["needed"]:
        print("The map data is not built yet: building it from your game files (a few minutes, progress on the page).")
        live.start_build()
    else:
        live.start_watching()
    url = f"http://127.0.0.1:{port}/"
    print(f"DD2 Completionist Tracker: {url}  (watching {save_dir}; close this window or press Ctrl+C to stop)")
    for u in urls:
        print(f"  on your phone (same Wi-Fi): {u}")
    if lan:
        who = "DD2 Completionist Tracker" if dd2_paths.FROZEN else "Python"
        print(f"  If the phone can't connect, Windows must let {who} accept connections on this network. On a network")
        print("  Windows calls 'Private', allow it in the prompt; on a 'Public' one, allow public networks or make the")
        print("  network 'Private' in the Windows network settings.")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, [url]).start()
    httpd.serve_forever()
