"""Measure seconds per power flow. This number decides whether stage S1 is feasible as scoped.

S1 is 42 operating points x 72 control steps, and the live controller bisects about 7 times
per step, so roughly 30,000 solves before S2 to S4.

Run:  py tests/solve_timing.py [n]
"""
import os, sys, time, random
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from feeder_csv import load_feeder
from solver import OpenDSSSolver
from build_sincal_model import profile_kw

n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
feeder = load_feeder()
base = {l.name: profile_kw(HERE, feeder.shapes[l.shape], 1080) for l in feeder.loads}
s = OpenDSSSolver(feeder, transformer_kva=150.0).build()

s.set_loads(base); s.solve()          # warm up, not counted
rng = random.Random(7)
times = []
for i in range(n):
    # vary the loads so nothing is cached between solves, as in a real sweep
    loads = {k: v * (0.8 + 0.4 * rng.random()) for k, v in base.items()}
    t0 = time.perf_counter()
    s.set_loads(loads)
    s.solve()
    times.append(time.perf_counter() - t0)
times.sort()
dt = sum(times)
per = dt / n
pick = lambda q: times[min(int(q * n), n - 1)]
print("solves            %d" % n)
print("total             %.3f s" % dt)
print("per solve  mean   %.4f s  (%.0f solves/s)" % (per, 1 / per))
print("           median %.4f s" % pick(0.5))
print("           p95    %.4f s" % pick(0.95))
print("           max    %.4f s" % times[-1])
per = pick(0.95)   # size the sweep on the slow end, not the average
print()
for stage, solves in (("S1 (42 pts x 72 steps x ~7 bisection + 2 baselines)", 42 * 72 * 9),
                      ("S1 controller A only", 42 * 72 * 7)):
    print("  %-52s %7d solves -> %5.1f min" % (stage, solves, solves * per / 60))
