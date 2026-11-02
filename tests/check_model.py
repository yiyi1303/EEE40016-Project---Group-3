"""Structural checks on a built SINCAL database, before opening it in SINCAL.

SINCAL will not tell you politely when a model is inconsistent; it either refuses the
project or solves something that is not what you meant. These checks catch the mistakes
that writing rows by hand can produce: dangling references, elements with no detail row,
branches with the wrong number of terminals, buses nothing connects to.

Run:  py tests/check_model.py models/EULV_benchmark_files/database.db
"""
import os
import sqlite3
import sys

TWO_TERMINAL = {"Line", "TwoWindingTransformer"}
ONE_TERMINAL = {"Load", "Infeeder", "SynchronousMachine"}


def check(db):
    con = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
    q = lambda s, *a: con.execute(s, a).fetchall()          # noqa: E731
    one = lambda s, *a: con.execute(s, a).fetchone()[0]     # noqa: E731

    problems, facts = [], {}

    facts["nodes"] = one("select count(*) from Node")
    facts["elements"] = one("select count(*) from Element")
    facts["terminals"] = one("select count(*) from Terminal")
    for t in sorted(r[0] for r in q("select distinct Type from Element")):
        facts["  " + t] = one("select count(*) from Element where Type=?", t)

    # every terminal must point at a node and an element that exist
    n = one("select count(*) from Terminal t left join Node n using (Node_ID) "
            "where n.Node_ID is null")
    if n:
        problems.append("%d terminal(s) reference a node that does not exist" % n)
    n = one("select count(*) from Terminal t left join Element e using (Element_ID) "
            "where e.Element_ID is null")
    if n:
        problems.append("%d terminal(s) reference an element that does not exist" % n)

    # every element must have its detail row in the matching type table
    tables = {r[0] for r in q("select name from sqlite_master where type='table'")}
    for (typ,) in q("select distinct Type from Element"):
        if typ not in tables:
            problems.append("element type %s has no table" % typ)
            continue
        n = one("select count(*) from Element e where e.Type=? and e.Element_ID not in "
                "(select Element_ID from [%s])" % typ, typ)
        if n:
            problems.append("%d %s element(s) have no row in the %s table" % (n, typ, typ))
        n = one("select count(*) from [%s] x where x.Element_ID not in "
                "(select Element_ID from Element)" % typ)
        if n:
            problems.append("%d orphan row(s) in %s with no Element" % (n, typ))

    # terminal counts per element type
    for typ, want in [(t, 2) for t in TWO_TERMINAL] + [(t, 1) for t in ONE_TERMINAL]:
        bad = q("select e.Name, count(t.Terminal_ID) c from Element e "
                "left join Terminal t using (Element_ID) where e.Type=? "
                "group by e.Element_ID having c != ?", typ, want)
        if bad:
            problems.append("%d %s element(s) do not have %d terminal(s), e.g. %s"
                            % (len(bad), typ, want, ", ".join(b[0] for b in bad[:5])))

    # a two-terminal element joining a node to itself is a modelling error
    bad = one("select count(*) from (select Element_ID from Terminal group by Element_ID "
              "having count(*)=2 and count(distinct Node_ID)=1)")
    if bad:
        problems.append("%d branch(es) have both terminals on the same node" % bad)

    # every node should have at least one thing connected to it
    islanded = one("select count(*) from Node where Node_ID not in "
                   "(select Node_ID from Terminal)")
    facts["nodes with nothing attached"] = islanded
    if islanded:
        problems.append("%d node(s) have no terminal attached" % islanded)

    # ids unique
    for t, col in [("Node", "Node_ID"), ("Element", "Element_ID"),
                   ("Terminal", "Terminal_ID")]:
        if one("select count(*) from %s" % t) != one(
                "select count(distinct %s) from %s" % (col, t)):
            problems.append("%s has duplicate %s values" % (t, col))

    # phase bitmask on terminals must be 1..7
    n = one("select count(*) from Terminal where Flag_Terminal not between 1 and 7")
    if n:
        problems.append("%d terminal(s) have an out-of-range phase bitmask" % n)
    facts["single-phase terminals"] = one(
        "select count(*) from Terminal where Flag_Terminal in (1,2,4)")

    # electrical sanity
    facts["total load (kW)"] = round(one("select sum(P) from Load") * 1000.0, 2)
    facts["total line length (km)"] = round(one("select sum(l) from Line"), 4)
    facts["transformer (kVA)"] = round(one("select Sn from TwoWindingTransformer") * 1000.0)
    n = one("select count(*) from Line where r <= 0 or x <= 0 or l <= 0")
    if n:
        problems.append("%d line(s) have a non-positive length, r or x" % n)
    n = one("select count(*) from Line where Ith <= 0")
    facts["lines with no thermal rating"] = n

    # everything must be in variant 1 and switched in, or it silently drops out
    for t in ("Node", "Element", "Terminal"):
        n = one("select count(*) from [%s] where Variant_ID != 1" % t)
        if n:
            problems.append("%d row(s) in %s are not in variant 1" % (n, t))
    n = one("select count(*) from Element where Flag_State != 1")
    if n:
        problems.append("%d element(s) are switched out" % n)

    con.close()
    return problems, facts


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    db = sys.argv[1]
    if not os.path.exists(db):
        raise SystemExit("no such database: %s" % db)

    problems, facts = check(db)
    print(os.path.basename(os.path.dirname(db)))
    for k, v in facts.items():
        print("  %-30s %s" % (k, v))
    print()
    if problems:
        print("FAILED %d check(s):" % len(problems))
        for p in problems:
            print("  -", p)
        return 1
    print("all structural checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
