"""Figures for stages S1, S2 and S3, from results/stages/.

    stage_S1.png   the primary crossover surface for B and for C: mean advantage over the
                   static limit (controller A) across latency and loss, safe runs only, with
                   the break-even contour. Cells where most seeds broke a limit are crossed.
    stage_S2.png   the stale-data hold against no hold, at three points of the S1 grid
    stage_S3.png   controller B with the battery and without, on the 3 x 3 subset

Run:  py src/plot_stages.py [results folder, default results/stages]
"""
import glob
import json
import os
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# results/stages (the main case) unless another folder is given, e.g. results/stress_s2
STAGES = os.path.join(HERE, sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "results",
                                                                             "stages")
BLACK, RED, GREY = "#000000", "#C8102E", "#666666"
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Calibri", "Segoe UI", "Arial", "DejaVu Sans"]
plt.rcParams.update({"font.size": 11})


def load(stage):
    out = []
    for p in sorted(glob.glob(os.path.join(STAGES, "%s_seed*.json" % stage))):
        out += json.load(open(p, encoding="utf-8"))["runs"]
    return out


def adv(r):
    return 100.0 * (r["energy_kwh"] - r["static_kwh"]) / r["static_kwh"]


def s1():
    runs = load("S1")
    if not runs:
        return None
    lats = sorted({r["latency_s"] for r in runs if r["controller"] != "A"})
    losses = sorted({r["loss"] for r in runs if r["controller"] != "A"})
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.4), dpi=200, sharey=True)
    lim = 0.0
    grids = {}
    for key in "BC":
        Z = np.full((len(losses), len(lats)), np.nan)
        U = np.zeros_like(Z)
        N = np.zeros_like(Z)          # seeds run in the cell
        S = np.zeros_like(Z)          # seeds with no violation
        for i, loss in enumerate(losses):
            for j, lat in enumerate(lats):
                c = [r for r in runs if r["controller"] == key and r["latency_s"] == lat
                     and r["loss"] == loss]
                safe = [adv(r) for r in c if r["counted"]]
                if safe:
                    Z[i, j] = statistics.fmean(safe)
                U[i, j] = sum(1 for r in c if not r["counted"]) / max(len(c), 1)
                N[i, j], S[i, j] = len(c), len(safe)
        grids[key] = (Z, U, N, S)
        lim = max(lim, np.nanmax(np.abs(Z)))
    lim = 5.0 * np.ceil(lim / 5.0)
    xs = np.arange(len(lats))
    ys = np.arange(len(losses))
    from matplotlib.patches import Rectangle
    for ax, key, title in zip(axes, "BC", ("B  trust-weighted", "C  binary fallback")):
        Z, U, N, S = grids[key]
        # A cell where most seeds broke a limit is not a place live control can operate, so it
        # is shown as unsafe and left out of both the colour and the break-even line, rather
        # than coloured by the minority of seeds that happened to stay safe.
        Zd = Z.copy()
        Zd[U > 0.5] = np.nan
        im = ax.imshow(np.ma.masked_invalid(Zd), origin="lower", cmap="RdGy_r", vmin=-lim,
                       vmax=lim, aspect="auto")
        for i in range(len(losses)):
            for j in range(len(lats)):
                if U[i, j] > 0.5:
                    ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor="#EEEEEE",
                                           edgecolor="#BBBBBB", hatch="///", lw=0))
                    ax.text(j, i, "unsafe", ha="center", va="center", fontsize=7.5,
                            color=GREY)
                elif not np.isnan(Zd[i, j]):
                    # a mean over safe seeds alone would hide the seeds that broke a limit,
                    # so the cell says how many stayed safe whenever any did not
                    v = Zd[i, j]
                    label = "0" if abs(v) < 0.5 else "%+.0f" % v
                    if S[i, j] < N[i, j]:
                        label += "\n%d/%d safe" % (S[i, j], N[i, j])
                    ax.text(j, i, label, ha="center", va="center",
                            fontsize=8.5 if S[i, j] == N[i, j] else 7.5, linespacing=1.1,
                            color="white" if abs(v) > 0.55 * lim else BLACK)
        if np.isfinite(Zd).sum() >= 4 and np.nanmin(Zd) < 0 < np.nanmax(Zd):
            try:
                ax.contour(xs, ys, np.ma.masked_invalid(Zd), levels=[0.0], colors=BLACK,
                           linewidths=2.0)
            except (ValueError, IndexError):
                pass
        ax.set_xticks(xs)
        ax.set_xticklabels([str(int(l)) for l in lats])
        ax.set_yticks(ys)
        ax.set_yticklabels(["%g" % (l * 100) for l in losses])
        ax.set_xlabel("telemetry latency (s), both directions")
        ax.set_title(title, loc="left", fontsize=11.5)
    axes[0].set_ylabel("packet loss (%)")
    cb = fig.colorbar(im, ax=axes, pad=0.015)
    cb.set_label("advantage over the static limit (%)")
    fig.text(0.01, -0.04, "Mean over the seeds that broke no limit; 'n/13 safe' where any seed "
             "broke one. Black line: break-even with the static limit (controller A). Hatched: a "
             "limit was broken in more than half the seeds.", fontsize=9, color=GREY)
    out = os.path.join(STAGES, "stage_S1.png")
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out


