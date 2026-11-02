"""Locate the crossover properly: refine the grid where the coarse sweep changed sign.

The coarse S1 grid put the crossing between (60 s, 10%) and (120 s, 20%). This walks a
fine grid across that region and interpolates, for each loss rate, the latency at which
the live controller stops beating the static baseline.

The baseline is recalibrated for every seed. It has to be: the safe static limit is the
largest fixed kW that never violates, and that depends on which cars turn up and when.
Comparing a seed's dynamic result against another seed's baseline would be meaningless.

Run:  py src/refine_crossover.py [--seeds 7 8 9] [--out results/crossover.json]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep import StudyRun                     # noqa: E402
import controllers                             # noqa: E402
from controllers import FixedLimit             # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(HERE, "results")

LATENCIES = [60, 75, 90, 105, 120]
LOSSES = [0.10, 0.125, 0.15, 0.175, 0.20]


def calibrate_static(study, seed, log=print):
    """Largest fixed limit with zero violations all evening, on the actuation grid.

    The one in sweep.py, which also tests the 7.2 kW ceiling; this copy used to skip it and
    returned 7.1 kW on uncongested seeds, which are common under the s1 demand.
    """
    import sweep
    kw, kwh, n = sweep.calibrate_static(study, seed)
    log("   seed %d baseline: %.1f kW, %.1f kWh (%d runs)" % (seed, kw, kwh, n))
    return kw, kwh


def interpolate_crossing(latencies, deltas):
    """Latency at which the advantage over the baseline crosses zero.

    `deltas` is the percentage advantage at each latency. Returns None when the sign does
    not change anywhere in the range, which means the crossing is outside it.
    """
    for i in range(len(latencies) - 1):
        a, b = deltas[i], deltas[i + 1]
        if a >= 0 >= b and a != b:
            x0, x1 = latencies[i], latencies[i + 1]
            return round(x0 + (x1 - x0) * a / (a - b), 1)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, nargs="+", default=[7, 8, 9])
    ap.add_argument("--margin-mode", choices=("flat", "age"), default=None,
                    help="flat security factor, or a margin that grows with data age")
    ap.add_argument("--trust-loss-weight", type=float, default=None,
                    help="weight on packet loss in the trust score; 0 gives age-only trust")
    ap.add_argument("--latencies", type=float, nargs="+", default=None,
                    help="override the latency axis, e.g. --latencies 5 15 30 45 60")
    ap.add_argument("--losses", type=float, nargs="+", default=None,
                    help="override the loss axis as fractions, e.g. --losses 0.175 0.2")
    ap.add_argument("--out", default=os.path.join(RESULTS, "crossover.json"))
    a = ap.parse_args()

    global LATENCIES, LOSSES
    if a.latencies:
        LATENCIES = list(a.latencies)
    if a.losses:
        LOSSES = list(a.losses)

    cfg = json.load(open(os.path.join(HERE, "config", "study.json"), encoding="utf-8"))
    if a.trust_loss_weight is not None:
        cfg.setdefault("controller_settings", {})["trust_loss_weight"] = a.trust_loss_weight
    if a.margin_mode is not None:
        cfg["envelope"]["margin_mode"] = a.margin_mode
    study = StudyRun(cfg)
    t0 = time.time()
    out = {"stage": "S1 refinement", "latencies_s": LATENCIES, "losses": LOSSES,
           "transformer_kva": study.kva, "seeds": {}, "runs": []}

    for seed in a.seeds:
        print("seed %d" % seed, flush=True)
        base_kw, base_kwh = calibrate_static(study, seed)
        ctrl = controllers.build(study.cfg, base_kw)["B"]      # B: trust-weighted (Table 2)
        out["seeds"][str(seed)] = {"baseline_kw": base_kw, "baseline_kwh": round(base_kwh, 2),
                                   "crossing_latency_s": {}}
        for loss in LOSSES:
            deltas = []
            for lat in LATENCIES:
                r = study.run(ctrl, lat, loss, seed)
                d = 100.0 * (r.energy_kwh - base_kwh) / base_kwh if base_kwh else 0.0
                if not r.counted:
                    d = float("nan")
                deltas.append(d)
                out["runs"].append({"seed": seed, "latency_s": lat, "loss": loss,
                                    "energy_kwh": round(r.energy_kwh, 2),
                                    "baseline_kwh": round(base_kwh, 2),
                                    "delta_pct": round(d, 2) if d == d else None,
                                    "violations": r.violations,
                                    "mean_trust": round(r.mean_trust, 3),
                                    "mean_limit_kw": round(r.mean_limit_kw, 2)})
            cross = interpolate_crossing(LATENCIES, deltas)
            out["seeds"][str(seed)]["crossing_latency_s"][str(loss)] = cross
            print("   loss %4.1f%%  " % (loss * 100)
                  + " ".join("%+6.1f" % d for d in deltas)
                  + "   crossing %s" % ("%.0f s" % cross if cross else "outside range"),
                  flush=True)

    out["wall_clock_s"] = round(time.time() - t0, 1)
    os.makedirs(RESULTS, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\n%d runs in %.0f s -> %s" % (len(out["runs"]), out["wall_clock_s"], a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
