"""Build docs/Digital_Twin_Guide.pdf: a plain-language guide to the twin node, its models
and its results.

    py docs/guide/build_guide.py

Draws three explanatory diagrams (matplotlib) into docs/guide/, then lays out the PDF with
ReportLab around them and the result figures already in results/. Rerun after the results
change; the numbers in the text are the final runs of 2-3 October 2026.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402
from matplotlib.patches import FancyBboxPatch, Circle             # noqa: E402
from PIL import Image as PILImage                                 # noqa: E402

from reportlab.lib import colors                                  # noqa: E402
from reportlab.lib.enums import TA_LEFT                           # noqa: E402
from reportlab.lib.pagesizes import A4                            # noqa: E402
from reportlab.lib.styles import ParagraphStyle                   # noqa: E402
from reportlab.lib.units import cm                                # noqa: E402
from reportlab.pdfbase import pdfmetrics                          # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont                      # noqa: E402
from reportlab.lib.fonts import addMapping                        # noqa: E402
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,  # noqa: E402
                                NextPageTemplate, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle, CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(PROJECT, "docs", "Digital_Twin_Guide.pdf")
RES = os.path.join(PROJECT, "results")

RED = "#C8102E"
INK = "#1A1A1A"
GREY = "#666666"
LIGHT = "#F3F3F3"
TINT = "#FBEAEC"

# ------------------------------------------------------------------ diagrams

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Calibri", "Segoe UI", "Arial", "DejaVu Sans"]


def _box(ax, x, y, w, h, title, body, face=LIGHT, edge="#9A9A9A", num=None, tsize=11.5,
         bsize=9.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2",
                                linewidth=1.3, edgecolor=edge, facecolor=face))
    ax.text(x + w / 2, y + h - 1.6, title, ha="center", va="top", fontsize=tsize,
            fontweight="bold", color=INK)
    ax.text(x + w / 2, y + h - 4.6, body, ha="center", va="top", fontsize=bsize,
            color="#333333", linespacing=1.25)
    if num is not None:
        ax.add_patch(Circle((x + 0.2, y + h - 0.2), 1.55, facecolor=RED, edgecolor="white",
                            linewidth=1.2, zorder=5))
        ax.text(x + 0.2, y + h - 0.25, str(num), ha="center", va="center", fontsize=10,
                color="white", fontweight="bold", zorder=6)


def _arrow(ax, x1, y1, x2, y2, color="#444444", style="-|>", lw=1.6, conn=None):
    props = dict(arrowstyle=style, color=color, lw=lw, shrinkA=0, shrinkB=0,
                 mutation_scale=14)
    if conn:
        props["connectionstyle"] = conn
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=props)


def _canvas(w=10.0, h=4.6, xmax=100, ymax=46):
    fig, ax = plt.subplots(figsize=(w, h), dpi=300)
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


def fig_nodes(path):
    fig, ax = _canvas(10, 4.9, 100, 50)
    _box(ax, 8, 36, 84, 12, "Digital twin server  (Munir)",
         "the street model in OpenDSS  ·  the five network checks  ·  the safe-limit search\n"
         "controllers A, B and C  ·  the experiment runner", face=TINT, edge=RED)
    _box(ax, 8, 18.5, 40, 10.5, "Comms injector and trust  (Hoang)",
         "delays, drops and freezes messages\nscores how far the data can be trusted")
    _box(ax, 8, 1.2, 40, 10.5, "EV charge points  (Lomitha)",
         "apply the limit to each charger, report energy,\nfall back to 1.4 kW  ·  Raspberry Pi over MQTT")
    _box(ax, 56, 1.2, 36, 10.5, "Battery, BMS and EMS  (Gia)",
         "state of charge  ·  volt-var and volt-watt\nresponse to the local voltage")
    # up: readings; down: limits
    _arrow(ax, 18, 11.9, 18, 18.3)
    _arrow(ax, 18, 29.2, 18, 35.8)
    _arrow(ax, 38, 35.8, 38, 29.2)
    _arrow(ax, 38, 18.3, 38, 11.9)
    ax.text(17, 32.5, "meter readings\nevery 30 s", ha="right", va="center", fontsize=9,
            color=GREY)
    ax.text(17, 15.1, "readings and\ncar status", ha="right", va="center", fontsize=9,
            color=GREY)
    ax.text(39.2, 32.5, "charging limits\nevery 5 min", ha="left", va="center", fontsize=9,
            color=GREY)
    ax.text(39.2, 15.1, "the limit that\ngot through", ha="left", va="center", fontsize=9,
            color=GREY)
    _arrow(ax, 74, 11.9, 74, 35.8, style="<|-|>")
    ax.text(75.3, 24, "the battery's response is\npart of the street's power flow",
            ha="left", va="center", fontsize=9, color=GREY)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_loop(path):
    fig, ax = _canvas(10, 4.9, 100, 50)
    w, h = 21.5, 15
    top, bot = 33, 5
    xs = [1.5, 26.5, 51.5, 76.5]
    tops = [("The street now", "house demand, solar,\nthe battery and what\nthe cars draw"),
            ("Meters report", "a reading from every\nhouse every 30 s"),
            ("Comms link, up", "each reading can be\ndelayed, lost or\nfrozen"),
            ("Twin's picture", "built from what arrived,\nmaybe minutes old,\nplus a trust score")]
    for i, (x, (t, b)) in enumerate(zip(xs, tops)):
        _box(ax, x, top, w, h - 2, t, b, num=i + 1,
             face=TINT if i == 0 else LIGHT, edge=RED if i == 0 else "#9A9A9A")
    bots = [(76.5, "Safe limit (envelope)", "highest kW per car that\nkeeps all five limits, with\na margin for the data's age"),
            (51.5, "Controller A, B or C", "turns the envelope and\nthe trust score into the\nlimit it sends"),
            (26.5, "Comms link, down", "the limit can be late or lost;\nchargers use the newest\nschedule entry, or 1.4 kW")]
    for i, (x, t, b) in enumerate(bots):
        _box(ax, x, bot, w, h - 2, t, b, num=i + 5)
    for x in xs[:-1]:
        _arrow(ax, x + w + 0.4, top + 6.5, x + w + 3.4, top + 6.5)
    _arrow(ax, xs[3] + w / 2, top - 0.3, xs[3] + w / 2, bot + h - 1.7)
    _arrow(ax, 76.5 - 0.4, bot + 6.5, 73 + 0.4, bot + 6.5)
    _arrow(ax, 51.5 - 0.4, bot + 6.5, 48 + 0.4, bot + 6.5)
    # 7 back to 1
    ax.plot([26.1, 12.25], [bot + 6.5, bot + 6.5], color=RED, lw=1.8)
    _arrow(ax, 12.25, bot + 6.5, 12.25, top - 0.3, color=RED, lw=1.8)
    ax.text(13.2, 22.5, "what the chargers draw is applied\nto the true street and checked\n"
            "against the five limits", ha="left", va="center", fontsize=9, color=RED)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_schedule(path):
    fig, ax = _canvas(10, 4.2, 100, 42)
    x0, cw = 22, 18.5
    steps = ["step j", "j + 1", "j + 2", "j + 3"]
    status = [("arrives", "#2E7D32"), ("lost", RED), ("lost", RED), ("lost", RED)]
    for i, s in enumerate(steps):
        cx = x0 + i * cw + cw / 2
        ax.text(cx, 40.5, s, ha="center", va="center", fontsize=10.5, fontweight="bold",
                color=INK)
        lab, col = status[i]
        ax.add_patch(Circle((cx - 4.2, 36.6), 0.9, facecolor=col, edgecolor="none"))
        ax.text(cx - 2.8, 36.6, "message " + lab, ha="left", va="center", fontsize=9,
                color=col)
    for i in range(5):
        ax.plot([x0 + i * cw, x0 + i * cw], [3, 34], color="#DDDDDD", lw=0.9, zorder=0)

    def block(i, y, text, face, edge, hatch=None):
        ax.add_patch(FancyBboxPatch((x0 + i * cw + 0.6, y), cw - 1.2, 10,
                                    boxstyle="round,pad=0.1,rounding_size=0.8",
                                    facecolor=face, edgecolor=edge, linewidth=1.2,
                                    hatch=hatch))
        ax.text(x0 + i * cw + cw / 2, y + 5, text, ha="center", va="center", fontsize=9.3,
                color=INK, linespacing=1.2,
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="none",
                          alpha=0.92) if hatch else None)

    ax.text(1, 27.5, "Before:\none limit per\nmessage", ha="left", va="center",
            fontsize=10, fontweight="bold", color=INK, linespacing=1.15)
    block(0, 22.5, "limit from step j\nmargin 1%", TINT, RED)
    block(1, 22.5, "same limit\ndata now 5 min old", "#F7D7DC", RED, hatch="///")
    block(2, 22.5, "same limit\ndata now 10 min old", "#F7D7DC", RED, hatch="///")
    block(3, 22.5, "1.4 kW fallback", LIGHT, "#9A9A9A")
    ax.text(1, 10.5, "After:\na schedule of\nthree entries", ha="left", va="center",
            fontsize=10, fontweight="bold", color=INK, linespacing=1.15)
    block(0, 5.5, "entry 0\nmargin 1%", TINT, RED)
    block(1, 5.5, "entry 1\nmargin 12.5%", TINT, RED)
    block(2, 5.5, "entry 2\nmargin 16%", TINT, RED)
    block(3, 5.5, "1.4 kW fallback", LIGHT, "#9A9A9A")
    ax.text(x0, 1.4, "Margins shown are for fresh data (0 s delay). Hatched: a limit "
            "planned for fresher data than it now has.", ha="left", va="center",
            fontsize=8.5, color=GREY, style="italic")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)



# ------------------------------------------------------------------ result charts, print size
# Drawn at the size they are printed (6.6 in = the text width), so every label is a real
# 6.5-9 pt. Colours are the dataviz reference palette: diverging blue <-> red with a neutral
# grey midpoint (blue = live control ahead of the fixed limit, red = behind); categorical
# slots 1-2 (blue, orange) for two series; the blue ordinal ramp from step 250 up for the
# four timeouts. Text stays in ink colours, never series colours.

import glob as _glob                                              # noqa: E402
import json as _json                                              # noqa: E402
import math as _math                                              # noqa: E402
import statistics as _stats                                       # noqa: E402
import sys as _sys                                                # noqa: E402

import numpy as _np                                               # noqa: E402
from matplotlib.colors import LinearSegmentedColormap             # noqa: E402
from matplotlib.patches import Rectangle                          # noqa: E402
import matplotlib.patheffects as _pe                              # noqa: E402

INK1, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, ORANGE = "#2a78d6", "#eb6834"
DIVERGING = LinearSegmentedColormap.from_list(
    "guide_div", ["#a1201f", "#e34948", "#f3b3ad", "#f0efec", "#9ec5f4", "#3987e5", "#184f95"])
LAT = [0, 5, 30, 60, 120, 300, 600]
LOSS = [0.0, 0.01, 0.05, 0.10, 0.20, 0.40]


def _runs(folder, stage):
    out = []
    for f in sorted(_glob.glob(os.path.join(RES, folder, "%s_seed*.json" % stage))):
        out += _json.load(open(f, encoding="utf-8"))["runs"]
    return out


def _adv(r):
    return 100.0 * (r["energy_kwh"] - r["static_kwh"]) / r["static_kwh"]


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=8, length=3, color=AXIS)


def chart_heatmaps(folder, path):
    runs = _runs(folder, "S1")
    fig, axes = plt.subplots(2, 1, figsize=(6.6, 7.0), dpi=300)
    grids = {}
    lim = 0.0
    for key in "BC":
        Z = _np.full((len(LOSS), len(LAT)), _np.nan)
        U, N, S = (_np.zeros_like(Z) for _ in range(3))
        for i, loss in enumerate(LOSS):
            for j, lat in enumerate(LAT):
                c = [r for r in runs if r["controller"] == key and r["latency_s"] == lat
                     and r["loss"] == loss]
                safe = [_adv(r) for r in c if r["counted"]]
                if safe:
                    Z[i, j] = _stats.fmean(safe)
                N[i, j], S[i, j] = len(c), len(safe)
                U[i, j] = (len(c) - len(safe)) / max(len(c), 1)
        grids[key] = (Z, U, N, S)
        lim = max(lim, _np.nanmax(_np.abs(Z)))
    lim = 5.0 * _math.ceil(lim / 5.0)
    xs, ys = _np.arange(len(LAT)), _np.arange(len(LOSS))
    for ax, key, title in zip(axes, "BC", ("B, trust-weighted", "C, binary fallback")):
        Z, U, N, S = grids[key]
        Zd = Z.copy()
        Zd[U > 0.5] = _np.nan
        im = ax.imshow(_np.ma.masked_invalid(Zd), origin="lower", cmap=DIVERGING, vmin=-lim,
                       vmax=lim, aspect="auto")
        for i in range(len(LOSS)):
            for j in range(len(LAT)):
                # each label wears a halo in its own cell's colour, so the break-even line
                # stops short of the text instead of running through it
                if U[i, j] > 0.5:
                    ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor="#f0efec",
                                           edgecolor="#b9b8b1", hatch="////", lw=0))
                    ax.text(j, i, "unsafe\n%d/%d safe" % (S[i, j], N[i, j]), ha="center",
                            va="center", fontsize=6.6, color=INK2, linespacing=1.05, zorder=4,
                            path_effects=[_pe.withStroke(linewidth=3, foreground="#f0efec")])
                    continue
                v = Zd[i, j]
                if _np.isnan(v):
                    continue
                col = "white" if abs(v) > 0.6 * lim else INK1
                halo = [_pe.withStroke(linewidth=3.2,
                                       foreground=DIVERGING((v + lim) / (2 * lim)))]
                lab = "0" if abs(v) < 0.5 else "%+.0f" % v
                if S[i, j] < N[i, j]:
                    ax.text(j, i + 0.13, lab, ha="center", va="center", fontsize=8.6,
                            color=col, fontweight="bold", zorder=4, path_effects=halo)
                    ax.text(j, i - 0.2, "%d/%d safe" % (S[i, j], N[i, j]), ha="center",
                            va="center", fontsize=6.5, color=col, zorder=4, path_effects=halo)
                else:
                    ax.text(j, i, lab, ha="center", va="center", fontsize=8.6, color=col,
                            fontweight="bold", zorder=4, path_effects=halo)
        if _np.isfinite(Zd).sum() >= 4 and _np.nanmin(Zd) < 0 < _np.nanmax(Zd):
            try:
                ax.contour(xs, ys, _np.ma.masked_invalid(Zd), levels=[0.0], colors=INK1,
                           linewidths=1.7, zorder=3)
            except (ValueError, IndexError):
                pass
        ax.set_xticks(xs)
        ax.set_xticklabels([str(l) for l in LAT])
        ax.set_yticks(ys)
        ax.set_yticklabels(["%g" % (l * 100) for l in LOSS])
        ax.set_xlabel("delay (s), both directions", fontsize=8.5, color=INK2)
        ax.set_ylabel("packet loss (%)", fontsize=8.5, color=INK2)
        ax.set_title(title, loc="left", fontsize=10, color=INK1, fontweight="bold")
        ax.tick_params(colors=INK2, labelsize=8, length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
    fig.subplots_adjust(hspace=0.42, right=0.86, left=0.1, top=0.95, bottom=0.08)
    cax = fig.add_axes([0.89, 0.25, 0.022, 0.5])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("advantage over the fixed limit (%)", fontsize=8.5, color=INK2)
    cb.ax.tick_params(labelsize=7.5, colors=INK2, length=2)
    cb.outline.set_visible(False)
    fig.text(0.89, 0.79, "blue: ahead", fontsize=7.5, color=INK2)
    fig.text(0.89, 0.205, "red: behind", fontsize=7.5, color=INK2)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def chart_stale(path):
    runs = _runs("stages", "S2")
    pts = [(5, 0.01), (60, 0.10), (300, 0.20)]
    holds = [0.0, 2.0, 5.0, 8.0]
    fig, axes = plt.subplots(1, 3, figsize=(6.6, 2.75), dpi=300, sharey=True)
    for ax, (lat, loss) in zip(axes, pts):
        for k, (key, colour) in enumerate((("B", BLUE), ("C", ORANGE))):
            means, labels = [], []
            for h in holds:
                c = [r for r in runs if r["controller"] == key and r["latency_s"] == lat
                     and r["loss"] == loss and r["stale_hold_min"] == h]
                safe = [_adv(r) for r in c if r["counted"]]
                means.append(_stats.fmean(safe) if safe else 0.0)
                labels.append("%d/%d" % (len(safe), len(c)))
            x = _np.arange(len(holds)) + (k - 0.5) * 0.4
            bars = ax.bar(x, means, 0.38, color=colour, edgecolor="white", linewidth=0.8,
                          label="B, trust-weighted" if key == "B" else "C, binary fallback")
            for b, lab, m in zip(bars, labels, means):
                y = m + 0.7 if m >= 0 else m - 0.7
                ax.text(b.get_x() + b.get_width() / 2, y, lab, ha="center",
                        va="bottom" if m >= 0 else "top", fontsize=6.2, color=INK2)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(_np.arange(len(holds)))
        ax.set_xticklabels(["none" if h == 0 else "%g min" % h for h in holds])
        ax.set_title("%d s delay, %g%% loss" % (lat, loss * 100), loc="left", fontsize=8.8,
                     color=INK1, fontweight="bold")
        ax.set_xlabel("frozen data", fontsize=8, color=INK2)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        _style(ax)
    lo, hi = axes[0].get_ylim()
    axes[0].set_ylim(lo - 1.5, hi + 2.5)
    axes[0].set_ylabel("advantage over fixed limit (%)", fontsize=8, color=INK2)
    axes[0].legend(frameon=False, fontsize=7.5, loc="lower left")
    fig.tight_layout(w_pad=1.2)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def chart_battery(path):
    on, off = _runs("stages", "S1"), _runs("stages", "S3")
    cells = [(l, p) for l in (5, 60, 300) for p in (0.01, 0.10, 0.20)]
    fig, ax = plt.subplots(figsize=(6.6, 2.6), dpi=300)
    x = _np.arange(len(cells))
    for k, (runs, label, colour) in enumerate(((on, "battery on", BLUE),
                                               (off, "battery off", ORANGE))):
        m = []
        for lat, loss in cells:
            safe = [_adv(r) for r in runs if r["controller"] == "B" and r["latency_s"] == lat
                    and r["loss"] == loss and r["counted"]]
            m.append(_stats.fmean(safe) if safe else _np.nan)
        ax.bar(x + (k - 0.5) * 0.4, m, 0.38, color=colour, edgecolor="white", linewidth=0.8,
               label=label)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(["%d s\n%g%%" % (l, p * 100) for l, p in cells], fontsize=7.6)
    ax.set_ylabel("B's advantage over its own\nnetwork's fixed limit (%)", fontsize=8,
                  color=INK2)
    ax.set_xlabel("delay and packet loss", fontsize=8, color=INK2)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=7.8, loc="lower left")
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def chart_timeout(path):
    _sys.path.insert(0, os.path.join(PROJECT, "src"))
    from timeout_sensitivity import crossing, quantile
    table = {}
    for f in _glob.glob(os.path.join(RES, "timeout_sensitivity", "timeout_*_seed*.json")):
        d = _json.load(open(f, encoding="utf-8"))
        by = {}
        for r in d["runs"]:
            if r["delta_pct"] is not None:
                by.setdefault(r["loss"], []).append((r["latency_s"], r["delta_pct"]))
        for loss, pts in by.items():
            table.setdefault(d["timeout_min"], {}).setdefault(loss, []).append(
                crossing(sorted(pts)))
    ramp = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
    fig, ax = plt.subplots(figsize=(6.0, 2.9), dpi=300)
    for T, colour in zip(sorted(table), ramp):
        xs, ys = [], []
        for loss in sorted(table[T]):
            vals = [v for v in table[T][loss] if v is not None]
            if vals:
                xs.append(loss * 100)
                ys.append(quantile(vals, 0.5))
        ax.plot(xs, ys, color=colour, lw=1.8, marker="o", ms=4.5,
                markeredgecolor="white", markeredgewidth=0.8,
                label="%d min%s" % (T, "  (used)" if T == 15 else ""))
        ax.text(xs[0] - 0.6, ys[0], "%d min" % T, ha="right", va="center", fontsize=7.6,
                color=INK2)
    ax.set_xlim(5.5, 41)
    ax.set_ylim(-5, 175)
    ax.set_xticks([10, 20, 30, 40])
    ax.set_xlabel("packet loss (%)", fontsize=8, color=INK2)
    ax.set_ylabel("delay where B stops\nbeating the fixed limit (s)", fontsize=8, color=INK2)
    ax.grid(color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(title="timeout", title_fontsize=7.8, frameon=False, fontsize=7.6,
              loc="upper right")
    ax.text(30.4, 8, "0 s = behind the fixed limit even at 0 s delay", fontsize=7, color=INK2)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)

# ------------------------------------------------------------------ PDF styles

FONT_DIR = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("Cal", os.path.join(FONT_DIR, "calibri.ttf")))
pdfmetrics.registerFont(TTFont("Cal-B", os.path.join(FONT_DIR, "calibrib.ttf")))
pdfmetrics.registerFont(TTFont("Cal-I", os.path.join(FONT_DIR, "calibrii.ttf")))
pdfmetrics.registerFont(TTFont("Cal-BI", os.path.join(FONT_DIR, "calibriz.ttf")))
addMapping("Cal", 0, 0, "Cal")
addMapping("Cal", 1, 0, "Cal-B")
addMapping("Cal", 0, 1, "Cal-I")
addMapping("Cal", 1, 1, "Cal-BI")

BODY = ParagraphStyle("body", fontName="Cal", fontSize=10.6, leading=15, textColor=INK,
                      spaceAfter=7, alignment=TA_LEFT)
H1 = ParagraphStyle("h1", fontName="Cal-B", fontSize=19, leading=23, textColor=INK,
                    spaceBefore=4, spaceAfter=10)
H2 = ParagraphStyle("h2", fontName="Cal-B", fontSize=13.2, leading=17, textColor=RED,
                    spaceBefore=10, spaceAfter=5)
H3 = ParagraphStyle("h3", fontName="Cal-B", fontSize=11, leading=15, textColor=INK,
                    spaceBefore=6, spaceAfter=3)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=14, bulletIndent=3, spaceAfter=4)
NUM = ParagraphStyle("num", parent=BODY, leftIndent=18, bulletIndent=2, spaceAfter=4)
CAP = ParagraphStyle("cap", fontName="Cal-I", fontSize=9.2, leading=12.5, textColor=GREY,
                     spaceBefore=3, spaceAfter=12)
CELL = ParagraphStyle("cell", fontName="Cal", fontSize=9.4, leading=12.4, textColor=INK)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Cal-B")
CALL = ParagraphStyle("call", parent=BODY, fontSize=10.4, leading=14.5, spaceAfter=0)
TOC1 = ParagraphStyle("toc1", fontName="Cal", fontSize=11.5, leading=21, leftIndent=0)
TOC2 = ParagraphStyle("toc2", fontName="Cal", fontSize=10, leading=13.5, leftIndent=16,
                      textColor="#333333")

FRAME_W = A4[0] - 4.4 * cm
TITLE = "Your digital twin node, explained"
FOOTER = "Your digital twin node, explained  ·  EEE40016"


class GuideDoc(BaseDocTemplate):
    def __init__(self, path, **kw):
        super().__init__(path, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                         topMargin=2.0 * cm, bottomMargin=2.0 * cm,
                         title=TITLE,
                         author="EEE40016 digital twin node", **kw)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=_cover_page),
                               PageTemplate(id="body", frames=[frame], onPage=_body_page)])
        self._n = 0

    def beforeDocument(self):
        # multiBuild lays the document out several times; the bookmark keys must be the same
        # on every pass or the contents page never settles
        self._n = 0

    def afterFlowable(self, flow):
        if isinstance(flow, Paragraph) and flow.style.name in ("h1", "h2"):
            level = 0 if flow.style.name == "h1" else 1
            text = flow.getPlainText()
            self._n += 1
            key = "h%d" % self._n
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            if level == 0:          # the contents page lists sections; bookmarks list both
                self.notify("TOCEntry", (level, text, self.page, key))


def _cover_page(canv, doc):
    canv.saveState()
    canv.setFillColor(colors.HexColor(RED))
    canv.rect(0, A4[1] - 1.2 * cm, A4[0], 1.2 * cm, stroke=0, fill=1)
    canv.restoreState()


def _body_page(canv, doc):
    canv.saveState()
    canv.setStrokeColor(colors.HexColor("#DDDDDD"))
    canv.setLineWidth(0.6)
    canv.line(2.2 * cm, 1.45 * cm, A4[0] - 2.2 * cm, 1.45 * cm)
    canv.setFont("Cal", 8.5)
    canv.setFillColor(colors.HexColor(GREY))
    canv.drawString(2.2 * cm, 1.0 * cm, FOOTER)
    canv.drawRightString(A4[0] - 2.2 * cm, 1.0 * cm, str(doc.page))
    canv.restoreState()


# ------------------------------------------------------------------ helpers

story = []


def h1(t, need=9):
    story.append(CondPageBreak(need * cm))
    story.append(Paragraph(t, H1))


def h2(t, need=3.5):
    story.append(CondPageBreak(need * cm))
    story.append(Paragraph(t, H2))


def fig_cm(path, width=1.0):
    """Printed height of a figure plus its caption, in cm, so its heading can stay with it."""
    im = PILImage.open(path)
    return width * FRAME_W * im.size[1] / im.size[0] / cm + 2.2


def h3(t):
    story.append(Paragraph(t, H3))


def p(t):
    story.append(Paragraph(t, BODY))


def bullets(items):
    for it in items:
        story.append(Paragraph(it, BUL, bulletText="•"))
    story.append(Spacer(1, 4))


def numbered(items):
    for i, it in enumerate(items, 1):
        story.append(Paragraph(it, NUM, bulletText="%d." % i))
    story.append(Spacer(1, 4))


def callout(t, face=TINT, edge=RED):
    tb = Table([[Paragraph(t, CALL)]], colWidths=[FRAME_W])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(face)),
                            ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(edge)),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                            ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(Spacer(1, 3))
    story.append(tb)
    story.append(Spacer(1, 9))


def table(rows, widths, header=True, size=None):
    """rows: lists of strings (Paragraph markup). widths: fractions of the frame width."""
    style = CELL if size is None else ParagraphStyle("c%s" % size, parent=CELL,
                                                     fontSize=size, leading=size * 1.32)
    bstyle = ParagraphStyle(style.name + "b", parent=style, fontName="Cal-B")
    data = []
    for r, row in enumerate(rows):
        data.append([Paragraph(c, bstyle if (header and r == 0) else style) for c in row])
    tb = Table(data, colWidths=[w * FRAME_W for w in widths], repeatRows=1 if header else 0)
    ts = [("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if header:
        ts += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT)),
               ("LINEBELOW", (0, 0), (-1, 0), 0.9, colors.HexColor("#999999"))]
    tb.setStyle(TableStyle(ts))
    story.append(KeepTogether([tb]) if len(rows) <= 10 else tb)
    story.append(Spacer(1, 10))


def figure(path, caption, width=1.0):
    im = PILImage.open(path)
    w = width * FRAME_W
    h = w * im.size[1] / im.size[0]
    story.append(KeepTogether([Spacer(1, 2), Image(path, width=w, height=h),
                               Paragraph(caption, CAP)]))


# ------------------------------------------------------------------ content

def build_story(figs):
    # ---- cover
    story.append(Spacer(1, 3.2 * cm))
    story.append(Paragraph("Your digital twin node, explained",
                           ParagraphStyle("t", fontName="Cal-B", fontSize=30, leading=36,
                                          textColor=INK)))
    story.append(Spacer(1, 6))
    story.append(Paragraph("What was built, how the models work, and what the results say",
                           ParagraphStyle("st", fontName="Cal", fontSize=15, leading=20,
                                          textColor=GREY)))
    story.append(Spacer(1, 22))
    tb = Table([[""]], colWidths=[4 * cm], rowHeights=[3])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(RED))]))
    tb.hAlign = "LEFT"
    story.append(tb)
    story.append(Spacer(1, 18))
    cov = ParagraphStyle("cov", parent=BODY, fontSize=11.5, leading=17)
    story.append(Paragraph("EEE40016 Design of Smart Power Grids<br/>"
                           "Node: digital twin server (Munir Aslam)<br/>3 October 2026", cov))
    story.append(Spacer(1, 1.6 * cm))
    callout("This guide explains the whole twin node in plain terms: the question the project "
            "asks, how the street and its electricity network are modelled, how a safe charging "
            "limit is worked out every five minutes, how bad communications are simulated, the "
            "three controllers being compared, and what the final experiments found. Every "
            "number comes from the final runs of 2 and 3 October 2026. The project folder is "
            "<font name='Cal-B'>Downloads\\EEE40016\\project</font>.", face="#F6F6F6",
            edge="#9A9A9A")
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())

    # ---- contents
    story.append(Paragraph("Contents", ParagraphStyle("toctitle", parent=H1)))
    toc = TableOfContents()
    toc.levelStyles = [TOC1, TOC2]
    toc.dotsMinLevel = 0
    story.append(toc)
    story.append(Spacer(1, 10))
    p("<font name='Cal-B'>How to read this.</font> Section 1 gives the whole story on one "
      "page. Sections 2 to 8 explain how the model works, one piece at a time, in the order "
      "the pieces are used. Sections 9 to 11 cover the main design fix, the experiments and "
      "the results. The rest covers how the model was checked, what went wrong along the "
      "way, what the results depend on, what is left, and where everything is. A glossary "
      "at the end explains the terms.")
    story.append(PageBreak())

    # ---- 1
    h1("1. The short version")
    p("The project asks one question: <font name='Cal-B'>when does live control of EV "
      "charging beat a simple fixed limit, given that the communications between the network "
      "and the chargers are never perfect?</font>")
    p("Live control means the network works out a safe charging limit every five minutes from "
      "what the street is doing at that moment (a dynamic operating envelope) and sends it "
      "to the chargers. A fixed limit is one safe number set in advance and never changed. "
      "Live control can give cars more energy when the network has room, but it relies on "
      "data and messages that can arrive late, go missing or stop updating. If the data is "
      "stale, a limit that looked safe may no longer be safe.")
    p("Your node, the digital twin server, answers that question from start to finish. It "
      "simulates a real street (55 houses, 22 EVs, rooftop solar and a battery) through an "
      "evening from 16:00 to 22:00, degrades the communications in a controlled way, and "
      "compares three controllers:")
    bullets(["<font name='Cal-B'>A, fixed limit:</font> one safe limit all evening.",
             "<font name='Cal-B'>B, trust-weighted:</font> the live limit, turned down as the "
             "data becomes less trustworthy. This is the project's proposal.",
             "<font name='Cal-B'>C, binary fallback:</font> the live limit in full until the "
             "data is 15 minutes old, then the fixed limit. This is how deployed systems in "
             "the Australian trials work."])
    p("What the final experiments found (13 simulated evenings for every setting):")
    bullets(["<font name='Cal-B'>Live control pays when the street is congested and the comms "
             "are good.</font> On a normal evening B gave cars up to about 15% more energy than "
             "the fixed limit and stayed ahead up to about a minute of delay at low packet "
             "loss. Past about two minutes of delay, or with 20% or more packet loss, the fixed "
             "limit did as well or better.",
             "<font name='Cal-B'>B is the safer way to do live control.</font> C got slightly "
             "more energy than B on good links, but broke a network limit in 82 runs out of "
             "546, against 9 for B. On the design-day stress case it was 140 against 20.",
             "<font name='Cal-B'>About half of normal evenings are not congested at all,"
             "</font> so live control has nothing to win on them.",
             "<font name='Cal-B'>Frozen data is the most dangerous failure.</font> Readings "
             "that stop changing but keep fresh timestamps fool the trust score completely.",
             "<font name='Cal-B'>A fix made during the work (setpoint schedules)</font> removed "
             "most of the violations caused by late or lost messages, at almost no cost in "
             "energy."])
    callout("<font name='Cal-B'>These are not the project's final results yet.</font> Three "
            "teammates' parts (comms and trust, the charge-point controller, and the battery) "
            "are stand-ins written for this build, and the cable ratings are provisional. When "
            "the real parts pass the same tests, the experiments are rerun with them.")

    # ---- 2
    h1("2. The project and where your node fits")
    p("The project has four parts, called nodes, one per team member. Figure 1 shows how they "
      "connect. Your node sits in the middle: it holds the model of the street, works out the "
      "safe limits and runs the experiments.")
    figure(figs["nodes"], "Figure 1. The four nodes. Readings go up through the comms link "
           "to the twin; charging limits come back down the same way. The grey boxes are "
           "stand-ins written for this build, to be replaced by each teammate's own code.")
    table([["Node", "Owner", "What it does", "In this build"],
           ["Digital twin server", "Munir", "street model, network checks, safe-limit search, "
            "controllers, experiment runner", "built and validated"],
           ["Comms injector and trust", "Hoang", "delays, drops and freezes messages; scores "
            "how far the data can be trusted", "stand-in, <font name='Cal-I'>src/telemetry.py"
            "</font>"],
           ["EV charge-point controller", "Lomitha", "applies the limit to each charger, "
            "reports energy, falls back to 1.4 kW", "stand-in, <font name='Cal-I'>src/edge.py"
            "</font>; runs on the Pi"],
           ["Battery, BMS and EMS", "Gia", "battery state of charge and inverter response",
            "stand-in, <font name='Cal-I'>src/battery.py</font>"]],
          [0.24, 0.12, 0.40, 0.24])
    p("One rule makes the integration work: each teammate writes their logic as a plain Python "
      "class with no networking inside it. The simulator calls that class directly for "
      "thousands of runs, and the Raspberry Pi runs the very same class behind MQTT for the "
      "hardware demo. A test (<font name='Cal-I'>test_mqtt_equivalence.py</font>) runs one "
      "evening both ways and checks they give exactly the same answer at every step. It "
      "passes at three different comms settings.")
    p("The messages between nodes are defined once, in <font name='Cal-I'>messages.py</font>. "
      "Since 2 October it is version 2, because a limit now carries a schedule entry and a "
      "time window (Section 9). Everyone has to use the new file, and "
      "<font name='Cal-I'>docs/INTERFACES.md</font> lists exactly what each person must "
      "build.")

    # ---- 3
    h1("3. The street: the network model")
    p("The street is the <font name='Cal-B'>IEEE European Low Voltage Test Feeder</font>, a "
      "published benchmark based on a real suburban street. It has 906 connection points "
      "(called buses) and 55 houses fed from one transformer through underground cables. Each "
      "house is connected to one of the three phases, which is why the phases can end up "
      "unequally loaded.")
    p("It is solved in <font name='Cal-B'>OpenDSS</font>, a free power-flow program, as a full "
      "three-phase unbalanced model. SINCAL was the first choice, but the laptop's licence only "
      "allows 50 nodes, so OpenDSS runs the study and SINCAL is used to cross-check it "
      "(Section 12).")
    table([["Part", "How it is modelled"],
           ["Feeder", "IEEE European LV Test Feeder: 906 buses, 55 houses, three-phase "
            "unbalanced"],
           ["Transformer", "re-rated from 800 kVA to 150 kVA (4% impedance) so that it can "
            "actually be stressed"],
           ["Supply voltage", "1.00 pu at the transformer. The published 1.05 pu left only "
            "0.2 V of headroom below the 253 V limit."],
           ["House demand", "the measured one-minute load profiles that come with the "
            "feeder"],
           ["Rooftop solar", "33 of the 55 houses (60%): 6.6 kW of panels on a 5 kW inverter, "
            "clear-sky output for a late-spring day, with a cloud passing from 16:40 to "
            "16:55"],
           ["Weather", "Bureau of Meteorology air temperature (Melbourne Olympic Park), used "
            "for the transformer's temperature"],
           ["Battery", "one 100 kWh, 50 kVA unit at the electrical middle of the street (bus "
            "686), responding to local voltage as AS/NZS 4777.2 requires (volt-var and "
            "volt-watt)"],
           ["EVs", "22 houses (40%), each with a 7.2 kW charger that can be set in 0.1 kW "
            "steps"],
           ["Time", "16:00 to 22:00 in 5-minute control steps (72 steps); meters report "
            "every 30 seconds"]],
          [0.22, 0.78])
    p("<font name='Cal-B'>Is the model right?</font> With the original 800 kVA transformer and "
      "no EVs, it reproduces the published IEEE solution at all 2,721 phase-node voltages. The "
      "worst difference is 0.0002%, against an allowed 0.5% (validation check V1).")

    # ---- 4
    h1("4. One evening, step by step")
    p("Every five minutes the same loop runs. Figure 2 shows it, and the numbers below match "
      "the numbers in the figure.")
    figure(figs["loop"], "Figure 2. One 5-minute control step. Steps 2 to 6 work from what "
           "the twin believes; step 7 is judged against what is really happening.")
    numbered(["<font name='Cal-B'>The street is at its true state:</font> house demand, solar "
              "output, the battery's response and whatever the cars are drawing.",
              "<font name='Cal-B'>Meters report every 30 seconds.</font> Each reading carries "
              "the value at its own moment.",
              "<font name='Cal-B'>Each reading goes through the comms link,</font> which can "
              "delay it, drop it or freeze it (Section 6).",
              "<font name='Cal-B'>The twin builds its picture of the street</font> from "
              "whatever has arrived. That picture may be minutes old. The twin also scores how "
              "much it trusts the picture.",
              "<font name='Cal-B'>The twin works out the safe limit (the envelope)</font> from "
              "that picture: the highest charging power per car that keeps every network "
              "limit satisfied, with a safety margin that grows with the age of the data "
              "(Section 5).",
              "<font name='Cal-B'>The controller (A, B or C)</font> turns the envelope and the "
              "trust score into the limit it actually sends (Section 7).",
              "<font name='Cal-B'>The limit goes back down the comms link,</font> which can "
              "also delay or lose it. The chargers use the newest instructions they hold, or "
              "drop to a safe 1.4 kW if those are too old. What the chargers actually draw is "
              "then applied to the true street and checked against the five network "
              "limits."])
    p("The gap between step 5 and the check in step 7 is what the study is about. The limit is "
      "worked out from what the twin believes, but it is judged against what is really "
      "happening. When the data is stale the two can differ, and a limit that looked safe can "
      "break the network. Being more careful costs charging energy. The question is where "
      "that trade-off tips.")

    # ---- 5
    h1("5. The network limits and the safe limit")
    h2("5.1 The five limits")
    table([["Limit", "Basis", "Value", "What it means"],
           ["Voltage", "AS 60038", "216.2 to 253 V", "every house's voltage must stay inside "
            "the legal band"],
           ["Cable current", "cable ratings (provisional, Section 14)", "100% of rating",
            "no cable may carry more than its rating; the main cable at the start of the "
            "street is rated 175 A per phase"],
           ["Transformer loading", "nameplate", "100% of 150 kVA", "the transformer must not "
            "be overloaded"],
           ["Transformer hot spot", "IEC 60076-7 thermal model", "98 °C", "the hottest point "
            "inside the transformer; it heats up slowly, so a brief overload is tolerated but "
            "a sustained one is not"],
           ["Voltage unbalance", "voltage unbalance factor (VUF)", "2%", "the three phases "
            "must not drift too far apart; single-phase chargers push them apart"]],
          [0.18, 0.24, 0.16, 0.42])
    p("A run counts only if every limit holds at every one of the 72 steps. Break one limit "
      "once and the run is marked unsafe. With realistic demand, the limits that actually "
      "bite are <font name='Cal-B'>cable current and voltage unbalance</font>; the "
      "transformer rarely limits anything.")
    h2("5.2 How the safe limit is found")
    p("The envelope is one number for each step: the highest power per charger such that, if "
      "every plugged-in car drew it, the street would stay inside all five limits. All "
      "charging cars get the same limit (equal share). A car that is nearly full only draws "
      "what it still needs, and the calculation uses exactly those draws, so the plan matches "
      "what the network will really see.")
    p("It is found by <font name='Cal-B'>bisection</font>, the same idea as guessing a number "
      "with higher-or-lower answers. Try 7.2 kW; if that breaks a limit, try halfway down; "
      "keep halving the gap, always on the 0.1 kW steps a charger can actually use. About "
      "seven power flows give the exact answer on that grid. A check (V3) compares it with "
      "trying every step one by one; the two agree to within 0.1 kW at every test point.")
    h2("5.3 The safety margin")
    p("The envelope is worked out from the twin's picture, which may be old. While readings "
      "travel and wait, house demand keeps moving, so the limits used for planning are "
      "tightened by a margin that grows with the age of the data. The margins were measured "
      "from the feeder's own profiles: each one covers 95% of how far demand drifts over that "
      "time.")
    table([["Age of the data (min)", "0", "1", "2", "3", "5", "7", "10", "15"],
           ["Margin on current, voltage, transformer", "1.0%", "6.8%", "8.5%", "10.7%",
            "12.7%", "14.5%", "16.0%", "17.1%"],
           ["Margin on unbalance (percentage points)", "0.05", "0.33", "0.42", "0.46",
            "0.53", "0.55", "0.61", "0.75"]],
          [0.34] + [0.0825] * 8, size=9)
    p("Unbalance has its own, much larger margin, because one house switching a few kW on one "
      "phase moves it a lot. Because the margins cover 95% of the drift, they leave a small "
      "tail they do not cover. Most of the remaining violations in the results come from that "
      "tail.")
    h2("5.4 Do no harm")
    p("At 16:00 the solar panels are still exporting, and some house voltages can already be "
      "above 253 V with no charging at all. Refusing to charge then would be backwards, because "
      "charging pulls the voltage down. So when a limit is already broken before any charging, "
      "charging is allowed as long as it does not make that breach worse.")

    # ---- 6
    h1("6. Communications and trust")
    h2("6.1 What the comms link does to messages")
    bullets(["<font name='Cal-B'>Latency (delay):</font> each message is delayed by a random "
             "amount around the set value. Tested at 0, 5, 30, 60, 120, 300 and 600 seconds.",
             "<font name='Cal-B'>Packet loss:</font> each message is lost independently with "
             "the set probability. Tested at 0, 1, 5, 10, 20 and 40%.",
             "<font name='Cal-B'>Both directions:</font> readings going up and limits coming "
             "down are both degraded, independently of each other.",
             "<font name='Cal-B'>Frozen data:</font> readings stop changing for 2, 5 or 8 "
             "minutes but keep fresh timestamps, as when a meter or gateway hangs. To any "
             "check based on age, this looks perfectly healthy."])
    p("A late message is not the same as a lost one. The twin only counts a reading as lost "
      "once it is older than the delays it actually sees. An early version got this wrong and "
      "made the trust score far too low.")
    h2("6.2 The trust score")
    p("The trust score is a number between 0 and 1 for how much the twin believes its picture. "
      "It multiplies three simple terms, so it is easy to explain and check:")
    table([["Term", "Formula", "What it captures"],
           ["Age", "1 − (age of the newest reading ÷ 15 minutes)", "fresh data scores 1; "
            "15-minute-old data scores 0"],
           ["Loss", "1 − measured loss rate", "a link that loses messages is less "
            "trustworthy"],
           ["Plausibility", "1, or 0.5 if total demand jumped more than five-fold",
            "a crude sanity check on the readings"]],
          [0.16, 0.44, 0.40])
    callout("<font name='Cal-B'>Example.</font> The newest reading is 3 minutes old and 10% of "
            "messages are being lost. Age term 1 − 3/15 = 0.8, loss term 0.9, plausible, so "
            "trust = 0.8 × 0.9 = 0.72.", face="#F6F6F6", edge="#9A9A9A")
    h2("6.3 When instructions stop arriving")
    p("The chargers act on the newest instructions they hold. If those are older than 15 "
      "minutes, or nothing has arrived, they charge at <font name='Cal-B'>1.4 kW</font>. That "
      "fallback matches the 1.5 kW export fallback SA Power Networks uses, and is about the "
      "lowest setting a typical AC charger accepts (6 A single-phase). A car that plugged in "
      "after the instructions were issued only gets 1.4 kW until new instructions arrive, "
      "because those instructions never planned for it. Without that rule, one lost message "
      "once pushed a cable to 106%.")

    # ---- 7
    h1("7. The three controllers")
    table([["Controller", "Rule", "The idea"],
           ["A, fixed limit", "the same limit all evening", "the safe baseline; it ignores the "
            "data completely"],
           ["B, trust-weighted", "limit = 1.4 + trust × (envelope − 1.4)", "lean on the "
            "envelope as far as the data deserves, sliding towards the 1.4 kW floor as trust "
            "falls"],
           ["C, binary fallback", "full envelope while the data is under 15 minutes old, then "
            "the fixed limit", "all or nothing, as deployed systems work today"]],
          [0.2, 0.38, 0.42])
    p("Taking the example from Section 6 (trust 0.72), with an envelope of 5.0 kW and a fixed "
      "limit of 2.5 kW:")
    table([["Controller", "Limit sent", "Why"],
           ["A", "2.5 kW", "always the fixed limit"],
           ["B", "3.9 kW", "1.4 + 0.72 × (5.0 − 1.4) = 3.99, rounded down to the 0.1 kW "
            "grid"],
           ["C", "5.0 kW", "the data is under 15 minutes old, so the full envelope"]],
          [0.2, 0.2, 0.6])
    p("<font name='Cal-B'>How the fixed limit A is set.</font> Using 7.2 kW as the fixed limit "
      "broke the network on 44 of 72 steps, so that comparison would mean nothing. Instead, "
      "for each simulated evening, A is set to the highest fixed value that would have stayed "
      "safe all evening, found by trial with perfect information. A real operator could not "
      "know that number in advance, so A is if anything a generous baseline.")
    p("<font name='Cal-B'>How results are scored.</font> For B and C, the energy the cars got is "
      "compared with what they got under A on the same evening, as a percentage. A run that "
      "broke any limit does not count; the results show how many evenings stayed safe.")

    # ---- 8
    h1("8. EV demand: who charges, when, and how much")
    h2("8.1 Why the demand was changed")
    p("The first version used placeholder sessions: every car got home around 18:30 wanting 8 "
      "to 26 kWh. Checked against real data, that was about three times more charging energy "
      "per evening than the evidence supports. With it the transformer was overloaded on 91% "
      "of evenings, which is not a realistic street.")
    h2("8.2 What it is now")
    p("<font name='Cal-B'>When cars get home and how far they drove</font> comes from VISTA, the "
      "Victorian travel survey (2024-25): each driver's last arrival home and that day's "
      "driving, at 0.17 kWh per km with 90% charger efficiency. That is 1,765 real weekday "
      "person-days from Greater Melbourne, weighted to represent the population.")
    p("<font name='Cal-B'>How often people plug in</font> comes from metered trial data. In the "
      "Jemena-led Melbourne trial (ARENA, 2023), EVs charged on about a third of days (34%), "
      "at about 18 kWh per charging day. So in the <font name='Cal-B'>main case</font> each car "
      "plugs in on a given evening with probability 0.34, wanting all the energy driven since "
      "it last charged. The <font name='Cal-B'>stress case</font> is the design day Australian "
      "distributors plan for (the University of Melbourne method for the ENA): 70% of cars "
      "plug in, each wanting two days of driving. You chose these two on 2 October.")
    table([["Demand", "Cars charging (average)", "Energy wanted (kWh)",
            "Uncontrolled peak (median)", "Evenings over the transformer"],
           ["Placeholder (old)", "22", "374", "159 kW", "91%"],
           ["Main case", "5.9", "120", "68 kW", "0%"],
           ["Stress case", "12.0", "171", "84 kW", "0%"]],
          [0.24, 0.17, 0.17, 0.2, 0.22])
    p("The transformer stays at 150 kVA (about 142 kW). Shrinking it again just to create "
      "congestion would not be defensible. With realistic demand, the limits that matter are "
      "the cables and voltage unbalance.")
    p("Each of the 13 simulated evenings (called seeds) is a fresh random draw: which cars plug "
      "in, when, how much they want, and the random delays and losses on the comms link. In "
      "the main case, 6 of the 13 evenings never get congested at all.")

    # ---- 9
    h1("9. The held-limit problem and the fix")
    p("This was the most important fault found during the work, so it gets its own section.")
    h2("9.1 The problem")
    p("The twin sends new instructions every five minutes. If a message is lost or late, the "
      "chargers keep using the last one they got. The old code gave each limit a safety margin "
      "for the age the data had when the limit was calculated. But a held limit might be used "
      "five or ten minutes later, on data that much older, so its margin was too small for how "
      "it was actually used. In a replay of the comms link, chargers were running on a held "
      "limit on 33% of steps at 120 s of delay even with no packet loss, and on 79% at 300 s.")
    figure(figs["schedule"], "Figure 3. Two lost messages, before and after the fix. Before, "
           "the same limit is reused on older and older data; after, each interval has its own "
           "entry planned for the data age it will really have.")
    h2("9.2 The fix: setpoint schedules")
    p("The fix was chosen by a design panel that compared three independent designs. Each "
      "message now carries a short <font name='Cal-B'>schedule of three limits</font>: one for "
      "the next 5 minutes, one for 5 to 10 minutes and one for 10 to 15 minutes. Each later "
      "entry is planned with the margin for the older data it will be used on. The chargers use "
      "the entry for the current interval, and drop to 1.4 kW when the schedule runs out after "
      "15 minutes, which is exactly when they would have fallen back anyway.")
    p("This is how IEEE 2030.5 and CSIP-AUS controls work: each control has a time window, and "
      "the device falls back to a default when the window ends. Nothing else changed. The "
      "controllers, the trust score and the comms link's random draws are identical, so 10% "
      "packet loss means exactly what it meant before.")
    h2("9.3 How the fix was checked")
    bullets(["18 runs recorded before the change were reproduced exactly, step by step, with the "
             "schedule switched off. With it switched on, the 12 runs that never had a held "
             "message were identical too.",
             "Ten dedicated tests passed, including one showing that entries computed when "
             "needed match those a real twin would compute in advance.",
             "Four independent reviewers checked the code. They found no faults in the control "
             "logic; the four bookkeeping issues they did find were fixed.",
             "The MQTT path still gives exactly the same answer."])
    h2("9.4 What it achieved")
    p("The comparison below uses the same evenings with the schedule off and on. The pass marks "
      "were set by the design panel before anything ran. The third column uses the old, heavy "
      "placeholder demand, because that is where held limits caused the most trouble.")
    table([["", "Main case", "Stress case", "Heavy demand"],
           ["B: violating steps on held limits", "39 → 8", "67 → 13", "139 → 28"],
           ["C: violating steps on held limits", "199 → 86", "315 → 117", "826 → 226"],
           ["At least 80% fewer (after setting aside late-arriving and finished cars), B",
            "77%, fail", "82%, pass", "78%, fail"],
           ["The same, C", "56%, fail", "65%, fail", "71%, fail"],
           ["B as safe at 0 s delay as at 5 s", "pass", "one evening short", "pass"],
           ["B's energy cost on good links under 5%", "pass", "pass", "pass"]],
          [0.43, 0.19, 0.19, 0.19])
    p("Violations on held limits fell by about 80% for B and by more than half for C, and B "
      "lost less than 5% of its energy on good links. Under the heavy demand, cable overloads "
      "fell from 55 to 2 for B and from 638 to 140 for C. The fix did not meet every target the "
      "panel set: a held limit is still a little riskier per step than a fresh one, mostly "
      "through voltage unbalance on C, which charges right up to the edge with nothing held "
      "back. That is reported as it is; the fix was not tuned until it passed.")
    p("Two variations were also tried. Making late-arriving cars wait at 0 kW instead of 1.4 kW "
      "changed almost nothing. Scoring trust at the moment each entry is used, rather than when "
      "it was planned, cost B 15% of its energy to remove just two violating steps. Neither was "
      "worth adopting.")

    # ---- 10
    h1("10. The experiments that were run")
    p("Each run is one simulated evening (72 steps), taking 5 to 30 seconds of computing. The "
      "final runs, about 9,000 evenings in all, took roughly eight hours on the laptop in "
      "parallel.")
    table([["Experiment", "What changes", "Runs"],
           ["S1, main case", "7 delays × 6 loss levels, controllers A, B and C, 13 evenings, "
            "main-case demand", "1,105"],
           ["S1, stress case", "the same grid on the design-day demand", "1,105"],
           ["S2, frozen data", "frozen readings of 0, 2, 5 or 8 minutes at three S1 points "
            "(good, moderate and poor links)", "351"],
           ["S3, battery off", "the battery removed, on a 3 × 3 part of the S1 grid", "130"],
           ["Fix check", "S1 again with the schedule switched off for the main and stress "
            "cases, and the old heavy demand run both with and without it", "4 × 1,105"],
           ["Sensitivity", "late cars wait at 0 kW; trust scored at the time of use", "2 × 156"],
           ["Timeout", "timeouts of 5, 15, 30 and 60 minutes on the 7 congested evenings", "672"]],
          [0.2, 0.62, 0.18])
    p("S4, the warning day (how long the battery keeps critical loads going in an outage), is "
      "not built. It needs decisions only you and Gia can make (Section 15).")

    # ---- 11
    h1("11. The results")
    h2("11.1 How to read the result maps")
    p("Figures 4 and 5 are grids, one for B and one for C. Each row is a packet-loss level and "
      "each column a delay. The number in a cell is the average advantage over the fixed limit, "
      "in percent, over the evenings that stayed safe. Blue means ahead of the fixed limit, red "
      "means behind, and grey is about even. Where some evenings broke a limit, the cell also "
      "says how many stayed safe (for example 8/13 safe). Hatched cells broke a limit in more "
      "than half the evenings. The black line is break-even: on the low-delay side of it live "
      "control wins, beyond it the fixed limit wins.")
    h2("11.2 Main case", need=fig_cm(figs["main"]) + 1)
    figure(figs["main"], "Figure 4. Main case (a third of EVs plug in each evening). Advantage "
           "over the fixed limit, averaged over the evenings that stayed safe; 13 evenings per "
           "cell. The black line is break-even.")
    bullets(["<font name='Cal-B'>B</font> beat the fixed limit by 15% with no delay or loss, "
             "and by 5 to 9% from 5 to 60 s at low loss. It broke even between 60 and 120 s at "
             "low loss and at about 5 s once loss reached 20%, and it was behind everywhere at "
             "40% loss. It broke a limit in 9 of 546 runs, all voltage unbalance.",
             "<font name='Cal-B'>C</font> was 10 to 15% ahead up to 60 s and broke even around "
             "300 s, but it broke a limit in 82 of 546 runs. From 300 s it was unsafe in up to "
             "7 of 13 evenings per cell.",
             "<font name='Cal-B'>A</font> never broke a limit, by construction. Its limit came "
             "out at 2.5 to 6.4 kW on the seven congested evenings and at the full 7.2 kW on "
             "the other six, where every controller delivers the same energy. Those six pull "
             "every average towards zero."])
    h2("11.3 Stress case", need=fig_cm(figs["stress"]) + 1)
    figure(figs["stress"], "Figure 5. Stress case (the design day, 70% of EVs plug in). "
           "Advantage over the fixed limit, averaged over the evenings that stayed safe; 13 "
           "evenings per cell.")
    bullets(["Twelve of 13 evenings were congested, most with fixed limits of 2.9 to 4.7 kW, so "
             "live control had much more to win.",
             "B was 21% ahead with no delay, 10 to 17% ahead from 5 to 60 s at up to 10% loss, "
             "still ahead at 300 s with 5% loss or less, and behind at 600 s and at 40% loss. "
             "It broke a limit in 20 of 546 runs.",
             "C broke a limit in 140 of 546 runs. Beyond 60 s its cells typically had only 7 or "
             "8 of 13 evenings safe."])
    callout("<font name='Cal-B'>The central comparison.</font> On both demand cases, "
            "trust-weighting gives up a little energy to binary fallback on good links, and in "
            "return breaks network limits seven to nine times less often.")
    h2("11.4 Frozen data", need=fig_cm(figs["stale"]) + 1)
    figure(figs["stale"], "Figure 6. Frozen readings (fresh timestamps, values stuck) at three "
           "link qualities, main case. Bar labels: evenings that stayed safe, out of 13.")
    bullets(["A 5- or 8-minute freeze left B safe in only 7 or 8 of 13 evenings on a good link "
             "(5 s, 1% loss), and 10 of 13 at 60 s and 10% loss. C fell to 6 or 7 of 13.",
             "A 2-minute freeze was mostly tolerated (B safe in 12 of 13).",
             "On a poor link (300 s, 20% loss) the freeze made no difference to B, because its "
             "trust was already low.",
             "The trust score cannot see frozen data that carries fresh timestamps. This bears "
             "out the plan's hypothesis that stale data does more damage than packet loss."])
    h2("11.5 The battery", need=fig_cm(figs["battery"]) + 1)
    figure(figs["battery"], "Figure 7. B's advantage over its own network's fixed limit, with "
           "the battery (blue) and without it (orange), main case.")
    p("Without the battery, the safe fixed limit drops on 3 of 13 evenings (for example from "
      "7.2 to 5.9 kW), and B's advantage over that lower fixed limit grows by 3 to 4 points in "
      "every cell. The battery's automatic voltage response mostly helps the fixed limit, so "
      "with the battery there is less left for live control to win.")
    h2("11.6 The timeout")
    p("The timeout is how long the system keeps trusting old information before giving up and "
      "falling back to 1.4 kW. The study uses 15 minutes; this test tried 5, 30 and 60 minutes "
      "as well, changing it at both ends together.")
    figure(figs["timeout"], "Figure 8. The delay at which B stops beating the fixed limit, for "
           "four timeouts (median of the 7 congested main-case evenings).", width=0.91)
    table([["Packet loss", "5 min", "15 min (used)", "30 min", "60 min"],
           ["10%", "20 s", "90 s", "122 s", "149 s"],
           ["20%", "never", "30 s", "44 s", "54 s"],
           ["30% and 40%", "never", "never", "never", "never"],
           ["Runs that broke a limit", "0 of 168", "1 of 168", "5 of 168", "9 of 168"]],
          [0.28, 0.18, 0.18, 0.18, 0.18])
    p("A longer timeout lets B stay ahead at longer delays, but by trusting older data, so it "
      "breaks more limits. A very short timeout throws away good information: at 20% loss with a "
      "5-minute timeout, B never beats the fixed limit. The timeout matters less than it did in "
      "the earlier model, where one setting kept B ahead past 10 minutes of delay. The report "
      "has to state the crossover together with the 15-minute timeout.")
    h2("11.7 Putting it together")
    p("Live control is worth it while the data is fresh: within about a minute of delay and "
      "under 10 to 20% packet loss on a normal evening, and within a few minutes on a congested "
      "design day. Inside that region, trust-weighting gets most of the benefit of using the "
      "envelope in full while breaking limits far less often than the all-or-nothing approach "
      "used today. Outside it, a well-chosen fixed limit does as well. The biggest single "
      "danger is data that stops updating without anyone noticing.")

    # ---- 12
    h1("12. How we know the model is right")
    p("The research plan lists nine validation checks (V1 to V9). Each one tests a piece "
      "against an answer that does not come from the simulator itself.")
    table([["Check", "What it tests", "Result"],
           ["V1", "the network model matches the published feeder", "pass: worst 0.0002% "
            "(limit 0.5%)"],
           ["V2", "the battery follows AS/NZS 4777.2", "pass against the stand-in"],
           ["V3", "the envelope search finds the true envelope", "pass: within the 0.1 kW "
            "tolerance of a one-by-one search"],
           ["V4", "envelopes are safe and as large as possible", "pass: no violations, every "
            "envelope maximal"],
           ["V5", "the comms link delivers the delay and loss asked for", "pass against the "
            "stand-in: within 3.1% and 0.71 points over 20,000 messages"],
           ["V6", "trust behaves sensibly at the extremes", "pass against the stand-in: 1 on "
            "clean data, 0 after 15 minutes of blackout"],
           ["V7", "the battery conserves energy", "pass against the stand-in: balances to "
            "0.0000%"],
           ["V8", "the whole chain gives a known answer", "pass: a hand calculation and the "
            "simulation agree on the first cable overload, 16:40"],
           ["V9", "results regenerate a week later", "pass: all three runs identical eight "
            "days after recording (checked 11 October)"],
           ["MQTT", "the hardware path gives the same answer", "identical at three comms "
            "settings"],
           ["SINCAL", "a second engine agrees", "a 47-node cut agrees with OpenDSS within 0.1%; "
            "the full street needs the uni computers"]],
          [0.12, 0.44, 0.44])
    p("V2, V5, V6 and V7 test the stand-ins for now. They double as the hand-over tests: each "
      "teammate's real code has to pass the same test before it replaces the stand-in.")
    p("<font name='Cal-B'>V8 in plain words.</font> Every house gets an EV charging at full "
      "power with no limit, and simple arithmetic (power divided by voltage on each phase) "
      "predicts when the main cable will first overload: 16:40, at 112% of its rating. The full "
      "simulation also overloads that cable at 16:40, at 113%. Voltage unbalance breaks "
      "earlier, at 16:25, but the hand calculation never tried to predict unbalance, so V8 "
      "judges only the cable (amendment 28).")

    # ---- 13
    h1("13. Problems found and fixed along the way")
    p("All 28 design changes and faults are written up in "
      "<font name='Cal-I'>notes/plan_amendments.md</font>, each with its reason. These are the "
      "ones that changed the results most.")
    table([["Problem", "What it did", "Fix (amendment)"],
           ["A 7.2 kW fixed limit broke 44 of 72 steps", "the research question could not be "
            "answered", "calibrate A to the best safe fixed limit for each evening (1)"],
           ["Supply at 1.05 pu left 0.2 V of headroom", "the first few cars tripped overvoltage "
            "whatever the controller did", "1.00 pu, as a distributor would tap down (5)"],
           ["No safety margin", "violations were worst when the data was best", "a margin that "
            "grows with the data's age (6, 11, 13)"],
           ["Late messages counted as lost", "trust far too low, results biased", "count a "
            "message lost only once it is older than the observed delays (7)"],
           ["Envelope planned with cars that were not charging", "unbalance violations even "
            "with perfect data", "plan with exactly the draws the chargers will produce (10)"],
           ["Unbalance margin a third of its real drift", "most fresh-data runs broke unbalance",
            "a separate, larger unbalance margin (21)"],
           ["A held limit applied to newly arrived cars", "one lost message pushed a cable to "
            "106%", "a limit covers only the cars connected when it was issued (22)"],
           ["Random seeds differed between processes", "results could not be reproduced",
            "fixed seeding (23)"],
           ["Held limits planned for fresher data than they had", "most live-control violations "
            "at long delays", "setpoint schedules (24, 25)"],
           ["SINCAL importer: wrong phase codes, winding type, zero-sequence switch",
            "SINCAL saw 6 kW of a 57 kW street, silently", "corrected database codes (26)"],
           ["Placeholder sessions three times too heavy", "the street looked far more congested "
            "than it is", "VISTA plus metered plug-in rates (27)"],
           ["V8 compared a cable prediction against any violation", "a correct prediction was "
            "marked as a failure", "V8 judges the limit it predicts (28)"]],
          [0.36, 0.32, 0.32], size=9.1)

    # ---- 14
    h1("14. What the results depend on")
    bullets(["<font name='Cal-B'>Cable ratings are provisional.</font> The feeder package has no "
             "current ratings, so they were estimated from the conductor sizes. They need "
             "checking against AS/NZS 3008.1.1. Cable current is one of the two limits that "
             "bite, so these numbers matter.",
             "<font name='Cal-B'>Three teammates' parts are stand-ins.</font>",
             "<font name='Cal-B'>The 15-minute timeout</font> shapes the crossover (Section "
             "11.6).",
             "<font name='Cal-B'>Margins at the 95th percentile</font> leave a small tail of "
             "risk by design.",
             "<font name='Cal-B'>The demand model.</font> Each day's driving is drawn afresh, so "
             "a heavy driver is not heavy every day, and every charging day is treated as an "
             "evening plug-in when the car gets home, which is on the cautious side.",
             "<font name='Cal-B'>Thirteen evenings per setting.</font> In the main case only "
             "seven of them are congested.",
             "<font name='Cal-B'>A steady-state model.</font> Each 5-minute step is one power "
             "flow; anything faster than that is not modelled."])

    # ---- 15
    h1("15. What is left, and who does it")
    table([["Item", "Who", "Notes"],
           ["Real comms and trust code", "Hoang", "pass V5, V6 and the MQTT test; downlink and "
            "trust rules R6 and R7 in INTERFACES.md"],
           ["Real charge-point controller", "Lomitha", "pass the MQTT test; schedule rules R1 "
            "to R5; message version 2"],
           ["Real battery model", "Gia", "pass V2 and V7"],
           ["S4, the warning day", "Gia and Munir", "decide when the warning arrives, the "
            "battery reserve, which loads are critical, when the outage happens and how "
            "survival hours are measured"],
           ["Cable ratings", "Munir", "check config/cable_ratings.json against AS/NZS 3008.1.1"],
           ["SINCAL full check", "Munir", "on the uni computers, using avd_crosscheck.zip"],
           ["Pi integration", "the team", "12 October, following Putting_It_Together.pdf; "
            "the commands are in team/README.md"],
           ["Report and slides", "the team", "agree amendments 1 to 28 with the convener; "
            "update the controller labels, the calibrated fixed limit, the demand scenario "
            "and the results"]],
          [0.26, 0.16, 0.58])
    p("Once the real parts pass their tests, the experiments are rerun with them using "
      "<font name='Cal-I'>tools/run_parallel.py</font> and <font name='Cal-I'>--team "
      "all</font>, and those become the project's final results.")

    # ---- 16
    h1("16. Where everything is")
    table([["Path (inside the project folder)", "What is in it"],
           ["notes/AUDIT.md", "every commitment in the research plan, checked against the build, "
            "with the final results"],
           ["notes/plan_amendments.md", "the 28 design changes and faults, with reasons"],
           ["docs/INTERFACES.md", "what each teammate has to build"],
           ["config/study.json", "every setting of the study in one place"],
           ["src/", "the model: sweep.py (one evening), envelope.py, network_state.py, "
            "controllers.py, telemetry.py, edge.py, battery.py, ev_sessions.py, stages.py"],
           ["tests/", "validation checks V1 to V9, the MQTT test, the schedule tests"],
           ["tools/", "run_parallel.py (the experiment queue), compare_paired.py, the SINCAL "
            "tools"],
           ["results/stages/", "main-case results and figures"],
           ["results/stress_s2/", "stress-case results and figure"],
           ["results/paired_main/, paired_stress/, mechanism_standin/, sensitivity/",
            "the before-and-after checks of the fix"],
           ["results/timeout_sensitivity/", "the timeout test"],
           ["results/superseded/", "old results, kept for the record but not to be quoted"],
           ["avd_crosscheck.zip", "the SINCAL package for the uni computers"]],
          [0.42, 0.58])

    # ---- 17
    h1("17. Glossary")
    table([["Term", "Meaning"],
           ["Dynamic operating envelope (envelope)", "the safe charging limit worked out from "
            "the current state of the network and updated regularly, here every 5 minutes"],
           ["Fixed (static) limit", "one safe limit set in advance and never changed"],
           ["Setpoint", "the limit sent to the chargers"],
           ["Schedule", "a setpoint message carrying limits for the next three 5-minute "
            "intervals"],
           ["Fallback", "the 1.4 kW the chargers use when their instructions are too old"],
           ["Latency", "how long a message takes to arrive"],
           ["Packet loss", "the share of messages that never arrive"],
           ["Frozen (stale) data", "readings that stop updating while still looking fresh"],
           ["Trust score", "a number from 0 to 1 for how much the twin believes its data"],
           ["Seed", "one simulated evening: a random draw of who charges and what the comms "
            "do"],
           ["Break-even (crossover)", "the delay or loss at which live control stops beating "
            "the fixed limit"],
           ["Bisection", "finding a value by repeatedly halving the range it could be in"],
           ["Voltage unbalance (VUF)", "how unequal the three phase voltages are, in percent"],
           ["Hot spot", "the hottest point inside the transformer's windings"],
           ["pu (per unit)", "a value as a fraction of its nominal value; 1.00 pu is exactly "
            "nominal"],
           ["Bus, phase, feeder", "a connection point; one of the three supply conductors; "
            "the whole low-voltage street network"],
           ["OpenDSS, SINCAL", "power-flow programs: OpenDSS runs the study, SINCAL "
            "cross-checks it"],
           ["MQTT", "the lightweight messaging system the Raspberry Pi uses"],
           ["IEEE 2030.5, CSIP-AUS", "the standard and its Australian profile for sending "
            "limits to devices like chargers and inverters"],
           ["VISTA", "the Victorian Integrated Survey of Travel and Activity"],
           ["Stand-in", "working code written in place of a teammate's part until theirs is "
            "ready"]],
          [0.32, 0.68])


def main():
    os.makedirs(HERE, exist_ok=True)
    figs = {"nodes": os.path.join(HERE, "fig1_nodes.png"),
            "loop": os.path.join(HERE, "fig2_loop.png"),
            "schedule": os.path.join(HERE, "fig3_schedule.png")}
    figs.update({"main": os.path.join(HERE, "fig4_main.png"),
                 "stress": os.path.join(HERE, "fig5_stress.png"),
                 "stale": os.path.join(HERE, "fig6_stale.png"),
                 "battery": os.path.join(HERE, "fig7_battery.png"),
                 "timeout": os.path.join(HERE, "fig8_timeout.png")})
    fig_nodes(figs["nodes"])
    fig_loop(figs["loop"])
    fig_schedule(figs["schedule"])
    chart_heatmaps("stages", figs["main"])
    chart_heatmaps("stress_s2", figs["stress"])
    chart_stale(figs["stale"])
    chart_battery(figs["battery"])
    chart_timeout(figs["timeout"])
    build_story(figs)
    doc = GuideDoc(OUT)
    doc.multiBuild(story)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