def s2():
    runs = load("S2")
    if not runs:
        return None
    pts = sorted({(r["latency_s"], r["loss"]) for r in runs})
    holds = sorted({r["stale_hold_min"] for r in runs if r["controller"] != "A"})
    fig, axes = plt.subplots(1, len(pts), figsize=(12.4, 3.8), dpi=200, sharey=True)
    for ax, (lat, loss) in zip(axes, pts):
        for k, key in enumerate("BC"):
            means, labels = [], []
            for h in holds:
                c = [r for r in runs if r["controller"] == key and r["latency_s"] == lat
                     and r["loss"] == loss and r["stale_hold_min"] == h]
                safe = [adv(r) for r in c if r["counted"]]
                means.append(statistics.fmean(safe) if safe else 0.0)
                labels.append("%d/%d" % (len(safe), len(c)))
            x = np.arange(len(holds)) + (k - 0.5) * 0.38
            bars = ax.bar(x, means, 0.36, color=RED if key == "B" else GREY,
                          label="B trust-weighted" if key == "B" else "C binary fallback")
            for b, lab in zip(bars, labels):
                ax.text(b.get_x() + b.get_width() / 2, max(b.get_height(), 0) + 0.8, lab,
                        ha="center", fontsize=7.5, color=BLACK)
        ax.axhline(0, color=BLACK, lw=1.0)
        lo, hi = ax.get_ylim()
        ax.set_ylim(lo, hi + 0.12 * (hi - lo))      # room for the bar labels
        ax.set_xticks(np.arange(len(holds)))
        ax.set_xticklabels(["off" if h == 0 else "%g min" % h for h in holds])
        ax.set_title("%d s latency, %g%% loss" % (lat, loss * 100), fontsize=11, loc="left")
        ax.set_xlabel("stale-data hold (V3)")
    axes[0].set_ylabel("advantage over static (%)")
    axes[0].legend(frameon=False, fontsize=9)
    fig.text(0.01, -0.02, "Bar labels: seeds with no violation / seeds run. Mean over safe "
             "seeds only.", fontsize=9, color=GREY)
    out = os.path.join(STAGES, "stage_S2.png")
    fig.tight_layout()
    fig.savefig(out, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return out


def s3():
    on, off = load("S1"), load("S3")
    if not on or not off:
        return None
    cells = sorted({(r["latency_s"], r["loss"]) for r in off if r["controller"] == "B"})
    fig, ax = plt.subplots(figsize=(8.6, 3.9), dpi=200)
    x = np.arange(len(cells))
    for k, (runs, label, colour) in enumerate(((on, "battery on (S1)", RED),
                                               (off, "battery off (S3)", GREY))):
        m = []
        for lat, loss in cells:
            safe = [adv(r) for r in runs if r["controller"] == "B" and r["latency_s"] == lat
                    and r["loss"] == loss and r["counted"]]
            m.append(statistics.fmean(safe) if safe else np.nan)
        ax.bar(x + (k - 0.5) * 0.38, m, 0.36, color=colour, label=label)
    ax.axhline(0, color=BLACK, lw=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(["%ds\n%g%%" % (l, p * 100) for l, p in cells], fontsize=9)
    ax.set_ylabel("B advantage over its\nnetwork's static limit (%)")
    ax.legend(frameon=False, fontsize=9.5)
    out = os.path.join(STAGES, "stage_S3.png")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


if __name__ == "__main__":
    for f in (s1, s2, s3):
        p = f()
        print("wrote" if p else "no data for", p or f.__name__)
