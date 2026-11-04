"""Licence texts of what the Windows program ships besides our own code: the Python runtime and the installed
packages bundled by PyInstaller (cryptography with its statically linked OpenSSL, Pillow with the image libraries it
bundles, PyInstaller's bootloader). packaging/tracker.spec copies them into licenses/ next to the exe."""
import importlib.metadata
import os
import shutil
import sys

BUNDLED = ("cryptography", "pillow", "pyinstaller")
MARKERS = ("LICEN", "COPYING", "NOTICE")


def collect(dest, dists=BUNDLED):
    """copy the licence files into dest as <package>-<file>; returns (files copied, packages not installed)"""
    os.makedirs(dest, exist_ok=True)
    copied, missing = [], []
    python = os.path.join(sys.base_prefix, "LICENSE.txt")
    if not os.path.exists(python):
        raise FileNotFoundError(f"Python's licence text is missing: {python}")
    shutil.copyfile(python, os.path.join(dest, "python-LICENSE.txt"))
    copied.append("python-LICENSE.txt")
    for name in dists:
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
            continue
        for f in dist.files or []:
            base = os.path.basename(str(f))
            if any(m in base.upper() for m in MARKERS) and "dist-info" in str(f):
                target = f"{name}-{base}" + ("" if os.path.splitext(base)[1] else ".txt")
                shutil.copyfile(dist.locate_file(f), os.path.join(dest, target))
                copied.append(target)
    return copied, missing
