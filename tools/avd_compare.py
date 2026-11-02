"""Compare a SINCAL result brought back from the uni AVD with OpenDSS on this laptop.

The AVD has the full SINCAL licence, so it can solve the 906-bus feeder that the Xplore
licence here refuses. Solve there, copy the project's _files folder back, then run this on
the returned database:

    py tools/avd_compare.py path/to/EULV_benchmark_files/database.db
    py tools/avd_compare.py path/to/EULV_study_files/database.db

The kW and kvar of every load are read out of the returned database, so OpenDSS solves
exactly the loading SINCAL solved, whatever minute the model was built at. The case
(transformer rating and source voltage) is read from the database too. For the benchmark
case the published IEEE solution is added as a third column, so the result is a three-way
agreement: IEEE, OpenDSS and SINCAL.

Pass criterion as V1: every node voltage within 0.5%.
Out: notes/avd_crosscheck_<case>.md
"""
import json
import math
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, os.path.join(HERE, "tests"))
from feeder_csv import load_feeder                       # noqa: E402
from solver import OpenDSSSolver, read_sincal_voltages   # noqa: E402

TOLERANCE_PCT = 0.5


def case_from_db(db):
    con = sqlite3.connect("file:%s?mode=ro" % os.path.abspath(db).replace("\\", "/"), uri=True)
    sn = con.execute("select Sn from TwoWindingTransformer").fetchone()[0]
    u = con.execute("select u from Infeeder").fetchone()[0]
    loads = {name.strip(): (p * 1000.0, q * 1000.0) for name, p, q in con.execute(
        "select e.Name, l.P, l.Q from Load l join Element e using (Element_ID)")}
    con.close()
    return {"transformer_kva": round(sn * 1000.0, 3), "source_pu": round(u / 100.0, 6),
            "loads": loads}


def main(db):
    if not os.path.exists(db):
        raise SystemExit("no such file: %s" % db)
    v_sin = read_sincal_voltages(db)           # raises if only a balanced result is present
    case = case_from_db(db)
    name = "benchmark" if abs(case["transformer_kva"] - 800) < 1 else "study"

    f = load_feeder()
    pf = {ld.name: ld.pf for ld in f.loads}
    for ld_name, (p, q) in case["loads"].items():
        if ld_name in pf and p > 0:
            implied = p / math.hypot(p, q)
            if abs(implied - pf[ld_name]) > 1e-3:
                print("warning: %s power factor %.4f in SINCAL, %.4f in the package"
                      % (ld_name, implied, pf[ld_name]))

    dss = OpenDSSSolver(feeder=f, transformer_kva=case["transformer_kva"],
                        source_pu=case["source_pu"]).build()
    dss.set_loads({k: p for k, (p, _) in case["loads"].items()})
    dss.solve()
    v_dss = dss.node_voltages()

    diffs = {k: 100.0 * abs(v_sin[k] - v_dss[k]) / v_dss[k] for k in v_dss
             if k in v_sin and v_dss[k] > 0}
    worst = max(diffs, key=diffs.get)
    missing = sorted(set(v_dss) - set(v_sin))
    passed = diffs[worst] <= TOLERANCE_PCT and not missing

    ieee = None
    if name == "benchmark":
        from v1_benchmark import published_voltages
        ref = published_voltages()
        d_ieee = {k: 100.0 * abs(v_sin[k] - ref[k]) / ref[k] for k in ref if k in v_sin}
        wk = max(d_ieee, key=d_ieee.get)
        ieee = {"compared": len(d_ieee), "max_pct": d_ieee[wk], "worst": "%s.%d" % wk,
                "mean_pct": sum(d_ieee.values()) / len(d_ieee)}
        passed = passed and ieee["max_pct"] <= TOLERANCE_PCT

    lines = ["# SINCAL (uni AVD) against OpenDSS, full feeder, %s case" % name, "",
             "| | |", "| --- | --- |",
             "| database | `%s` |" % os.path.abspath(db),
             "| transformer | %g kVA |" % case["transformer_kva"],
             "| source | %.2f pu |" % case["source_pu"],
             "| total load | %.2f kW |" % sum(p for p, _ in case["loads"].values()),
             "| phase-nodes compared | %d |" % len(diffs),
             "| nodes missing from SINCAL | %d |" % len(missing),
             "| largest difference, SINCAL vs OpenDSS | %.4f%% at %s.%d |"
             % (diffs[worst], worst[0], worst[1]),
             "| mean difference | %.4f%% |" % (sum(diffs.values()) / len(diffs))]
    if ieee:
        lines += ["| largest difference, SINCAL vs published IEEE | %.4f%% at %s |"
                  % (ieee["max_pct"], ieee["worst"]),
                  "| mean difference vs IEEE | %.4f%% |" % ieee["mean_pct"]]
    lines += ["| result (within %.1f%%) | **%s** |" % (TOLERANCE_PCT,
                                                     "PASS" if passed else "FAIL"), ""]
    out = os.path.join(HERE, "notes", "avd_crosscheck_%s.md" % name)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))
    print("wrote", out)
    return 0 if passed else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
