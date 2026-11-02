"""Acceptance tests for the teammates' nodes: V2, V5, V6 and V7 from the validation plan.

These run against the stand-ins by default. Each teammate runs the same test on their file
in team/ with --team hoang or --team gia (no editing needed); passing it is the hand-over
condition.

    V2  battery    volt-var and volt-watt follow AS/NZS 4777.2              (Gia)
    V5  comms      the injector delivers the latency and loss commanded      (Hoang)
    V6  comms      trust is 1 on clean data, 0 within the timeout on
                   blackout, and monotonic in between                        (Hoang)
    V7  battery    the state-of-charge model neither creates nor destroys
                   energy                                                     (Gia)

Pass criteria are the plan's, Table 12, quoted at each test.

Run:  py tests/test_node_acceptance.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

# --- swap your own class in here --------------------------------------------------------
from battery import BatteryStandIn as Battery                 # Gia: your battery
from telemetry import TelemetryLink as Link                   # Hoang: your injector + trust
from telemetry import DownlinkChannel as Downlink             # Hoang: your downlink path
from telemetry import Observation                             # noqa: E402
# -----------------------------------------------------------------------------------------

# The reference curve, written out independently of the battery class so that V2 compares
# the code against the standard rather than against itself. AS/NZS 4777.2:2020, Australia A
# region defaults. PROVISIONAL: Gia to confirm these points against the standard.
REF_VOLT_VAR = [(207.0, 0.44), (220.0, 0.0), (240.0, 0.0), (258.0, -0.60)]  # Q / S, + supplies
REF_VOLT_WATT = [(253.0, 1.0), (260.0, 0.2)]                                 # P / Prated, discharge

results = []


def record(name, ok, detail):
    results.append((name, ok, detail))
    print("%-4s %s  %s" % (name, "PASS" if ok else "FAIL", detail))


def ref(v, pts):
    if v <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if v <= x1:
            return y0 + (y1 - y0) * (v - x0) / (x1 - x0)
    return pts[-1][1]


# ------------------------------------------------------------------------------ V2

def v2():
    """Pass: output within 1% of the published curve at 20 test points; response time inside
    the standard's limits."""
    b = Battery()
    s_kva, p_max = b.status()["s_kva"], b.status()["p_max_kw"]
    worst = 0.0
    # volt-var: 20 points spread across the whole curve, battery idle so Q has full room
    for k in range(20):
        v = 200.0 + k * (262.0 - 200.0) / 19
        _, q_load = b.response(v, 0.0)
        q_frac = -q_load / s_kva                      # load convention -> supplying positive
        worst = max(worst, abs(q_frac - ref(v, REF_VOLT_VAR)))
    vv = worst
    # volt-watt on discharge: asked for full power, allowed what the curve says
    worst = 0.0
    for k in range(20):
        v = 248.0 + k * (262.0 - 248.0) / 19
        p, _ = b.response(v, -p_max)
        worst = max(worst, abs(-p / p_max - ref(v, REF_VOLT_WATT)))
    vw = worst
    ok = vv <= 0.01 and vw <= 0.01
    record("V2", ok, "volt-var worst error %.4f, volt-watt worst error %.4f of rating (limit 0.01). "
                     "Response time: the model is quasi-static at 5 min and the standard's settling "
                     "time is seconds, so the response is taken at steady state within each step." % (vv, vw))


# ------------------------------------------------------------------------------ V5

def v5():
    """Pass: mean latency within 5% of commanded; loss within 1 percentage point.

    Sample size matters here. Loss is binomial, and at 40% loss the standard error over n
    messages is sqrt(0.24 / n). To resolve 1 percentage point at 95% confidence needs about
    9,200 messages; 2,000 gives +/- 2.1 points, so a perfectly accurate injector would fail
    by chance. 20,000 messages per level puts the noise at +/- 0.68 points.
    """
    N_WINDOWS = 2000                                 # x 10 samples = 20,000 messages
    worst_lat, worst_loss = 0.0, 0.0
    for lat in (5, 30, 60, 120, 300, 600):
        for loss in (0.0, 0.05, 0.2, 0.4):
            link = Link(lat, loss, seed=7)
            for w in range(N_WINDOWS):
                link.publish_window({"x": 1.0}, 960 + 5 * w, 965 + 5 * w)
            msgs = link._msgs
            got = [m for m in msgs if m.arrives != math.inf]
            mean_delay_s = 60.0 * sum(m.arrives - m.sent for m in got) / len(got)
            worst_lat = max(worst_lat, abs(mean_delay_s - lat) / lat)
            worst_loss = max(worst_loss, abs((1.0 - len(got) / len(msgs)) - loss))
    # the downlink path, held to the same criterion
    worst_dl_lat, worst_dl_loss = 0.0, 0.0
    for lat in (30, 300):
        for loss in (0.05, 0.4):
            d = Downlink(lat, loss, seed=7)
            for k in range(20000):
                d.send(k, 960 + 5 * k)
            delays = [60.0 * (a - snt) for a, snt, _ in d._inflight]
            worst_dl_lat = max(worst_dl_lat, abs(sum(delays) / len(delays) - lat) / lat)
            worst_dl_loss = max(worst_dl_loss, abs(d.dropped / d.sent - loss))
    ok = (worst_lat <= 0.05 and worst_loss <= 0.01 and
          worst_dl_lat <= 0.05 and worst_dl_loss <= 0.01)
    record("V5", ok, "uplink: worst latency error %.1f%%, worst loss error %.2f pp; downlink: "
                     "%.1f%%, %.2f pp (limits 5%% and 1 pp; 20,000 messages per level)"
                     % (100 * worst_lat, 100 * worst_loss, 100 * worst_dl_lat,
                        100 * worst_dl_loss))


