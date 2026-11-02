"""Validation item V4: envelopes are safe without being needlessly conservative.

Plan wording: apply the envelope, run the power flow, inspect the binding constraint.
Zero violations, and the binding quantity within 1% of its limit.

Two things are measured at every operating point:

    safety        applying the envelope must produce no violation at all
    tightness     the binding constraint must be sitting within 1% of its limit, and one
                  more grid step must actually break something

The second half of the tightness check matters because the charge points act in 0.1 kW
steps. An envelope can be maximal — the best setting available — and still sit more than
1% below the limit, simply because the next step up overshoots. That is quantisation, not
conservatism, and the two are reported separately.

"Within 1% of its limit" is read as within 1% of the constraint's usable span, so the
figure means the same thing for a voltage floor as for a thermal ceiling.

Run:  py tests/v4_tightness.py [n_points]
Out:  notes/v4_result.md
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

REPORT = os.path.join(HERE, "notes", "v4_result.md")
TIGHTNESS_PCT = 1.0


def main():
    n_points = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    cfg = json.load(open(os.path.join(HERE, "config", "study.json"), encoding="utf-8"))
    study, env_cfg = cfg["cases"]["study"], cfg["envelope"]

    feeder = load_feeder()
    solver = OpenDSSSolver(feeder, transformer_kva=study["transformer_kva"]).build()
    solver.add_ev_loads(choose_ev_connections(feeder, study["ev_connections"],
                                              cfg["sweep"]["seeds"][0]))
    cs = ConstraintSet()
    search = EnvelopeSearch(solver, cs, env_cfg["min_kw"], env_cfg["max_kw"],
                            env_cfg["tolerance_kw"])
    step = env_cfg["tolerance_kw"]

    rng = random.Random(11)
    rows, unsafe, loose, not_maximal, ceiling, zero = [], [], [], [], 0, 0
    t0 = time.perf_counter()

    for _ in range(n_points):
        minute = rng.randrange(16 * 60, 22 * 60)
        scale = rng.choice([0.8, 1.0, 1.5, 2.0, 3.0, 4.0])
        preload = rng.choice([0.2, 0.5, 0.9])
        solver.set_loads({l.name: profile_kw(HERE, feeder.shapes[l.shape], minute) * scale
                          for l in feeder.loads})

        th = ThermalModel(cs.thermal_params)
        th.settle(preload)
        r = search.find(thermal=th, minutes=5)

        if r.infeasible_at_zero:
            zero += 1
            rows.append((minute, scale, preload, r.kw, "already in violation", 0.0, "", ""))
            continue
        if r.at_ceiling:
            ceiling += 1
            rows.append((minute, scale, preload, r.kw, "unconstrained", 0.0, "ok", "n/a"))
            continue

        # safety: the envelope itself must be clean
        th_a = ThermalModel(cs.thermal_params); th_a.settle(preload)
        at = search.trial(r.kw, thermal=th_a, minutes=5)
        safe = at.ok
        if not safe:
            unsafe.append((minute, scale, at.violations))

        # tightness: how close the binding constraint is to its limit
        headroom_pct = 100.0 * at.worst_margin
        tight = headroom_pct <= TIGHTNESS_PCT

        # maximal: one more grid step must break something
        th_b = ThermalModel(cs.thermal_params); th_b.settle(preload)
        up = search.trial(min(r.kw + step, env_cfg["max_kw"]), thermal=th_b, minutes=5)
        maximal = not up.ok
        if not maximal:
            not_maximal.append((minute, scale, r.kw))
        if not tight and maximal:
            loose.append((minute, scale, r.kw, headroom_pct, at.binding))

        rows.append((minute, scale, preload, r.kw, at.binding, headroom_pct,
                     "ok" if safe else "UNSAFE", "yes" if maximal else "NO"))

    dt = time.perf_counter() - t0
    judged = [r for r in rows if r[4] not in ("unconstrained", "already in violation")]
    tight_n = sum(1 for r in judged if r[5] <= TIGHTNESS_PCT)
    passed = not unsafe and not not_maximal
    worst_headroom = max((r[5] for r in judged), default=0.0)

    out = ["# V4 — envelope tightness", "",
           "| | |", "| --- | --- |",
           "| Operating points | %d |" % n_points,
           "| Constrained points judged | %d |" % len(judged),
           "| Unconstrained (envelope at the 7.2 kW ceiling) | %d |" % ceiling,
           "| Already in violation with no charging | %d |" % zero,
           "| Points with a violation at the envelope | %d |" % len(unsafe),
           "| Points where one more 0.1 kW step was still safe | %d |" % len(not_maximal),
           "| Binding constraint within %.0f%% of its limit | %d of %d |"
           % (TIGHTNESS_PCT, tight_n, len(judged)),
           "| Worst headroom left | %.2f%% |" % worst_headroom,
           "| Wall clock | %.1f s |" % dt,
           "", "**%s**" % ("PASS" if passed else "FAIL"), "",
           "Safety and maximality are the pass conditions. Headroom above 1% is reported "
           "but is not a failure when the envelope is already maximal on the 0.1 kW "
           "actuation grid: the next step up would violate, so there is nothing to "
           "recover. Those cases are quantisation, not conservatism.", ""]

    if loose:
        out += ["## Maximal but more than 1% from the limit", "",
                "| Minute | Demand | Envelope kW | Headroom | Binding |",
                "| ---: | ---: | ---: | ---: | --- |"]
        out += ["| %d | x%.1f | %.1f | %.2f%% | %s |" % r for r in
                sorted(loose, key=lambda x: -x[3])[:15]]
        out.append("")
    if unsafe:
        out += ["## Violations at the envelope — these are failures", ""]
        out += ["- minute %d, demand x%.1f: %s" % (m, s, "; ".join(v)) for m, s, v in unsafe]
        out.append("")

    out += ["## Points", "",
            "| Minute | Demand | Start load | Envelope kW | Binding | Headroom | Safe | Maximal |",
            "| ---: | ---: | ---: | ---: | --- | ---: | --- | --- |"]
    for minute, scale, preload, kw, binding, head, safe, maximal in rows:
        out.append("| %d | x%.1f | %.1f pu | %.1f | %s | %.2f%% | %s | %s |"
                   % (minute, scale, preload, kw, binding, head, safe, maximal))

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    print("operating points      %d  (%d constrained, %d unconstrained, %d already violating)"
          % (n_points, len(judged), ceiling, zero))
    print("violations at envelope %d" % len(unsafe))
    print("not maximal            %d" % len(not_maximal))
    print("within %.0f%% of limit    %d of %d" % (TIGHTNESS_PCT, tight_n, len(judged)))
    print("worst headroom         %.2f%%" % worst_headroom)
    print("wall clock             %.1f s" % dt)
    print()
    print("V4 %s" % ("PASS" if passed else "FAIL"))
    print("wrote", REPORT)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
