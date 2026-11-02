"""Run one simulated evening with the charge points on the Raspberry Pi. The laptop side.

    py tools/run_with_pi.py --broker <broker address>                    the basic run
    py tools/run_with_pi.py --broker <address> --compare                 also check the Pi
                                                                         run matches the
                                                                         simulation exactly
Start the Pi first (python3 run_pi_node.py --broker <address>); this waits for it.

Options:
    --controller B        A fixed, B trust-weighted (default), C binary fallback
    --latency 60          delay in seconds, both directions
    --loss 0.10           packet loss, 0 to 1
    --seed 7              which simulated evening; the Pi must use the same seed
    --static-kw 2.5       the fixed limit for A and C; omitted, it is calibrated (~1 min)
    --plugin-model s1     s1 main case (default) or s2 stress case; the Pi must match
    --start-broker        also run the MQTT broker on this laptop
    --battery-on-pi       the battery runs on the Pi too (run_pi_node.py --battery): the twin
                          calls it over MQTT. With --compare, the comparison runs the same
                          battery class here, so EQUIVALENT covers the battery as well
    --team hoang          teammates' files in team/ instead of the stand-ins: hoang,
                          gia, lomitha, a comma-separated list, or all. With --compare,
                          use the same controller as the Pi (--team lomitha on both).
    --link / --downlink / --battery / --fleet module:Class
                          any other class for one part; wins over --team

Prints one line per 5-minute step as the evening runs, then a summary, and saves the run to
results/hil/. Physical network delay is measured and reported, never added to the study's
simulated delay.
"""
import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from sweep import StudyRun, calibrate_static              # noqa: E402
import controllers                                         # noqa: E402
from mqtt_edge import MqttEdge, RemoteBattery, start_local_broker  # noqa: E402
import plugins                                             # noqa: E402

COMPARED = ("commanded_kw", "envelope_kw", "applied_kw", "entry", "ok", "binding", "charging")


