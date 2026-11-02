"""Build the zip that hands the whole project to a teammate: EEE40016_for_Gia.zip.

    py tools/make_handover.py [--out EEE40016_for_Gia.zip]

Everything needed to run, check and finish the work on another laptop with a Raspberry Pi:
the code, settings, data (the raw VISTA survey included, so sessions can be rebuilt), every
current result, the guides, the teammates' parts, the SINCAL files, and README_FIRST.md on
top. The Pi package is rebuilt first, so it matches the code. Left out: run logs, Python
caches, the unpacked Pi folder (the tools rebuild it), and results/superseded (results from
before faults were fixed, which must not be quoted).
"""
import argparse
import os
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = "EEE40016_project"
FILES = ["README_FIRST.md", "README.md", "requirements_laptop.txt", "pi_package.zip",
         "avd_crosscheck.zip"]
FOLDERS = ["config", "data", "docs", "notes", "results", "src", "tests", "tools", "team",
           "models"]
SKIP_DIRS = {"__pycache__", ".git", ".claude", "superseded"}
SKIP_EXT = (".pyc", ".pyo")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "EEE40016_for_Gia.zip"))
    a = ap.parse_args()
    print("rebuilding the Pi package ...")
    if subprocess.call([sys.executable, os.path.join(HERE, "tools", "make_pi_package.py")]):
        raise SystemExit("the Pi package did not build")
    out = os.path.abspath(a.out)
    tmp = out + ".part"
    n, size = 0, 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in FILES:
            p = os.path.join(HERE, f)
            if not os.path.exists(p):
                raise SystemExit("missing %s" % f)
            z.write(p, "%s/%s" % (TOP, f))
            n, size = n + 1, size + os.path.getsize(p)
        for d in FOLDERS:
            for root, dirs, files in os.walk(os.path.join(HERE, d)):
                dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
                for fn in sorted(files):
                    if fn.endswith(SKIP_EXT):
                        continue
                    p = os.path.join(root, fn)
                    if os.path.abspath(p) in (out, tmp):
                        continue
                    rel = os.path.relpath(p, HERE).replace(os.sep, "/")
                    z.write(p, "%s/%s" % (TOP, rel))
                    n, size = n + 1, size + os.path.getsize(p)
    os.replace(tmp, out)
    print("wrote %s: %d files, %.1f MB unpacked, %.1f MB zipped (%s)"
          % (os.path.relpath(out, HERE), n, size / 1e6, os.path.getsize(out) / 1e6,
             time.strftime("%Y-%m-%d %H:%M")))


if __name__ == "__main__":
    main()
