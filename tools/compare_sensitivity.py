"""The two setpoint-schedule sensitivity runs against the main case, cell by cell.

    py tools/compare_sensitivity.py

Each variant ran B and C on the six hold-heavy cells (stages.py S1H_POINTS) for the same
13 seeds as the main case, so every run pairs with the main-case run at the same controller,
cell and seed in results/stages.

    uncovered0   cars that arrived after the governing schedule was issued wait at 0 kW
                 instead of drawing the 1.4 kW fallback (amendment 22's rule). Pre-registered
                 trigger: if held-step violations with an uncovered car drawing are more than
                 25% of the main case's held-step violations, propose uncovered_kw = 0 to the
                 EV node.
    app_basis    trust and age at the time each entry is applied, rather than at the time it
                 was planned, so the controller law itself shades later entries harder.

Out: results/sensitivity/comparison.md
"""
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from stages import S1H_POINTS                                   # noqa: E402


def load(folder, stage):
    runs = {}
    for p in glob.glob(os.path.join(HERE, folder, "%s_seed*.json" % stage)):
        for r in json.load(open(p, encoding="utf-8"))["runs"]:
            runs[(r["controller"], r["latency_s"], r["loss"], r["seed"])] = r
    return runs


def held(r):
    return sum(v for k, v in r["viol_by_entry"].items() if k not in ("0", "D"))


def main():
    base = load("results/stages", "S1")
    out = ["# Setpoint-schedule sensitivity runs against the main case (S1 demand)", "",
           "Six hold-heavy cells (%s), B and C, 13 seeds; each run paired with the main-case "
           "run at the same controller, cell and seed." % ", ".join(
               "%d s/%g%%" % (l, p * 100) for l, p in S1H_POINTS), ""]
    for name, folder, what in (
            ("uncovered0", "results/sensitivity/uncovered0", "late cars wait at 0 kW"),
            ("app_basis", "results/sensitivity/app_basis", "trust and age at application")):
        var = load(folder, "S1H")
        out += ["## %s: %s" % (name, what), "",
                "| controller | runs with a violation, main -> variant | violating held steps "
                "| with an uncovered car drawing | energy change, mean over runs |",
                "| --- | --- | --- | --- | --- |"]
        for c in "BC":
            keys = [k for k in var if k[0] == c and k in base]
            bad = (sum(not base[k]["counted"] for k in keys), sum(not var[k]["counted"] for k in keys))
            hs = (sum(held(base[k]) for k in keys), sum(held(var[k]) for k in keys))
            nc = (sum(base[k]["viol_with_new_car"] for k in keys),
                  sum(var[k]["viol_with_new_car"] for k in keys))
            de = statistics.fmean(100.0 * (var[k]["energy_kwh"] - base[k]["energy_kwh"])
                                  / base[k]["energy_kwh"] for k in keys if base[k]["energy_kwh"] > 0)
            out.append("| %s (%d runs) | %d -> %d | %d -> %d | %d -> %d | %+.2f%% |"
                       % (c, len(keys), bad[0], bad[1], hs[0], hs[1], nc[0], nc[1], de))
            if name == "uncovered0":
                share = nc[0] / hs[0] if hs[0] else 0.0
                out.append("")
                out.append("%s: in the main case %d of %d held-step violations (%.0f%%) had an "
                           "uncovered car drawing; trigger (more than 25%%) %s."
                           % (c, nc[0], hs[0], 100 * share,
                              "MET: propose uncovered_kw = 0 to the EV node" if share > 0.25
                              else "not met"))
                out.append("")
        out.append("")
    path = os.path.join(HERE, "results", "sensitivity", "comparison.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    print("wrote", path)


if __name__ == "__main__":
    main()
