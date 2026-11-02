"""Drop a teammate's class into the study without editing anyone else's code.

Each of the three teammates' parts has a stand-in in src/ and a default slot on StudyRun:

    StudyRun.link_cls       Hoang     uplink injector and trust      (telemetry.TelemetryLink)
    StudyRun.downlink_cls   Hoang     downlink injector               (telemetry.DownlinkChannel)
    StudyRun.battery_cls    Gia       battery, BMS and EMS            (battery.BatteryStandIn)
    StudyRun.fleet_cls      Lomitha   charge-point controller         (edge.ChargePointFleet)

A replacement is named as "module:Class", relative to the project folder or src/, for
example "team.hoang_link:HoangLink". Starting points for all four are in team/.

    from plugins import load_class, use
    use(study, link="team.hoang_link:HoangLink", battery="team.gia_battery:GiaBattery")

On the command line, --team hoang (or gia, lomitha, a comma-separated list, or all) picks
the files in team/ without typing the class names; --link, --downlink, --battery and
--fleet name any other class and win over --team.
"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SLOTS = ("link", "downlink", "battery", "fleet")
TEAM = {"hoang": {"link": "team.hoang_link:HoangLink",
                  "downlink": "team.hoang_link:HoangDownlink"},
        "lomitha": {"fleet": "team.lomitha_fleet:LomithaFleet"},
        "gia": {"battery": "team.gia_battery:GiaBattery"}}
_HELP = {"link": "Hoang's uplink class", "downlink": "Hoang's downlink class",
         "battery": "Gia's battery class", "fleet": "Lomitha's charge-point controller class"}


def load_class(spec):
    """The class named by "module:Class"."""
    if not spec or ":" not in spec:
        raise ValueError("name a class as module:Class, e.g. team.hoang_link:HoangLink "
                         "(got %r)" % (spec,))
    module, name = spec.split(":", 1)
    for p in (HERE, os.path.join(HERE, "src")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        return getattr(importlib.import_module(module), name)
    except AttributeError:
        raise SystemExit("%s has no class %s" % (module, name))


def use(study, link=None, downlink=None, battery=None, fleet=None):
    """Point a StudyRun at the named classes; anything left as None keeps its stand-in.
    Returns a short description of what is in use, for logs."""
    for slot, spec in (("link_cls", link), ("downlink_cls", downlink),
                       ("battery_cls", battery), ("fleet_cls", fleet)):
        if spec:
            setattr(study, slot, load_class(spec))
    return ", ".join("%s=%s.%s" % (slot[:-4], getattr(study, slot).__module__,
                                   getattr(study, slot).__name__)
                     for slot in ("link_cls", "downlink_cls", "battery_cls", "fleet_cls"))


def add_arguments(ap, slots=SLOTS):
    """Add --team and a module:Class option for each slot to an argparse parser."""
    ap.add_argument("--team", metavar="NAMES",
                    help="use teammates' files in team/: %s (comma separated) or all"
                    % ", ".join(sorted(TEAM)))
    for s in slots:
        ap.add_argument("--" + s, metavar="MODULE:CLASS", help=_HELP[s] + ", as module:Class")


def specs(args, slots=SLOTS):
    """{slot: "module:Class"} from parsed --team and per-slot options, keeping only the
    given slots; a per-slot option wins over --team."""
    out = {}
    names = [n.strip().lower() for n in (getattr(args, "team", None) or "").split(",")
             if n.strip()]
    for n in (sorted(TEAM) if "all" in names else names):
        if n not in TEAM:
            raise SystemExit("--team: no teammate called %r (use %s, or all)"
                             % (n, ", ".join(sorted(TEAM))))
        out.update(TEAM[n])
    for s in SLOTS:
        if getattr(args, s, None):
            out[s] = getattr(args, s)
    return {s: v for s, v in out.items() if s in slots}
