"""
Charging session plant and fleet runner: exercises EVChargePointGateway the way the BMS
file's PackPlant exercises the BMS gateway.

Sign convention: P > 0 means import (charging). No export.

The plant is deliberately not a battery model. A session is: arrival, an energy
requirement, a departure, and a linear acceptance taper near full. The vehicle draws the
smaller of the offered pilot power, its own acceptance, and whatever energy it still needs.

Stubs, NOT built here (they belong to other nodes, see docs/01-my-scope.md):
    EnvelopeSource / StubTwin   twin node computes envelopes; these just replay a schedule
    TrustSource                 comms node computes trust; this just replays a value
    Link / ScriptedLink         comms node owns the degradation injector; ScriptedLink is a
                                deterministic test fixture (fixed delays, named drops), it
                                draws no random numbers and models no loss process

Reproducibility (docs/04 V9): every run takes a seed, writes gzip CSVs with mtime 0 so the
bytes depend only on content, and a JSON manifest with seed, variant levels, commit hash,
scenario tag and run duration. Run duration is wall clock, so it is the one manifest field
that differs between identical runs; the time series files are byte identical.
"""
from __future__ import annotations
import csv
import gzip
import io
import json
import math
import subprocess
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Optional, Protocol

try:
    import numpy as np      # only the standalone fleet runner below needs numpy
except ImportError:         # [Changed for integration] the Raspberry Pi package has no numpy;
    np = None               # the plant classes it uses work without it

from ev_charge_point_gateway import (
    ChargePointParams, EVChargePointGateway, Envelope, GatewayConfig, Measurements,
    PlugState, State, quantise_pilot, usable_voltage,
)


# --------------------------------------------------------------------------
# Session and vehicle
# --------------------------------------------------------------------------
@dataclass
class SessionSpec:
    connection_id: str
    arrival_s: float               # simulated seconds since midnight
    departure_s: float             # may be beyond the window (overnight charging)
    energy_required_kwh: float
    battery_kwh: float = 60.0      # CHOSEN placeholder until D4 (VISTA) sessions exist
    soc_arrival: float = 0.3       # CHOSEN placeholder, only used for the taper


@dataclass
class VehicleParams:
    obc_kw: float = 7.4            # CHOSEN: on board charger above the 7.2 kW cap so it never binds
    taper_start_soc: float = 0.80  # CHOSEN: acceptance falls linearly above this SoC
    taper_min_frac: float = 0.10   # CHOSEN: stops the taper asymptote so sessions can finish


class EVSessionPlant:
    """One vehicle on one charge point for one session."""

    def __init__(self, spec: SessionSpec, vp: VehicleParams | None = None):
        self.spec, self.vp = spec, vp or VehicleParams()
        self.delivered_kwh = 0.0
        self.p_last_kw = 0.0
        self.i_last_a = 0.0

    @property
    def soc(self) -> float:
        return self.spec.soc_arrival + self.delivered_kwh / self.spec.battery_kwh

    def plugged(self, t: float) -> bool:
        return self.spec.arrival_s <= t < self.spec.departure_s

    @property
    def complete(self) -> bool:
        return self.delivered_kwh >= self.spec.energy_required_kwh - 1e-9

    def accept_kw(self) -> float:
        """Vehicle's own acceptance before the remaining energy cap."""
        if self.complete:
            return 0.0
        vp = self.vp
        frac = (1.0 - self.soc) / (1.0 - vp.taper_start_soc)
        return vp.obc_kw * min(1.0, max(vp.taper_min_frac, frac))

    def measure(self, t: float, v: float) -> Measurements:
        if not self.plugged(t):
            self.p_last_kw, self.i_last_a = 0.0, 0.0
            plug = PlugState.UNPLUGGED
        elif self.complete:
            plug = PlugState.COMPLETE
        elif self.p_last_kw > 0.0:
            plug = PlugState.CHARGING
        else:
            plug = PlugState.PLUGGED_IDLE
        # Unity power factor is a CHOSEN simplification, so Q is zero.
        return Measurements(v, self.i_last_a, self.p_last_kw, 0.0, plug,
                            ev_accept_kw=self.accept_kw() if plug is not PlugState.UNPLUGGED
                            else 0.0)

    def apply(self, i_pilot_a: float, v: float, dt: float, t: float) -> float:
        """Draw power over [t, t + dt) given the pilot current. Returns kW drawn."""
        if not self.plugged(t) or self.complete or i_pilot_a <= 0.0:
            p = 0.0
        else:
            remaining = self.spec.energy_required_kwh - self.delivered_kwh
            p = min(v * i_pilot_a / 1000.0, self.accept_kw(), remaining * 3600.0 / dt)
        self.delivered_kwh += p * dt / 3600.0
        self.p_last_kw = p
        self.i_last_a = p * 1000.0 / v if v > 0 else 0.0
        return p


