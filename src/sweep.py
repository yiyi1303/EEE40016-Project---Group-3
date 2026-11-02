"""Run the study: one controller, one telemetry condition, one simulated evening.

The shape of a single control step, and the reason the whole thing exists:

    1. the feeder is at its true state: household demand from the measured profiles,
       rooftop PV from the clear-sky model, and the battery's autonomous response
    2. telemetry is published every 30 s, each sample with the reading at its own time,
       then delayed, dropped or frozen by the injector in simulated time
    3. the twin sees whatever arrived, which may be minutes old, and scores its trust
    4. the twin computes an envelope from that believed state, not from the truth
    5. the controller turns envelope, trust and age into a charging limit
    6. the setpoint goes back down a link that is degraded too. Each message is a short
       schedule: one limit for each of the next few 5-minute intervals, each planned with
       the margin for the age its data will have when it is applied. The charge points act
       on the entry for the current interval from the newest schedule that reached them,
       or on their local fallback once it runs out (plan amendment 25)
    7. what the charge points actually did is applied to the *true* feeder, and judged

Step 4 against step 7 is the experiment. A limit computed from stale data can be unsafe
when applied to a network that has moved on, and the cost of being careful about that is
charging energy not delivered. The crossover is where the care stops being worth it.

Run:  py src/sweep.py --latency 60 --loss 0.1 --controller B --trace
"""
import argparse
import csv
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass, field, replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feeder_csv import load_feeder, electrical_midpoint          # noqa: E402
from solver import OpenDSSSolver                                  # noqa: E402
from network_state import ConstraintSet, ThermalModel             # noqa: E402
from envelope import EnvelopeSearch, choose_ev_connections        # noqa: E402
from telemetry import TelemetryLink, DownlinkChannel              # noqa: E402
from ev_sessions import load_or_create                            # noqa: E402
from edge import ChargePointFleet, InProcessEdge, select_entry    # noqa: E402
from battery import BatteryStandIn                                # noqa: E402
from messages import Setpoint                                     # noqa: E402
from build_sincal_model import profile_kw                         # noqa: E402
import controllers                                                # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(HERE, "config", "study.json")
RESULTS = os.path.join(HERE, "results")


@dataclass
class RunResult:
    controller: str
    latency_s: float
    loss: float
    seed: int
    stale_hold_min: float = 0.0
    battery: bool = False
    soc_bias: float = 0.0
    energy_kwh: float = 0.0          # the metric: EV energy delivered
    demanded_kwh: float = 0.0
    violations: int = 0              # control steps with at least one violation
    violation_types: dict = field(default_factory=dict)
    counted: bool = True             # a run with any violation does not count
    mean_trust: float = 0.0
    mean_limit_kw: float = 0.0
    mean_age_min: float = 0.0
    peak_hot_spot_c: float = 0.0
    fallbacks: int = 0               # steps where the charge points used the local fallback
    relaxed_steps: int = 0           # steps where the do-no-harm rule applied
    battery_soc_end: float = 0.0
    battery_q_mean_kvar: float = 0.0
    solves: int = 0
    seconds: float = 0.0
    sessions: str = ""               # session source / plug-in model, e.g. "vista/s1"
    # setpoint schedules (plan amendment 25) and the diagnostics that attribute violations
    setpoint_schedule: bool = True
    schedule_age_basis: str = "data"
    uncovered_kw: float = 1.4
    entry_counts: list = field(default_factory=list)   # steps on entry 0..H-1, then default
    viol_by_entry: dict = field(default_factory=dict)  # violating steps by entry, "D" default
    held_new_car_steps: int = 0      # k >= 1 steps where a car the entry did not cover drew power
    viol_with_new_car: int = 0       # ...of those, steps that violated
    viol_with_finish: int = 0        # violating k >= 1 steps where a planned car had finished
    viol_lag_over_15: int = 0        # violating k >= 1 steps applied beyond the margin curve's end
    viol_attributed: int = 0         # violating k >= 1 steps with any of the three causes above
    viol_unattributed: int = 0       # the rest: what the margin itself was meant to cover
    guard_binds: int = 0             # entries k >= 1 that planned above entry 0 and were capped
    relaxed_entries: int = 0         # entries k >= 1 planned under the do-no-harm rule
    mean_applied_kw: float = 0.0     # the limit the charge points acted on, fallback included

    @property
    def served_fraction(self):
        return self.energy_kwh / self.demanded_kwh if self.demanded_kwh else 0.0


