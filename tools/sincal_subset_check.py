"""SINCAL against OpenDSS on a reduced feeder, small enough for the Xplore licence.

The Xplore licence on this laptop refuses to solve more than 50 nodes, so the full 906-bus
feeder can only be cross-checked on the uni AVD. This runs the same check here on a cut of
the feeder that fits, which tests everything the importer writes (single-phase loads on
their phase, line impedances in both sequences, the Dyn11 transformer, the infeeder) before
anyone carries the full model to a licensed machine.

How the feeder is cut, so the two engines see an identical network:

    1  Plain cable segments are merged. A bus with exactly two cables, no load and not the
       busbar carries no current of its own, so the two cables are in series and add. The
       package's cables have no shunt capacitance (C = 0), so this is exact, not an
       approximation. 906 buses become 205.
    2  The longest path from the transformer is kept, then each customer's branch in turn,
       farthest first, while the total stays under the node cap.
    3  A load whose branch did not fit moves, on its own phase, to the nearest kept bus
       upstream. Total demand and its phase split are unchanged, so the transformer and the
       trunk carry the full feeder's load.

Both engines are then given that reduced feeder and the same kW per load, and the per-phase
voltages are compared at every node. The pass criterion is V1's: within 0.5%.

Run:  py tools/sincal_subset_check.py              (benchmark and study cases)
Out:  notes/sincal_subset_check.md, models/EULV_subset_<case>.sin
"""
import collections
import json
import math
import os
import sys
from dataclasses import replace

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from feeder_csv import Feeder, Line, LineCode, load_feeder     # noqa: E402
from build_sincal_model import build, profile_kw, MODELS      # noqa: E402
from solver import OpenDSSSolver, SincalSolver                 # noqa: E402

CONFIG = os.path.join(HERE, "config", "study.json")
REPORT = os.path.join(HERE, "notes", "sincal_subset_check.md")
NODE_CAP = 50          # Xplore: "Only 50 nodes are permitted for Simulation"
LV_NODES = 46          # leaves the 11 kV source bus and a margin under the cap
TOLERANCE_PCT = 0.5
# (case, minute of the load profiles, why this minute)
CASES = [("benchmark", 566, "V1's published on-peak snapshot, 800 kVA, 1.05 pu"),
         ("study", None, "study transformer (150 kVA) and source (1.00 pu) at the evening "
                         "minute of highest feeder demand")]


