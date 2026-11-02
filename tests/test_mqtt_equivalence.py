"""Integration check: the MQTT path gives exactly the result the in-process path gives.

This is what makes the sweep's results valid for the real system. The thousands of sweep
runs use the in-process edge because it is fast and deterministic. If the same evening run
through a real MQTT broker, with the edge in a separate client exactly as it would sit on
the Raspberry Pi, produced a different answer, the sweep would be describing a system that
does not exist.

It runs one simulated evening both ways and requires, step by step:

    the same commanded limit, and the same schedule entry and limit applied
    the same draws from every charge point
    the same pass or fail against every constraint
    the same total energy, to floating-point exactness

It also reports the physical LAN round trips, which the plan says must be logged and kept
out of the simulated delay.

Run:  py tests/test_mqtt_equivalence.py [latency_s] [loss]
"""
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from sweep import StudyRun                                          # noqa: E402
import controllers                                                  # noqa: E402
from edge import ChargePointFleet                                   # noqa: E402
from ev_sessions import load_or_create                              # noqa: E402
from mqtt_edge import PiNode, MqttEdge, start_local_broker          # noqa: E402

PORT = 18832
SEED = 7


def main():
    latency = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    loss = float(sys.argv[2]) if len(sys.argv) > 2 else 0.10

    st = StudyRun()
    # controller B, the trust-weighted envelope, with a fixed static limit: calibration is
    # not what this test is about
    ctrl = controllers.build(st.cfg, static_kw=2.1)["B"]

    # --- in process, as the sweep runs it
    t0 = time.perf_counter()
    trace_a = []
    a = st.run(ctrl, latency, loss, SEED, trace_a)
    wall_a = time.perf_counter() - t0

    # --- over MQTT, with the edge as a separate client, as on the Pi
    start_local_broker(PORT)
    sessions = load_or_create(st.feeder, st.ev_connections, SEED,
                              tag="_n%d" % len(st.ev_connections), **st.session_args)
    pi = PiNode(ChargePointFleet(sessions, st.cfg["controller_settings"]["fallback_kw"],
                                 st.cfg["controller_settings"].get("uncovered_kw")),
                node="edge", port=PORT, step_min=st.step_min).start()
    twin_edge = MqttEdge(st.household, node="edge", port=PORT, step_min=st.step_min)
    time.sleep(1.0)                       # both clients subscribed before step 0

    t0 = time.perf_counter()
    trace_b = []
    b = st.run(ctrl, latency, loss, SEED, trace_b, edge=twin_edge)
    wall_b = time.perf_counter() - t0
    twin_edge.close()
    pi.stop()

    # --- compare, step by step
    diffs = []
    for x, y in zip(trace_a, trace_b):
        for k in ("commanded_kw", "envelope_kw", "applied_kw", "entry", "ok", "binding",
                  "charging"):
            if x[k] != y[k]:
                diffs.append((x["step"], k, x[k], y[k]))
    # The two sides add the same energies in a different order (per car on the charge
    # points, per step in the twin), so floating-point rounding can differ in the last
    # bits. That is arithmetic, not behaviour; anything above a micro-kWh would be real.
    energy_gap = abs(a.energy_kwh - b.energy_kwh)
    same_energy = energy_gap < 1e-6
    same = (not diffs and same_energy and a.violations == b.violations
            and len(trace_a) == len(trace_b))

    print("one evening, controller B, latency %g s, loss %.0f%%, seed %d"
          % (latency, loss * 100, SEED))
    print()
    print("%-26s %14s %14s" % ("", "in process", "over MQTT"))
    print("%-26s %14.6f %14.6f" % ("energy delivered (kWh)", a.energy_kwh, b.energy_kwh))
    print("%-26s %14d %14d" % ("violating steps", a.violations, b.violations))
    print("%-26s %14d %14d" % ("control steps", len(trace_a), len(trace_b)))
    print("%-26s %14d %14d" % ("edge fallbacks", a.fallbacks, b.fallbacks))
    print("%-26s %14.1f %14.1f" % ("wall clock (s)", wall_a, wall_b))
    print("%-26s %29.2e" % ("energy difference (kWh)", energy_gap))
    print()
    lan = twin_edge.lan_ms
    print("MQTT messages exchanged     %d (13 per control step: 1 sync, 10 samples, 1 setpoint, 1 ack)" % (13 * len(trace_b)))
    print("physical LAN round trip     median %.1f ms, max %.1f ms  (logged, not simulated)"
          % (statistics.median(lan), max(lan)))
    print("missed replies              %d" % len(twin_edge.misses))
    print("steps that differ           %d" % len(diffs))
    for d in diffs[:10]:
        print("   step %d  %s: %r vs %r" % d)
    print()
    print("EQUIVALENT" if same else "NOT EQUIVALENT")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
