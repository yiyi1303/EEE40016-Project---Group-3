"""Checks for Lomitha's charge-point controller as integrated (team/lomitha_fleet.py).

    py tests/test_lomitha_adapter.py

1. The adapter keeps the interface. With the IEC 61851 pilot rules and the car's taper
   switched off (pilot steps of 1e-9 A, no 6 A minimum, no taper), LomithaFleet must give
   the stand-in's answer: the same energy to within 0.001 kWh and the same violations and
   fallbacks, on five evenings that exercise schedules, fallbacks, late cars and the
   static limit. PASS or FAIL.
2. What Lomitha's model changes. The same evenings with Lomitha's real settings, beside
   the stand-in: energy delivered, steps that broke a limit, fallback steps. Reported, not
   judged; the pilot rules can only lower a draw, never raise it above the limit.
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, HERE)
from sweep import StudyRun                                     # noqa: E402
import controllers                                             # noqa: E402
from team.lomitha_fleet import LomithaFleet                    # noqa: E402
from ev_charge_point_gateway import ChargePointParams          # noqa: E402
from charging_session import VehicleParams                     # noqa: E402

STATIC_KW = 2.5               # seed 7's calibrated fixed limit
CASES = [("B", 60, 0.10), ("C", 300, 0.20), ("B", 600, 0.10), ("B", 0, 0.40), ("A", 0, 0.0)]
SEED = 7


class IdealLomitha(LomithaFleet):
    """Lomitha's controller with the pilot quantisation and the taper switched off."""

    def __init__(self, sessions, fallback_kw=1.4, uncovered_kw=None):
        super().__init__(sessions, fallback_kw, uncovered_kw,
                         cp=ChargePointParams(i_min_a=0.0, i_step_a=1e-9),
                         vp=VehicleParams(obc_kw=22.0, taper_start_soc=0.999999))


def run(fleet_cls, key, lat, loss):
    st = StudyRun()
    st.fleet_cls = fleet_cls
    c = controllers.build(st.cfg, STATIC_KW)[key]
    return st.run(c, lat, loss, SEED)


def main():
    print("1. adapter against the stand-in, quantisation and taper off (seed %d)" % SEED)
    ok = True
    rows = []
    for key, lat, loss in CASES:
        base = run(StudyRun.fleet_cls, key, lat, loss)
        ideal = run(IdealLomitha, key, lat, loss)
        real = run(LomithaFleet, key, lat, loss)
        same = (abs(base.energy_kwh - ideal.energy_kwh) < 1e-3
                and base.violations == ideal.violations and base.fallbacks == ideal.fallbacks)
        ok &= same
        print("   %s %4ds %3.0f%%   stand-in %.3f kWh, %d viol, %d fallback   ideal %.3f "
              "kWh, %d viol, %d fallback   %s"
              % (key, lat, loss * 100, base.energy_kwh, base.violations, base.fallbacks,
                 ideal.energy_kwh, ideal.violations, ideal.fallbacks,
                 "same" if same else "DIFFERENT"))
        rows.append((key, lat, loss, base, real))
    print("   %s\n" % ("PASS" if ok else "FAIL"))

    print("2. Lomitha's real settings (6 A minimum, 0.6 A steps, taper above 80%) "
          "beside the stand-in")
    print("   %-14s %22s %22s" % ("", "stand-in", "Lomitha"))
    for key, lat, loss, base, real in rows:
        print("   %s %4ds %3.0f%%   %8.2f kWh %2d viol    %8.2f kWh %2d viol  (%+.1f%%)"
              % (key, lat, loss * 100, base.energy_kwh, base.violations, real.energy_kwh,
                 real.violations, 100 * (real.energy_kwh / base.energy_kwh - 1)))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