def reduce_feeder(f, lv_nodes=LV_NODES):
    """A reduced copy of the feeder with at most lv_nodes LV buses. See the module notes."""
    adj = collections.defaultdict(list)
    for ln in f.lines:
        adj[ln.bus1].append((ln.bus2, ln))
        adj[ln.bus2].append((ln.bus1, ln))
    root = f.transformer.bus_lv
    if len(f.lines) != len(adj) - 1:
        raise ValueError("feeder is not radial; the reduction assumes a tree")

    parent, pline, dist, order = {root: None}, {}, {root: 0.0}, [root]
    for b in order:                                   # breadth first from the busbar
        for n, ln in adj[b]:
            if n not in parent:
                parent[n], pline[n] = b, ln
                dist[n] = dist[b] + ln.length_km
                order.append(n)

    load_bus = {ld.bus for ld in f.loads}
    structural = {b for b in adj if b == root or b in load_bus or len(adj[b]) != 2}

    # merged tree: each structural bus hangs off the next structural bus upstream
    mparent, chain = {}, {}
    for s in structural - {root}:
        lines, b = [], s
        while True:
            lines.append(pline[b])
            b = parent[b]
            if b in structural:
                break
        mparent[s], chain[s] = b, lines

    def path_up(b, kept):
        out = []
        while b not in kept:
            out.append(b)
            b = mparent[b]
        return out

    kept = {root}
    for b in sorted(load_bus, key=lambda x: -dist[x]):
        new = path_up(b, kept)
        if len(kept) + len(new) <= lv_nodes:
            kept.update(new)

    codes, lines = {}, []
    for s in sorted(kept - {root}, key=lambda x: dist[x]):
        segs = chain[s]
        # series cables add per sequence: Z_phase is linear in Z1 and Z0, so summing the
        # sequence impedances is the same as summing the phase matrices
        z = {k: sum(getattr(f.linecodes[ln.linecode], k) * ln.length_km for ln in segs)
             for k in ("r1", "x1", "r0", "x0", "c1", "c0")}
        name = "M%d" % s
        codes[name] = LineCode(name=name, nphases=3, **z)
        lines.append(Line(name="LINE_M%d" % s, bus1=mparent[s], bus2=s, phases="ABC",
                          length_km=1.0, linecode=name))

    loads, moved = [], 0
    for ld in f.loads:
        b = ld.bus
        while b not in kept:
            b = mparent[b]
        moved += b != ld.bus
        loads.append(replace(ld, bus=b))

    reduced = Feeder(source=f.source, transformer=f.transformer, linecodes=codes,
                     lines=lines, loads=loads, coords={}, shapes=f.shapes)
    info = {"buses_full": len(adj), "buses_after_merge": len(structural),
            "lv_buses_kept": len(kept), "lines_kept": len(lines),
            "loads_on_own_bus": len(f.loads) - moved, "loads_moved_upstream": moved,
            "km_full": round(max(dist.values()), 3),
            "km_kept": round(max(dist[b] for b in kept), 3),
            "farthest_load_kept": max((dist[b], b) for b in kept if b in load_bus)[1]}
    return reduced, info


def evening_peak_minute(f, start=960, end=1320):
    """Minute in 16:00-22:00 with the highest total house demand."""
    return max(range(start, end + 1),
               key=lambda m: sum(profile_kw(HERE, f.shapes[ld.shape], m) for ld in f.loads))


def compare(a, b):
    """Per-node % difference of b against a over the nodes both have."""
    diffs = {k: 100.0 * abs(b[k] - a[k]) / a[k] for k in a if k in b and a[k] > 0}
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    return diffs, only_a, only_b


def run_case(f, case, minute, cfg):
    c = cfg["cases"][case]
    reduced, info = reduce_feeder(f)
    kw = {ld.name: profile_kw(HERE, f.shapes[ld.shape], minute) for ld in reduced.loads}

    dss = OpenDSSSolver(feeder=reduced, transformer_kva=c["transformer_kva"],
                        source_pu=c["source_pu"]).build()
    dss.set_loads(kw)
    dss.solve()
    v_dss = dss.node_voltages()

    name = "EULV_subset_%s" % case
    built = build(case, minute, feeder=reduced, name=name, load_kw=kw)
    nodes = built["counts"]["Node"]
    if nodes > NODE_CAP:
        raise SystemExit("reduced model has %d nodes, over the %d cap" % (nodes, NODE_CAP))
    sin = SincalSolver(os.path.join(MODELS, name + "_files"))
    sin.solve("LF_USYM")
    v_sin = sin.node_voltages()

    diffs, only_dss, only_sin = compare(v_dss, v_sin)
    worst_key = max(diffs, key=diffs.get)
    lv = [k for k in v_dss if k[0] != reduced.transformer.bus_hv.upper()]
    vmin_key = min(lv, key=lambda k: v_dss[k])
    return {
        "case": case, "minute": minute, "transformer_kva": c["transformer_kva"],
        "source_pu": c["source_pu"], "total_kw": round(sum(kw.values()), 2),
        "reduction": info, "sincal_nodes": nodes,
        "nodes_compared": len(diffs), "only_opendss": only_dss, "only_sincal": only_sin,
        "max_diff_pct": round(diffs[worst_key], 4), "worst_node": "%s.%d" % worst_key,
        "mean_diff_pct": round(sum(diffs.values()) / len(diffs), 4),
        "lowest_node": "%s.%d" % vmin_key,
        "lowest_v_opendss": round(v_dss[vmin_key], 2),
        "lowest_v_sincal": round(v_sin.get(vmin_key, float("nan")), 2),
        "passed": diffs[worst_key] <= TOLERANCE_PCT and not only_dss and not only_sin,
        "project": os.path.join(MODELS, name + ".sin"),
    }


