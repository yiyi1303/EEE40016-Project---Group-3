"""How much does the crossover depend on the stale timeout?

The trust score falls in a straight line from 1 at zero age to 0 at the stale timeout, and
the charge points fall back to 1.4 kW once their newest setpoint is older than their own
timeout. A short timeout gives up on old information quickly; a long one keeps believing
it. The timeout is a design choice, not a measurement, and it is the exact analogue of the
fallback timeout SA Power Networks moved from 30 minutes to four hours in their flexible
exports rollout. If the crossover moves a long way with it, the timeout is part of the
answer and has to be reported as such.

One timeout is varied at both ends together, as the config intends ("set equal to the
twin's stale timeout so both ends give up on old information at the same age"): the twin's
stale_timeout_min and the edge's edge_fallback_timeout_min. Since amendment 25 the edge
timeout also sets the schedule length, H = floor((T - 2.5) / 5) + 1: 1 entry at 5 min, 3 at
15, 6 at 30, 12 at 60.

The final model: setpoint schedules on, the main-case demand (S1), controller B against the
static limit A. Seeds are the seven main-case seeds where the static limit binds (below
7.2 kW): on the other six A already delivers everything the cars can take, so there is no
crossover to locate.

    py src/timeout_sensitivity.py --all [--workers 12]     every timeout x seed, in parallel
    py src/timeout_sensitivity.py --timeout 15 --seed 7     one job
    py src/timeout_sensitivity.py --summarise

The static baseline does not depend on the timeout (a fixed controller never looks at
telemetry, and its calibration run at 0 s / 0% has no held setpoints), so every timeout is
compared against the same baseline for a given seed.
Out: results/timeout_sensitivity/
"""
import argparse
import copy
import glob
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "results", "timeout_sensitivity")
CONFIG = os.path.join(HERE, "config", "study.json")

TIMEOUTS = [5, 15, 30, 60]
SEEDS = [7, 10, 11, 14, 15, 16, 18]      # main-case seeds whose static limit binds
LOSSES = [0.10, 0.20, 0.30, 0.40]
LATENCIES = [0, 15, 60, 120, 300, 600]

BEYOND, NEVER = math.inf, 0.0


def crossing(points):
    """Zero crossing of [(latency, delta)], or BEYOND / NEVER when it is off the grid."""
    if not points:
        return None
    if points[0][1] < 0:
        return NEVER
    for (x0, a), (x1, b) in zip(points, points[1:]):
        if a >= 0 >= b and a != b:
            return x0 + (x1 - x0) * a / (a - b)
    return BEYOND if all(d >= 0 for _, d in points) else None


def run_one(job):
    timeout, seed = job
    from sweep import StudyRun, calibrate_static
    import controllers
    cfg = copy.deepcopy(json.load(open(CONFIG, encoding="utf-8")))
    ctl = cfg.setdefault("controller_settings", {})
    ctl["stale_timeout_min"] = float(timeout)
    ctl["edge_fallback_timeout_min"] = float(timeout)
    study = StudyRun(cfg)
    t0 = time.time()
    base_kw, base_kwh, _ = calibrate_static(study, seed)
    ctrl = controllers.build(cfg, base_kw)["B"]                 # B: trust-weighted (Table 2)
    out = {"timeout_min": timeout, "seed": seed, "baseline_kw": base_kw,
           "baseline_kwh": base_kwh, "sessions": study.session_args, "runs": []}
    for loss in LOSSES:
        for lat in LATENCIES:
            r = study.run(ctrl, lat, loss, seed)
            d = 100.0 * (r.energy_kwh - base_kwh) / base_kwh if r.counted else None
            out["runs"].append({"loss": loss, "latency_s": lat,
                                "energy_kwh": round(r.energy_kwh, 2),
                                "delta_pct": None if d is None else round(d, 2),
                                "violations": r.violations, "fallbacks": r.fallbacks,
                                "entry_counts": r.entry_counts,
                                "mean_trust": round(r.mean_trust, 3)})
    out["wall_clock_s"] = round(time.time() - t0, 1)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "timeout_%d_seed%d.json" % (timeout, seed))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return "timeout %2d min, seed %2d: static %.1f kW, %.0f s" % (timeout, seed, base_kw,
                                                                  out["wall_clock_s"])


def quantile(vals, q):
    vals = sorted(vals)
    pos = q * (len(vals) - 1)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    a, b = vals[lo], vals[hi]
    if lo == hi or a == b:
        return a
    if math.isinf(b):
        return b if pos - lo > 0.5 else a
    return a + (b - a) * (pos - lo)


