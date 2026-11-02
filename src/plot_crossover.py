"""Draw the S1 crossover surface from any number of result files.

Merges every `crossover*.json` given, so grids run in separate passes over different
latency or loss ranges are treated as one surface.

Two panels:

    left    the surface itself: mean advantage over each seed's own static baseline,
            across latency and packet loss, with the zero contour drawn in. The contour
            is the crossover. This is the figure the plan calls "the primary crossover
            surface".
    right   the crossing latency at each loss rate, as a median with an interquartile
            band across seeds.

Why a median. At low loss many seeds never cross inside the grid: the live envelope is
still ahead at the longest latency tested. Those are right-censored, the crossing is
somewhere beyond the grid edge, and a mean over the seeds that did cross would quietly
drop them and come out too low. The median stays well defined as long as fewer than half
the seeds are censored, and treating "beyond the grid" as +infinity is exactly right for
it. Seeds that are behind even at the lowest latency are the opposite case and sit at 0.

Run:  py src/plot_crossover.py "results/crossover_*.json"
"""
import glob
import json
import math
import os
import statistics
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLACK, RED, GREY, BAND = "#000000", "#C8102E", "#777777", "#F2C9D0"
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Calibri", "Segoe UI", "Arial", "DejaVu Sans"]
plt.rcParams.update({"text.color": BLACK, "axes.labelcolor": BLACK,
                     "xtick.color": BLACK, "ytick.color": BLACK,
                     "axes.edgecolor": BLACK, "axes.linewidth": 0.9, "font.size": 11})

BEYOND, NEVER = math.inf, 0.0


def crossing(points):
    """points: [(latency, delta)] sorted by latency.

    Returns the interpolated zero crossing, BEYOND if the advantage never falls to zero
    inside the grid, NEVER if it is already negative at the lowest latency, or None if the
    series is too patchy to say.
    """
    if not points:
        return None
    if points[0][1] < 0:
        return NEVER
    for (x0, a), (x1, b) in zip(points, points[1:]):
        if a >= 0 >= b and a != b:
            return x0 + (x1 - x0) * a / (a - b)
    if all(d >= 0 for _, d in points):
        return BEYOND
    return None


def quantile(sorted_vals, q):
    """Linear-interpolated quantile that tolerates +inf at the top end."""
    n = len(sorted_vals)
    pos = q * (n - 1)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    a, b = sorted_vals[lo], sorted_vals[hi]
    if lo == hi or a == b:
        return a
    if math.isinf(b):
        return b if pos - lo > 0.5 else a
    return a + (b - a) * (pos - lo)


