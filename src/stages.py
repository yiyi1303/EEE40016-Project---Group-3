"""The study stages, exactly as Table 9 of the research plan defines them.

    S1  normal day, V1 at 7 levels x V2 at 6 levels, 42 points, controllers A, B, C
        the primary crossover surface
    S2  normal day, V3 stale hold at 4 levels at three representative S1 points, A, B, C
        isolates the stale-data failure mode
    S3  normal day, V5 battery disabled, a reduced 3 x 3 subset of S1, controllers A, B
        how far the battery moves the crossover, against the matching S1 cells
    S4  warning day, V4 SoC error x a 3 x 3 subset: NOT RUN. It needs scenario decisions
        only the team can make; see notes/AUDIT.md.

Controller A, the static limit, is recalibrated for every seed and every network variant
(battery on or off), because the safe static limit depends on both.

One process per seed, so stages run in parallel:

    py src/stages.py --stage S1 --seed 7
    py src/stages.py --summarise

Options for paired comparisons (amendment 25), written to their own folder:

    --out results/paired_schedule/off --no-schedule     single held setpoint (the baseline)
    --age-basis application / --uncovered-kw 0          schedule sensitivity variants

Teammates' code instead of the stand-ins (written to results/stages_team unless --out says
otherwise, so it can never overwrite the stand-in results):

    --team all            every file in team/ (or hoang, gia, lomitha, comma separated)
    --link / --downlink / --battery / --fleet module:Class    any other class for one part
"""
import argparse
import glob
import json
import os
import statistics
import sys
import time
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep import StudyRun, calibrate_static          # noqa: E402
import controllers                                    # noqa: E402
import plugins                                        # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "results", "stages")

S1_LATENCY = [0, 5, 30, 60, 120, 300, 600]            # V1, Table 8
S1_LOSS = [0.0, 0.01, 0.05, 0.10, 0.20, 0.40]          # V2, Table 8
S2_HOLD = [0.0, 2.0, 5.0, 8.0]                         # V3, Table 8: disabled, 2, 5, 8 min
S2_POINTS = [(5, 0.01), (60, 0.10), (300, 0.20)]       # good, moderate, poor: one per regime
S3_LATENCY = [5, 60, 300]                              # a 3 x 3 subset of S1
S3_LOSS = [0.01, 0.10, 0.20]
# the six S1 cells where schedules matter most (most steps on held entries), for the
# amendment-25 sensitivity runs: --uncovered-kw 0 and --age-basis application
S1H_POINTS = [(0, 0.40), (120, 0.10), (300, 0.0), (300, 0.10), (600, 0.0), (600, 0.10)]


