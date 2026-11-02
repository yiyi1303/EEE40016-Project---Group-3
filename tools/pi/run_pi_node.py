"""Run the EV charge-point controller (and, with --battery, the battery) on the Raspberry Pi.

    python3 run_pi_node.py --broker <address of the MQTT broker>

Options:
    --seed 7              which simulated evening (the laptop must use the same seed)
    --scenario s1         s1 main case (default), s2 stress case
    --team lomitha        Lomitha's controller (team/lomitha_fleet.py) instead of the
                          stand-in; --team gia uses Gia's battery (team/gia_battery.py) for
                          --battery; --team lomitha,gia or --team all for both
    --battery             also run the battery here, for the twin to call over MQTT (the
                          laptop side then needs --battery-on-pi)
    --fleet module:Class  any other controller class, e.g. team.lomitha_fleet:LomithaFleet
    --node edge           the node name (topics eee40016/.../edge)
    --retry 120           keep trying to reach the broker for this many seconds (default:
                          give up at once)
    --idle-exit 30        stop by itself once the evening is over: nothing from the laptop
                          for this many seconds after the first step (default: run until
                          Ctrl+C)
    --quiet               no line per step

Needs only Python 3. A copy of the MQTT library (paho-mqtt) travels in paho/ next to this
file, so nothing has to be installed. The 22 charge points are virtual: one controller
object runs them all, the way a site controller or gateway runs many chargers. Press Ctrl+C
to stop; the laptop is told the Pi went offline.
"""
import argparse
import importlib
import json
import os
import sys
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                 # this folder first: messages, edge, team/, paho/

TEAM_ON_PI = ("lomitha", "gia")          # the parts that can run here


def load_class(spec):
    module, _, name = spec.partition(":")
    if not name:
        raise SystemExit("--fleet must be module:Class, e.g. team.lomitha_fleet:LomithaFleet")
    try:
        return getattr(importlib.import_module(module), name)
    except ModuleNotFoundError as e:
        if e.name == "bms_industrial":
            raise SystemExit("Gia's battery needs team/bms_industrial.py and "
                             "team/a123_params.json, which are not in this package. Add them "
                             "to team/ on the laptop and rebuild (py tools/make_pi_package.py), "
                             "or run without gia in --team to use the stand-in battery.")
        raise


class Narrated:
    """Wraps the controller: prints one line per control step (unless quiet), and notes when
    the laptop last asked for something, so the runner can tell when the evening is over.
    Passes everything through unchanged."""

    def __init__(self, inner, quiet=False):
        self.inner = inner
        self.quiet = quiet
        self.last = None                 # time.monotonic() of the last step; None before

    def status(self, t):
        self.last = time.monotonic()
        return self.inner.status(t)

    def apply(self, limit_kw, t, minutes, node="edge", step=0, **kw):
        ack = self.inner.apply(limit_kw, t, minutes, node, step, **kw)
        self.last = time.monotonic()
        if not self.quiet:
            cars = sum(1 for d in ack.draws.values() if d > 1e-9)
            hh, mm = divmod(int(round(t)), 60)
            what = "fallback 1.4 kW  " if ack.fallback else "limit %4.1f kW   " % limit_kw
            print("step %2d  %02d:%02d  %s %2d cars charging, %5.1f kW in total"
                  % (step, hh, mm, what, cars, sum(ack.draws.values())), flush=True)
        return ack

    def __getattr__(self, name):
        return getattr(self.inner, name)


def team_names(spec):
    names = [n.strip().lower() for n in (spec or "").split(",") if n.strip()]
    if "all" in names:
        return set(TEAM_ON_PI)
    bad = [n for n in names if n not in TEAM_ON_PI]
    if bad:
        raise SystemExit("--team on the Pi takes %s or all (Hoang's part runs on the laptop); "
                         "got %s" % (", ".join(TEAM_ON_PI), ", ".join(bad)))
    return set(names)


