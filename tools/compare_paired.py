"""Score the paired S1 (schedule off vs on) against the criteria fixed before it ran.

    py tools/compare_paired.py --on results/stages --off results/paired_main/off \\
        --out results/paired_main/comparison.md --title "main case (s1)"

Reads S1_seed*.json from the two folders, pairs runs by (controller,
latency, loss, seed), and reports the pre-registered criteria from the design (amendment 25):

    hard        fallback counts identical in every pair; hold-free pairs identical
    per cell    share of violating steps on entries k >= 1 no larger than the share of steps
                on k >= 1
    overall     violating steps on k >= 1 fall by at least 80%, after setting aside those
                with a car the entry did not cover drawing power, a planned car that had
                finished, or a lag past the end of the margin curve (RunResult counters)
    0 s         B's safe-seed count at 0 s at least its count at 5 s, at every loss level
    cost        B's paired energy change at 0-60 s with <= 10% loss flagged if worse than -5%

plus paired energy differences over ALL runs (not safe runs only), safe-seed counts, and
violations by entry and by type.
"""
import argparse
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAT = [0, 5, 30, 60, 120, 300, 600]
LOSS = [0.0, 0.01, 0.05, 0.10, 0.20, 0.40]


def load(d):
    runs, scen = {}, set()
    for p in sorted(glob.glob(os.path.join(d, "S1_seed*.json"))):
        f = json.load(open(p, encoding="utf-8"))
        scen.add((f.get("sessions"), f.get("plugin_model")))
        for r in f["runs"]:
            runs[(r["controller"], r["latency_s"], r["loss"], r["seed"])] = r
    if len(scen) > 1:
        raise SystemExit("%s mixes demand scenarios: %s" % (d, sorted(scen)))
    return runs, scen.pop() if scen else None


def k1(r, field="entry_counts"):
    """Steps (or violating steps) on entries k >= 1."""
    if field == "entry_counts":
        return sum(r["entry_counts"][1:-1])
    return sum(v for k, v in r["viol_by_entry"].items() if k not in ("0", "D"))


