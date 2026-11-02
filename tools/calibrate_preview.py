"""How congested is each demand scenario? The static limit per seed, as a quick preview.

    py tools/calibrate_preview.py [--models s1,s2] [--seeds 7-19] [--workers 8]

For each plug-in model and seed, bisects the largest fixed limit with no violation all
evening (controller A's calibration, amendment 1) and reports it with the energy wanted and
the energy the static limit delivers. A seed whose static limit sits at the 7.2 kW ceiling
is not congested at all: live control has nothing to win there. Out: printed table.
"""
import argparse
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, os.path.join(HERE, "tools"))


def one(args):
    model, seed = args
    from sweep import StudyRun, calibrate_static
    st = StudyRun()
    st.plugin_model = model
    kw, kwh, n = calibrate_static(st, seed)
    demanded = st.make_edge(seed).demanded_kwh
    return model, seed, kw, kwh, demanded


def main():
    from run_parallel import seeds_from
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default="s1,s2")
    ap.add_argument("--seeds", default="7-19")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    models = a.models.split(",")
    # create the session files once, here, before the workers read them
    from sweep import StudyRun
    from ev_sessions import load_or_create
    st = StudyRun()
    for m in models:
        for s in seeds_from(a.seeds):
            load_or_create(st.feeder, st.ev_connections, s,
                           tag="_n%d" % len(st.ev_connections), plugin_model=m)
    jobs = [(m, s) for m in models for s in seeds_from(a.seeds)]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(one, jobs))
    for m in models:
        r = [x for x in rows if x[0] == m]
        print("\nplug-in model %s" % m)
        print("%5s %10s %12s %12s" % ("seed", "static kW", "static kWh", "wanted kWh"))
        for _, seed, kw, kwh, dem in r:
            print("%5d %10.1f %12.1f %12.1f" % (seed, kw, kwh, dem))
        cong = [x for x in r if x[2] < 7.2 - 1e-9]
        print("congested seeds (static below 7.2 kW): %d of %d; median static %.1f kW"
              % (len(cong), len(r), statistics.median(x[2] for x in r)))


if __name__ == "__main__":
    main()