# --------------------------------------------------------------------------
# Session sources
# --------------------------------------------------------------------------
def generate_sessions(n: int, seed: int, window_start_s: float = 16 * 3600.0,
                      window_end_s: float = 22 * 3600.0) -> list[SessionSpec]:
    """PLACEHOLDER session generator. Every distribution parameter here is CHOSEN, not
    measured. Replace with VISTA derived sessions (D4 in docs/05) read from the twin's I8
    scenario file via load_sessions_csv() before any result is reported.
    """
    rng = np.random.default_rng(seed)
    arr_mean_s, arr_sd_s = 18.0 * 3600.0, 3600.0     # CHOSEN: arrivals centred on 18:00
    dist_median_km, dist_sigma = 30.0, 0.6           # CHOSEN: lognormal daily distance
    kwh_per_km = 0.18                                # CHOSEN: consumption figure (docs/05 note)
    battery_kwh, soc_target = 60.0, 0.90             # CHOSEN
    out = []
    for k in range(n):
        arr = float(np.clip(rng.normal(arr_mean_s, arr_sd_s), window_start_s, window_end_s - 300))
        dist = float(rng.lognormal(math.log(dist_median_km), dist_sigma))
        e_req = min(dist * kwh_per_km, battery_kwh * (soc_target - 0.10))
        out.append(SessionSpec(f"ev{k + 1:02d}", round(arr, 1), 31 * 3600.0,  # leave 07:00
                               round(e_req, 4), battery_kwh,
                               round(soc_target - e_req / battery_kwh, 6)))
    return out


SESSION_CSV_FIELDS = ("connection_id", "arrival_s", "departure_s", "energy_required_kwh",
                      "battery_kwh", "soc_arrival")


def load_sessions_csv(path: str | Path) -> list[SessionSpec]:
    """Read sessions from CSV. Column set is a PROPOSAL; the I8 format is the twin's."""
    with open(path, newline="") as f:
        return [SessionSpec(r["connection_id"], float(r["arrival_s"]), float(r["departure_s"]),
                            float(r["energy_required_kwh"]), float(r["battery_kwh"]),
                            float(r["soc_arrival"])) for r in csv.DictReader(f)]


# --------------------------------------------------------------------------
# Stubs for other nodes (interfaces only)
# --------------------------------------------------------------------------
class EnvelopeSource(Protocol):
    def limit_kw(self, connection_id: str, t: float) -> float: ...


class TrustSource(Protocol):
    def trust(self, connection_id: str, t: float) -> float: ...


@dataclass
class ConstantEnvelope:
    kw: float

    def limit_kw(self, connection_id, t):
        return self.kw


@dataclass
class ScheduleEnvelope:
    """Piecewise constant: list of (t_start_s, kw), sorted. Before the first entry, rated."""
    steps: list
    default_kw: float = 7.2

    def limit_kw(self, connection_id, t):
        kw = self.default_kw
        for t0, v in self.steps:
            if t >= t0:
                kw = v
        return kw


@dataclass
class ConstantTrust:
    value: float = 1.0

    def trust(self, connection_id, t):
        return self.value


class StubTwin:
    """Publishes I2 envelopes on a fixed period. Stands in for the twin node."""

    def __init__(self, env: EnvelopeSource, trust: TrustSource, validity_s: float):
        self.env, self.trust_src, self.validity_s = env, trust, validity_s
        self.seq: Counter = Counter()

    def publish(self, connection_id: str, t: float) -> Envelope:
        self.seq[connection_id] += 1
        return Envelope(self.seq[connection_id], t, connection_id,
                        self.env.limit_kw(connection_id, t),
                        self.trust_src.trust(connection_id, t), t + self.validity_s)


class Link(Protocol):
    def send(self, msg: Envelope, t: float) -> None: ...
    def deliver(self, t: float) -> list: ...


class PerfectLink:
    def __init__(self):
        self.q: list = []

    def send(self, msg, t):
        self.q.append(msg)

    def deliver(self, t):
        out, self.q = self.q, []
        return out


