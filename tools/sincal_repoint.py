"""Point a copied SINCAL project at its own database.

A SINCAL project stores an absolute path to its database in <name>_files/database.ini.
Copy the project to another machine and that path is wrong, so SINCAL opens it against
nothing. Run this once after copying, from anywhere, giving it the .sin file.

    py sincal_repoint.py EULV_study.sin
"""
import os
import sys


def repoint(sin_path):
    sin_path = os.path.abspath(sin_path)
    files = os.path.splitext(sin_path)[0] + "_files"
    db = os.path.join(files, "database.db")
    ini = os.path.join(files, "database.ini")
    for p in (files, db, ini):
        if not os.path.exists(p):
            raise SystemExit("missing: %s" % p)
    with open(ini, encoding="utf-8") as f:
        lines = f.read().splitlines()
    out = ["FILE=" + db if ln.upper().startswith("FILE=") else ln for ln in lines]
    with open(ini, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("pointed at %s" % db)


if __name__ == "__main__":
    repoint(sys.argv[1] if len(sys.argv) > 1 else "EULV_study.sin")
