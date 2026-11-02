"""Compare two trust formulas: where does each put the crossover?

Left: the zero contour of mean advantage for each variant, on the same latency x loss axes.
Right: median crossing latency against loss for each, with interquartile bands.

The point of the figure is to separate physics from formula. Wherever the two contours
agree, the crossover is set by the data genuinely going stale. Wherever they part, it is
set by how the trust score chooses to weigh packet loss.

Run:  py src/plot_trust_comparison.py
"""
import glob
import math
import json
import os
import statistics
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_crossover import crossing, quantile     # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLACK, RED, GREY = "#000000", "#C8102E", "#555555"
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Calibri", "Segoe UI", "Arial", "DejaVu Sans"]
plt.rcParams.update({"font.size": 11})

VARIANTS = [
    ("age and loss (w = 1)", ["results/crossover_seed*.json", "results/crossover_hiloss_seed*.json"],
     RED, "-"),
    ("age only (w = 0)", ["results/ageonly/crossover_seed*.json"], GREY, "--"),
]


def load(patterns):
    series = defaultdict(dict)
    for pat in patterns:
        for p in glob.glob(os.path.join(HERE, pat)):
            for r in json.load(open(p, encoding="utf-8"))["runs"]:
                if r["delta_pct"] is not None:
                    series[(r["seed"], r["loss"])][r["latency_s"]] = r["delta_pct"]
    return series


def main():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.5), dpi=200)
    summary = {}

    for label, patterns, colour, ls in VARIANTS:
        series = load(patterns)
        if not series:
            print("no data yet for %s" % label)
            continue
        seeds = sorted({s for s, _ in series})
        losses = sorted({l for _, l in series})
        lats = sorted({x for v in series.values() for x in v})

        Z = np.full((len(losses), len(lats)), np.nan)
        for i, loss in enumerate(losses):
            for j, lat in enumerate(lats):
                vals = [series[(s, loss)][lat] for s in seeds
                        if (s, loss) in series and lat in series[(s, loss)]]
                if vals:
                    Z[i, j] = statistics.fmean(vals)
        X, Y = np.meshgrid(lats, [l * 100 for l in losses])
        try:
            ax1.contour(X, Y, np.ma.masked_invalid(Z), levels=[0.0], colors=colour,
                        linewidths=2.2, linestyles=ls)
        except (ValueError, IndexError):
            pass
        ax1.plot([], [], color=colour, lw=2.2, ls=ls, label=label)

        xs, med, q1, q3 = [], [], [], []
        rows = []
        for loss in losses:
            vals = sorted(v for v in (crossing(sorted(series[(s, loss)].items()))
                                      for s in seeds if (s, loss) in series) if v is not None)
            if not vals:
                continue
            m = quantile(vals, 0.5)
            rows.append((loss, m, len(vals)))
            xs.append(loss * 100)
            med.append(min(m, lats[-1]))
            q1.append(min(quantile(vals, 0.25), lats[-1]))
            q3.append(min(quantile(vals, 0.75), lats[-1]))
        ax2.fill_between(xs, q1, q3, color=colour, alpha=0.13, lw=0)
        ax2.plot(xs, med, color=colour, lw=2.0, ls=ls, marker="o", ms=4.5, label=label)
        summary[label] = (rows, lats[-1], len(seeds))

    ax1.set_xscale("symlog", linthresh=5, linscale=0.5)
    ticks = [0, 5, 15, 30, 60, 120, 300, 600]
    ax1.set_xticks(ticks)
    ax1.set_xticklabels([str(t) for t in ticks])
    ax1.set_xlim(0, 600)
    ax1.set_ylim(5, 40)
    ax1.set_xlabel("telemetry latency (s)")
    ax1.set_ylabel("packet loss (%)")
    ax1.set_title("where live envelopes stop paying", fontsize=11.5, loc="left")
    ax1.grid(color="#EAEAEA", lw=0.8)
    ax1.set_axisbelow(True)
    ax1.legend(frameon=False, fontsize=9.5, loc="upper right")
    ax1.text(0.02, 0.03, "live envelope ahead below each line", transform=ax1.transAxes,
             fontsize=9.5, color=GREY)

    ax2.axhline(600, color="#999999", lw=0.8, ls=":")
    ax2.set_xlabel("packet loss (%)")
    ax2.set_ylabel("median latency at the crossing (s)")
    ax2.set_ylim(0, 640)
    ax2.grid(color="#EAEAEA", lw=0.8)
    ax2.set_axisbelow(True)
    ax2.legend(frameon=False, fontsize=9.5)

    fig.tight_layout()
    out = os.path.join(HERE, "results", "trust_comparison.png")
    fig.savefig(out, facecolor="white")

    labels = list(summary)
    if labels:
        losses = sorted({r[0] for rows, _, _ in summary.values() for r in rows})
        print("median crossing latency (s)")
        print("%7s" % "loss" + "".join("%24s" % l for l in labels))
        for loss in losses:
            line = "%6.1f%%" % (loss * 100)
            for l in labels:
                rows, edge, _ = summary[l]
                m = next((r[1] for r in rows if r[0] == loss), None)
                line += "%24s" % ("-" if m is None else
                                  (">%d" % edge if math.isinf(m) else "%.0f" % m))
            print(line)
    print("wrote", out)


if __name__ == "__main__":
    main()
