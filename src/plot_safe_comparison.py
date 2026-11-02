"""Compare trust formulas on the only fair basis: winning safely.

A run with any violation does not count, per the plan. For the question "is live control
worth running here", that means a violating live run is a loss for live control: at that
operating point it was not a valid way to run the network, and the static limit, which is
safe by construction, is the better choice.

So each cell of the grid gets one number: the share of seeds in which the live envelope was
both violation-free and ahead of its seed's static baseline. The crossover is where that
share falls below one half. Violations are counted rather than dropped, and there is no
censoring problem at the grid edge.

Left: the 50% contour for each trust formula.
Right: the violation rate against latency, which is where the formulas really differ.

Run:  py src/plot_safe_comparison.py
"""
import glob
import json
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RED, GREY = "#C8102E", "#555555"
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Calibri", "Segoe UI", "Arial", "DejaVu Sans"]
plt.rcParams.update({"font.size": 11})

VARIANTS = [
    ("as planned: age and loss, flat 5%", ["results/final/w1_flat/crossover_seed*.json"],
     RED, "-"),
    ("age only, flat 5%", ["results/final/w0_flat/crossover_seed*.json"], GREY, "--"),
    ("age only, age-scaled margin", ["results/final/w0_age/crossover_seed*.json"],
     "#1D5C7C", "-"),
]


def load(patterns):
    cells = defaultdict(list)          # (loss, latency) -> [(safe, delta)]
    for pat in patterns:
        for p in glob.glob(os.path.join(HERE, pat)):
            for r in json.load(open(p, encoding="utf-8"))["runs"]:
                safe = r["violations"] == 0
                delta = r["delta_pct"] if r["delta_pct"] is not None else None
                if delta is None and safe:
                    continue                # should not happen; skip rather than guess
                if delta is None:
                    delta = 100.0 * (r["energy_kwh"] - r["baseline_kwh"]) / r["baseline_kwh"]
                cells[(r["loss"], r["latency_s"])].append((safe, delta))
    return cells


def main():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.5), dpi=200)
    report = {}

    for label, patterns, colour, ls in VARIANTS:
        cells = load(patterns)
        if not cells:
            continue
        losses = sorted({l for l, _ in cells})
        lats = sorted({x for _, x in cells})

        W = np.full((len(losses), len(lats)), np.nan)
        for i, loss in enumerate(losses):
            for j, lat in enumerate(lats):
                c = cells.get((loss, lat))
                if c:
                    W[i, j] = sum(1 for safe, d in c if safe and d > 0) / len(c)
        X, Y = np.meshgrid(lats, [l * 100 for l in losses])
        try:
            ax1.contour(X, Y, W, levels=[0.5], colors=colour, linewidths=2.2, linestyles=ls)
        except (ValueError, IndexError):
            pass
        ax1.plot([], [], color=colour, lw=2.2, ls=ls, label=label)

        # violation rate by latency, pooled over loss and seed
        vx, vy = [], []
        for lat in lats:
            runs = [s for loss in losses for s in cells.get((loss, lat), [])]
            if runs:
                vx.append(lat)
                vy.append(100.0 * sum(1 for safe, _ in runs if not safe) / len(runs))
        ax2.plot(vx, vy, color=colour, lw=2.0, ls=ls, marker="o", ms=4.5, label=label)

        total = sum(len(v) for v in cells.values())
        unsafe = sum(1 for v in cells.values() for safe, _ in v if not safe)
        report[label] = (W, losses, lats, total, unsafe)

    for ax in (ax1, ax2):
        ax.set_xscale("symlog", linthresh=5, linscale=0.5)
        ticks = [0, 5, 15, 30, 60, 120, 300, 600]
        ax.set_xticks(ticks)
        ax.set_xticklabels([str(t) for t in ticks])
        ax.set_xlim(0, 600)
        ax.set_xlabel("telemetry latency (s)")
        ax.grid(color="#EAEAEA", lw=0.8)
        ax.set_axisbelow(True)
        ax.legend(frameon=False, fontsize=9.5)
    ax1.set_ylim(5, 40)
    ax1.set_ylabel("packet loss (%)")
    ax1.set_title("live envelope ahead and safe in half the seeds", fontsize=11, loc="left")
    ax1.text(0.02, 0.03, "below each line, live control wins safely in most seeds",
             transform=ax1.transAxes, fontsize=9.5, color=GREY)
    ax2.set_ylabel("runs with any violation (%)")
    ax2.set_title("how often each formula breaks a limit", fontsize=11, loc="left")
    ax2.set_ylim(bottom=0)

    fig.tight_layout()
    out = os.path.join(HERE, "results", "final", "safe_comparison.png")
    fig.savefig(out, facecolor="white")

    # the numbers: for each loss, the longest latency at which live wins safely in >= half
    labels = list(report)
    print("longest latency (s) at which live control is safe and ahead in at least half the seeds")
    print("%7s" % "loss" + "".join("%30s" % l for l in labels))
    losses = report[labels[0]][1]
    for i, loss in enumerate(losses):
        line = "%6.1f%%" % (loss * 100)
        for l in labels:
            W, ls_, lats, _, _ = report[l]
            ii = ls_.index(loss) if loss in ls_ else None
            if ii is None:
                line += "%30s" % "-"
                continue
            ok = [lats[j] for j in range(len(lats)) if W[ii, j] >= 0.5]
            # longest latency before the share first drops below a half
            last = None
            for j in range(len(lats)):
                if W[ii, j] >= 0.5:
                    last = lats[j]
                else:
                    break
            line += "%30s" % ("never" if last is None else
                              (">=600" if last == lats[-1] else "%g" % last))
        print(line)
    print()
    for l in labels:
        _, _, _, total, unsafe = report[l]
        print("%-22s %d of %d runs had a violation (%.1f%%)" % (l, unsafe, total,
                                                                 100.0 * unsafe / total))
    print("wrote", out)


if __name__ == "__main__":
    main()
