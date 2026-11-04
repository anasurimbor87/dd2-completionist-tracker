"""The leak guard finds personal data and game files before they reach git.
Run: python tests/unit/test_check_publish.py"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import check_publish  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as tmp:
        # built from pieces so this file itself passes the scan
        files = {
            "a.txt": "see C:" + "\\Users\\someone\\x for details",
            "b.txt": "mail me at someone" + "@" + "mailhost.de",
            "c.txt": "1+x@users.noreply.github.com noreply@anthropic.com you@example.org C:\\Users\\<name>",
            "d.txt": "my Arisen is Brunhild",
            "e.txt": "Steam/userdata/12345678/2054970",
            "f.user.3": "",
            "g.jpg": "",
            "clean.py": "print('hello')\n",
        }
        for name, text in files.items():
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
                f.write(text)
        with open(os.path.join(tmp, "big.bin"), "wb") as f:
            f.write(b"\0" * (5 * 1024 * 1024 + 1))
        paths = sorted(files) + ["big.bin"]

        problems = check_publish.scan(paths, tmp, private=["Brunhild"], account_ids=[12345678])
        for p in problems:
            print("   ", p)
        check(any("a.txt" in p and "user path" in p for p in problems), "a path under a user's folder is found")
        check(any("b.txt" in p and "e-mail" in p for p in problems), "an e-mail address is found")
        check(not any("c.txt" in p for p in problems), "no-reply and example addresses and the <name> placeholder are allowed")
        check(any("d.txt" in p and "Brunhild" in p for p in problems), "a private string is found")
        check(any("e.txt" in p and "12345678" in p for p in problems), "a Steam account id is found")
        check(any("f.user.3" in p for p in problems) and any("g.jpg" in p for p in problems),
              "game file types and images are refused")
        check(any("big.bin" in p and "5 MB" in p for p in problems), "files over 5 MB are refused")
        check(check_publish.scan(["clean.py"], tmp, [], []) == [], "a clean file passes")
        # Steam's userdata\0 (no account) or a short folder name would match any number in the code
        check(check_publish.usable_ids([0, 7, 12345678]) == [12345678], "only real account ids are searched for")

        # every account on the PC counts, with or without DD2 saves
        steam = os.path.join(tmp, "Steam")
        for acc, slot in (("22222222", None), ("33333333", "data001Slot.bin"), ("0", None)):
            d = os.path.join(steam, "userdata", acc, "2054970", "remote", "win64_save")
            os.makedirs(d)
            if slot:
                open(os.path.join(d, slot), "wb").close()
        check(sorted(check_publish.account_ids(steam)) == [22222222, 33333333], "all Steam accounts of the PC are searched for")

        # the pre-commit hook also sees files that were renamed into the commit
        repo = os.path.join(tmp, "repo")
        os.makedirs(repo)
        git = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, check=True).stdout
        git("init", "-q")
        git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "--allow-empty", "-m", "start")
        with open(os.path.join(repo, "old.txt"), "w") as f:
            f.write("a line\n")
        git("add", "old.txt")
        git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "add")
        git("mv", "old.txt", "new.txt")
        check("new.txt" in check_publish.git_files(True, repo), "a renamed file is checked by the hook")
    finish()


if __name__ == "__main__":
    main()
