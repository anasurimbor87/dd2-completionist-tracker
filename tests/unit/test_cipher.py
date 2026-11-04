"""The save container and cipher on a made-up save: it decrypts back to its body, damaged files are refused.
Run: python tests/unit/test_cipher.py"""
import contextlib
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testlib import check, finish  # noqa: E402

import dd2_decrypt  # noqa: E402
import savebuilder  # noqa: E402

ACCOUNT = 12345678  # made up


def process(path, account, out):
    with contextlib.redirect_stdout(io.StringIO()):
        return dd2_decrypt.process(path, account, out)


def error_of(fn):
    try:
        fn()
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return None


def main():
    body = b"made-up save body " * 400
    big = bytes(range(256)) * 1200  # 300 KB: several cipher blocks
    with tempfile.TemporaryDirectory() as tmp:
        def write(name, data):
            path = os.path.join(tmp, name)
            with open(path, "wb") as f:
                f.write(data)
            return path

        raw = savebuilder.build_save(body, ACCOUNT)
        check(process(write("data001Slot.bin", raw), ACCOUNT, tmp) == body, "a made-up save decrypts and inflates to its body")
        plain = write("data002Slot.bin", savebuilder.build_save(big, ACCOUNT, deflate=False))
        check(process(plain, ACCOUNT, tmp) == big, "a 300 KB save without deflate decrypts over several blocks")
        flipped = bytearray(raw)
        flipped[len(flipped) // 2] ^= 0xFF
        e = error_of(lambda: process(write("flipped.bin", bytes(flipped)), ACCOUNT, tmp))
        check(e is not None and "hash mismatch" in e, f"a damaged byte is refused ({e})")
        e = error_of(lambda: process(write("short.bin", raw[:20]), ACCOUNT, tmp))
        check(e is not None and "too short" in e, f"a 20-byte file is refused ({e})")
        e = error_of(lambda: process(write("other.bin", raw), ACCOUNT + 1, tmp))
        check(e is not None, f"another account's key does not read the save ({e})")
    finish()


if __name__ == "__main__":
    main()
