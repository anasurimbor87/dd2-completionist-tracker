"""Where the tracker reads its page and writes its data: the repository when run from source, DD2_DATA_DIR when set,
and a clear message when that folder can't be written. Run: python tests/unit/test_paths.py"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish  # noqa: E402

PROBE = ("import sys, json; sys.path.insert(0, sys.argv[1]); import dd2_paths as p; "
         "print(json.dumps([p.APP_DIR, p.DATA_DIR, p.page_dir(), p.map_out_dir(), p.assets_dir(), p.check_writable()]))")


def probe(env_dir):
    env = {k: v for k, v in os.environ.items() if k != "DD2_DATA_DIR"}
    if env_dir:
        env["DD2_DATA_DIR"] = env_dir
    out = subprocess.run([sys.executable, "-c", PROBE, os.path.join(ROOT, "tools")], env=env,
                         capture_output=True, text=True)
    import json
    return json.loads(out.stdout) if out.returncode == 0 else out.stderr


def main():
    app, data, page, maps, assets, problem = probe(None)
    check(os.path.normpath(app) == os.path.normpath(ROOT) == os.path.normpath(data), "from source both folders are the repository")
    check(os.path.normpath(page) == os.path.join(os.path.normpath(ROOT), "map") and os.path.normpath(maps) == os.path.normpath(page),
          "the page and the generated map files share map/ from source")
    check(os.path.normpath(assets) == os.path.join(os.path.normpath(ROOT), "assets") and problem is None,
          "assets/ next to the code, and the folder is writable")
    with tempfile.TemporaryDirectory() as tmp:
        app, data, page, maps, assets, problem = probe(tmp)
        check(os.path.normpath(data) == os.path.normpath(tmp) and os.path.normpath(maps) == os.path.join(os.path.normpath(tmp), "map")
              and os.path.normpath(page) == os.path.join(os.path.normpath(ROOT), "map"),
              "DD2_DATA_DIR moves the data, not the page")
        check(os.path.normpath(assets) == os.path.join(os.path.normpath(ROOT), "assets"),
              f"nor the pinned third-party data, which stays next to the code ({assets})")
        env = dict(os.environ, DD2_DATA_DIR=tmp)
        lock = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import dd2; print(dd2.ASSETS_LOCK)", ROOT],
                              env=env, capture_output=True, text=True)
        check(os.path.normpath(lock.stdout.strip()) == os.path.join(os.path.normpath(ROOT), "assets.lock.json"),
              f"fetch-assets reads the lock next to the code ({lock.stdout.strip() or lock.stderr.strip()[-120:]})")
        blocked = os.path.join(tmp, "a file, not a folder")
        open(blocked, "w").close()
        *_rest, problem = probe(blocked)
        check(isinstance(problem, str) and blocked in problem and "Documents" in problem,
              f"an unwritable data folder gets a message naming it and suggesting Documents ({problem})")
    finish()


if __name__ == "__main__":
    main()
