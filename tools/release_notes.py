"""The text of a GitHub Release: the version's section of CHANGELOG.md (written for players, see CONTRIBUTING.md),
plus a short footer. The release workflow runs it for the pushed tag; a tag without a section stops the release.
Run: python tools/release_notes.py v1.1.0 [out file]"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "anasurimbor87/dd2-completionist-tracker"


def section(text, version):
    """the body of the '## [version] - date' section, without its heading, or None"""
    v = re.escape(version[1:] if version.startswith("v") else version)
    m = re.search(rf"^## \[{v}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]\n]+\]: |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m and m.group(1).strip() else None


def unwrap(body):
    """one line per paragraph and list item: GitHub shows each line break of a release text, while CHANGELOG.md is
    wrapped for reading in an editor"""
    out = []
    for line in body.split("\n"):
        starts_block = not line.strip() or line.startswith(("#", "- ", "---"))
        if out and out[-1].strip() and not out[-1].startswith(("#", "---")) and not starts_block:
            out[-1] += " " + line.strip()
        else:
            out.append(line)
    return "\n".join(out)


def notes(text, version, repo=REPO):
    body = section(text, version)
    if body is None:
        raise SystemExit(f"CHANGELOG.md has no section for {version}: write one before tagging")
    url = f"https://github.com/{repo}"
    return (f"{unwrap(body)}\n\n---\n\n"
            f"**New here?** Download the ZIP below and see [Download and start]({url}#download-and-start). "
            f"**Updating?** See \"How do I update?\" in the [questions]({url}#questions). "
            f"Every version's changes: [CHANGELOG.md]({url}/blob/main/CHANGELOG.md).\n")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    text = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    out = notes(text, sys.argv[1], os.environ.get("GITHUB_REPOSITORY") or REPO)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as f:
            f.write(out)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(out, end="")


if __name__ == "__main__":
    main()
