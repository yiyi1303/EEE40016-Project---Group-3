"""The edge: charge points, their controller, and the meters the twin reads through.

STAND-IN for Lomitha's EV charge-point controller. It shows the shape the real one must
have: a plain Python class with no MQTT inside it. That one rule decides whether
integration works.

    ChargePointFleet   the controller logic. Pure Python, deterministic, no networking.
                       This is what Lomitha writes. The sweep imports it directly for the
                       thousands of simulated runs, and the Raspberry Pi runs the very same
                       class behind the MQTT wrapper in mqtt_edge.py for the hardware demo.

    InProcessEdge      the fleet plus the meters, called directly. Used by the sweep.

The twin talks to either through two calls, which are the whole edge interface:

    start_step(step, t_from, t_to, period_min) -> (samples, ev_status)
        samples: [(sent_minute, {connection: kW}), ...], one per telemetry sample in the
        window, each with the reading at its own time
    apply(setpoint)                -> Ack
        setpoint None, or one with fallback=True, means: charge on the local fallback

If the controller logic lived inside MQTT callbacks instead, the sweep could never run it,
and the results would describe a controller nobody built.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from messages import Ack  # noqa: E402


def select_entry(issued_step, step, horizon):
    """Which entry of a schedule issued at `issued_step` governs control step `step`, or
    None if the schedule does not cover it (not yet started, or run out).

    Entry k covers the k-th 5-minute interval after the schedule was issued (plan amendment
    25). A real charge point would read this off its own clock against each entry's
    interval; in simulated time the step count is that clock.
    """
    k = step - issued_step
    return k if 0 <= k < horizon else None


class ChargePointFleet:
    """Every charge point one edge node controls, and what each car still wants.

    Energy delivered is the edge's own state, because it is the charge point that knows
    how much it has put into the car. It reports that upward, and the twin plans with it.
    """

    def __init__(self, sessions, fallback_kw=1.4, uncovered_kw=None):
        self.sessions = {s.ev_name: s for s in sessions}
        self.delivered = {s.ev_name: 0.0 for s in sessions}
        self.fallback_kw = fallback_kw
        # what a car that arrived after the setpoint was issued may draw (amendment 22)
        self.uncovered_kw = fallback_kw if uncovered_kw is None else uncovered_kw

    def status(self, t):
        return {n: {"connected": s.arrival_min <= t,
                    "delivered_kwh": round(self.delivered[n], 9),
                    "wanted_kwh": s.energy_kwh}
                for n, s in self.sessions.items()}

    def apply(self, limit_kw, t, minutes, node="edge", step=0, issued_at=None,
              valid_from=None, valid_until=None):
        """Charge every car that is here and not full, at the limit or what it still needs.

        `limit_kw=None` means no setpoint arrived: the charge points use the local
        fallback, which is the edge's own safety net and the counterpart of the fixed
        export limit a CSIP-AUS inverter drops to when it loses its server.

        `issued_at` is when the setpoint was computed. A setpoint covers only the cars that
        were connected then. A car that plugged in afterwards charges at the fallback until
        a setpoint issued after its arrival reaches it. Without this, a held setpoint
        computed for ten cars was applied to twelve when a downlink message was lost, and
        the head cable reached 106% (notes/plan_amendments.md, item 22). What such a car
        draws is `uncovered_kw`, the fallback unless configured otherwise.

        `valid_from` and `valid_until` are the interval the limit was planned for (schema 2,
        amendment 25). Outside it the limit is not executed and the charge points use the
        fallback, as a 2030.5 device reverts to its DefaultDERControl when a control's
        interval ends. The twin always sends the entry for the current interval, so this
        is a guard that should never fire; tests/test_setpoint_schedule.py checks it does not.
        """
        fallback = limit_kw is None
        if not fallback and ((valid_from is not None and t < valid_from - 1e-9)
                             or (valid_until is not None and t >= valid_until - 1e-9)):
            fallback = True
            self.validity_fallbacks = getattr(self, "validity_fallbacks", 0) + 1
        kw = self.fallback_kw if fallback else limit_kw
        draws = {}
        for n, s in self.sessions.items():
            want = s.energy_kwh - self.delivered[n]
            if s.arrival_min <= t and want > 1e-9:
                car_kw = kw
                if not fallback and issued_at is not None and s.arrival_min > issued_at:
                    car_kw = min(kw, self.uncovered_kw)
                d = min(car_kw, want * 60.0 / minutes)
                self.delivered[n] += d * minutes / 60.0
                draws[n] = d
        return Ack(node=node, step=step, draws=draws, fallback=fallback)

    @property
    def total_kwh(self):
        return sum(self.delivered.values())

    @property
    def demanded_kwh(self):
        return sum(s.energy_kwh for s in self.sessions.values())


class InProcessEdge:
    """The fleet and the meters, called directly. What the sweep uses."""

    node = "edge"

    def __init__(self, fleet, meter_readings, step_min):
        self.fleet = fleet
        self.meter_readings = meter_readings    # callable: minute -> {connection: kW}
        self.step_min = step_min
        self._t = None
        self._step = None

    def start_step(self, step, t_from, t_to, period_min=0.5):
        self._t, self._step = t_to, step
        samples, t = [], t_from
        while True:
            t = round(t + period_min, 9)
            if t > t_to + 1e-9:
                break
            samples.append((t, self.meter_readings(int(t + 1e-9))))
        return samples, self.fleet.status(t_to)

    def apply(self, setpoint):
        limit = (None if setpoint is None or getattr(setpoint, "fallback", False)
                 else setpoint.limit_kw)
        issued = None if setpoint is None else setpoint.t_to
        return self.fleet.apply(limit, self._t, self.step_min, self.node, self._step, issued,
                                getattr(setpoint, "valid_from", None),
                                getattr(setpoint, "valid_until", None))

    @property
    def total_kwh(self):
        return self.fleet.total_kwh

    @property
    def demanded_kwh(self):
        return self.fleet.demanded_kwh

    def close(self):
        pass
