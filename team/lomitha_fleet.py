"""Lomitha: the EV charge-point controller, built on Lomitha's own code in team/lomitha/.

    ev_charge_point_gateway.py   EVChargePointGateway: one charge point. Takes a limit (a
                                 DOE envelope), applies the rating and the IEC 61851 pilot
                                 rules (6 A minimum, 0.6 A steps, always rounded down),
                                 meters the energy, handles faults and the fallback.
    charging_session.py          EVSessionPlant: the car on the charge point, with its own
                                 acceptance (taper above 80% state of charge).

This file is the adapter between that code and the twin. It runs one gateway and one car
per charge point, all 22 from one object, and keeps the interface the twin relies on
(docs/INTERFACES.md):

    R1  a limit is executed only inside [valid_from, valid_until): checked here for the start,
        and by the gateway's own watchdog for the end (half-open, as in 2030.5)
    R2  the newest schedule wins: each envelope gets a higher sequence number, and the
        gateway rejects anything out of order
    R3  when nothing valid is in force the gateway falls back to 1.4 kW by itself: each
        envelope covers one 5-minute interval, so if no new one arrives the old one has
        ended and the watchdog reverts (hold 0 s, fallback 1.4 kW from the study config)
    R4  a car that plugged in after the setpoint was issued gets uncovered_kw (1.4 kW)
    R5  no derating of its own: the twin has already weighed trust into the limit
        (controller B), so the gateway runs its "apply as received" preset and is handed
        trust 1.0; contracting by trust again here would count it twice

Used by the experiments (in process) and on the Raspberry Pi (behind run_pi_node.py):
    python3 run_pi_node.py --broker <address> --team lomitha
    py tools/pi_session.py --pi <user>@<Pi address> --team lomitha
    py tools/run_with_pi.py --broker <address> --compare --team lomitha

Changed in Lomitha's files for integration, and marked there: validity intervals made
half-open (R1), and numpy made optional so the Pi needs nothing installed. Everything else
is as Lomitha wrote it.
"""
import os
import sys

_LOMITHA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lomitha")
if _LOMITHA not in sys.path:
    # imported under their own top-level names, as charging_session.py expects: a second
    # copy under another name would have its own PlugState enum (see the gateway's __main__)
    sys.path.insert(0, _LOMITHA)

from ev_charge_point_gateway import (ChargePointParams, ControllerMode,  # noqa: E402
                                     Envelope, EVChargePointGateway, config_for)
from charging_session import EVSessionPlant, SessionSpec, VehicleParams  # noqa: E402
from messages import Ack                                                 # noqa: E402

EDGE_TIMEOUT_MIN = 15.0       # config/study.json controller_settings.edge_fallback_timeout_min
DEPART_S = 31 * 3600.0        # cars stay plugged in past the window (Lomitha's 07:00 departure)


def _vehicle(s):
    """SessionSpec for one of the twin's sessions. The twin's sessions say when a car
    arrives and how much it wants, not its battery, which the taper needs. CHOSEN, after
    Lomitha's own placeholders: charge to 90%, a 60 kWh battery, or a larger one if the car
    wants more than 48 kWh, so the arrival state of charge never falls below 10%."""
    e = max(0.0, float(s.energy_kwh))
    battery = max(60.0, e / 0.8)
    return SessionSpec(s.ev_name, arrival_s=float(s.arrival_min) * 60.0, departure_s=DEPART_S,
                       energy_required_kwh=e, battery_kwh=battery,
                       soc_arrival=0.9 - e / battery)


class LomithaFleet:
    """Every charge point on the street, run from one controller.

    Built as LomithaFleet(sessions, fallback_kw=1.4, uncovered_kw=None). `sessions` is a
    list with one entry per charge point: .ev_name, .arrival_min (when the car plugs in,
    minutes past midnight) and .energy_kwh (what it wants). cp and vp replace Lomitha's
    charge-point and vehicle parameters (tests use them; leave them out otherwise).
    """

    def __init__(self, sessions, fallback_kw=1.4, uncovered_kw=None, cp=None, vp=None):
        self.sessions = {s.ev_name: s for s in sessions}
        self.fallback_kw = fallback_kw
        self.uncovered_kw = fallback_kw if uncovered_kw is None else uncovered_kw
        self.cp = cp or ChargePointParams()
        # one preset for every study controller: A, B and C are chosen in the twin, which
        # sends the finished limit. Hold 0 s and fallback 1.4 kW per R1, R3 (Lomitha's
        # defaults were a 60 s hold and a 7.2 kW fallback, which this feeder cannot carry).
        cfg = config_for(ControllerMode.BINARY_FALLBACK, fallback_kw=fallback_kw,
                         hold_s=0.0, rx_timeout_s=EDGE_TIMEOUT_MIN * 60.0)
        self.gateways = {n: EVChargePointGateway(self.cp, cfg, n) for n in self.sessions}
        self.cars = {n: EVSessionPlant(_vehicle(s), vp) for n, s in self.sessions.items()}
        self.seq = 0
        self.validity_fallbacks = 0
        self.last_results = {}            # the gateway's Result per charge point, last step

    def status(self, t):
        """Every charge point at simulated time t (minutes). The twin plans with this."""
        return {n: {"connected": s.arrival_min <= t,
                    "delivered_kwh": round(self.gateways[n].run_energy_kwh, 9),
                    "wanted_kwh": s.energy_kwh}
                for n, s in self.sessions.items()}

    def apply(self, limit_kw, t, minutes, node="edge", step=0, issued_at=None,
              valid_from=None, valid_until=None):
        """Charge for `minutes` from simulated minute t. limit_kw None: no valid setpoint,
        so the gateways fall back. Returns messages.Ack with what each car really drew."""
        now, dt = t * 60.0, minutes * 60.0
        fallback = limit_kw is None
        if not fallback and ((valid_from is not None and t < valid_from - 1e-9)
                             or (valid_until is not None and t >= valid_until - 1e-9)):
            fallback = True                       # R1; the twin never sends this, a guard
            self.validity_fallbacks += 1
        if not fallback:
            end = now + dt if valid_until is None else min(valid_until * 60.0, now + dt)
            for n, s in self.sessions.items():
                kw = limit_kw
                if issued_at is not None and s.arrival_min > issued_at:
                    kw = min(kw, self.uncovered_kw)                       # R4
                self.seq += 1
                self.gateways[n].receive(Envelope(
                    self.seq, (issued_at if issued_at is not None else t) * 60.0, n,
                    kw, 1.0, end), now)                                   # R2, R5
        # else: nothing new arrives, the last envelope ended at `now`, and each gateway's
        # watchdog reverts to the fallback on its own (R3)
        v = self.cp.v_nominal      # the twin sends no voltages yet: Lomitha's 230 V default
        draws = {}
        for n, gw in self.gateways.items():
            car = self.cars[n]
            here = car.plugged(now) and not car.complete
            r = gw.step(car.measure(now, v), now)
            p = car.apply(r.i_pilot_a, v, dt, now)
            gw.meter(p, dt)
            self.last_results[n] = r
            if here:
                draws[n] = p
        return Ack(node=node, step=step, draws=draws, fallback=fallback)

    @property
    def total_kwh(self):
        return sum(gw.run_energy_kwh for gw in self.gateways.values())

    @property
    def demanded_kwh(self):
        return sum(s.energy_kwh for s in self.sessions.values())
