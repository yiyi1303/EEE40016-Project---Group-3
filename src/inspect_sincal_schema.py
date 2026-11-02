"""Dump the SINCAL SQLite schema from a known-good project.

The feeder has 906 nodes and 905 lines, which rules out drawing it by hand. The fast
route is to write rows straight into SINCAL's own SQLite database, so we first need to
know exactly what columns those tables have and which ones are mandatory. Lab1 is a
small model that SINCAL itself created and solved, so it is a trustworthy template.

Run:  py src/inspect_sincal_schema.py
Out:  notes/sincal_schema.md
"""
import os
import sqlite3

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(os.path.dirname(HERE), "Lab1_files", "database.db")
OUT = os.path.join(HERE, "notes", "sincal_schema.md")

# The tables the importer has to populate, plus the ones that describe the study setup.
WANTED = ["Node", "Line", "Load", "TwoWindingTransformer", "Terminal", "Element",
          "VoltageLevel", "GraphicNode", "GraphicText", "CalcParameter", "Infeeder"]


def main():
    if not os.path.exists(TEMPLATE):
        raise SystemExit("template database not found: %s" % TEMPLATE)

    con = sqlite3.connect("file:%s?mode=ro" % TEMPLATE.replace("\\", "/"), uri=True)
    all_tables = [r[0] for r in con.execute(
        "select name from sqlite_master where type='table' order by name")]

    populated = []
    for t in all_tables:
        try:
            n = con.execute("select count(*) from [%s]" % t).fetchone()[0]
        except sqlite3.Error:
            n = -1
        if n > 0:
            populated.append((t, n))

    lines = ["# PSS(R)SINCAL SQLite schema",
             "",
             "Read from `%s` (Lab 1, built and solved by SINCAL itself)." % os.path.basename(TEMPLATE),
             "",
             "%d tables in the file, %d of them populated." % (len(all_tables), len(populated)),
             "",
             "## Populated tables",
             "",
             "| Table | Rows |", "| --- | ---: |"]
    lines += ["| %s | %d |" % (t, n) for t, n in populated]

    lines += ["", "## Columns of the tables the importer writes", ""]
    for t in WANTED:
        if t not in all_tables:
            lines += ["### %s" % t, "", "_not present in this model_", ""]
            continue
        cols = con.execute("PRAGMA table_info([%s])" % t).fetchall()
        n = con.execute("select count(*) from [%s]" % t).fetchone()[0]
        lines += ["### %s  (%d columns, %d rows here)" % (t, len(cols), n), "",
                  "| # | Column | Type | Not null | Default | PK |",
                  "| ---: | --- | --- | :---: | --- | :---: |"]
        for cid, name, typ, notnull, dflt, pk in cols:
            lines.append("| %d | `%s` | %s | %s | %s | %s |" % (
                cid, name, typ or "", "yes" if notnull else "", "" if dflt is None else dflt,
                "yes" if pk else ""))
        # one real row, so we can see what SINCAL actually puts in each field
        row = con.execute("select * from [%s] limit 1" % t).fetchone()
        if row:
            names = [c[1] for c in cols]
            shown = ", ".join("%s=%r" % (k, v) for k, v in zip(names, row) if v not in (None, "", 0))
            lines += ["", "Example row (non-empty fields only):", "", "```", shown, "```"]
        lines.append("")

    con.close()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s" % OUT)
    print("%d tables, %d populated" % (len(all_tables), len(populated)))
    for t, n in populated:
        print("   %-28s %d" % (t, n))


if __name__ == "__main__":
    main()