def run_stage(stage, seed, overrides=None, sessions=None, plugin_model=None, parts=None):
    study = StudyRun()
    study.ctl.update(overrides or {})
    if parts:
        print("parts: %s" % plugins.use(study, **parts), flush=True)
    if sessions:
        study.session_source = sessions
    if plugin_model:
        study.plugin_model = plugin_model
    rows = []
    t0 = time.time()

    def cal(battery):
        kw, kwh, n = calibrate_static(study, seed, battery_enabled=battery)
        print("seed %d, battery %s: static limit %.1f kW, %.1f kWh (%d runs)"
              % (seed, "on" if battery else "off", kw, kwh, n), flush=True)
        return kw, kwh

    if stage == "S1":
        kw, kwh = cal(True)
        c = controllers.build(study.cfg, kw)
        for lat in S1_LATENCY:
            for loss in S1_LOSS:
                for key in "ABC":
                    if key == "A" and (lat, loss) != (0, 0.0):
                        continue        # A ignores telemetry: one run stands for every cell
                    r = study.run(c[key], lat, loss, seed)
                    rows.append(dict(asdict(r), static_kw=kw, static_kwh=kwh))
                print("  S1 seed %d  %4ds %3.0f%%  B %.1f kWh  C %.1f kWh"
                      % (seed, lat, loss * 100, rows[-2]["energy_kwh"] if len(rows) > 1 else 0,
                         rows[-1]["energy_kwh"]), flush=True)

    elif stage == "S2":
        kw, kwh = cal(True)
        c = controllers.build(study.cfg, kw)
        for lat, loss in S2_POINTS:
            for hold in S2_HOLD:
                for key in "ABC":
                    if key == "A" and hold > 0:
                        continue
                    r = study.run(c[key], lat, loss, seed, stale_hold_min=hold)
                    rows.append(dict(asdict(r), static_kw=kw, static_kwh=kwh))
                print("  S2 seed %d  %4ds %3.0f%%  hold %g min done" % (seed, lat, loss * 100,
                                                                      hold), flush=True)

    elif stage == "S3":
        kw, kwh = cal(False)                     # the static limit without the battery
        c = controllers.build(study.cfg, kw)
        for lat in S3_LATENCY:
            for loss in S3_LOSS:
                for key in "AB":
                    if key == "A" and (lat, loss) != (S3_LATENCY[0], S3_LOSS[0]):
                        continue
                    r = study.run(c[key], lat, loss, seed, battery_enabled=False)
                    rows.append(dict(asdict(r), static_kw=kw, static_kwh=kwh))
                print("  S3 seed %d  %4ds %3.0f%% done" % (seed, lat, loss * 100), flush=True)
    elif stage == "S1H":
        kw, kwh = cal(True)
        c = controllers.build(study.cfg, kw)
        for lat, loss in S1H_POINTS:
            for key in "BC":
                r = study.run(c[key], lat, loss, seed)
                rows.append(dict(asdict(r), static_kw=kw, static_kwh=kwh))
            print("  S1H seed %d  %4ds %3.0f%% done" % (seed, lat, loss * 100), flush=True)
    else:
        raise SystemExit("unknown stage %s" % stage)

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "%s_seed%d.json" % (stage, seed))
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"stage": stage, "seed": seed, "runs": rows, "overrides": overrides or {},
                   "sessions": study.session_args["source"],
                   "plugin_model": study.session_args["plugin_model"],
                   "parts": parts or {},
                   "wall_clock_s": round(time.time() - t0, 1)}, f, indent=2)
    print("wrote %s (%d runs, %.0f s)" % (path, len(rows), time.time() - t0))


# ---------------------------------------------------------------------- summary

def _load(stage):
    runs, scen = [], set()
    for p in sorted(glob.glob(os.path.join(OUT, "%s_seed*.json" % stage))):
        d = json.load(open(p, encoding="utf-8"))
        runs += d["runs"]
        scen.add((d.get("sessions"), d.get("plugin_model"),
                  json.dumps(d.get("overrides", {}), sort_keys=True),
                  json.dumps(d.get("parts") or {}, sort_keys=True)))
    if len(scen) > 1:
        raise SystemExit("%s in %s mixes scenarios or settings: %s" % (stage, OUT, sorted(scen)))
    return runs


def _adv(r):
    return 100.0 * (r["energy_kwh"] - r["static_kwh"]) / r["static_kwh"]