class LiveEdge(MqttEdge):
    """The MQTT edge, printing one line per step as the Pi answers."""

    def apply(self, setpoint):
        ack = super().apply(setpoint)
        hh, mm = divmod(int(round(self._t_to)), 60)
        if getattr(setpoint, "fallback", False):
            what = "fallback 1.4 kW     "
        else:
            what = "limit %4.1f kW (e%d) " % (setpoint.limit_kw, max(setpoint.entry, 0))
        cars = sum(1 for d in ack.draws.values() if d > 1e-9)
        print("  step %2d  %02d:%02d  %s %2d cars  %5.1f kW   Pi replied in %4.0f ms"
              % (setpoint.step, hh, mm, what, cars, sum(ack.draws.values()),
                 self.lan_ms[-1] if self.lan_ms else float("nan")), flush=True)
        return ack


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--broker", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--node", default="edge")
    ap.add_argument("--controller", default="B", choices=list("ABC"))
    ap.add_argument("--latency", type=float, default=60.0)
    ap.add_argument("--loss", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--static-kw", type=float, default=None)
    ap.add_argument("--plugin-model", choices=("s1", "s2"), default=None)
    ap.add_argument("--start-broker", action="store_true")
    ap.add_argument("--broker-host", default="0.0.0.0",
                    help="where --start-broker listens (127.0.0.1 for a laptop-only rehearsal)")
    ap.add_argument("--wait", type=float, default=60.0, help="seconds to wait for the Pi")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--battery-on-pi", action="store_true")
    plugins.add_arguments(ap)
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)        # each line at once, even into a log

    st = StudyRun()
    if a.plugin_model:
        st.plugin_model = a.plugin_model
    parts = plugins.use(st, **plugins.specs(a))
    print("parts in use: %s" % parts)
    print("demand: %(source)s/%(plugin_model)s, seed %%d" % st.session_args % a.seed)

    if a.start_broker:
        start_local_broker(a.port, a.broker_host)
        print("MQTT broker started on this laptop (%s:%d)" % (a.broker_host, a.port))
        if a.broker_host == "0.0.0.0":
            from broker import lan_addresses
            print("  the Pi should use --broker %s" % (", ".join(lan_addresses()) or "?"))

    edge = LiveEdge(st.household, node=a.node, broker=a.broker, port=a.port,
                    step_min=st.step_min)
    print("waiting up to %.0f s for the Pi (node '%s') at %s:%d ..."
          % (a.wait, a.node, a.broker, a.port))
    if not edge.wait_for_edge(a.wait):
        edge.close()
        raise SystemExit(
            "the Pi did not report in. Check, in this order:\n"
            "  1. is run_pi_node.py running on the Pi, and did it say 'connected'?\n"
            "  2. are both using the same --broker address and port?\n"
            "  3. same network? (uni Wi-Fi often blocks device-to-device traffic: use a "
            "phone hotspot)\n"
            "  4. broker on this laptop: did Windows ask to allow Python? It must be allowed")
    print("the Pi is online.")
    local_battery = st.battery_cls            # the class the Pi runs, for the comparison
    if a.battery_on_pi:
        RemoteBattery.connect(a.broker, a.port)
        if not RemoteBattery.wait_online(a.wait):
            edge.close()
            raise SystemExit("the battery on the Pi did not report in: start run_pi_node.py "
                             "with --battery (and --team gia for Gia's battery)")
        print("the battery on the Pi is online (%s.%s runs there)"
              % (local_battery.__module__, local_battery.__name__))

    kw = a.static_kw
    if kw is None:
        print("calibrating the fixed limit for seed %d (about a minute) ..." % a.seed)
        kw = calibrate_static(st, a.seed)[0]
    print("fixed limit %.1f kW" % kw)
    ctrl = controllers.build(st.cfg, kw)[a.controller]

    print("\nevening 16:00-22:00, controller %s, %g s delay, %g%% loss, over MQTT"
          % (a.controller, a.latency, a.loss * 100))
    t0 = time.time()
    trace = []
    if a.battery_on_pi:
        st.battery_cls = RemoteBattery        # only for this evening: calibration ran here
    try:
        r = st.run(ctrl, a.latency, a.loss, a.seed, trace, edge=edge)
    finally:
        edge.close()
        st.battery_cls = local_battery
        if a.battery_on_pi:
            RemoteBattery.close()
    wall = time.time() - t0
    lan = edge.lan_ms
    print("\nenergy delivered   %.1f kWh of %.1f wanted" % (r.energy_kwh, r.demanded_kwh))
    print("network limits     %s" % ("never broken" if not r.violations else
                                     "broken on %d steps %s" % (r.violations,
                                                                r.violation_types)))
    print("schedule entries   %s (entry 0, 1, 2, fallback)" % r.entry_counts)
    print("Pi round trips     median %.0f ms, max %.0f ms; missed replies %d; %.0f s in all"
          % (statistics.median(lan) if lan else float("nan"), max(lan) if lan else float("nan"),
             len(edge.misses), wall))
    bat_ms = list(RemoteBattery.round_trips_ms) if a.battery_on_pi else []
    if r.battery:
        print("battery            SoC at the end %.4f, mean Q %.2f kvar%s"
              % (r.battery_soc_end, r.battery_q_mean_kvar,
                 "; on the Pi, %d calls, median %.0f ms" % (len(bat_ms),
                                                            statistics.median(bat_ms))
                 if bat_ms else ""))

    result = {"args": vars(a), "parts": parts, "static_kw": kw,
              "energy_kwh": r.energy_kwh, "violations": r.violations,
              "entry_counts": r.entry_counts, "lan_ms": lan, "misses": edge.misses,
              "battery_on_pi": a.battery_on_pi, "battery_ms": bat_ms,
              "battery_soc_end": r.battery_soc_end,
              "battery_q_mean_kvar": r.battery_q_mean_kvar, "trace": trace}
    if a.compare:
        print("\nrunning the same evening inside the simulator to compare ...")
        trace2 = []
        r2 = st.run(ctrl, a.latency, a.loss, a.seed, trace2)
        diffs = [(x["step"], k, x[k], y[k]) for x, y in zip(trace, trace2)
                 for k in COMPARED if x.get(k) != y.get(k)]
        gap = abs(r.energy_kwh - r2.energy_kwh)
        why = []
        if diffs:
            why.append("%d step values differ" % len(diffs))
        if gap >= 1e-6:
            why.append("energy differs by %.6f kWh" % gap)
        if len(trace) != len(trace2):
            why.append("%d steps against %d" % (len(trace), len(trace2)))
        if r.violations != r2.violations:
            why.append("violations %d against %d" % (r.violations, r2.violations))
        # the battery values are compared to 1e-9, not exactly: the comparison is the second
        # evening in this process, and the power flow starts from where the first ended,
        # which moves the 14th digit of the mean Q (the battery calls themselves match bit
        # for bit over MQTT, checked call by call)
        if abs(r.battery_soc_end - r2.battery_soc_end) > 1e-9:
            why.append("battery SoC %r against %r" % (r.battery_soc_end, r2.battery_soc_end))
        if abs(r.battery_q_mean_kvar - r2.battery_q_mean_kvar) > 1e-9:
            why.append("battery mean Q %r against %r" % (r.battery_q_mean_kvar,
                                                         r2.battery_q_mean_kvar))
        same = not why
        if r.battery:
            print("battery SoC at the end: %s %.6f, in the simulator %.6f"
                  % ("Pi" if a.battery_on_pi else "this run", r.battery_soc_end,
                     r2.battery_soc_end))
        print("energy over MQTT %.6f kWh, in the simulator %.6f kWh; steps that differ %d"
              % (r.energy_kwh, r2.energy_kwh, len(diffs)))
        for d in diffs[:8]:
            print("   step %d  %s: Pi %r vs simulator %r" % d)
        for w in why:
            print("   differs: " + w)
        print("EQUIVALENT" if same else "NOT EQUIVALENT")
        result.update({"compare_energy_kwh": r2.energy_kwh, "differences": diffs[:50],
                       "compare_battery_soc_end": r2.battery_soc_end,
                       "compare_battery_q_mean_kvar": r2.battery_q_mean_kvar,
                       "why_not_equivalent": why, "equivalent": same})
    out = os.path.join(HERE, "results", "hil")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "%s_seed%d_%s_%gs_%g.json" % (time.strftime("%Y%m%d_%H%M%S"),
                                                        a.seed, a.controller, a.latency,
                                                        a.loss))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print("saved %s" % os.path.relpath(path, HERE))
    return 0 if (not a.compare or result.get("equivalent")) else 1


if __name__ == "__main__":
    sys.exit(main())
