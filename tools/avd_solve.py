"""Solve the feeder projects with SINCAL's unbalanced load flow. Run this ON THE UNI AVD.

Needs Python with pywin32 (py -m pip install pywin32). Run from the folder this file is in:

    py avd_solve.py

For each EULV_*.sin next to this script it points the project at its own database (the
path inside database.ini is from the laptop it was built on), runs the unbalanced load flow
(LF_USYM), checks SINCAL's log for warnings, and says whether per-phase results were
written. Then copy the EULV_*_files folders back to the laptop and run tools/avd_compare.py
on each database.db.

No Python on the AVD? Do it by hand instead, per README.txt: open each .sin in SINCAL, run
the UNBALANCED load flow (not the ordinary one), save, close, copy the _files folder back.
"""
import glob
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def repoint(sin):
    files = os.path.splitext(sin)[0] + "_files"
    db = os.path.join(files, "database.db")
    ini = os.path.join(files, "database.ini")
    with open(ini, encoding="utf-8") as f:
        lines = f.read().splitlines()
    with open(ini, "w", encoding="utf-8") as f:
        f.write("\n".join("FILE=" + db if ln.upper().startswith("FILE=") else ln
                          for ln in lines) + "\n")
    return files, db


def solve(sin):
    import win32com.client as w
    files, db = repoint(sin)
    sim = w.Dispatch("Sincal.Simulation")   # do not call BatchMode: it crashes the caller
    sim.Init("EN")
    sim.DataSource("SQLITE", db, "", "")
    sim.Start("LF_USYM")
    ok = sim.StatusID == 1101
    con = sqlite3.connect(db)
    n = con.execute("select count(*) from ULFNodeResult").fetchone()[0]
    nodes = con.execute("select count(*) from Node").fetchone()[0]
    con.close()
    warnings = []
    log = os.path.join(files, "LOG", "Log.001.db")
    if os.path.exists(log):
        lc = sqlite3.connect(log)
        warnings = [t for (t,) in lc.execute(
            "select distinct Text from LogMsg where LogLevel >= 20")]
        lc.close()
    print("%-22s status %s  per-phase node results %d of %d nodes"
          % (os.path.basename(sin), "OK" if ok else sim.StatusText, n, nodes))
    for t in warnings:
        print("    SINCAL says:", t)
    return ok and n == nodes and not warnings


def main():
    sins = sorted(glob.glob(os.path.join(HERE, "EULV_*.sin")))
    if not sins:
        raise SystemExit("no EULV_*.sin next to this script")
    results = [solve(s) for s in sins]
    print()
    if all(results):
        print("All solved cleanly. Copy these folders back to the laptop:")
        for s in sins:
            print("   ", os.path.splitext(s)[0] + "_files")
    else:
        print("Something did not solve cleanly; bring the LOG folder back as well.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
