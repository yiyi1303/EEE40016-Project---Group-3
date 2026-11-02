"""Run stage processes in parallel, a fixed number at a time, each with its own log.

    py tools/run_parallel.py --jobs 12 --log logs/final --seeds 7-19 \\
        --arm "main:S1:results/stages:" \\
        --arm "main_off:S1:results/paired_main/off:--no-schedule"

Each --arm is name:stage:out_folder:extra stages.py arguments (space separated). One process
per (arm, seed), queued in the order the arms are given, so put the results that matter
first. Session files for every scenario the arms use are created first, in this process, so
parallel runs never race to write the same file. Prints one line as each process finishes.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))


def seeds_from(spec):
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def parse_arm(arm):
    parts = arm.split(":", 3)
    if len(parts) < 3:
        raise SystemExit("--arm must be name:stage:out[:extra], got %r" % arm)
    name, stage, out = parts[:3]
    extra = parts[3].split() if len(parts) > 3 else []
    return name, stage, out, extra


def option(extra, flag, default):
    return extra[extra.index(flag) + 1] if flag in extra else default


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--log", default="logs/parallel")
    ap.add_argument("--seeds", default="7-19")
    ap.add_argument("--arm", action="append", required=True)
    a = ap.parse_args()

    from sweep import StudyRun
    from ev_sessions import load_or_create
    st = StudyRun()
    seeds = seeds_from(a.seeds)
    arms = [parse_arm(x) for x in a.arm]
    from ev_sessions import scenario
    for _, _, _, e in arms:
        if any(x.startswith(("--sessions=", "--plugin-model=", "--plugin=", "--sess"))
               and x not in ("--sessions",) for x in e):
            raise SystemExit("write --sessions X / --plugin-model X with a space: %s" % e)
    scenarios = {scenario(option(e, "--sessions", st.session_source),
                          option(e, "--plugin-model", st.plugin_model)) for _, _, _, e in arms}
    for source, model in sorted(scenarios):
        for s in seeds:
            load_or_create(st.feeder, st.ev_connections, s,
                           tag="_n%d" % len(st.ev_connections), source=source,
                           plugin_model=model)
    print("sessions ready for %s" % ", ".join("%s/%s" % x for x in sorted(scenarios)),
          flush=True)

    jobs = []
    for name, stage, out, extra in arms:
        for s in seeds:
            cmd = [sys.executable, os.path.join(HERE, "src", "stages.py"), "--stage", stage,
                   "--seed", str(s), "--out", out] + extra
            jobs.append(("%s_%s_seed%d" % (name, stage, s), cmd))

    os.makedirs(os.path.join(HERE, a.log), exist_ok=True)
    running, t0, failed = [], time.time(), 0
    while jobs or running:
        while jobs and len(running) < a.jobs:
            tag, cmd = jobs.pop(0)
            log = open(os.path.join(HERE, a.log, tag + ".log"), "w", encoding="utf-8")
            running.append((tag, subprocess.Popen(cmd, cwd=HERE, stdout=log,
                                                  stderr=subprocess.STDOUT), log))
        time.sleep(2)
        for item in list(running):
            tag, p, log = item
            if p.poll() is not None:
                log.close()
                running.remove(item)
                failed += p.returncode != 0
                print("%6.0f s  %-30s %s  (%d left, %d running)"
                      % (time.time() - t0, tag, "ok" if p.returncode == 0 else
                         "FAILED %d" % p.returncode, len(jobs), len(running)), flush=True)
    print("done in %.0f s, %d failed" % (time.time() - t0, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