def main(on_dir, off_dir, out_path, title):
    (off, s_off), (on, s_on) = load(off_dir), load(on_dir)
    if s_off != s_on:
        raise SystemExit("the two arms ran different demand: off %s, on %s" % (s_off, s_on))
    keys = sorted(set(off) & set(on))
    out = []

    def say(s=""):
        print(s)
        out.append(s)

    seeds = sorted({k[3] for k in keys})
    say("# Paired S1, %s: single held setpoint (off) vs setpoint schedule (on)" % title)
    say("")
    say("%d paired runs, seeds %s. Only in one arm: %d off, %d on."
        % (len(keys), ",".join(map(str, seeds)), len(set(off) - set(on)), len(set(on) - set(off))))

    # ---- hard criteria
    fb_bad = [k for k in keys if off[k]["fallbacks"] != on[k]["fallbacks"]
              or off[k]["entry_counts"] != on[k]["entry_counts"]]
    holdfree = [k for k in keys if k1(off[k]) == 0]
    hf_bad = [k for k in holdfree if (off[k]["energy_kwh"], off[k]["violations"])
              != (on[k]["energy_kwh"], on[k]["violations"])]
    say("")
    say("## Hard criteria")
    say("- fallback and entry counts identical in every pair: **%s** (%d differ)"
        % ("PASS" if not fb_bad else "FAIL", len(fb_bad)))
    say("- hold-free pairs identical (energy and violations): **%s** (%d of %d differ)"
        % ("PASS" if not hf_bad else "FAIL", len(hf_bad), len(holdfree)))

    # ---- held-step violations
    say("")
    say("## Violations on held entries (k >= 1)")
    for c in "BC":
        ks = [k for k in keys if k[0] == c]
        v_off = sum(k1(off[k], "viol") for k in ks)
        v_on = sum(k1(on[k], "viol") for k in ks)
        a_off = sum(off[k]["viol_attributed"] for k in ks)
        a_on = sum(on[k]["viol_attributed"] for k in ks)
        un_off = sum(off[k]["viol_unattributed"] for k in ks)
        un_on = sum(on[k]["viol_unattributed"] for k in ks)
        drop = 100.0 * (un_off - un_on) / un_off if un_off else float("nan")
        parts = {f: (sum(off[k][f] for k in ks), sum(on[k][f] for k in ks))
                 for f in ("viol_with_new_car", "viol_with_finish", "viol_lag_over_15")}
        say("- %s: violating held steps %d -> %d. Attributed %d -> %d (uncovered car drawing "
            "%d -> %d, planned car finished %d -> %d, past the margin curve %d -> %d). The rest, "
            "which the margin should cover: %d -> %d (%s)"
            % (c, v_off, v_on, a_off, a_on, *parts["viol_with_new_car"],
               *parts["viol_with_finish"], *parts["viol_lag_over_15"], un_off, un_on,
               "%.0f%% fewer" % drop if un_off else "none before"))
        say("  criterion (the rest fall by at least 80%%): **%s**"
            % ("PASS" if (not un_off or drop >= 80) else "FAIL"))
    cell_bad = []
    for c in "BC":
        for lat in LAT:
            for loss in LOSS:
                ks = [k for k in keys if k[:3] == (c, lat, loss)]
                steps = sum(sum(on[k]["entry_counts"]) for k in ks)
                viol = sum(on[k]["violations"] for k in ks)
                if not steps or not viol:
                    continue
                share_steps = sum(k1(on[k]) for k in ks) / steps
                share_viol = sum(k1(on[k], "viol") for k in ks) / viol
                if share_viol > share_steps + 1e-9:
                    cell_bad.append("%s %ds %g%%: %.0f%% of violations on held entries vs "
                                    "%.0f%% of steps" % (c, lat, loss * 100, 100 * share_viol,
                                                         100 * share_steps))
    say("- per cell, violations on held entries no more common than held entries: **%s**%s"
        % ("PASS" if not cell_bad else "FAIL (%d cells)" % len(cell_bad),
           "".join("\n  - " + x for x in cell_bad[:12])))

    # ---- safe-seed counts
    say("")
    say("## Seeds with no violation (of %d), off -> on" % len(seeds))
    for c in "BC":
        say("")
        say("controller %s" % c)
        say("")
        say("| loss | " + " | ".join("%d s" % l for l in LAT) + " |")
        say("| --- |" + " --- |" * len(LAT))
        for loss in LOSS:
            row = []
            for lat in LAT:
                ks = [k for k in keys if k[:3] == (c, lat, loss)]
                row.append("%d -> %d" % (sum(off[k]["counted"] for k in ks),
                                         sum(on[k]["counted"] for k in ks)))
            say("| %g%% | %s |" % (loss * 100, " | ".join(row)))
    zero_bad = []
    for loss in LOSS:
        s0 = sum(on[k]["counted"] for k in keys if k[:3] == ("B", 0, loss))
        s5 = sum(on[k]["counted"] for k in keys if k[:3] == ("B", 5, loss))
        if s0 < s5:
            zero_bad.append("%g%%: %d at 0 s vs %d at 5 s" % (loss * 100, s0, s5))
    say("")
    say("- B as safe at 0 s as at 5 s at every loss level (the amendment-24 anomaly gone): "
        "**%s** %s" % ("PASS" if not zero_bad else "FAIL", "; ".join(zero_bad)))

    # ---- energy
    say("")
    say("## Paired energy change, on vs off, over ALL runs (mean %, by seed pairs)")
    for c in "BC":
        say("")
        say("controller %s" % c)
        say("")
        say("| loss | " + " | ".join("%d s" % l for l in LAT) + " |")
        say("| --- |" + " --- |" * len(LAT))
        for loss in LOSS:
            row = []
            for lat in LAT:
                d = [100.0 * (on[k]["energy_kwh"] - off[k]["energy_kwh"]) / off[k]["energy_kwh"]
                     for k in keys if k[:3] == (c, lat, loss) and off[k]["energy_kwh"] > 0]
                row.append("%+.1f" % statistics.fmean(d) if d else "-")
            say("| %g%% | %s |" % (loss * 100, " | ".join(row)))
    costly = []
    for lat in (0, 5, 30, 60):
        for loss in (0.0, 0.01, 0.05, 0.10):
            d = [100.0 * (on[k]["energy_kwh"] - off[k]["energy_kwh"]) / off[k]["energy_kwh"]
                 for k in keys if k[:3] == ("B", lat, loss) and off[k]["energy_kwh"] > 0]
            if d and statistics.fmean(d) < -5.0:
                costly.append("%ds %g%% %+.1f%%" % (lat, loss * 100, statistics.fmean(d)))
    say("")
    say("- B's cost at 0-60 s, <= 10%% loss, within 5%%: **%s** %s"
        % ("PASS" if not costly else "REVIEW", "; ".join(costly)))

    # ---- ahead of A, safely
    say("")
    say("## Share of seeds both safe and ahead of the static limit (A), off -> on")
    for c in "BC":
        cells = []
        for lat in LAT:
            for loss in LOSS:
                ks = [k for k in keys if k[:3] == (c, lat, loss)]
                f = lambda arm: sum(1 for k in ks if arm[k]["counted"]              # noqa: E731
                                    and arm[k]["energy_kwh"] > arm[k]["static_kwh"] + 1e-6)
                cells.append((f(off), f(on), len(ks)))
        say("- %s: %d -> %d of %d seed-cells" % (c, sum(x[0] for x in cells),
                                                 sum(x[1] for x in cells),
                                                 sum(x[2] for x in cells)))

    # ---- by type and entry
    say("")
    say("## Violating steps by entry and by type")
    for c in "BC":
        for name, arm in (("off", off), ("on", on)):
            ks = [k for k in keys if k[0] == c]
            be, bt = {}, {}
            for k in ks:
                for e, v in arm[k]["viol_by_entry"].items():
                    be[e] = be.get(e, 0) + v
                for t, v in arm[k]["violation_types"].items():
                    bt[t] = bt.get(t, 0) + v
            say("- %s %-3s by entry %s; by type %s; guard binds %d"
                % (c, name, dict(sorted(be.items())), dict(sorted(bt.items())),
                   sum(arm[k]["guard_binds"] for k in ks)))
    statics = sorted({(k[3], off[k]["static_kw"]) for k in keys})
    say("")
    say("static limits by seed: " + ", ".join("%d:%.1f" % s for s in statics))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\nwrote", out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--on", required=True)
    ap.add_argument("--off", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    main(os.path.join(HERE, a.on), os.path.join(HERE, a.off), os.path.join(HERE, a.out),
         a.title)
