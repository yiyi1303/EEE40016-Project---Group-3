"""Turn a solved power flow into a pass or fail, and say which constraint is binding.

This is what the envelope search calls at every bisection step, so it has to be cheap and
it has to be decisive. Four constraints are enforced, per the research plan:

    voltage            AS 60038, 216.2 V to 253 V line to neutral
    cable current      against the ratings in config/cable_ratings.json
    transformer        apparent power against nameplate
    hot spot           IEC 60076-7, with thermal inertia carried between steps
    unbalance          voltage unbalance factor

`worst_margin` is the headroom on the tightest constraint, normalised so the constraints
are comparable: 1.0 is untouched, 0.0 is exactly at the limit, negative is a violation.
The envelope search bisects on the sign of that number.
"""
import json
import math
import os
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(HERE, "config", "study.json")
CABLES = os.path.join(HERE, "config", "cable_ratings.json")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------- thermal model

class ThermalModel:
    """IEC 60076-7 exponential hot-spot model, stepped through the study window.

    Thermal inertia matters here. A distribution transformer's oil time constant is about
    three hours, so an evening EV peak of an hour or two does not reach the steady-state
    temperature its loading implies. Judging each 5-minute step against a steady-state
    calculation would reject loadings the transformer could actually carry, which would
    bias the crossover point.
    """

    def __init__(self, params=None, ambient_c=None):
        p = params or _load(CABLES)["transformer_thermal"]
        self.p = p
        self.ambient = p["ambient_default_c"] if ambient_c is None else ambient_c
        self.d_oil = 0.0          # top-oil rise over ambient, K
        self.d_hot = 0.0          # hot-spot rise over top-oil, K
        self.settle(0.5)          # start from the steady state of a lightly loaded unit

    def steady_rises(self, k):
        """Steady-state top-oil and hot-spot rises at per-unit loading k."""
        p = self.p
        r = p["loss_ratio_R"]
        d_oil = p["top_oil_rise_rated_k"] * ((1.0 + r * k * k) / (1.0 + r)) ** p["oil_exponent_x"]
        d_hot = p["hot_spot_to_top_oil_gradient_k"] * k ** p["winding_exponent_y"]
        return d_oil, d_hot

    def settle(self, k):
        """Jump straight to the steady state, for initialising before a run."""
        self.d_oil, self.d_hot = self.steady_rises(k)
        return self.hot_spot()

    def step(self, k, minutes, ambient_c=None):
        """Advance the model by `minutes` at per-unit loading `k`."""
        p = self.p
        if ambient_c is not None:
            self.ambient = ambient_c
        oil_u, hot_u = self.steady_rises(k)
        tau_o = p["k11"] * p["tau_oil_min"]
        tau_w = p["k22"] * p["tau_winding_min"]
        self.d_oil += (oil_u - self.d_oil) * (1.0 - math.exp(-minutes / tau_o))
        self.d_hot += (hot_u - self.d_hot) * (1.0 - math.exp(-minutes / tau_w))
        return self.hot_spot()

    def hot_spot(self):
        return self.ambient + self.d_oil + self.d_hot

    def copy(self):
        """A detached copy, so the envelope search can try a step without committing to it."""
        c = ThermalModel(self.p, self.ambient)
        c.d_oil, c.d_hot = self.d_oil, self.d_hot
        return c


# ------------------------------------------------------------------------- the state

@dataclass
class NetworkState:
    ok: bool
    binding: str
    worst_margin: float
    violations: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    def __str__(self):
        head = "OK" if self.ok else "VIOLATION"
        return "%s | binding %s | margin %+.3f" % (head, self.binding, self.worst_margin)


