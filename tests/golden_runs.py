"""Golden runs for the setpoint-schedule change (plan amendment 25).

    py tests/golden_runs.py --record --src results/superseded/src_before_schedule_fix
                                                               once, on the code BEFORE
    py tests/golden_runs.py --check --flag off                 schedule off: must be identical
    py tests/golden_runs.py --check --flag on                  schedule on: hold-free cells
                                                               must be identical

--record stores RunResult and the full trace for each point in results/golden/. --check
re-runs the points on the current code and compares every field the golden has, step by
step. New fields added by the change are ignored; a changed value in an old field is not.

The points: the three V9 points, the three traced cases from the design (held setpoints at
0 s, 300 s and 600 s), and seeds 7-9 for B and C at 0 s and 30 s with no loss, which have no
held setpoints at all.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(HERE, "results", "golden")
STATIC_KW = 2.1

# (controller, latency_s, loss, stale_hold_min, seed, holds expected)
POINTS = [("B", 5, 0.01, 0.0, 7, True), ("C", 300, 0.20, 0.0, 7, True),
          ("B", 60, 0.10, 5.0, 7, True),
          ("B", 0, 0.10, 0.0, 8, True), ("C", 300, 0.0, 0.0, 7, True),
          ("B", 600, 0.10, 0.0, 7, True)]
for _seed in (7, 8, 9):
    for _lat in (0, 30):
        for _c in "BC":
            POINTS.append((_c, _lat, 0.0, 0.0, _seed, False))


def key(p):
    c, lat, loss, hold, seed, _ = p
    return "%s_lat%g_loss%g_hold%g_seed%d" % (c, lat, loss, hold, seed)


def _run(args):
    src, p, overrides = args
    sys.path.insert(0, os.path.join(HERE, src))
    import controllers
    from sweep import StudyRun
    study = StudyRun()
    study.ctl.update(overrides)
    # the goldens were recorded on VISTA sessions with every car plugging in each evening
    study.session_source, study.plugin_model = "vista", "daily"
    c, lat, loss, hold, seed, _ = p
    trace = []
    r = study.run(controllers.build(study.cfg, STATIC_KW)[c], lat, loss, seed, trace,
                  stale_hold_min=hold)
    d = asdict(r)
    d.pop("seconds")
    return key(p), {"result": d, "trace": trace}


def compare(gold, new):
    """Differences in any field the golden has. Returns a list of strings."""
    out = []
    for k, v in gold["result"].items():
        if new["result"].get(k) != v:
            out.append("result.%s: %r -> %r" % (k, v, new["result"].get(k)))
    if len(gold["trace"]) != len(new["trace"]):
        out.append("trace length %d -> %d" % (len(gold["trace"]), len(new["trace"])))
    for g, n in zip(gold["trace"], new["trace"]):
        for k, v in g.items():
            if n.get(k) != v:
                out.append("step %d %s: %r -> %r" % (g["step"], k, v, n.get(k)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--record", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--src", default="src")
    ap.add_argument("--flag", choices=("on", "off"), default="off")
    ap.add_argument("--workers", type=int, default=9)
    a = ap.parse_args()

    overrides = {}
    points = POINTS
    if a.check:
        overrides = {"setpoint_schedule": a.flag == "on"}
        if a.flag == "on":
            points = [p for p in POINTS if not p[5]]
    with ProcessPoolExecutor(a.workers) as ex:
        results = dict(ex.map(_run, [(a.src, p, overrides) for p in points]))

    os.makedirs(GOLDEN, exist_ok=True)
    if a.record:
        for k, v in results.items():
            with open(os.path.join(GOLDEN, k + ".json"), "w", encoding="utf-8") as f:
                json.dump(v, f, sort_keys=True)
        print("recorded %d golden runs in %s" % (len(results), GOLDEN))
        return 0

    bad = 0
    for p in points:
        k = key(p)
        with open(os.path.join(GOLDEN, k + ".json"), encoding="utf-8") as f:
            gold = json.load(f)
        diffs = compare(gold, results[k])
        print("%-36s %s" % (k, "IDENTICAL" if not diffs else "DIFFERS (%d)" % len(diffs)))
        for d in diffs[:6]:
            print("      ", d)
        bad += bool(diffs)
    print("\n%d of %d identical (schedule %s)" % (len(points) - bad, len(points), a.flag))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