# ------------------------------------------------------------------------------ V6

def v6():
    """Pass: trust = 1.0 on clean data; reaches 0 within the timeout on blackout; monotonic
    decreasing with no reversals."""
    # clean data: every step must be exactly 1
    link = Link(0, 0, seed=7)
    clean = []
    for w in range(84):
        a, b = 900 + 5 * w, 905 + 5 * w
        link.publish_window(lambda t: {"x": t}, a, b)
        if w >= 12:
            clean.append(link.trust(link.observe(b, {"x": b})))
    clean_ok = all(abs(t - 1.0) < 1e-12 for t in clean)

    # blackout: healthy for an hour, then nothing at all
    link = Link(0, 0, seed=7)
    for w in range(12):
        link.publish_window({"x": 1.0}, 900 + 5 * w, 905 + 5 * w)
    t_off = 960.0
    timeout = link.stale_timeout_min
    reached = None
    for k in range(0, 40):
        t = t_off + 0.5 * k
        if link.trust(link.observe(t, {"x": 1.0})) <= 0.0:
            reached = t - t_off
            break
    blackout_ok = reached is not None and reached <= timeout + 1e-9

    # monotonic: the trust function in each argument, as assumption A14 requires
    rev = 0
    prev = None
    for k in range(0, 61):
        tr = link.trust(Observation({}, k * timeout / 60.0, 0.1, 0, 0, 0.0))
        rev += prev is not None and tr > prev + 1e-12
        prev = tr
    prev = None
    for k in range(0, 101):
        tr = link.trust(Observation({}, 2.0, k / 100.0, 0, 0, 0.0))
        rev += prev is not None and tr > prev + 1e-12
        prev = tr
    ok = clean_ok and blackout_ok and rev == 0
    record("V6", ok, "clean data %s; blackout reaches 0 after %s min (timeout %g); "
                     "%d reversals across age and loss sweeps"
                     % ("trust 1.0 at every step" if clean_ok else "NOT always 1.0",
                        "%.1f" % reached if reached is not None else "never", timeout, rev))


# ------------------------------------------------------------------------------ V7

def v7():
    """Pass: closes within 2%, accounting for stated round-trip efficiency."""
    b = Battery(soc0=0.5)
    e = b.spec.e_kwh
    soc0 = b.soc
    # a full evening's worth of cycling, deliberately running into both SoC limits
    plan = [(40.0, 60), (50.0, 70), (-50.0, 120), (-30.0, 60), (0.0, 30), (25.0, 45)]
    lo_soc = hi_soc = b.soc
    for p, minutes in plan:
        for _ in range(minutes // 5):
            pk, _ = b.response(232.0, p)
            b.commit(pk, 5)
            lo_soc, hi_soc = min(lo_soc, b.soc), max(hi_soc, b.soc)
    hit_max = hi_soc >= b.spec.soc_max - 1e-9
    hit_min = lo_soc <= b.spec.soc_min + 1e-9
    stored = b.energy_in_kwh * b.spec.eta_charge - b.energy_out_kwh / b.spec.eta_discharge
    change = (b.soc - soc0) * e
    gap = abs(stored - change) / max(abs(change), 1e-9) if abs(change) > 1e-6 else abs(stored)
    # the cycle has to run into both SoC limits, or the edge cases were never exercised
    ok = gap <= 0.02 and hit_max and hit_min
    record("V7", ok, "energy in %.2f kWh, out %.2f kWh, net into cells %.3f kWh vs SoC change "
                     "%.3f kWh: closes within %.4f%% (limit 2%%); cycle reached max SoC: %s, "
                     "min SoC: %s" % (b.energy_in_kwh, b.energy_out_kwh, stored, change,
                                      100 * gap, "yes" if hit_max else "NO",
                                      "yes" if hit_min else "NO"))


def _use_plugins():
    """--team hoang / --team gia run these tests on a teammate's file in team/ instead of
    the stand-in; --link / --downlink / --battery module:Class name any other class, e.g.
        py tests/test_node_acceptance.py --team hoang
        py tests/test_node_acceptance.py --battery team.gia_battery:GiaBattery"""
    import argparse
    import plugins
    ap = argparse.ArgumentParser(description="V2, V5, V6, V7 acceptance tests")
    plugins.add_arguments(ap, slots=("link", "downlink", "battery"))
    a = ap.parse_args()
    chosen = plugins.specs(a, slots=("link", "downlink", "battery"))
    if any(n in (a.team or "").lower() for n in ("lomitha", "all")):
        print("(Lomitha's controller is not in these tests: check it on the Pi with "
              "tools/run_with_pi.py --compare)")
    g = globals()
    for name, slot in (("Link", "link"), ("Downlink", "downlink"), ("Battery", "battery")):
        if slot in chosen:
            g[name] = plugins.load_class(chosen[slot])
            print("testing %s: %s" % (name, chosen[slot]))


def main():
    _use_plugins()
    print("acceptance tests for the teammates' nodes, against the current classes\n")
    v2()
    v5()
    v6()
    v7()
    failed = [r for r in results if not r[1]]
    print("\n%d of %d passed" % (len(results) - len(failed), len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
