"""Run the test scripts: python tests/run.py [unit|local|all] (default: unit).

unit:  synthetic data only, runs anywhere (GitHub Actions, any PC).
local: real game files and saves; a script whose inputs are missing reports SKIP.
Each script runs in its own process; the full output of a failing one is printed. Exit code 1 if any failed."""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(kinds):
    failed = 0
    for kind in kinds:
        for script in sorted(glob.glob(os.path.join(HERE, kind, "test_*.py"))):
            name = f"{kind}/{os.path.basename(script)}"
            proc = subprocess.run([sys.executable, script], capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", cwd=os.path.dirname(HERE))
            out = proc.stdout + proc.stderr
            if proc.returncode != 0:
                failed += 1
                print(f"FAIL {name}\n" + "\n".join("     " + line for line in out.rstrip().splitlines()))
            elif any(line.startswith("SKIP ") for line in out.splitlines()):
                reason = next(line for line in out.splitlines() if line.startswith("SKIP "))[5:]
                print(f"SKIP {name}: {reason}")
            else:
                print(f"ok   {name}")
    print(f"\n{failed} script(s) failed")
    return 1 if failed else 0


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "unit"
    kinds = {"unit": ["unit"], "local": ["local"], "all": ["unit", "local"]}.get(arg)
    if not kinds:
        sys.exit(__doc__)
    sys.exit(run(kinds))


if __name__ == "__main__":
    main()