class ScriptedLink:
    """Deterministic test fixture: per message delay and drop decided by caller functions.
    Not the degradation injector. It has no random state and no loss model.
    """

    def __init__(self, delay_fn: Callable[[Envelope], float] = lambda m: 0.0,
                 drop_fn: Callable[[Envelope], bool] = lambda m: False):
        self.delay_fn, self.drop_fn = delay_fn, drop_fn
        self.q: list = []          # (due_time, insertion_index, msg)
        self.n = 0

    def send(self, msg, t):
        if self.drop_fn(msg):
            return
        self.q.append((t + self.delay_fn(msg), self.n, msg))
        self.n += 1

    def deliver(self, t):
        due = sorted(x for x in self.q if x[0] <= t)
        self.q = [x for x in self.q if x[0] > t]
        return [m for _, _, m in due]


# --------------------------------------------------------------------------
# Fleet runner
# --------------------------------------------------------------------------
@dataclass
class RunConfig:
    window_start_s: float = 16 * 3600.0   # docs/00 study window
    window_end_s: float = 22 * 3600.0
    dt_s: float = 5.0                     # matches the 5 s I1 rate
    envelope_period_s: float = 30.0       # I2 rate in docs/02 (see NOTES.md on 30 s vs 300 s)
    validity_s: float = 60.0              # CHOSEN: valid_until horizon set by the stub twin
    seed: int = 0
    scenario_tag: str = "standalone"
    variant: dict = field(default_factory=dict)


@dataclass
class RunResult:
    total_energy_kwh: float               # window energy, 16:00 to 22:00 (D4)
    sessions: list
    state_steps: dict
    floor_stop_steps: int
    rejections: dict
    times_s: np.ndarray
    aggregate_p_kw: np.ndarray
    rows: list
    run_duration_s: float = 0.0


TIMESERIES_FIELDS = ("t_s", "connection_id", "plug_state", "state", "limit_received_kw",
                     "limit_applied_kw", "trust", "envelope_age_s", "i_pilot_a", "p_kw",
                     "session_energy_kwh", "floor_stop", "reasons")


def run_fleet(sessions: list[SessionSpec], gw_cfg: GatewayConfig, run_cfg: RunConfig,
              envelope_source: EnvelopeSource | None = None,
              trust_source: TrustSource | None = None,
              link: Link | None = None,
              voltage_fn: Callable[[str, float], float] | None = None,
              cp: ChargePointParams | None = None,
              vp: VehicleParams | None = None,
              uplink_sink: Callable[[dict], None] | None = None) -> RunResult:
    """Run one controller over the window. No envelope_source means the twin sends nothing."""
    wall0 = time.perf_counter()
    cp = cp or ChargePointParams()
    ids = [s.connection_id for s in sessions]
    if len(set(ids)) != len(ids):
        raise ValueError("one session per connection per run")
    plants = {s.connection_id: EVSessionPlant(s, vp) for s in sessions}
    gws = {c: EVChargePointGateway(cp, gw_cfg, c) for c in ids}
    twin = (StubTwin(envelope_source, trust_source or ConstantTrust(1.0), run_cfg.validity_s)
            if envelope_source is not None else None)
    link = link or PerfectLink()
    voltage_fn = voltage_fn or (lambda c, t: cp.v_nominal)

    dt = run_cfg.dt_s
    n_steps = int(round((run_cfg.window_end_s - run_cfg.window_start_s) / dt))
    times = run_cfg.window_start_s + dt * np.arange(n_steps)
    agg = np.zeros(n_steps)
    period_steps = max(1, int(round(run_cfg.envelope_period_s / dt)))
    state_steps: Counter = Counter({s.value: 0 for s in State})
    rejections: Counter = Counter()
    floor_steps = 0
    rows = []

    for k in range(n_steps):
        t = float(times[k])
        if twin is not None and k % period_steps == 0:
            for c in ids:
                link.send(twin.publish(c, t), t)
        for msg in link.deliver(t):
            if msg.connection_id in gws:
                ok, why = gws[msg.connection_id].receive(msg, t)
                if not ok:
                    rejections[why] += 1
        for c in ids:
            gw, plant = gws[c], plants[c]
            v = usable_voltage(cp, voltage_fn(c, t))
            m = plant.measure(t, v)
            r = gw.step(m, t)
            if uplink_sink is not None:
                uplink_sink(gw.telemetry(m, t))
            p = plant.apply(r.i_pilot_a, v, dt, t)
            gw.meter(p, dt)
            agg[k] += p
            state_steps[r.state.value] += 1
            floor_steps += int(r.floor_stop)
            rows.append((t, c, m.plug_state.value, r.state.value, r.limit_received_kw,
                         r.limit_applied_kw, r.trust, r.envelope_age_s, r.i_pilot_a, p,
                         gw.session_energy_kwh, int(r.floor_stop),
                         "|".join(dict.fromkeys(r.reasons))))

    sess = []
    for s in sessions:
        gw, plant = gws[s.connection_id], plants[s.connection_id]
        metered = gw.session_energies_kwh[0] if gw.session_energies_kwh else gw.session_energy_kwh
        sess.append({"connection_id": s.connection_id,
                     "arrival_s": s.arrival_s,
                     "energy_required_kwh": s.energy_required_kwh,
                     "energy_delivered_kwh": metered,
                     "plant_energy_kwh": plant.delivered_kwh,
                     "requirement_met": int(metered >= s.energy_required_kwh - 1e-6)})
    return RunResult(sum(g.run_energy_kwh for g in gws.values()), sess, dict(state_steps),
                     floor_steps, dict(rejections), times, agg, rows,
                     time.perf_counter() - wall0)