def summarise():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Calibri", "Segoe UI", "Arial", "DejaVu Sans"]

    files = glob.glob(os.path.join(OUT, "timeout_*_seed*.json"))
    if not files:
        raise SystemExit("no results in %s yet" % OUT)

    table, unsafe, seeds = {}, {}, set()
    for p in files:
        d = json.load(open(p, encoding="utf-8"))
        T, seed = d["timeout_min"], d["seed"]
        seeds.add(seed)
        by = {}
        for r in d["runs"]:
            u = unsafe.setdefault(T, [0, 0])
            u[0] += r["violations"] > 0
            u[1] += 1
            if r["delta_pct"] is not None:
                by.setdefault(r["loss"], []).append((r["latency_s"], r["delta_pct"]))
        for loss, pts in by.items():
            table.setdefault(T, {}).setdefault(loss, []).append(crossing(sorted(pts)))

    fmt = lambda v: ">600" if math.isinf(v) else ("never" if v == 0 else "%.0f" % v)  # noqa: E731
    Ts = sorted(table)
    lines = ["Timeout sensitivity on the final model: controller B against the static limit,",
             "setpoint schedules on, main-case demand (S1), one timeout at both ends.",
             "Median latency (s) where B's advantage crosses zero, over %d seeds (%s)."
             % (len(seeds), ", ".join(map(str, sorted(seeds)))),
             "'never': behind the static limit even at 0 s. '>600': still ahead at 600 s.", "",
             "%8s" % "loss" + "".join("%12s" % ("%d min" % T) for T in Ts)]
    for loss in LOSSES:
        row = "%7.0f%%" % (loss * 100)
        for T in Ts:
            vals = [v for v in table[T].get(loss, []) if v is not None]
            row += "%12s" % (fmt(quantile(vals, 0.5)) if vals else "-")
        lines.append(row)
    lines += ["", "runs that broke a limit: " + ", ".join(
        "%d min %d of %d" % (T, unsafe[T][0], unsafe[T][1]) for T in Ts)]
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(OUT, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")

    fig, ax = plt.subplots(figsize=(6.6, 4.2), dpi=200)
    shades = ["#F2A7B4", "#E0607A", "#C8102E", "#6E0718"]
    for T, colour in zip(Ts, shades):
        pts = []
        for loss in LOSSES:
            vals = [v for v in table[T].get(loss, []) if v is not None]
            if vals:
                pts.append((loss * 100, quantile(vals, 0.5)))
        # measured crossings as a solid line; "still ahead at 600 s" is censored, so it is
        # drawn as a hollow arrowhead on the grid edge and joined only by a dotted line,
        # never as though it were a value that was observed
        ax.plot([], [], color=colour, lw=1.9, marker="o", ms=5, label="timeout %d min" % T)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            both = not math.isinf(y0) and not math.isinf(y1)
            ax.plot([x0, x1], [min(y0, 620), min(y1, 620)], color=colour, lw=1.9,
                    ls="-" if both else ":")
        for x, y in pts:
            if math.isinf(y):
                ax.plot(x, 620, marker="^", ms=8, mfc="white", mec=colour, mew=1.8, ls="")
            else:
                ax.plot(x, y, marker="o", ms=5, color=colour, ls="")
    finite = [quantile([v for v in table[T].get(loss, []) if v is not None], 0.5)
              for T in Ts for loss in LOSSES if table[T].get(loss)]
    if any(math.isinf(v) for v in finite):
        ax.plot([], [], marker="^", ms=8, mfc="white", mec="#555555", mew=1.6, ls="",
                label="still ahead at 600 s")
        ax.axhline(600, color="#999999", lw=0.8, ls=":")
        ax.text(10.3, 575, "edge of grid", fontsize=9, color="#777777")
        ax.set_ylim(0, 660)
    else:
        top = max(v for v in finite if not math.isinf(v))
        ax.set_ylim(0, 1.25 * top if top > 0 else 60)
    ax.set_xlabel("packet loss (%)")
    ax.set_ylabel("median latency at the crossing (s)")
    ax.grid(color="#EAEAEA", lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9.5, loc="upper right")
    ax.set_title("median of %d seeds, main case; 0 s means B is behind the static limit even "
                 "at 0 s" % len(seeds), fontsize=9.5, color="#555555", loc="left")
    fig.tight_layout()
    out = os.path.join(OUT, "timeout_sensitivity.png")
    fig.savefig(out, facecolor="white")
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--timeout", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        summarise()
    elif a.all:
        from concurrent.futures import ProcessPoolExecutor
        # slow seeds first, so the last wave is short
        order = {7: 0, 14: 1, 10: 2, 11: 3, 15: 4, 16: 5, 18: 6}
        jobs = sorted(((T, s) for T in TIMEOUTS for s in SEEDS),
                      key=lambda j: (order.get(j[1], 9), -j[0]))
        with ProcessPoolExecutor(a.workers) as ex:
            for msg in ex.map(run_one, jobs):
                print(msg, flush=True)
        summarise()
    elif a.timeout and a.seed:
        print(run_one((a.timeout, a.seed)))
    else:
        raise SystemExit("give --all, --timeout N --seed S, or --summarise")


if __name__ == "__main__":
    main()
