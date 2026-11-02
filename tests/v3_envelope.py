"""Validation item V3: the bisection finds the true envelope.

Plan wording: for 30 random operating points, compare the bisection result against an
exhaustive 0.05 kW sweep, and require agreement within 0.1 kW.

The exhaustive sweep is deliberately stupid. It walks up in 0.05 kW steps and takes the
last feasible one, so the only way it can be wrong is if feasibility is not monotonic in
the limit. If the two ever disagree by more than the tolerance, that is the assumption to
suspect, not the arithmetic.

Run:  py tests/v3_envelope.py [n_points]
Out:  notes/v3_result.md
"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from feeder_csv import load_feeder                                   # noqa: E402
from solver import OpenDSSSolver                                     # noqa: E402
from network_state import ConstraintSet, ThermalModel                # noqa: E402
from envelope import EnvelopeSearch, choose_ev_connections           # noqa: E402
from build_sincal_model import profile_kw                            # noqa: E402

REPORT = os.path.join(HERE, "notes", "v3_result.md")
TOLERANCE_KW = 0.1


def main():
    n_points = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    cfg = json.load(open(os.path.join(HERE, "config", "study.json"), encoding="utf-8"))
    study = cfg["cases"]["study"]
    env_cfg = cfg["envelope"]

    feeder = load_feeder()
    solver = OpenDSSSolver(feeder, transformer_kva=study["transformer_kva"]).build()
    evs = choose_ev_connections(feeder, study["ev_connections"], cfg["sweep"]["seeds"][0])
    solver.add_ev_loads(evs)
    cs = ConstraintSet()
    search = EnvelopeSearch(solver, cs, env_cfg["min_kw"], env_cfg["max_kw"],
                            env_cfg["tolerance_kw"])

    # operating points: a minute of the day, a demand scaling, and a starting oil
    # temperature, so the comparison covers light, normal and stressed conditions
    rng = random.Random(3)
    points = []
    for _ in range(n_points):
        minute = rng.randrange(16 * 60, 22 * 60)
        scale = rng.choice([0.6, 1.0, 1.5, 2.5, 4.0])
        preload = rng.choice([0.2, 0.6, 1.0])
        points.append((minute, scale, preload))

    rows, worst, bisect_solves, brute_solves = [], 0.0, 0, 0
    non_monotonic = []
    t0 = time.perf_counter()
    for minute, scale, preload in points:
        house = {l.name: profile_kw(HERE, feeder.shapes[l.shape], minute) * scale
                 for l in feeder.loads}
        solver.set_loads(house)

        th = ThermalModel(cs.thermal_params)
        th.settle(preload)
        a = search.find(thermal=th, minutes=5)
        bisect_solves += a.solves

        th2 = ThermalModel(cs.thermal_params)
        th2.settle(preload)
        b = search.exhaustive(0.05, thermal=th2, minutes=5)
        brute_solves += b.solves
        if getattr(b, 'non_monotonic', None):
            non_monotonic.append((minute, scale, preload, b.non_monotonic))

        diff = abs(a.kw - b.kw)
        worst = max(worst, diff)
        rows.append((minute, scale, preload, a.kw, b.kw, diff, a.binding, a.solves, b.solves))
    dt = time.perf_counter() - t0

    failures = [r for r in rows if r[5] > TOLERANCE_KW]
    passed = not failures and not non_monotonic

    out = ["# V3 — bisection against an exhaustive sweep", "",
           "| | |", "| --- | --- |",
           "| Operating points | %d |" % n_points,
           "| Tolerance | %.2f kW |" % TOLERANCE_KW,
           "| Worst disagreement | %.4f kW |" % worst,
           "| Points outside tolerance | %d |" % len(failures),
           "| Bisection solves | %d (%.1f per point) |" % (bisect_solves, bisect_solves / n_points),
           "| Exhaustive solves | %d (%.1f per point) |" % (brute_solves, brute_solves / n_points),
           "| Saving | %.1fx fewer solves |" % (brute_solves / max(bisect_solves, 1)),
           "| Wall clock | %.1f s for both methods |" % dt,
           "| Points where feasibility was not monotonic | %d |" % len(non_monotonic),
           "", "**%s**" % ("PASS" if passed else "FAIL"), "",
           "The exhaustive sweep scans the whole 0 to 7.2 kW range rather than stopping at "
           "the first infeasible step, so it also tests assumption A9 directly: feasibility "
           "is monotonic in the limit, which is what the bisection relies on.", "",
           "## Points", "",
           "| Minute | Demand | Start load | Bisection kW | Exhaustive kW | Diff | Binding | Solves |",
           "| ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |"]
    for minute, scale, preload, a, b, d, binding, sa, sb in rows:
        out.append("| %d | x%.1f | %.1f pu | %.2f | %.2f | %.3f | %s | %d vs %d |"
                   % (minute, scale, preload, a, b, d, binding, sa, sb))

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    print("operating points    %d" % n_points)
    print("worst disagreement  %.4f kW" % worst)
    print("outside tolerance   %d" % len(failures))
    print("solves per point    %.1f bisection vs %.1f exhaustive (%.1fx)"
          % (bisect_solves / n_points, brute_solves / n_points,
             brute_solves / max(bisect_solves, 1)))
    print("wall clock          %.1f s" % dt)
    print("non-monotonic pts   %d   (assumption A9)" % len(non_monotonic))
    binds = {}
    for r in rows:
        binds[r[6]] = binds.get(r[6], 0) + 1
    print("binding constraints %s" % ", ".join("%s=%d" % kv for kv in sorted(binds.items())))
    print()
    print("V3 %s  (tolerance %.2f kW)" % ("PASS" if passed else "FAIL", TOLERANCE_KW))
    print("wrote", REPORT)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