class ConstraintSet:
    """The limits a network state is judged against.

    `security_factor` below 1 tightens every limit towards its nominal condition, giving
    a set of planning constraints that are stricter than the real ones. Two instances are
    used: a tightened set for computing the envelope, and the true set for judging what
    actually happened.

    The reason is that an envelope computed to be exactly maximal has, by construction,
    zero headroom. Applied to a network that has moved even slightly since the last
    telemetry arrived, it violates. Real operating envelopes are calculated with a margin
    for exactly this, and holding the margin on the constraint rather than on the power
    means it lands on whichever constraint is actually binding.
    """

    def __init__(self, config=None, cables=None, security_factor=1.0):
        cfg = config or _load(CONFIG)
        cab = cables or _load(CABLES)
        c = cfg["constraints"]
        f = float(security_factor)
        self.security_factor = f
        nominal = 0.5 * (c["voltage"]["min_v"] + c["voltage"]["max_v"])
        self.v_min = nominal - f * (nominal - c["voltage"]["min_v"])
        self.v_max = nominal + f * (c["voltage"]["max_v"] - nominal)
        self.vuf_max = f * c["voltage_unbalance"]["max_vuf_percent"]
        self.tx_max_pct = f * c["transformer_loading"]["max_loading_percent"]
        ambient = cab["transformer_thermal"]["ambient_default_c"]
        self.hot_max = ambient + f * (c["transformer_thermal"]["max_hot_spot_c"] - ambient)
        self.line_max_pct = f * c["cable_current"]["max_loading_percent"]
        self.ratings = {k: v["rating_a"] for k, v in cab["ratings"].items()}
        self.thermal_params = cab["transformer_thermal"]

    def line_rating(self, linecode):
        if linecode not in self.ratings:
            raise KeyError("no current rating for line code %r; add it to "
                           "config/cable_ratings.json" % linecode)
        return self.ratings[linecode]

    # -- the evaluation ---------------------------------------------------------

    def evaluate(self, solver, thermal=None, minutes=None, ambient_c=None,
                 skip=()):
        """Judge a solved network. `thermal` is advanced only if `minutes` is given."""
        feeder = solver.feeder
        margins, detail, violations = {}, {}, []

        # --- voltage, line to neutral, at every LV node
        volts = solver.node_voltages()
        lv_buses = {str(b) for b in feeder.buses}
        lv = {k: v for k, v in volts.items() if k[0] in lv_buses and v > 0}
        if lv:
            v_lo_key = min(lv, key=lv.get)
            v_hi_key = max(lv, key=lv.get)
            v_lo, v_hi = lv[v_lo_key], lv[v_hi_key]
            detail["v_min"] = (v_lo, "%s.%d" % v_lo_key)
            detail["v_max"] = (v_hi, "%s.%d" % v_hi_key)
            nominal = 0.5 * (self.v_min + self.v_max)
            margins["voltage_low"] = (v_lo - self.v_min) / (nominal - self.v_min)
            margins["voltage_high"] = (self.v_max - v_hi) / (self.v_max - nominal)
            if v_lo < self.v_min:
                violations.append("undervoltage %.1f V at %s.%d"
                                  % (v_lo, v_lo_key[0], v_lo_key[1]))
            if v_hi > self.v_max:
                violations.append("overvoltage %.1f V at %s.%d"
                                  % (v_hi, v_hi_key[0], v_hi_key[1]))

        # --- voltage unbalance factor, per bus with all three phases present
        if "unbalance" not in skip:
            worst_vuf, worst_bus = 0.0, None
            by_bus = {}
            for (bus, node), v in lv.items():
                by_bus.setdefault(bus, {})[node] = v
            for bus, ph in by_bus.items():
                if len(ph) < 3:
                    continue
                vuf = vuf_percent(ph[1], ph[2], ph[3])
                if vuf > worst_vuf:
                    worst_vuf, worst_bus = vuf, bus
            detail["vuf_max"] = (worst_vuf, worst_bus)
            margins["unbalance"] = (self.vuf_max - worst_vuf) / self.vuf_max
            if worst_vuf > self.vuf_max:
                violations.append("unbalance %.2f%% at bus %s" % (worst_vuf, worst_bus))

        # --- transformer apparent power
        tx_pct = solver.transformer_loading_percent()
        detail["transformer_pct"] = tx_pct
        margins["transformer"] = (self.tx_max_pct - tx_pct) / self.tx_max_pct
        if tx_pct > self.tx_max_pct:
            violations.append("transformer at %.1f%% of nameplate" % tx_pct)

        # --- hot spot, carrying thermal inertia between steps
        if thermal is not None:
            k = tx_pct / 100.0
            t = thermal.step(k, minutes, ambient_c) if minutes else thermal.hot_spot()
            detail["hot_spot_c"] = t
            span = self.hot_max - thermal.ambient
            margins["hot_spot"] = (self.hot_max - t) / span if span > 0 else 0.0
            if t > self.hot_max:
                violations.append("hot spot %.1f C" % t)

        # --- cable current
        if "cable" not in skip:
            currents = solver.line_currents()
            code_of = {l.name.upper(): l.linecode for l in feeder.lines}
            worst_pct, worst_line = 0.0, None
            for name, amps in currents.items():
                code = code_of.get(name.upper())
                if code is None:
                    continue
                pct = 100.0 * amps / self.line_rating(code)
                if pct > worst_pct:
                    worst_pct, worst_line = pct, name
            detail["cable_pct"] = (worst_pct, worst_line)
            margins["cable"] = (self.line_max_pct - worst_pct) / self.line_max_pct
            if worst_pct > self.line_max_pct:
                violations.append("cable %s at %.1f%% of rating" % (worst_line, worst_pct))

        binding = min(margins, key=margins.get) if margins else "none"
        worst = margins[binding] if margins else 0.0
        detail["margins"] = margins
        return NetworkState(ok=not violations, binding=binding, worst_margin=worst,
                            violations=violations, detail=detail)


def vuf_percent(va, vb, vc):
    """Voltage unbalance factor, negative over positive sequence, from magnitudes.

    Phase angles are assumed to be the balanced 0, -120, +120 degrees. On an LV feeder
    where unbalance comes from unequal single-phase loading rather than from a fault,
    this tracks the true factor closely and costs three complex operations instead of
    a full symmetrical component extraction at every node.
    """
    a = complex(-0.5, math.sqrt(3) / 2)
    va_c = complex(va, 0.0)
    vb_c = vb * complex(-0.5, -math.sqrt(3) / 2)
    vc_c = vc * a
    v1 = (va_c + a * vb_c + a * a * vc_c) / 3.0
    v2 = (va_c + a * a * vb_c + a * vc_c) / 3.0
    return 100.0 * abs(v2) / abs(v1) if abs(v1) > 0 else 0.0