def predict_uncontrolled_profile(sessions: list[SessionSpec], run_cfg: RunConfig,
                                 cp: ChargePointParams | None = None,
                                 v: float = 230.0) -> np.ndarray:
    """Closed form aggregate import (kW per step) with no envelope: every car draws the
    quantised rated power from its first step at or after arrival until its requirement is
    met. Valid only while no session reaches the taper. This is the node side of V8 run 2:
    the twin turns this profile into a predicted violation time.
    """
    cp = cp or ChargePointParams()
    dt = run_cfg.dt_s
    n = int(round((run_cfg.window_end_s - run_cfg.window_start_s) / dt))
    p_q = v * quantise_pilot(min(cp.circuit_a, cp.rated_kw * 1000.0 / v), cp) / 1000.0
    e_step = p_q * dt / 3600.0
    out = np.zeros(n)
    for s in sessions:
        k0 = max(0, math.ceil((s.arrival_s - run_cfg.window_start_s) / dt - 1e-9))
        k_dep = math.ceil((s.departure_s - run_cfg.window_start_s) / dt - 1e-9)
        n_full = math.floor(s.energy_required_kwh / e_step + 1e-12)
        rem = s.energy_required_kwh - n_full * e_step
        for j in range(n_full):
            if k0 + j < min(n, k_dep):
                out[k0 + j] += p_q
        if rem > 1e-12 and k0 + n_full < min(n, k_dep):
            out[k0 + n_full] += rem * 3600.0 / dt
    return out


# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------
def _fmt(x) -> str:
    if isinstance(x, float):
        return "nan" if math.isnan(x) else f"{x:.6f}"
    return str(x)


def _write_csv_gz(path: Path, header: Iterable[str], rows: Iterable) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow([_fmt(x) for x in r])
    # mtime=0 and empty filename keep the gzip header identical between runs (V9).
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                                                mtime=0) as gz:
        gz.write(buf.getvalue().encode("utf-8"))


def _plain(obj):
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def commit_hash() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True, cwd=Path(__file__).parent).stdout.strip()
    except Exception:
        return "unknown-no-git-repo"


def summary_row(res: RunResult, gw_cfg: GatewayConfig, run_cfg: RunConfig) -> dict:
    """One row per sweep point per controller; the only thing plotting scripts should read."""
    row = {"scenario_tag": run_cfg.scenario_tag, "seed": run_cfg.seed,
           "controller": gw_cfg.mode.value, **run_cfg.variant,
           "window_energy_kwh": round(res.total_energy_kwh, 6),
           "sessions": len(res.sessions),
           "sessions_met": sum(s["requirement_met"] for s in res.sessions),
           "floor_stop_steps": res.floor_stop_steps}
    row.update({f"steps_{k}": v for k, v in sorted(res.state_steps.items())})
    return row


def write_run_outputs(res: RunResult, out_dir: str | Path, gw_cfg: GatewayConfig,
                      run_cfg: RunConfig, cp: ChargePointParams | None = None) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv_gz(out / "timeseries.csv.gz", TIMESERIES_FIELDS, res.rows)
    _write_csv_gz(out / "sessions.csv.gz", list(res.sessions[0].keys()) if res.sessions
                  else ["connection_id"], [tuple(s.values()) for s in res.sessions])
    manifest = {
        "seed": run_cfg.seed,
        "scenario_tag": run_cfg.scenario_tag,
        "variant": run_cfg.variant,
        "commit": commit_hash(),
        "controller": gw_cfg.mode.value,
        "gateway_config": _plain(asdict(gw_cfg)),
        "charge_point": asdict(cp or ChargePointParams()),
        "run_config": _plain(asdict(run_cfg)),
        "window_energy_kwh": round(res.total_energy_kwh, 6),
        "window_energy_note": "energy inside 16:00 to 22:00 only, not daily (open decision D4)",
        "run_duration_s": round(res.run_duration_s, 3),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return out
