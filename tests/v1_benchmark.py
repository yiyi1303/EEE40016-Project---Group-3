"""Validation item V1: our feeder model must match the published IEEE solution.

Pass criterion from the research plan: every node voltage within 0.5% of the published
value. The published case is the on-peak snapshot at minute 566 of the load profiles,
with the original 800 kVA transformer and no EVs, PV or battery.

Run:  py tests/v1_benchmark.py
Out:  notes/v1_result.md
"""
import os
import sys

import openpyxl

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from feeder_csv import load_feeder                      # noqa: E402
from solver import OpenDSSSolver                        # noqa: E402
from build_sincal_model import profile_kw               # noqa: E402

REFERENCE = os.path.join(HERE, "data", "feeder", "Solutions", "OpenDSS", "Snapshots",
                         "Snapshot_566min_On Peak.xlsx")
REPORT = os.path.join(HERE, "notes", "v1_result.md")
MINUTE = 566
TOLERANCE_PCT = 0.5


def published_voltages(path=REFERENCE):
    """{(bus, phase_node): volts} from the published snapshot."""
    ws = openpyxl.load_workbook(path, data_only=True)["Voltages"]
    rows = ws.iter_rows(values_only=True)
    next(rows)                                          # header
    out = {}
    for r in rows:
        if r[0] is None:
            continue
        bus = str(r[0]).strip().upper()
        # columns repeat as Node, Magnitude, Angle, pu for up to three phases
        for i in (2, 6, 10):
            if i + 1 >= len(r) or r[i] in (None, ""):
                continue
            node, mag = int(r[i]), float(r[i + 1])
            if mag > 0:
                out[(bus, node)] = mag
    return out


def main():
    feeder = load_feeder()

    kw = {ld.name: profile_kw(HERE, feeder.shapes[ld.shape], MINUTE) for ld in feeder.loads}
    total_kw = sum(kw.values())

    solver = OpenDSSSolver(feeder, transformer_kva=feeder.transformer.mva * 1000.0).build()
    solver.set_loads(kw)
    solver.solve()

    ours = solver.node_voltages()
    ref = published_voltages()

    compared, errors, worst = 0, [], (0.0, None)
    for key, v_ref in ref.items():
        v_ours = ours.get(key)
        if v_ours is None or v_ref <= 0:
            continue
        compared += 1
        err = 100.0 * abs(v_ours - v_ref) / v_ref
        if err > worst[0]:
            worst = (err, key)
        if err > TOLERANCE_PCT:
            errors.append((key, v_ref, v_ours, err))

    missing = [k for k in ref if k not in ours]
    mean_err = (sum(100.0 * abs(ours[k] - ref[k]) / ref[k]
                    for k in ref if k in ours and ref[k] > 0) / compared) if compared else 0.0

    passed = not errors and not missing

    lines = ["# V1 — feeder model against the published solution", "",
             "| | |", "| --- | --- |",
             "| Engine | %s |" % solver.name,
             "| Case | benchmark, %d kVA transformer, no EVs |"
             % round(feeder.transformer.mva * 1000),
             "| Load snapshot | minute %d, %.2f kW total |" % (MINUTE, total_kw),
             "| Reference | `Solutions/OpenDSS/Snapshots/Snapshot_566min_On Peak.xlsx` |",
             "| Nodes compared | %d |" % compared,
             "| Tolerance | %.1f%% |" % TOLERANCE_PCT,
             "| Worst error | %.4f%% at bus %s phase %s |"
             % (worst[0], worst[1][0], worst[1][1]) if worst[1] else "| Worst error | n/a |",
             "| Mean error | %.4f%% |" % mean_err,
             "| Nodes over tolerance | %d |" % len(errors),
             "| Nodes missing from our model | %d |" % len(missing),
             "", "**%s**" % ("PASS" if passed else "FAIL"), ""]

    if errors:
        lines += ["## Nodes outside tolerance", "",
                  "| Bus | Phase | Published (V) | Ours (V) | Error |", "| --- | ---: | ---: | ---: | ---: |"]
        for (bus, node), a, b, e in sorted(errors, key=lambda x: -x[3])[:25]:
            lines.append("| %s | %d | %.3f | %.3f | %.3f%% |" % (bus, node, a, b, e))
        if len(errors) > 25:
            lines.append("")
            lines.append("...and %d more." % (len(errors) - 25))
    if missing:
        lines += ["", "Buses in the reference but not in our model: %s"
                  % ", ".join("%s.%d" % k for k in missing[:20])]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("engine            %s" % solver.name)
    print("load minute       %d  (%.2f kW)" % (MINUTE, total_kw))
    print("nodes compared    %d" % compared)
    print("worst error       %.4f%%%s" % (worst[0],
          "  at bus %s phase %s" % worst[1] if worst[1] else ""))
    print("mean error        %.4f%%" % mean_err)
    print("over tolerance    %d" % len(errors))
    print("missing nodes     %d" % len(missing))
    print()
    print("V1 %s  (tolerance %.1f%%)" % ("PASS" if passed else "FAIL", TOLERANCE_PCT))
    print("wrote", REPORT)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