def summarise():
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    # ---- S1
    s1 = _load("S1")
    if s1:
        seeds = sorted({r["seed"] for r in s1})
        say("S1: primary crossover surface, %d seeds" % len(seeds))
        say("advantage over the static limit, mean over seeds, safe runs only "
            "(n safe / n), B = trust-weighted, C = binary fallback")
        for key in "BC":
            say("\ncontroller %s" % key)
            say("%8s" % "loss" + "".join("%13s" % ("%ds" % l) for l in S1_LATENCY))
            for loss in S1_LOSS:
                row = "%7.0f%%" % (loss * 100)
                for lat in S1_LATENCY:
                    c = [r for r in s1 if r["controller"] == key and r["latency_s"] == lat
                         and r["loss"] == loss]
                    safe = [_adv(r) for r in c if r["counted"]]
                    row += "%13s" % ("%+.1f %d/%d" % (statistics.fmean(safe), len(safe), len(c))
                                     if safe else "unsafe %d" % len(c))
                say(row)
        bad = {k: sum(1 for r in s1 if r["controller"] == k and not r["counted"])
               for k in "ABC"}
        tot = {k: sum(1 for r in s1 if r["controller"] == k) for k in "ABC"}
        say("\nruns with a violation: " + ", ".join("%s %d of %d" % (k, bad[k], tot[k])
                                                    for k in "ABC"))
        statics = sorted({(r["seed"], r["static_kw"]) for r in s1})
        say("static limits by seed: " + ", ".join("%d:%.1f" % s for s in statics))

    # ---- S2
    s2 = _load("S2")
    if s2:
        say("\nS2: stale-data hold (V3), advantage over static, mean over seeds")
        say("%14s" % "point" + "".join("%15s" % ("hold %g min" % h) for h in S2_HOLD))
        for key in "BC":
            for lat, loss in S2_POINTS:
                row = "%s %4ds %3.0f%%" % (key, lat, loss * 100)
                for hold in S2_HOLD:
                    c = [r for r in s2 if r["controller"] == key and r["latency_s"] == lat
                         and r["loss"] == loss and r["stale_hold_min"] == hold]
                    safe = [_adv(r) for r in c if r["counted"]]
                    row += "%15s" % ("%+.1f %d/%d" % (statistics.fmean(safe), len(safe), len(c))
                                     if safe else "unsafe %d" % len(c))
                say(row)

    # ---- S3 against S1
    s3 = _load("S3")
    if s3 and s1:
        say("\nS3: battery off vs on (S1), controller B, mean advantage over each network's "
            "own static limit")
        say("%14s %16s %16s %10s" % ("point", "battery on (S1)", "battery off (S3)", "shift"))
        for lat in S3_LATENCY:
            for loss in S3_LOSS:
                on = [_adv(r) for r in s1 if r["controller"] == "B" and r["latency_s"] == lat
                      and r["loss"] == loss and r["counted"]]
                off = [_adv(r) for r in s3 if r["controller"] == "B" and r["latency_s"] == lat
                       and r["loss"] == loss and r["counted"]]
                if on and off:
                    say("%7ds %4.0f%% %15.1f%% %15.1f%% %+9.1f"
                        % (lat, loss * 100, statistics.fmean(on), statistics.fmean(off),
                           statistics.fmean(on) - statistics.fmean(off)))
        st_on = sorted({(r["seed"], r["static_kw"]) for r in s1})
        st_off = sorted({(r["seed"], r["static_kw"]) for r in s3})
        say("static limit with battery: %s" % ", ".join("%d:%.1f" % s for s in st_on))
        say("static limit without:      %s" % ", ".join("%d:%.1f" % s for s in st_off))

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nwrote %s" % os.path.join(OUT, "summary.txt"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=("S1", "S2", "S3", "S1H"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--summarise", action="store_true")
    ap.add_argument("--out", default=None,
                    help="folder for results, relative to the project (default results/stages)")
    ap.add_argument("--no-schedule", action="store_true",
                    help="single held setpoint instead of a schedule (pre-amendment-25)")
    ap.add_argument("--age-basis", choices=("data", "application"), default=None)
    ap.add_argument("--uncovered-kw", type=float, default=None)
    ap.add_argument("--sessions", choices=("vista", "standin"), default=None,
                    help="session source (default: config cases.study.session_source)")
    ap.add_argument("--plugin-model", choices=("daily", "s1", "s2"), default=None,
                    help="how often cars plug in (default: config cases.study.plugin_model)")
    plugins.add_arguments(ap)
    a = ap.parse_args()
    parts = plugins.specs(a)
    global OUT
    if a.out:
        OUT = os.path.join(HERE, a.out)
    elif parts or a.plugin_model or a.sessions:
        # teammates' code, or any scenario other than the study's own, gets its own folder,
        # so neither can overwrite the main case
        case = json.load(open(os.path.join(HERE, "config", "study.json"),
                              encoding="utf-8"))["cases"]["study"]
        tag = "%s_%s" % (a.sessions or case.get("session_source", "vista"),
                         a.plugin_model or case.get("plugin_model", "daily"))
        default = "%s_%s" % (case.get("session_source", "vista"),
                             case.get("plugin_model", "daily"))
        OUT = os.path.join(HERE, "results", "stages" + ("_team" if parts else "")
                           + ("_" + tag if tag != default else ""))
    overrides = {}
    if a.no_schedule:
        overrides["setpoint_schedule"] = False
    if a.age_basis:
        overrides["schedule_age_basis"] = a.age_basis
    if a.uncovered_kw is not None:
        overrides["uncovered_kw"] = a.uncovered_kw
    if a.summarise:
        summarise()
    elif a.stage:
        run_stage(a.stage, a.seed, overrides, a.sessions, a.plugin_model, parts)
    else:
        raise SystemExit("give --stage S1|S2|S3 --seed N, or --summarise")


if __name__ == "__main__":
    main()
