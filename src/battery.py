"""The battery node.

STAND-IN for Gia's battery, BMS and EMS. It exists so the twin can carry a battery in the
power flow, stage S3 can run, and there is a settled interface for Gia's model to replace.
Same rule as the other nodes: a plain Python class, no MQTT inside.

What Table 7 and Table 1 of the plan ask for, and what this does about each:

    one unit at the feeder's electrical midpoint      placed by the twin, bus 686
    about two hours of evening peak demand            100 kWh against a ~48 kW peak
    four-quadrant inverter                            50 kVA, P and Q both ways
    volt-var and volt-watt per AS/NZS 4777.2          both, on the terminal voltage
    state of charge                                   tracked, with round-trip losses
    a biased SoC estimate (axis V4)                   reported SoC = true SoC + bias
    EMS reserve behaviour                             a setpoint input; on a normal day the
                                                      EMS asks for nothing, so the battery's
                                                      effect is its autonomous response

The interface is three calls, split this way on purpose:

    response(v_local, setpoint_kw) -> (p_kw, q_kvar)    no side effects
    commit(p_kw, minutes)                               updates the state of charge
    status() -> dict

Volt-var settles in seconds, so within a 5-minute step it is at steady state, and steady
state depends on the voltage the battery itself helps set. The twin finds it by iterating
response() against the power flow until Q stops moving, then calls commit() once. A single
step() that both answered and changed the state could not be iterated.

PROVISIONAL, for Gia to confirm against AS/NZS 4777.2:2020: the response set points below
are the Australia A region defaults as I understand them, and the sizing is mine.
"""
from dataclasses import dataclass, field


def _interp(x, pts):
    """Piecewise-linear lookup, flat beyond the end points."""
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


@dataclass
class BatterySpec:
    e_kwh: float = 100.0              # ~2 h of the ~48 kW evening peak (Table 7)
    s_kva: float = 50.0               # inverter rating
    p_max_kw: float = 50.0
    soc_min: float = 0.10
    soc_max: float = 0.95
    eta_charge: float = 0.95          # 0.95 each way, about 90% round trip
    eta_discharge: float = 0.95
    # AS/NZS 4777.2:2020, Australia A defaults. Q as a fraction of rated S, positive supplies
    # vars (raises voltage). PROVISIONAL.
    volt_var: list = field(default_factory=lambda: [(207.0, 0.44), (220.0, 0.0),
                                                     (240.0, 0.0), (258.0, -0.60)])
    # discharge (generation) volt-watt: fraction of rated P allowed. PROVISIONAL.
    volt_watt: list = field(default_factory=lambda: [(253.0, 1.0), (260.0, 0.2)])
    # charging volt-watt: fraction of rated charging allowed, cut at low voltage. PROVISIONAL.
    charge_volt_watt: list = field(default_factory=lambda: [(207.0, 0.2), (215.0, 1.0)])


class BatteryStandIn:
    def __init__(self, spec=None, soc0=0.6, soc_bias=0.0, enabled=True):
        self.spec = spec or BatterySpec()
        self.soc = soc0
        self.soc_bias = soc_bias           # V4: the BMS reports soc + bias
        self.enabled = enabled             # V5: battery present or not
        self.energy_in_kwh = 0.0           # for the energy balance check, V7
        self.energy_out_kwh = 0.0
        self.soc_start = soc0

    # -- the interface ---------------------------------------------------------

    def response(self, v_local, setpoint_kw=0.0):
        """P and Q the inverter would produce at this terminal voltage. No side effects.

        setpoint_kw is the EMS request: positive charges, negative discharges. Volt-watt
        trims it, the SoC limits cap it, and volt-var sets Q from whatever capacity is left.
        """
        if not self.enabled:
            return 0.0, 0.0
        s = self.spec
        p = max(-s.p_max_kw, min(s.p_max_kw, setpoint_kw))
        if p < 0:                                            # discharging
            p = max(p, -s.p_max_kw * _interp(v_local, s.volt_watt))
            if self.soc <= s.soc_min:
                p = 0.0
        elif p > 0:                                          # charging
            p = min(p, s.p_max_kw * _interp(v_local, s.charge_volt_watt))
            if self.soc >= s.soc_max:
                p = 0.0
        q_frac = _interp(v_local, s.volt_var)
        q_room = max(0.0, (s.s_kva ** 2 - p ** 2)) ** 0.5
        q_supply = max(-q_room, min(q_room, q_frac * s.s_kva))
        # in load convention negative kvar supplies vars
        return p, -q_supply

    def commit(self, p_kw, minutes):
        """Run at p_kw for `minutes` and update the state of charge."""
        if not self.enabled or minutes <= 0:
            return
        s = self.spec
        h = minutes / 60.0
        # Only the energy the cells can actually take or give is counted. Capping the SoC
        # while still booking the full flow would create or destroy energy, which is exactly
        # what validation item V7 checks for.
        if p_kw > 0:
            room = max(0.0, (s.soc_max - self.soc) * s.e_kwh)        # kWh the cells can store
            stored = min(p_kw * h * s.eta_charge, room)
            self.energy_in_kwh += stored / s.eta_charge                # at the terminals
            self.soc += stored / s.e_kwh
        elif p_kw < 0:
            avail = max(0.0, (self.soc - s.soc_min) * s.e_kwh)
            drawn = min(-p_kw * h / s.eta_discharge, avail)
            self.energy_out_kwh += drawn * s.eta_discharge
            self.soc -= drawn / s.e_kwh

    def status(self):
        return {"soc_true": self.soc,
                "soc_reported": min(1.0, max(0.0, self.soc + self.soc_bias)),
                "e_kwh": self.spec.e_kwh, "p_max_kw": self.spec.p_max_kw,
                "s_kva": self.spec.s_kva, "enabled": self.enabled}

    # convenience matching the interface first proposed in docs/INTERFACES.md
    def step(self, t, minutes, v_local, setpoint_kw=0.0):
        p, q = self.response(v_local, setpoint_kw)
        self.commit(p, minutes)
        return p, q
