"""
EV charge point gateway: the edge controller for one charging connection. Applies a
Dynamic Operating Envelope (DOE) import limit received from the digital twin, or the
local fallback rule when no valid envelope is available, and turns the result into an
IEC 61851 control pilot current the vehicle will actually accept.

Sign convention (connection point / charge point AC terminals):
    P > 0  -> import (charging)       I > 0 -> import
    There is no export from an EV charge point in this study. P is never negative.

Priority (highest first):
    1. Plug state and hard limits             -> not plugged, pilot fault, circuit rating
    2. Charge point rating and IEC 61851      -> 7.2 kW cap, 6 A floor, pilot quantisation
    3. DOE envelope from the twin             -> p_limit_kw, contracted by trust (mode B),
                                                 held then replaced by fallback when stale
    4. Session energy requirement and taper   -> the vehicle's own acceptance, the "wish"

Pipeline per control cycle:
    validate (receive) -> hard limits -> watchdog -> trust -> rating -> quantise -> meter

What this node does NOT do: compute trust (comms node), inject degradation (comms node),
compute envelopes (twin node). Trust arrives inside the envelope and is consumed as given.

Three controllers under test are presets of the same gateway (see config_for()):
    A STATIC           envelope ignored, rating only
    B TRUST_WEIGHTED   envelope contracted toward a floor as trust falls, HOLD then FALLBACK
    C BINARY_FALLBACK  envelope as received, immediate FALLBACK on timeout (hold_s = 0)
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable, Optional


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------
class State(Enum):
    NORMAL = "NORMAL"      # envelope fresh and not binding below rating
    DERATED = "DERATED"    # envelope fresh and binding below rating
    HOLD = "HOLD"          # envelope stale, holding last accepted limit
    FALLBACK = "FALLBACK"  # stale too long (or none yet), local fallback rule applies
    FAULT = "FAULT"        # hard limit tripped, pilot off


class PlugState(Enum):
    # String values are the I1 wire format in docs/02-interfaces.md. Do not change.
    UNPLUGGED = "unplugged"
    PLUGGED_IDLE = "plugged_idle"
    CHARGING = "charging"
    COMPLETE = "complete"


class ControllerMode(Enum):
    STATIC = "A_STATIC"
    TRUST_WEIGHTED = "B_TRUST_WEIGHTED"
    BINARY_FALLBACK = "C_BINARY_FALLBACK"


class LimitScope(Enum):
    # Open decision raised in NOTES.md (D9): docs/02 says p_limit_kw is the import limit
    # "at the connection point", but this node does not meter household load and D6 says
    # allocation is per charging connection. Default treats the limit as the charge point's.
    CHARGE_POINT = "charge_point"
    CONNECTION_POINT = "connection_point"


@dataclass
class ChargePointParams:
    rated_kw: float = 7.2          # static cap, docs/00 and D9 (EV Council guideline)
    circuit_a: float = 32.0        # CHOSEN: typical single phase circuit behind a 7.2 kW unit
    v_nominal: float = 230.0       # AS 60038 nominal, used only if measured V is unusable
    i_min_a: float = 6.0           # IEC 61851-1 minimum pilot current (10 % duty), docs/01
    i_step_a: float = 0.6          # IEC 61851-1: 0.6 A per 1 % duty in the 10..85 % band, docs/01
    overcurrent_margin: float = 1.10  # CHOSEN: measured I above circuit_a * this trips FAULT


@dataclass
class GatewayConfig:
    mode: ControllerMode = ControllerMode.TRUST_WEIGHTED
    rx_timeout_s: float = 90.0     # CHOSEN: three missed I2 messages at the 30 s rate in docs/02
    hold_s: float = 60.0           # CHOSEN: hold last limit this long after it goes stale
    fallback_kw: float = 7.2       # D1 default: static cap. Arguably a sweep axis of its own.
    trust_floor_kw: float = 1.5    # CHOSEN: B contracts toward this. 1.5 kW echoes SAPN [2]
    max_limit_kw: float = 50.0     # CHOSEN: sanity bound, anything above is a bad message
    reject_expired_on_arrival: bool = True   # NOTES.md: added rejection rule, flagged
    limit_scope: LimitScope = LimitScope.CHARGE_POINT   # NOTES.md D9
    tol_kw: float = 1e-6


def config_for(mode: ControllerMode, **overrides) -> GatewayConfig:
    """Preset config for each controller under test. Overrides apply on top."""
    if mode is ControllerMode.STATIC:
        cfg = GatewayConfig(mode=mode)
    elif mode is ControllerMode.TRUST_WEIGHTED:
        cfg = GatewayConfig(mode=mode)
    elif mode is ControllerMode.BINARY_FALLBACK:
        # Deployed practice: immediate reversion to the static cap once the timeout expires.
        cfg = GatewayConfig(mode=mode, hold_s=0.0, fallback_kw=7.2)
    else:
        raise ValueError(mode)
    return replace(cfg, **overrides)


@dataclass
class Envelope:
    """I2 downlink message (docs/02). Field names match the wire format."""
    seq: int
    timestamp: float               # sender's simulated clock, s. Never used for validity.
    connection_id: str
    p_limit_kw: float
    trust: float                   # 0..1, computed by the comms node
    valid_until: float             # simulated s

    @classmethod
    def from_json(cls, payload: str | dict) -> "Envelope":
        d = json.loads(payload) if isinstance(payload, str) else payload
        return cls(int(d["seq"]), float(d["timestamp"]), str(d["connection_id"]),
                   float(d["p_limit_kw"]), float(d["trust"]), float(d["valid_until"]))


@dataclass
class Measurements:
    v_terminal: float              # V, at the charge point terminals
    i_a: float                     # A, measured line current
    p_kw: float                    # kW, measured real power, > 0 import
    q_kvar: float                  # kvar
    plug_state: PlugState
    pilot_fault: bool = False      # IEC 61851 state E/F reported by pilot hardware
    # Vehicle's own acceptance limit (taper, remaining energy). inf when unknown. Under
    # plain IEC 61851 the charge point cannot see this; it is used for audit and the
    # expected-power estimate only, never to raise the pilot.
    ev_accept_kw: float = math.inf
    site_load_kw: float = 0.0      # only used when limit_scope is CONNECTION_POINT


@dataclass
class Result:
    i_pilot_a: float               # pilot current offered to the vehicle
    p_offered_kw: float            # i_pilot at measured V
    p_expected_kw: float           # min(offered, vehicle acceptance)
    state: State
    reasons: list = field(default_factory=list)
    limit_received_kw: float = math.nan   # raw p_limit_kw of the envelope in use
    limit_applied_kw: float = math.nan    # after trust, hold or fallback
    trust: float = math.nan
    envelope_age_s: float = math.nan      # local now minus local receive time
    floor_stop: bool = False       # non zero limit quantised to zero by the 6 A floor


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def quantise_pilot(i_target_a: float, cp: ChargePointParams) -> float:
    """Largest pilot current on the IEC 61851 grid not above i_target_a, or 0 below the floor.

    Floor rather than round: rounding up would exceed the envelope. The discontinuity at
    i_min_a is deliberate and must not be smoothed: 5.9 A of headroom is 0 A of charging.
    """
    if not math.isfinite(i_target_a) or i_target_a < cp.i_min_a:
        return 0.0
    # Grid is integer duty cycle percent, so currents are whole multiples of i_step_a.
    # The small epsilon stops 6.0 / 0.6 landing on 9.999... and dropping a step.
    k = math.floor(i_target_a / cp.i_step_a + 1e-9)
    return max(cp.i_min_a, k * cp.i_step_a)


def watchdog(now: float, rx_time: Optional[float], valid_until: Optional[float],
             cfg: GatewayConfig) -> tuple[State, str]:
    """Freshness from LOCAL receive time and valid_until. Never the sender clock.

    The envelope goes stale at whichever comes first: valid_until passes, or nothing new
    has been received for rx_timeout_s. HOLD covers [onset, onset + hold_s), FALLBACK after.

    Intervals are half-open, as the shared interface requires (docs/INTERFACES.md R1: a
    limit is executed only inside [valid_from, valid_until), the IEEE 2030.5 convention): at
    exactly valid_until the envelope has ended. [Changed for integration: this used closed
    intervals, so a limit stayed in force for one extra step at the 5-minute boundary.]
    """
    if rx_time is None:
        return State.FALLBACK, "NO_ENVELOPE_YET"
    onset = min(valid_until, rx_time + cfg.rx_timeout_s)
    if now < onset:
        return State.NORMAL, ""
    why = "ENVELOPE_EXPIRED" if valid_until <= rx_time + cfg.rx_timeout_s else "RX_TIMEOUT"
    if now - onset < cfg.hold_s:
        return State.HOLD, why + "_HOLD"
    return State.FALLBACK, why + "_FALLBACK"


def trust_contract(p_limit_kw: float, trust: float, floor_kw: float) -> float:
    """Controller B: contract the envelope linearly toward floor_kw as trust falls.

    Linear is a CHOSEN shape; the brief only says "smoothly". Never raises a limit that is
    already below the floor, because trust can only make the node more conservative.
    """
    if p_limit_kw <= floor_kw:
        return p_limit_kw
    return floor_kw + clamp(trust, 0.0, 1.0) * (p_limit_kw - floor_kw)


def hard_limits(cp: ChargePointParams, m: Measurements) -> list:
    """Return fault reasons (empty if healthy)."""
    f = []
    if m.pilot_fault:
        f.append("PILOT_FAULT")
    if m.i_a > cp.circuit_a * cp.overcurrent_margin:
        f.append("OVERCURRENT")
    return f


def usable_voltage(cp: ChargePointParams, v: float) -> float:
    # A dead or missing voltage reading must not produce a huge current from kW / V.
    return v if (math.isfinite(v) and v > 0.5 * cp.v_nominal) else cp.v_nominal


# --------------------------------------------------------------------------
# The gateway
# --------------------------------------------------------------------------
class EVChargePointGateway:
    def __init__(self, cp: ChargePointParams, cfg: GatewayConfig, connection_id: str,
                 sensor_hook: Optional[Callable[[Measurements, float], Measurements]] = None):
        self.cp, self.cfg, self.connection_id = cp, cfg, connection_id
        self.last_env: Envelope | None = None
        self.last_env_rx_time = None     # LOCAL receive time (not sender clock)
        self.last_seq = -1
        self.fault_latched: list = []
        # D2: stale meter simulation is assumed to live in the comms injector. This hook
        # lets it move into the local measurement pipeline without touching anything else.
        self.sensor_hook = sensor_hook
        self.tx_seq = 0
        # Metering. Session energy resets on each plug-in; run energy never resets.
        self.session_energy_kwh = 0.0
        self.run_energy_kwh = 0.0
        self.session_energies_kwh: list = []
        self._plugged = False

    # -- envelope intake ------------------------------------------------
    def receive(self, env: Envelope, now: float) -> tuple[bool, str]:
        """Validate an I2 envelope; accept only if sane, ours, ordered and not expired."""
        if not all(map(math.isfinite, (env.p_limit_kw, env.trust, env.valid_until, env.timestamp))):
            return False, "REJECT_NAN"
        if env.connection_id != self.connection_id:
            return False, "REJECT_WRONG_CONNECTION"
        if env.p_limit_kw < 0 or env.p_limit_kw > self.cfg.max_limit_kw:
            return False, "REJECT_RANGE"
        if not 0.0 <= env.trust <= 1.0:
            return False, "REJECT_TRUST_RANGE"
        if env.seq <= self.last_seq:
            # D7: at 600 s latency two envelopes are in flight; an old one must not win.
            return False, "REJECT_OUT_OF_ORDER"
        # half-open validity (see watchdog): an envelope arriving at valid_until has ended
        if self.cfg.reject_expired_on_arrival and now >= env.valid_until:
            return False, "REJECT_EXPIRED"
        self.last_seq, self.last_env, self.last_env_rx_time = env.seq, env, now
        return True, "ACCEPTED"

    def reset_fault(self, m: Measurements) -> bool:
        """Operator reset; only succeeds if the condition has cleared."""
        if not hard_limits(self.cp, m):
            self.fault_latched.clear()
            return True
        return False

    # -- level 3: which limit applies -------------------------------------
    def _envelope_limit(self, now: float, reasons: list):
        """Return (state, limit_received_kw, limit_applied_kw, trust, age_s)."""
        cfg = self.cfg
        if cfg.mode is ControllerMode.STATIC:
            # Controller A consumes no telemetry, so degradation cannot reach it.
            return State.NORMAL, math.nan, self.cp.rated_kw, math.nan, math.nan

        env = self.last_env
        state, why = watchdog(now, self.last_env_rx_time,
                              env.valid_until if env else None, cfg)
        if why:
            reasons.append(why)
        if env is None:
            return state, math.nan, cfg.fallback_kw, math.nan, math.nan

        age = now - self.last_env_rx_time
        if state is State.FALLBACK:
            return state, env.p_limit_kw, cfg.fallback_kw, env.trust, age

        limit = env.p_limit_kw
        if cfg.mode is ControllerMode.TRUST_WEIGHTED:
            limit = trust_contract(limit, env.trust, cfg.trust_floor_kw)
            if limit < env.p_limit_kw - cfg.tol_kw:
                reasons.append("TRUST_CONTRACT")
        return state, env.p_limit_kw, limit, env.trust, age

    # -- main control step ---------------------------------------------
    def step(self, m: Measurements, now: float) -> Result:
        cp, cfg = self.cp, self.cfg
        reasons: list = []
        self._track_session(m.plug_state)

        # 1a. Hard limits: latch and turn the pilot off
        faults = hard_limits(cp, m)
        if faults:
            self.fault_latched = sorted(set(self.fault_latched) | set(faults))
        if self.fault_latched:
            return Result(0.0, 0.0, 0.0, State.FAULT, list(self.fault_latched))

        # 3 is evaluated before 1b/2 so that comms state is logged even with no car present;
        # the per state period counts in docs/04 should not depend on plug state.
        state, lim_rx, lim_kw, trust, age = self._envelope_limit(now, reasons)

        # 1b. Not plugged in: nothing to offer
        if m.plug_state is PlugState.UNPLUGGED:
            reasons.append("NOT_PLUGGED")
            return Result(0.0, 0.0, 0.0, state, reasons, lim_rx, lim_kw, trust, age)

        if cfg.limit_scope is LimitScope.CONNECTION_POINT:
            lim_kw = max(0.0, lim_kw - m.site_load_kw)
            reasons.append("SITE_LOAD_SUBTRACTED")

        # 1c + 2. Circuit rating, charge point rating, envelope, all as current at measured V
        v = usable_voltage(cp, m.v_terminal)
        i_circuit = cp.circuit_a
        i_rating = cp.rated_kw * 1000.0 / v
        i_env = lim_kw * 1000.0 / v
        i_target = min(i_circuit, i_rating, i_env)
        if i_env < min(i_circuit, i_rating):
            reasons.append("FALLBACK_LIMIT" if state is State.FALLBACK else "ENVELOPE_CLIP")
        elif i_circuit < i_rating:
            reasons.append("CIRCUIT_LIMIT")

        i_pilot = quantise_pilot(i_target, cp)
        floor_stop = False
        if i_pilot == 0.0 and i_target > 0.0:
            reasons.append("BELOW_MIN_CURRENT")
            floor_stop = True
        p_offered = v * i_pilot / 1000.0

        # 4. The vehicle's own acceptance. Unused headroom is not energy.
        if m.plug_state is PlugState.COMPLETE:
            reasons.append("SESSION_COMPLETE")
            p_expected = 0.0
            floor_stop = False    # stopped because full, not because of the floor
        else:
            p_expected = min(p_offered, max(0.0, m.ev_accept_kw))
            if p_expected < p_offered - cfg.tol_kw:
                reasons.append("EV_TAPER")

        if state is State.NORMAL and lim_kw < cp.rated_kw - cfg.tol_kw:
            state = State.DERATED
        return Result(i_pilot, p_offered, p_expected, state, reasons,
                      lim_rx, lim_kw, trust, age, floor_stop)

    # -- metering ---------------------------------------------------------
    def _track_session(self, plug: PlugState):
        plugged = plug is not PlugState.UNPLUGGED
        if plugged and not self._plugged:
            self.session_energy_kwh = 0.0
        if self._plugged and not plugged:
            self.session_energies_kwh.append(self.session_energy_kwh)
        self._plugged = plugged

    def meter(self, p_kw: float, dt: float):
        """Accumulate measured import over one step. Zero order hold, matching the plant.

        This is the number the study is judged on, so it integrates the MEASURED power,
        not the offered or expected power.
        """
        e = max(0.0, p_kw) * dt / 3600.0
        self.session_energy_kwh += e
        self.run_energy_kwh += e

    # -- I1 uplink --------------------------------------------------------
    def telemetry(self, m: Measurements, now: float) -> dict:
        """Build one I1 message (docs/02). Field names are the wire format."""
        if self.sensor_hook is not None:
            m = self.sensor_hook(m, now)
        self.tx_seq += 1
        return {
            "seq": self.tx_seq,
            "timestamp": float(now),
            "connection_id": self.connection_id,
            "v_terminal": float(m.v_terminal),
            "i": float(m.i_a),
            "p_kw": float(m.p_kw),
            "q_kvar": float(m.q_kvar),
            "plug_state": m.plug_state.value,
            "session_energy_kwh": float(self.session_energy_kwh),
        }


# --------------------------------------------------------------------------
# Demo plant + scenario to exercise the gateway
# --------------------------------------------------------------------------
def demo():
    # Imported here so the gateway module has no dependency on the plant model.
    from charging_session import EVSessionPlant, SessionSpec

    cp, dt = ChargePointParams(), 5.0
    cfg = config_for(ControllerMode.TRUST_WEIGHTED)
    gw = EVChargePointGateway(cp, cfg, "ev01")
    # CHOSEN demo session: arrives 17:00, needs 20 kWh, leaves next morning.
    plant = EVSessionPlant(SessionSpec("ev01", arrival_s=17 * 3600.0, departure_s=31 * 3600.0,
                                       energy_required_kwh=20.0, battery_kwh=60.0,
                                       soc_arrival=0.55))
    seq, v = 0, 230.0
    print(f"{'time':>5} {'env':>5} {'trust':>5} {'lim':>5} {'I':>5} {'P':>5} {'E':>6} "
          f"{'state':>9}  reasons")
    for t in range(16 * 3600, 22 * 3600 + 1, int(dt)):
        # Envelope every 30 s. Network tight 18:00 to 19:00, trust sags 19:00 to 19:30,
        # comms outage 20:00 to 20:20 (all CHOSEN demo values).
        comms_up = not (20 * 3600 <= t < 20 * 3600 + 1200)
        if t % 30 == 0 and comms_up:
            seq += 1
            env_kw = 1.0 if 18 * 3600 <= t < 18 * 3600 + 1800 else (
                3.0 if 18 * 3600 + 1800 <= t < 19 * 3600 else 7.2)
            trust = 0.4 if 19 * 3600 <= t < 19 * 3600 + 1800 else 1.0
            gw.receive(Envelope(seq, t, "ev01", env_kw, trust, t + 60.0), now=t)
        m = plant.measure(t, v)
        r = gw.step(m, now=t)
        p = plant.apply(r.i_pilot_a, v, dt, t)
        gw.meter(p, dt)
        if t % 900 == 0:
            env = gw.last_env.p_limit_kw if gw.last_env else math.nan
            tr = gw.last_env.trust if gw.last_env else math.nan
            print(f"{t // 3600:02d}:{t % 3600 // 60:02d} {env:>5.1f} {tr:>5.2f} "
                  f"{r.limit_applied_kw:>5.2f} {r.i_pilot_a:>5.1f} {p:>5.2f} "
                  f"{gw.session_energy_kwh:>6.2f} {r.state.value:>9}  "
                  f"{','.join(dict.fromkeys(r.reasons))}")
    print(f"window energy delivered: {gw.run_energy_kwh:.3f} kWh "
          f"(required {plant.spec.energy_required_kwh:.1f} kWh)")


if __name__ == "__main__":
    # charging_session imports this module by name. Without the alias it would load a
    # second copy with its own PlugState enum, and identity checks against it would fail.
    import sys
    sys.modules.setdefault("ev_charge_point_gateway", sys.modules[__name__])
    demo()