def main():
    args = sys.argv[1:]
    out = next((a.split("=", 1)[1] for a in args if a.startswith("--out=")),
               os.path.join(HERE, "results", "crossover.png"))
    args = [a for a in args if not a.startswith("--out=")]
    pats = args or [os.path.join(HERE, "results", "crossover_*.json")]
    paths = sorted({p for pat in pats for p in (glob.glob(pat) if any(c in pat for c in "*?")
                                                else [pat]) if os.path.exists(p)})
    if not paths:
        raise SystemExit("no result files found")

    runs, baselines = [], {}
    for p in paths:
        d = json.load(open(p, encoding="utf-8"))
        runs += d["runs"]
        baselines.update(d["seeds"])

    series = defaultdict(dict)
    for r in runs:
        if r["delta_pct"] is not None:
            series[(r["seed"], r["loss"])][r["latency_s"]] = r["delta_pct"]
    seeds = sorted({s for s, _ in series})
    losses = sorted({l for _, l in series})
    lats = sorted({lat for v in series.values() for lat in v})

    cross = {k: crossing(sorted(v.items())) for k, v in series.items()}

    # ---------------------------------------------------------------- surface
    Z = np.full((len(losses), len(lats)), np.nan)
    for i, loss in enumerate(losses):
        for j, lat in enumerate(lats):
            vals = [series[(s, loss)][lat] for s in seeds
                    if (s, loss) in series and lat in series[(s, loss)]]
            if vals:
                Z[i, j] = statistics.fmean(vals)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.6), dpi=200,
                                   gridspec_kw={"width_ratios": [1.15, 1]})
    X, Y = np.meshgrid(lats, [l * 100 for l in losses])
    raw = np.nanmax(np.abs(Z)) if np.isfinite(Z).any() else 5.0
    lim = 5.0 * math.ceil(raw / 5.0)
    cf = ax1.contourf(X, Y, np.ma.masked_invalid(Z), levels=np.arange(-lim, lim + 0.01, 2.5),
                      cmap="RdGy_r", extend="both")
    try:
        cs = ax1.contour(X, Y, np.ma.masked_invalid(Z), levels=[0.0], colors=BLACK,
                         linewidths=2.0)
        ax1.clabel(cs, fmt={0.0: "crossover"}, fontsize=9.5, inline=True)
    except (ValueError, IndexError):
        pass
    ax1.set_xscale("symlog", linthresh=5, linscale=0.5)
    ax1.set_xlim(lats[0], lats[-1])
    ax1.set_xticks([t for t in (0, 5, 15, 30, 60, 120, 300, 600) if lats[0] <= t <= lats[-1]])
    ax1.set_xticklabels([str(t) for t in (0, 5, 15, 30, 60, 120, 300, 600)
                         if lats[0] <= t <= lats[-1]])
    ax1.set_xlabel("telemetry latency (s)")
    ax1.set_ylabel("packet loss (%)")
    cb = fig.colorbar(cf, ax=ax1, pad=0.02, ticks=np.arange(-lim, lim + 0.01, 5))
    cb.set_label("advantage over static limit (%)")
    # live control wins at low latency and low loss, the static limit at high of both
    ax1.text(0.02, 0.03, "live envelope ahead", transform=ax1.transAxes,
             fontsize=9.5, color="white", fontweight="bold")
    ax1.text(0.98, 0.97, "static limit ahead", transform=ax1.transAxes, ha="right",
             va="top", fontsize=9.5, color="white", fontweight="bold")

    # ---------------------------------------------------------------- crossing
    xs, med, q1, q3, beyond_x = [], [], [], [], []
    for loss in losses:
        vals = sorted(cross[(s, loss)] for s in seeds
                      if (s, loss) in cross and cross[(s, loss)] is not None)
        if not vals:
            continue
        m = quantile(vals, 0.5)
        if math.isinf(m):
            beyond_x.append(loss * 100)
            continue
        xs.append(loss * 100)
        med.append(m)
        q1.append(quantile(vals, 0.25))
        q3.append(min(quantile(vals, 0.75), lats[-1]))
    if xs:
        ax2.fill_between(xs, q1, q3, color=BAND, lw=0, label="interquartile range")
        ax2.plot(xs, med, color=RED, lw=2.0, marker="o", ms=5, label="median", zorder=3)
    for bx in beyond_x:
        ax2.annotate("", xy=(bx, lats[-1]), xytext=(bx, lats[-1] * 0.8),
                     arrowprops=dict(arrowstyle="-|>", color=GREY, lw=1.4))
    if beyond_x:
        ax2.plot([], [], color=GREY, marker="^", ls="", label="median beyond %d s" % lats[-1])
    every_x = xs + beyond_x
    if every_x:
        pad = 0.04 * (max(every_x) - min(every_x) or 10)
        ax2.set_xlim(min(every_x) - pad, max(every_x) + pad)
    ax2.set_xlabel("packet loss (%)")
    ax2.set_ylabel("latency at the crossing (s)")
    ax2.set_ylim(0, lats[-1] * 1.05)
    ax2.grid(color="#EAEAEA", lw=0.8)
    ax2.set_axisbelow(True)
    ax2.legend(frameon=False, fontsize=9.5, loc="upper right")
    ax2.text(0.03, 0.04, "above the curve, a static limit does better",
             transform=ax2.transAxes, fontsize=9.5, color=GREY)

    fig.tight_layout()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, facecolor="white")

    # ---------------------------------------------------------------- numbers
    print("merged %d runs from %d files: %d seeds, %d latencies (%g-%g s), %d loss levels"
          % (len(runs), len(paths), len(seeds), len(lats), lats[0], lats[-1], len(losses)))
    print()
    print("%7s %9s %9s %9s  %6s %7s %6s" % ("loss", "median s", "q1", "q3",
                                            "cross", "beyond", "never"))
    for loss in losses:
        vals = sorted(cross[(s, loss)] for s in seeds
                      if (s, loss) in cross and cross[(s, loss)] is not None)
        if not vals:
            continue
        nb = sum(1 for v in vals if math.isinf(v))
        nn = sum(1 for v in vals if v == NEVER)
        fmt = lambda v: (">%d" % lats[-1]) if math.isinf(v) else "%.0f" % v  # noqa: E731
        print("%6.1f%% %9s %9s %9s  %6d %7d %6d"
              % (loss * 100, fmt(quantile(vals, 0.5)), fmt(quantile(vals, 0.25)),
                 fmt(quantile(vals, 0.75)), len(vals) - nb - nn, nb, nn))
    print("\ncross = crossed inside the grid, beyond = still ahead at %d s, "
          "never = behind even at %g s" % (lats[-1], lats[0]))
    print("baselines: %s" % ", ".join(
        "%s:%.1f" % (s, b["baseline_kw"]) for s, b in sorted(baselines.items(),
                                                             key=lambda kv: int(kv[0]))))
    print("wrote", out)


if __name__ == "__main__":
    main()