def connect(make, label, a, deadline):
    """Make an MQTT node, retrying while the broker refuses, then wait until the broker has
    accepted it. Returns the started node."""
    unreachable = ("could not reach the broker at %s:%d (%%s).\n"
                   "  Check: same network as the broker? the address right? the broker "
                   "running? (laptop broker: py tools/broker.py, and allow Python through the "
                   "laptop's firewall; Pi broker: sudo systemctl status mosquitto)"
                   % (a.broker, a.port))
    said, node = False, None
    while node is None:
        try:
            node = make()
        except (OSError, ConnectionError) as e:
            if a.retry <= 0 or time.monotonic() >= deadline:
                raise SystemExit(unreachable % e)
            if not said:
                print("the broker is not answering yet; trying again for up to %.0f s ..."
                      % a.retry)
                said = True
            time.sleep(2)
    node.c.reconnect_delay_set(min_delay=1, max_delay=2)   # retry briskly if it drops
    node.start()
    # the socket is open; "connected" means the broker has accepted us
    if not node.connected.wait(min(3.0, max(0.0, deadline - time.monotonic()))):
        print("waiting for the broker to answer (%s) ..." % label)
        if not node.connected.wait(max(0.0, deadline - time.monotonic())):
            node.stop()
            raise SystemExit(unreachable % "no answer from a broker there")
    return node


def main():
    cfg = json.load(open(os.path.join(HERE, "pi_config.json"), encoding="utf-8"))
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--broker", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--node", default="edge")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--scenario", default=cfg.get("default_scenario", "s1"),
                    choices=("s1", "s2"))
    ap.add_argument("--team", default=None)
    ap.add_argument("--battery", action="store_true")
    ap.add_argument("--fleet", default=None)
    ap.add_argument("--retry", type=float, default=0.0)
    ap.add_argument("--idle-exit", type=float, default=0.0)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)       # each line at once, even through tee
    team = team_names(a.team)

    try:
        from mqtt_edge import PiNode, BatteryNode
    except RuntimeError as e:
        raise SystemExit(str(e))
    path = os.path.join(HERE, "sessions", "seed_%d_%s.json" % (a.seed, a.scenario))
    if not os.path.exists(path):
        raise SystemExit("no sessions for seed %d, scenario %s in sessions/ (rebuild the "
                         "package on the laptop with tools/make_pi_package.py)"
                         % (a.seed, a.scenario))
    sessions = [SimpleNamespace(**s) for s in
                json.load(open(path, encoding="utf-8"))["sessions"]]
    spec = a.fleet or ("team.lomitha_fleet:LomithaFleet" if "lomitha" in team
                       else "edge:ChargePointFleet")
    cls = load_class(spec)
    fleet = cls(sessions, cfg["fallback_kw"], cfg.get("uncovered_kw"))
    controller = Narrated(fleet, quiet=a.quiet)

    print("EEE40016 edge node '%s': %d charge points, controller %s.%s"
          % (a.node, len(sessions), cls.__module__, cls.__name__))
    bat_cls = None
    if a.battery:
        bat_cls = load_class("team.gia_battery:GiaBattery" if "gia" in team
                             else "battery:BatteryStandIn")
        print("battery here too: %s.%s" % (bat_cls.__module__, bat_cls.__name__))
    elif "gia" in team:
        print("(--team gia only matters with --battery: without it the battery runs on the "
              "laptop)")
    print("seed %d, scenario %s; connecting to the broker at %s:%d ..."
          % (a.seed, a.scenario, a.broker, a.port))
    # retrying only when asked to; even then, a broker that does answer gets 10 s to say so
    deadline = time.monotonic() + max(a.retry, 10.0)
    nodes = [connect(lambda: PiNode(controller, a.node, a.broker, a.port,
                                    cfg["control_period_minutes"],
                                    sample_min=cfg["sample_min"]), "charge points", a,
                     deadline)]
    battery_node = None
    if bat_cls is not None:
        def narrate(b, p_kw, q_kvar):
            if not a.quiet:
                print("battery  SoC %5.1f%%  P %6.1f kW  Q %6.1f kvar"
                      % (100 * b.soc, p_kw, q_kvar), flush=True)
        battery_node = connect(lambda: BatteryNode(bat_cls, broker=a.broker, port=a.port,
                                                   narrate=narrate), "battery", a, deadline)
        nodes.append(battery_node)
    print("connected. Waiting for the laptop to start an evening (Ctrl+C to stop).")
    try:
        while True:
            time.sleep(0.5)
            stamps = [s for s in (controller.last,
                                  battery_node.last if battery_node else None) if s]
            if a.idle_exit and stamps and time.monotonic() - max(stamps) > a.idle_exit:
                print("nothing from the laptop for %.0f s: the evening is over, stopping"
                      % a.idle_exit)
                break
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        for n in nodes:
            n.stop()


if __name__ == "__main__":
    main()