def report(results):
    hm = lambda m: "%02d:%02d" % divmod(m, 60)   # noqa: E731
    r0 = results[0]["reduction"]
    lines = ["# SINCAL against OpenDSS on a reduced feeder", "",
             "Both engines solve the same reduced feeder with the same kW per load. SINCAL "
             "runs its unbalanced load flow (`LF_USYM`); OpenDSS its snapshot solve. "
             "Pass criterion as V1: every node voltage within %.1f%%." % TOLERANCE_PCT, "",
             "Reduction (identical for both cases): %d buses, %d after merging plain cable "
             "segments, %d kept. %d of 55 loads sit on their own bus; %d moved to the nearest "
             "kept bus upstream on their own phase. The kept part reaches %.3f km of the "
             "feeder's %.3f km, down to the load at bus %s." % (
                 r0["buses_full"], r0["buses_after_merge"], r0["lv_buses_kept"],
                 r0["loads_on_own_bus"], r0["loads_moved_upstream"], r0["km_kept"],
                 r0["km_full"], r0["farthest_load_kept"]), "",
             "| | " + " | ".join(r["case"] for r in results) + " |",
             "| --- |" + " --- |" * len(results)]
    rows = [("load minute", lambda r: "%d (%s)" % (r["minute"], hm(r["minute"]))),
            ("transformer", lambda r: "%d kVA" % r["transformer_kva"]),
            ("source", lambda r: "%.2f pu" % r["source_pu"]),
            ("total load", lambda r: "%.1f kW" % r["total_kw"]),
            ("SINCAL nodes (cap %d)" % NODE_CAP, lambda r: str(r["sincal_nodes"])),
            ("phase-nodes compared", lambda r: str(r["nodes_compared"])),
            ("lowest voltage, OpenDSS", lambda r: "%.2f V at %s" % (r["lowest_v_opendss"],
                                                                    r["lowest_node"])),
            ("lowest voltage, SINCAL", lambda r: "%.2f V" % r["lowest_v_sincal"]),
            ("largest difference", lambda r: "%.4f%% at %s" % (r["max_diff_pct"],
                                                               r["worst_node"])),
            ("mean difference", lambda r: "%.4f%%" % r["mean_diff_pct"]),
            ("nodes in one engine only", lambda r: str(len(r["only_opendss"])
                                                       + len(r["only_sincal"]))),
            ("result", lambda r: "**PASS**" if r["passed"] else "**FAIL**")]
    for label, fn in rows:
        lines.append("| %s | %s |" % (label, " | ".join(fn(r) for r in results)))
    lines += ["", "What this does not cover: the 906-bus feeder itself, which only the AVD's "
              "full licence can solve. `tools/make_avd_package.py` builds that run (avd_crosscheck.zip).", ""]
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main():
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    f = load_feeder()
    results = []
    for case, minute, why in CASES:
        m = minute if minute is not None else evening_peak_minute(f)
        r = run_case(f, case, m, cfg)
        results.append(r)
        print("%-9s minute %4d  %5.1f kW  nodes %d  compared %d  max %.4f%% at %s  "
              "mean %.4f%%  lowest %.2f V  %s"
              % (case, m, r["total_kw"], r["sincal_nodes"], r["nodes_compared"],
                 r["max_diff_pct"], r["worst_node"], r["mean_diff_pct"],
                 r["lowest_v_opendss"], "PASS" if r["passed"] else "FAIL"))
    report(results)
    with open(os.path.join(HERE, "results", "sincal_subset_check.json"), "w",
              encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    print("wrote", REPORT)
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