@dataclass(frozen=True)
class PlanSnapshot:
    """Everything the twin knew when it planned at one step, frozen.

    Entries k >= 1 of a schedule are computed from this, so they use the believed state of
    the step the schedule was issued at, never anything learned later. Holds copies, not
    references: the live cap, charging list and thermal model move on every step.
    """
    step: int
    t_to: float
    values: dict          # the twin's believed meter readings
    age_min: float
    trust: float
    charging: tuple       # cars connected and not full
    cap: dict             # the most each could draw this step, from the energy it wants
    thermal: object       # ThermalModel copy, before this step's application
    battery_pq: tuple     # the battery P, Q the solver held while planning
    env0_kw: float        # entry 0's envelope
    env0_tx_pct: float    # transformer loading at entry 0's envelope, for the thermal pre-step
    app_trust: tuple = ()  # trust at each entry's application age ('application' basis only)


def _read_minute_csv(path, column):
    with open(path, newline="") as f:
        return {int(r["minute"]): float(r[column]) for r in csv.DictReader(f)}


class StudyRun:
    # The teammates' parts. Each slot holds its stand-in until the teammate's own class is
    # dropped in (src/plugins.py, tools/run_with_pi.py, starting points in team/).
    link_cls = TelemetryLink          # Hoang: uplink injector and trust
    downlink_cls = DownlinkChannel    # Hoang: downlink injector
    battery_cls = BatteryStandIn      # Gia: battery, BMS and EMS
    fleet_cls = ChargePointFleet      # Lomitha: charge-point controller

    def __init__(self, config=None, transformer_kva=None):
        self.cfg = config or json.load(open(CONFIG, encoding="utf-8"))
        study = self.cfg["cases"]["study"]
        self.ctl = self.cfg.get("controller_settings", {})
        self.kva = transformer_kva or study["transformer_kva"]
        self.source_pu = study.get("source_pu")
        self.feeder = load_feeder()
        # which charging sessions the study runs (plan amendment 27)
        self.session_source = study.get("session_source", "vista")
        self.plugin_model = study.get("plugin_model", "daily")
        self.window = self.cfg["study_window"]
        self.step_min = self.window["control_period_minutes"]
        self.sample_min = self.window["telemetry_period_seconds"] / 60.0
        self.start_min = _hhmm(self.window["start"])
        self.end_min = _hhmm(self.window["end"])
        self.n_steps = int((self.end_min - self.start_min) / self.step_min)
        self.env_cfg = self.cfg["envelope"]
        # true limits for judging what happened, tightened limits for planning ahead
        self.cs = ConstraintSet(self.cfg)
        self.cs_plan = ConstraintSet(
            self.cfg, security_factor=self.env_cfg.get("security_factor", 1.0))

        self.solver = OpenDSSSolver(self.feeder, transformer_kva=self.kva,
                                    source_pu=self.source_pu).build()
        self.ev_connections = choose_ev_connections(
            self.feeder, study["ev_connections"], self.cfg["sweep"]["seeds"][0])
        self.solver.add_ev_loads(self.ev_connections)

        # rooftop PV, Table 7: 60% of connections, chosen once for the network
        self.pv_sites, self.pv_kw = [], {}
        if study.get("pv"):
            share = study.get("pv_share", 0.6)
            n = int(round(share * len(self.feeder.loads)))
            self.pv_sites = sorted(random.Random(study.get("pv_seed", 101))
                                   .sample(self.feeder.loads, n), key=lambda l: l.name)
            self.solver.add_pv(self.pv_sites)
            self.pv_kw = _read_minute_csv(os.path.join(HERE, "data", "pv_profile.csv"),
                                          "ac_kw_per_system")

        # ambient temperature, D5
        amb = os.path.join(HERE, "data", "ambient.csv")
        self.ambient_c = _read_minute_csv(amb, "air_temp_c") if os.path.exists(amb) else {}

        # the battery, Table 7: one unit at the electrical midpoint
        self.battery_bus = None
        if study.get("battery"):
            self.battery_bus, _, _ = electrical_midpoint(self.feeder)
            self.solver.add_battery(self.battery_bus, self.feeder.transformer.kv_lv)

        self.search = EnvelopeSearch(self.solver, self.cs_plan, self.env_cfg["min_kw"],
                                     self.env_cfg["max_kw"], self.env_cfg["tolerance_kw"])
        self._profile_cache = {}
        self._plan_cache = {}
        self._battery_pq = (0.0, 0.0)
        with open(os.path.join(HERE, "config", "cable_ratings.json"), encoding="utf-8") as f:
            self._cables = json.load(f)

    # -- planning margin --------------------------------------------------------

    @staticmethod
    def _curve(curve, lag):
        if lag == float("inf"):
            return curve[-1][1]
        if lag <= curve[0][0]:
            return curve[0][1]
        for (a0, m0), (a1, m1) in zip(curve, curve[1:]):
            if lag <= a1:
                return m0 + (m1 - m0) * (lag - a0) / (a1 - a0)
        return curve[-1][1]

    @staticmethod
    def value_lag(age_min):
        """How old the values are, in whole minutes. Profiles are one-minute data, so a
        sample half a minute old carries the previous minute's reading: a one-minute lag."""
        if age_min == float("inf"):
            return age_min
        return float(math.ceil(age_min - 1e-9)) if age_min > 0 else 0.0

    def margin_for_lag(self, lag_min):
        """Security margin, as a fraction of each limit, for values `lag_min` minutes old
        by the time the limit is applied.

        "flat": the fixed `security_factor` from config, whatever the lag.
        "age":  read off age_margin_curve: the 95th-percentile drift of per-phase demand
                over that lag, measured from the feeder's own profiles, with a 1% floor.
        """
        if self.env_cfg.get("margin_mode", "flat") == "flat":
            return 1.0 - self.env_cfg.get("security_factor", 1.0)
        return self._curve(self.env_cfg["age_margin_curve"], lag_min)

    def vuf_margin_for_lag(self, lag_min):
        """Unbalance margin in percentage points. In "age" mode it has its own curve,
        because unbalance drifts far faster with stale data than current does."""
        if self.env_cfg.get("margin_mode", "flat") == "flat":
            f = self.env_cfg.get("security_factor", 1.0)
            return (1.0 - f) * self.cfg["constraints"]["voltage_unbalance"]["max_vuf_percent"]
        return self._curve(self.env_cfg["vuf_margin_curve_pp"], lag_min)

    def margin_for_age(self, age_min):
        return self.margin_for_lag(self.value_lag(age_min))

    def vuf_margin_for_age(self, age_min):
        return self.vuf_margin_for_lag(self.value_lag(age_min))

    def planning_margins(self, age_min, extra_lag_min=0.0):
        """(margin, VUF margin in pp) for data `age_min` old applied `extra_lag_min` later,
        on the 0.005 grid the planning constraints are cached on.

        A schedule's entry k is applied 5k minutes after it was planned, so it is planned
        at lag value_lag(age) + 5k: the curves measure drift of the persistence forecast
        over exactly that lag (amendment 25). Entry 0 has no extra lag.
        """
        lag = self.value_lag(age_min) + extra_lag_min
        return (round(self.margin_for_lag(lag) / 0.005) * 0.005,
                round(self.vuf_margin_for_lag(lag) / 0.005) * 0.005)

    def planning_constraints(self, age_min, extra_lag_min=0.0):
        """Tightened limits for planning, cached by margin."""
        m, mv = self.planning_margins(age_min, extra_lag_min)
        key = (m, mv)
        if key not in self._plan_cache:
            cs = ConstraintSet(self.cfg, self._cables, security_factor=1.0 - m)
            limit = self.cfg["constraints"]["voltage_unbalance"]["max_vuf_percent"]
            cs.vuf_max = max(0.1, limit - mv)
            self._plan_cache[key] = cs
        return self._plan_cache[key]

    # -- inputs -----------------------------------------------------------------

    def household(self, minute):
        """Every meter reading at one minute: house demand per connection, plus PV output
        as PV_<connection> wherever there is rooftop PV."""
        if minute not in self._profile_cache:
            r = {l.name: profile_kw(HERE, self.feeder.shapes[l.shape], minute)
                 for l in self.feeder.loads}
            pv = self.pv_kw.get(minute, 0.0)
            for l in self.pv_sites:
                r["PV_" + l.name] = pv
            self._profile_cache[minute] = r
        return self._profile_cache[minute]

    def ambient_at(self, minute):
        if not self.ambient_c:
            return None
        return self.ambient_c.get(int(minute), None)

    # -- one run ----------------------------------------------------------------

    @property
    def session_args(self):
        """Source and plug-in model, for every caller of ev_sessions.load_or_create, so the
        twin and any edge built outside it (the MQTT test, the Pi) read the same sessions."""
        from ev_sessions import scenario
        source, model = scenario(self.session_source, self.plugin_model)
        return {"source": source, "plugin_model": model}

    def make_edge(self, seed):
        """The default edge: the charge-point fleet and the meters, called in process."""
        sessions = load_or_create(self.feeder, self.ev_connections, seed,
                                  tag="_n%d" % len(self.ev_connections), **self.session_args)
        fleet = self.fleet_cls(sessions, self.ctl.get("fallback_kw", 1.4),
                                 self.ctl.get("uncovered_kw"))
        return InProcessEdge(fleet, self.household, self.step_min)

    def _set_battery(self, p, q):
        """Every change to the battery's P, Q in the solver goes through here, so the value
        the solver holds is always known (a schedule entry plans with it, then restores it)."""
        self.solver.set_battery(p, q)
        self._battery_pq = (p, q)

    def _settle_battery(self, battery, setpoint_kw=0.0, iterations=6):
        """Volt-var settles in seconds, so within a 5-minute step it is at steady state, and
        steady state depends on the voltage the battery itself helps set. Iterate the
        inverter's response against the power flow until Q stops moving."""
        p = q = 0.0
        self.solver.solve()
        solves = 1
        for _ in range(iterations):
            v = self.solver.bus_voltage(self.battery_bus)
            p_new, q_new = battery.response(v, setpoint_kw)
            if abs(p_new - p) < 0.05 and abs(q_new - q) < 0.05:
                break
            p, q = p_new, q_new
            self._set_battery(p, q)
            self.solver.solve()
            solves += 1
        return p, q, solves

    def _snapshot_taken(self, snap, controller, basis, horizon):
        """Called once per step, just after the twin has planned and before anything is
        applied. Does nothing here; tests/test_setpoint_schedule.py hooks it to compute every
        entry eagerly, as a real twin would, and check the lazy values against it."""

    def _plan_entry(self, snap, k, controller, basis):
        """Entry k of the schedule issued at snap.step: (limit_kw, envelope_kw, solves,
        guard_bound, relaxed).

        Planned from the frozen believed state of the issuing step, as the twin would have
        planned it then, with three differences from entry 0: the margin is read at the
        lag it will have when applied (value_lag(age) + 5k), the transformer has been
        heated through the k intervals in between at entry 0's loading, and the ambient is
        the one at the entry's own interval. The envelope is capped at entry 0's, so an
        older entry can never be more permissive than the fresh one; guard_bound says the
        cap was needed; relaxed says the do-no-harm rule applied (the network already
        breached a limit with no charging). Computed only when an entry is selected; a real twin
        computes all of them at issue time, which tests/test_setpoint_schedule.py checks
        gives the same answer.
        """
        T = self.step_min
        tol, max_kw = self.env_cfg["tolerance_kw"], self.env_cfg["max_kw"]
        if basis == "application":
            trust, age = snap.app_trust[k], snap.age_min + T * k
        else:
            trust, age = snap.trust, snap.age_min
        if not snap.charging:
            return (controller.command(max_kw, trust, age, tol, max_kw).kw, max_kw, 0, False,
                    False)

        saved = (self.search.constraints, self.search.ev_setter, self._battery_pq)
        cap, charging = snap.cap, snap.charging
        try:
            self.solver.set_loads(snap.values)
            if self.battery_bus is not None:
                self._set_battery(*snap.battery_pq)
            self.search.constraints = self.planning_constraints(snap.age_min, T * k)
            # the snapshot's cars and caps, not the live ones the step loop has moved on to
            self.search.ev_setter = lambda kw: self.solver.set_ev_powers(
                {n: min(kw, cap[n]) for n in charging})
            th = snap.thermal.copy()
            for m in range(k):
                th.step(snap.env0_tx_pct / 100.0, T, self.ambient_at(snap.t_to + T * m))
            env = self.search.find(thermal=th, minutes=T,
                                   ambient_c=self.ambient_at(snap.t_to + T * k))
        finally:
            self.search.constraints, self.search.ev_setter = saved[0], saved[1]
            if self.battery_bus is not None:
                self._set_battery(*saved[2])
        env_k = min(env.kw, snap.env0_kw)
        bound = env.kw > snap.env0_kw + 1e-9
        cmd = controller.command(env_k, trust, age, tol, max_kw)
        return cmd.kw, env_k, env.solves, bound, bool(getattr(env, "relaxed", None))

    def run(self, controller, latency_s, loss, seed=7, trace=None, edge=None,
            stale_hold_min=0.0, battery_enabled=None, soc_bias=0.0):
        """One simulated evening. `edge` is anything with start_step() and apply(); by
        default the in-process fleet, or an MQTT edge for hardware in the loop."""
        t0 = time.perf_counter()
        edge = edge or self.make_edge(seed)
        timeout = self.ctl.get("stale_timeout_min", 15.0)
        T = self.step_min
        schedule = bool(self.ctl.get("setpoint_schedule", True))
        basis = self.ctl.get("schedule_age_basis", "data")
        if basis not in ("data", "application"):
            raise ValueError("schedule_age_basis must be 'data' or 'application'")
        fb_timeout = self.ctl.get("edge_fallback_timeout_min", timeout)
        # Schedule length, from the edge timeout. A setpoint issued at step j is read at
        # mid-step of step j + k, 5k + T/2 minutes later, and the edge drops it once that
        # exceeds the timeout. H entries is exactly what the timeout lets the edge use, so
        # a schedule runs out when the edge would have fallen back anyway: no hidden second
        # timeout (3 entries at 15 minutes).
        H = int((fb_timeout - T / 2.0) // T) + 1
        if H < 1 or (H - 1) * T + T / 2.0 > fb_timeout + 1e-9:
            raise ValueError("edge fallback timeout %g min leaves no schedule entry usable"
                             % fb_timeout)
        link = self.link_cls(
            latency_s, loss, self.window["telemetry_period_seconds"], seed=seed,
            stale_timeout_min=timeout,
            trust_loss_weight=self.ctl.get("trust_loss_weight", 1.0),
            stale_hold_min=stale_hold_min)
        downlink = self.downlink_cls(latency_s, loss, seed, fb_timeout)
        thermal = ThermalModel(self.cs.thermal_params,
                               ambient_c=self.ambient_at(self.start_min))
        thermal.settle(0.3)

        has_battery = self.battery_bus is not None
        if battery_enabled is None:
            battery_enabled = has_battery
        battery = self.battery_cls(soc_bias=soc_bias,
                                   enabled=battery_enabled and has_battery)
        if has_battery:
            self._set_battery(0.0, 0.0)

        # an hour of telemetry before the window opens, so the twin starts the evening with
        # the history a running system would have rather than completely cold
        for w in range(12):
            w_from = self.start_min - 60 + w * self.step_min
            link.publish_window(lambda t: self.household(int(t + 1e-9)), w_from,
                                w_from + self.step_min)

        res = RunResult(controller.name, latency_s, loss, seed, stale_hold_min,
                        battery.enabled, soc_bias, demanded_kwh=edge.demanded_kwh)
        res.setpoint_schedule, res.schedule_age_basis = schedule, basis
        res.sessions = "%(source)s/%(plugin_model)s" % self.session_args
        res.uncovered_kw = self.ctl.get("uncovered_kw", self.ctl.get("fallback_kw", 1.4))
        trusts, limits, ages, qs, applied = [], [], [], [], []
        previous_belief = None
        total_solves = 0
        snaps, entries = {}, {}
        entry_counts = [0] * (H + 1)
        viol_by_entry = {str(k): 0 for k in range(H)}
        viol_by_entry["D"] = 0
        # the margin curves are measured out to this lag and held flat beyond it
        curve_end = max(self.env_cfg.get("age_margin_curve", [[15.0, 0]])[-1][0],
                        self.env_cfg.get("vuf_margin_curve_pp", [[15.0, 0]])[-1][0])

        for i in range(self.n_steps):
            t_from = self.start_min + i * self.step_min
            t_to = t_from + self.step_min
            amb = self.ambient_at(t_to)

            # --- open the step: the edge reports every meter sample and its car status
            samples, ev_status = edge.start_step(i, t_from, t_to, self.sample_min)
            truth = samples[-1][1]
            by_time = {round(t, 6): r for t, r in samples}

            # --- what the twin gets, through the injector in simulated time
            link.publish_window(lambda t: by_time.get(round(t, 6), truth), t_from, t_to)
            obs = link.observe(t_to, truth)
            plausible = link.plausible(obs.values, previous_belief)
            trust = link.trust(obs, plausible)
            previous_belief = obs.values

            # cars here and not yet full, and the most each can draw this step, from the
            # energy it still wants. The charge points report this, so the twin knows it.
            cap = {n: (s["wanted_kwh"] - s["delivered_kwh"]) * 60.0 / self.step_min
                   for n, s in ev_status.items()
                   if s["connected"] and s["delivered_kwh"] < s["wanted_kwh"] - 1e-9}
            charging = sorted(cap)

            def draws(kw):
                """Exactly what the network will see for a given limit: cars not charging
                draw nothing, cars nearly full draw what they still need."""
                return {n: min(kw, cap[n]) for n in charging}

            # --- the envelope, computed from the believed state, planning with exactly the
            # draws application will produce. The battery is held at its last response.
            battery_pq = self._battery_pq          # what the solver holds while planning
            env0_tx_pct = 0.0
            if charging:
                self.solver.set_loads(obs.values)
                self.search.constraints = self.planning_constraints(obs.age_min)
                self.search.ev_setter = lambda kw: self.solver.set_ev_powers(draws(kw))
                env = self.search.find(thermal=thermal.copy(), minutes=self.step_min,
                                       ambient_c=amb)
                envelope_kw = env.kw
                env0_tx_pct = env.state.detail.get("transformer_pct", 0.0)
                total_solves += env.solves
                if getattr(env, "relaxed", None):
                    res.relaxed_steps += 1
            else:
                envelope_kw = self.env_cfg["max_kw"]

            cmd = controller.command(envelope_kw, trust, obs.age_min,
                                     self.env_cfg["tolerance_kw"], self.env_cfg["max_kw"])
            clean_trust = round(min(max(trust, 0.0), 1.0), 6)

            # what the twin knew when it planned this step, frozen for the schedule's later
            # entries. Copies: the live cap, charging list and thermal model move on.
            app_trust = ()
            if basis == "application":
                app_trust = tuple(link.trust(replace(obs, age_min=obs.age_min + T * k),
                                             plausible) for k in range(H))
            snaps[i] = PlanSnapshot(i, t_to, dict(obs.values), obs.age_min, trust,
                                    tuple(charging), dict(cap), thermal.copy(), battery_pq,
                                    envelope_kw, env0_tx_pct, app_trust)
            for j in [j for j in snaps if j < i - H + 1]:
                del snaps[j]
            self._snapshot_taken(snaps[i], controller, basis, H)

            # --- the schedule goes down a degraded link as ONE message: one loss draw, one
            # delay draw. The charge points act on the entry for this interval from the
            # newest schedule that reached them by mid-step, or fall back once it has run out.
            downlink.send(Setpoint(node=edge.node, step=i, t_to=t_to, limit_kw=cmd.kw,
                                   trust=clean_trust, envelope_kw=envelope_kw,
                                   issued_step=i, entry=0, valid_from=t_to,
                                   valid_until=t_to + H * T), t_to)
            held, _ = downlink.in_force(t_to + T / 2.0)
            k, entry_relaxed = None, None
            if held is None:
                effective = Setpoint(node=edge.node, step=i, t_to=t_to, limit_kw=0.0,
                                     trust=clean_trust, envelope_kw=envelope_kw,
                                     fallback=True, entry=-1)
                entry_counts[H] += 1
            else:
                k = select_entry(held.step, i, H)
                if k is None:
                    raise AssertionError("step %d governed by a schedule from step %d, outside "
                                         "its %d entries" % (i, held.step, H))
                if k == 0 or not schedule:
                    # the fresh entry, or (schedule off) the single held setpoint of
                    # amendments 22-24, applied unchanged
                    limit, env_k = held.limit_kw, held.envelope_kw
                else:
                    if (held.step, k) not in entries:
                        lim, ek, n, bound, rel = self._plan_entry(snaps[held.step], k,
                                                                  controller, basis)
                        total_solves += n
                        res.guard_binds += bound
                        res.relaxed_entries += rel
                        entries[(held.step, k)] = (lim, ek, rel)
                    limit, env_k, entry_relaxed = entries[(held.step, k)]
                # the setpoint keeps the time it was issued, so the charge points know which
                # cars it covers, and carries the interval it was planned for
                effective = Setpoint(node=edge.node, step=i, t_to=held.t_to, limit_kw=limit,
                                     trust=held.trust, envelope_kw=env_k,
                                     issued_step=held.step, entry=k,
                                     valid_from=held.t_to + T * k,
                                     valid_until=held.t_to + T * (k + 1))
                entry_counts[k] += 1
            for key in [key for key in entries if key[0] < i - H + 1]:
                del entries[key]
            ack = edge.apply(effective)
            draw = ack.draws
            if ack.fallback:
                res.fallbacks += 1
            new_cars, finished, app_lag = [], [], None
            if k is not None:
                # how old the applied limit's data is by now, whatever it was planned for
                app_lag = self.value_lag(snaps[held.step].age_min) + T * k
            if k is not None and k >= 1:
                planned = snaps[held.step].charging
                # cars the entry did not plan for that are actually drawing power
                new_cars = sorted(n for n, d in draw.items() if n not in planned and d > 1e-9)
                finished = [n for n in planned if n not in draw]
                res.held_new_car_steps += bool(new_cars)
            applied.append(self.ctl.get("fallback_kw", 1.4) if held is None
                           else effective.limit_kw)

            # --- apply what the charge points actually did to the true network, and judge
            self.solver.set_loads(truth)
            self.solver.set_ev_powers(draw)
            if battery.enabled:
                p_b, q_b, n = self._settle_battery(battery)
                battery.commit(p_b, self.step_min)
                qs.append(q_b)
                total_solves += n
            else:
                self.solver.solve()
                total_solves += 1
            state = self.cs.evaluate(self.solver, thermal=thermal, minutes=self.step_min,
                                     ambient_c=amb)

            if not state.ok:
                res.violations += 1
                res.counted = False
                for v in state.violations:
                    key = v.split()[0]
                    res.violation_types[key] = res.violation_types.get(key, 0) + 1
                viol_by_entry["D" if k is None else str(k)] += 1
                if k is not None and k >= 1:
                    over = app_lag > curve_end + 1e-9
                    res.viol_with_new_car += bool(new_cars)
                    res.viol_with_finish += bool(finished)
                    res.viol_lag_over_15 += over
                    attributed = bool(new_cars) or bool(finished) or over
                    res.viol_attributed += attributed
                    res.viol_unattributed += not attributed
            res.peak_hot_spot_c = max(res.peak_hot_spot_c,
                                      state.detail.get("hot_spot_c", 0.0))
            trusts.append(trust)
            limits.append(cmd.kw)
            ages.append(min(obs.age_min, 60.0))

            if trace is not None:
                lag = m = mv = None
                if k is not None:
                    # the lag the applied limit was planned at: data lag + 5k with the
                    # schedule, the data lag alone for the single held setpoint
                    a = snaps[held.step].age_min
                    extra = T * k if schedule and k else 0.0
                    lag = min(self.value_lag(a) + extra, 999.0)
                    m, mv = self.planning_margins(a, extra)
                trace.append({"step": i, "minute": t_to, "trust": round(trust, 3),
                              "age_min": round(min(obs.age_min, 999), 2),
                              "envelope_kw": envelope_kw, "commanded_kw": cmd.kw,
                              "applied_kw": None if held is None else effective.limit_kw,
                              "entry": -1 if k is None else k,
                              "issued_step": None if held is None else held.step,
                              "plan_lag_min": lag,
                              "app_lag_min": None if app_lag is None else min(app_lag, 999.0),
                              "entry_relaxed": entry_relaxed,
                              "margin": None if m is None else round(m, 4),
                              "vuf_margin_pp": None if mv is None else round(mv, 4),
                              "new_cars_at_default": len(new_cars),
                              "fallback": bool(ack.fallback),
                              "charging": len(charging), "ok": state.ok,
                              "binding": state.binding,
                              "violations": list(state.violations),
                              "hot_spot_c": round(state.detail.get("hot_spot_c", 0), 1),
                              "battery_q_kvar": round(qs[-1], 2) if qs else 0.0})

        res.energy_kwh = edge.total_kwh
        # an MQTT edge only learns what the cars want from the Pi's first reply
        res.demanded_kwh = edge.demanded_kwh
        res.mean_trust = sum(trusts) / len(trusts) if trusts else 0.0
        res.mean_limit_kw = sum(limits) / len(limits) if limits else 0.0
        res.mean_age_min = sum(ages) / len(ages) if ages else 0.0
        res.battery_soc_end = battery.soc
        res.battery_q_mean_kvar = sum(qs) / len(qs) if qs else 0.0
        res.solves = total_solves
        res.entry_counts = entry_counts
        res.viol_by_entry = viol_by_entry
        res.mean_applied_kw = sum(applied) / len(applied) if applied else 0.0
        res.seconds = time.perf_counter() - t0
        return res


def _hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def calibrate_static(study, seed, battery_enabled=None):
    """The largest fixed limit with zero violations all evening (plan amendment 1).

    A fixed limit consumes no telemetry, so this runs on a clean link. Bisected on the
    0.1 kW actuation grid. Returns (kw, energy_kwh, runs used).
    """
    step = study.env_cfg["tolerance_kw"]
    n = int(round(study.env_cfg["max_kw"] / step))
    cache = {}

    def ok(i):
        if i not in cache:
            r = study.run(controllers.StaticLimit(round(i * step, 4)), 0.0, 0.0, seed,
                          battery_enabled=battery_enabled)
            cache[i] = (r.violations == 0, r.energy_kwh)
        return cache[i][0]

    lo, hi = 0, n
    if not ok(lo):
        raise RuntimeError("seed %d violates with no charging at all" % seed)
    if ok(hi):
        return round(hi * step, 4), cache[hi][1], len(cache)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return round(lo * step, 4), cache[lo][1], len(cache)


# ------------------------------------------------------------------------- driver

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--latency", type=float, default=0.0)
    ap.add_argument("--loss", type=float, default=0.0)
    ap.add_argument("--controller", default="B", choices=list("ABC"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--stale-hold", type=float, default=0.0)
    ap.add_argument("--no-battery", action="store_true")
    ap.add_argument("--static-kw", type=float, default=None,
                    help="skip calibration and use this static limit")
    ap.add_argument("--trace", action="store_true", help="print every control step")
    ap.add_argument("--no-schedule", action="store_true",
                    help="single held setpoint instead of a schedule (the pre-amendment-25 "
                         "baseline)")
    ap.add_argument("--age-basis", choices=("data", "application"), default=None)
    ap.add_argument("--uncovered-kw", type=float, default=None)
    ap.add_argument("--sessions", choices=("vista", "standin"), default=None)
    ap.add_argument("--plugin-model", choices=("daily", "s1", "s2"), default=None)
    a = ap.parse_args()

    study = StudyRun()
    if a.sessions:
        study.session_source = a.sessions
    if a.plugin_model:
        study.plugin_model = a.plugin_model
    if a.no_schedule:
        study.ctl["setpoint_schedule"] = False
    if a.age_basis:
        study.ctl["schedule_age_basis"] = a.age_basis
    if a.uncovered_kw is not None:
        study.ctl["uncovered_kw"] = a.uncovered_kw
    bat = False if a.no_battery else None
    static_kw = a.static_kw
    if static_kw is None:
        static_kw, base_kwh, nr = calibrate_static(study, a.seed, bat)
        print("static limit for seed %d: %.1f kW (%.1f kWh, %d runs)" % (a.seed, static_kw,
                                                                        base_kwh, nr))
    ctrl = controllers.build(study.cfg, static_kw)[a.controller]
    trace = [] if a.trace else None
    r = study.run(ctrl, a.latency, a.loss, a.seed, trace, stale_hold_min=a.stale_hold,
                  battery_enabled=bat)
    if trace:
        print("%5s %7s %6s %6s %8s %8s %8s %5s %6s %s"
              % ("step", "time", "trust", "age", "envelope", "command", "applied", "entry",
                 "ok", "binding"))
        for t in trace:
            print("%5d %4d:%02d %6.2f %6.2f %8.1f %8.1f %8s %5s %6s %s"
                  % (t["step"], t["minute"] // 60, t["minute"] % 60, t["trust"], t["age_min"],
                     t["envelope_kw"], t["commanded_kw"],
                     "fallback" if t["applied_kw"] is None else "%.1f" % t["applied_kw"],
                     "-" if t["entry"] < 0 else t["entry"], t["ok"], t["binding"]))
        print()
    print("controller %s (%s) | latency %.0f s | loss %.0f%% | stale hold %g min | battery %s"
          " | sessions %s" % (r.controller, ctrl.label, r.latency_s, r.loss * 100,
                              r.stale_hold_min, "on" if r.battery else "off", r.sessions))
    print("energy delivered   %.1f kWh of %.1f wanted (%.0f%%)"
          % (r.energy_kwh, r.demanded_kwh, 100 * r.served_fraction))
    print("mean trust / limit %.3f / %.2f kW, mean age %.2f min" % (r.mean_trust,
                                                                    r.mean_limit_kw,
                                                                    r.mean_age_min))
    print("peak hot spot      %.1f C" % r.peak_hot_spot_c)
    print("charge-point fallbacks %d, do-no-harm steps %d" % (r.fallbacks, r.relaxed_steps))
    print("schedule %s (basis %s, uncovered %.1f kW): steps by entry %s, violations by entry %s"
          % ("on" if r.setpoint_schedule else "off", r.schedule_age_basis, r.uncovered_kw,
             r.entry_counts, r.viol_by_entry))
    print("held steps with an uncovered car drawing %d (violating %d); violating held steps "
          "with a car finished %d, past the margin curve %d; attributed %d, unattributed %d"
          % (r.held_new_car_steps, r.viol_with_new_car, r.viol_with_finish, r.viol_lag_over_15,
             r.viol_attributed, r.viol_unattributed))
    print("guard binds %d, do-no-harm entries %d" % (r.guard_binds, r.relaxed_entries))
    if r.battery:
        print("battery            SoC end %.3f, mean Q %.1f kvar" % (r.battery_soc_end,
                                                                     r.battery_q_mean_kvar))
    print("violations         %d steps %s" % (r.violations, r.violation_types or ""))
    print("solves             %d in %.1f s" % (r.solves, r.seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
