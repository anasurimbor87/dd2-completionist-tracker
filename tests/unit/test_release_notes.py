"""The text of a GitHub Release (tools/release_notes.py): the version's section of CHANGELOG.md, without its heading,
plus a short footer for new and updating players. Run: python tests/unit/test_release_notes.py"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import ROOT, check, finish  # noqa: E402

import release_notes  # noqa: E402

LOG = """# Changelog

Intro text.

## [2.0.0] - 2030-01-02

Second version.

### Added

- Something new.

## [1.0.0] - 2030-01-01

First version.

[2.0.0]: https://example.org/compare/v1.0.0...v2.0.0
[1.0.0]: https://example.org/releases/tag/v1.0.0
"""


def main():
    two = release_notes.section(LOG, "v2.0.0")
    check(two == "Second version.\n\n### Added\n\n- Something new.", f"a section without its heading, up to the next one ({two!r})")
    one = release_notes.section(LOG, "1.0.0")
    check(one == "First version.", f"the last section stops before the link list, with or without the v ({one!r})")
    check(release_notes.section(LOG, "v3.0.0") is None, "a version without a section has none")
    check(release_notes.section(LOG, "v1.0") is None, "a version must match whole, not as a prefix")

    # GitHub shows every line break of a release text: lines wrapped in the file are joined again
    wrapped = "One sentence\nwrapped here.\n\n### Added\n\n- An item\n  wrapped too.\n- **Bold** item.\n\n---\n\nEnd."
    joined = release_notes.unwrap(wrapped)
    check(joined == "One sentence wrapped here.\n\n### Added\n\n- An item wrapped too.\n- **Bold** item.\n\n---\n\nEnd.",
          f"wrapped paragraphs and list items become one line each ({joined!r})")
    notes = release_notes.notes(LOG, "v2.0.0", "someone/tracker")
    check(notes.startswith("Second version.") and "https://github.com/someone/tracker#download-and-start" in notes
          and "https://github.com/someone/tracker/blob/main/CHANGELOG.md" in notes,
          "the release text: the section, then links to starting, updating and all changes")
    try:
        release_notes.notes(LOG, "v3.0.0", "someone/tracker")
        failed = False
    except SystemExit:
        failed = True
    check(failed, "a tag without a changelog section stops the release")

    # the real changelog: each version heads its section with a date and has its link at the bottom
    text = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    versions = re.findall(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$", text, re.M)
    headings = re.findall(r"^## .*$", text, re.M)
    check(versions and len(versions) == len(headings), f"every section is '## [x.y.z] - YYYY-MM-DD' ({headings})")
    check(all(re.search(rf"^\[{re.escape(v)}\]: https://", text, re.M) for v in versions), "every version has its link")
    check(all(release_notes.section(text, v) for v in versions), "every version's section has text")
    flow = open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8").read()
    check("tools/release_notes.py" in flow and "body_path: release-notes.md" in flow and "generate_release_notes" not in flow,
          "the release workflow uses the changelog section as the release text")
    finish()


if __name__ == "__main__":
    main()
