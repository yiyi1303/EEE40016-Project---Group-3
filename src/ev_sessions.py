"""Charging sessions: who plugs in, when, and how much energy they want.

Sessions are generated once per seed and frozen to disk, as the plan requires. Every run
at that seed then draws from the same stored set, so a difference between two runs is
caused by the telemetry conditions and the controller, never by different cars turning up.

Session parameters are PROVISIONAL. Data item D4 calls for a distribution fitted to the
Victorian Integrated Survey of Travel and Activity; until that fit exists these are
documented stand-in distributions with the same shape. Swapping them changes the numbers
but not the method, and the frozen-session design means the swap is one regeneration.
"""
import json
import os
import random
from dataclasses import dataclass, asdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_DIR = os.path.join(HERE, "data", "sessions")

# PROVISIONAL, pending the VISTA fit (D4)
ARRIVAL_MEAN_H = 18.6
ARRIVAL_SD_H = 1.0
ARRIVAL_MIN_H = 16.1
ARRIVAL_MAX_H = 21.0
ENERGY_MIN_KWH = 8.0
ENERGY_MAX_KWH = 26.0


@dataclass
class Session:
    load_name: str          # the house connection this charge point sits on
    ev_name: str            # the EV load element in the network model
    arrival_min: int        # minutes past midnight
    energy_kwh: float       # energy wanted this session
    bus: str
    phase: str
    home_arrival_min: int = -1      # VISTA arrival before any adjustment for the window
    pre_window_kwh: float = 0.0     # energy already taken before 16:00, for early arrivals

    def present(self, minute):
        return minute >= self.arrival_min


WINDOW_START_MIN = 16 * 60
WINDOW_END_MIN = 22 * 60
CHARGER_KW = 7.2
# Code defaults. The study's own choice lives in config/study.json (cases.study.
# session_source and plugin_model) and reaches here through StudyRun.session_args.
SOURCE = "vista"                    # "vista" (D4) or "standin" (the earlier placeholder)
# How often a car plugs in (plan amendment 27; decided 2 Oct: s1 main case, s2 stress):
#   "daily"   every car every evening, wanting that day's driving (VISTA as fitted)
#   "s1"      each evening with probability 0.34, the share of days with any charging in the
#             Jemena-led Melbourne trial (ARENA 2023), wanting everything driven since its
#             last plug-in, built up over a 21-day warm-up
#   "s2"      the distributor design day (UoM for ENA/C4NET): probability 0.70, each session
#             two days of driving
PLUGIN_MODEL = "daily"
PLUGIN_P = {"s1": 0.34, "s2": 0.70}
WARMUP_DAYS = 21
NOT_TONIGHT_MIN = 24 * 60 + 1       # a car that does not plug in this evening never arrives


def generate(feeder, ev_connections, seed, source=None, plugin_model=None):
    """One session per charge point, sampled from the VISTA fit (D4), weighted.

    A car that got home before 16:00 has been charging at the full 7.2 kW since, with no
    network limit applied, because the study window has not opened. It is present from 16:00
    wanting only what it still lacks, which is often nothing. A car home after 22:00 never
    charges inside the window.

    `source` and `plugin_model` default to the module's SOURCE and PLUGIN_MODEL.
    """
    source, plugin_model = scenario(source, plugin_model)
    if plugin_model not in ("daily",) + tuple(PLUGIN_P):
        raise ValueError("unknown plug-in model %r" % plugin_model)
    rng = random.Random(seed * 1000 + 17)
    if source == "standin":
        out = []
        for ld in ev_connections:
            h = min(max(rng.gauss(ARRIVAL_MEAN_H, ARRIVAL_SD_H), ARRIVAL_MIN_H), ARRIVAL_MAX_H)
            out.append(Session(load_name=ld.name, ev_name="EV_%s" % ld.name,
                               arrival_min=int(round(h * 60)),
                               energy_kwh=rng.uniform(ENERGY_MIN_KWH, ENERGY_MAX_KWH),
                               bus=str(ld.bus), phase=ld.phase))
        return sorted(out, key=lambda s: s.arrival_min)

    from vista_sessions import load_empirical, BATTERY_CAP_KWH
    emp = load_empirical()
    weights = [w for _, _, w in emp]
    out = []
    for ld in ev_connections:
        arrival, energy, _ = rng.choices(emp, weights=weights, k=1)[0]
        if plugin_model in PLUGIN_P:
            # Each car has its own stream, so adding a car never reshuffles the others.
            # Daily driving is drawn afresh each day from the weighted VISTA person-days,
            # which ignores that a heavy driver tends to drive a lot every day (stated
            # simplification: it narrows the spread of session sizes, not their mean).
            crng = random.Random("%d|%s|%s" % (seed, ld.name, plugin_model))
            p = PLUGIN_P[plugin_model]
            deficit = 0.0
            for _ in range(WARMUP_DAYS):
                deficit = min(BATTERY_CAP_KWH,
                              deficit + crng.choices(emp, weights=weights, k=1)[0][1])
                if crng.random() < p:
                    deficit = 0.0
            arrival, day_kwh, _ = crng.choices(emp, weights=weights, k=1)[0]
            if plugin_model == "s2":
                energy = min(BATTERY_CAP_KWH,
                             day_kwh + crng.choices(emp, weights=weights, k=1)[0][1])
            else:
                energy = min(BATTERY_CAP_KWH, deficit + day_kwh)
            # a car that does not plug in tonight, or gets home after the window has
            # closed, has nothing to charge inside it
            if crng.random() >= p or arrival > WINDOW_END_MIN:
                out.append(Session(load_name=ld.name, ev_name="EV_%s" % ld.name,
                                   arrival_min=NOT_TONIGHT_MIN, energy_kwh=0.0,
                                   bus=str(ld.bus), phase=ld.phase))
                continue
        pre = 0.0
        start = arrival
        if arrival < WINDOW_START_MIN:
            pre = min(energy, CHARGER_KW * (WINDOW_START_MIN - arrival) / 60.0)
            start = WINDOW_START_MIN
        out.append(Session(load_name=ld.name, ev_name="EV_%s" % ld.name,
                           arrival_min=int(start), energy_kwh=round(energy - pre, 6),
                           bus=str(ld.bus), phase=ld.phase,
                           home_arrival_min=int(arrival), pre_window_kwh=round(pre, 6)))
    return sorted(out, key=lambda s: s.arrival_min)


def scenario(source=None, plugin_model=None):
    """(source, plugin_model) with defaults filled in. The stand-in sessions have no plug-in
    model (every car, every evening), so they are always labelled 'daily'."""
    source = source or SOURCE
    plugin_model = "daily" if source == "standin" else (plugin_model or PLUGIN_MODEL)
    return source, plugin_model


def path_for(seed, tag="", source=None, plugin_model=None):
    """Session sets are keyed by seed and by how many charge points there are, so a
    22-connection study and a 55-connection known-answer check cannot collide, and by
    source and plug-in model, so one scenario never reads another's file."""
    source, plugin_model = scenario(source, plugin_model)
    if source != "vista":
        tag += "_" + source
    if plugin_model != "daily":
        tag += "_" + plugin_model
    return os.path.join(SESSION_DIR, "seed_%d%s.json" % (seed, tag))


def save(sessions, seed, tag="", source=None, plugin_model=None):
    os.makedirs(SESSION_DIR, exist_ok=True)
    source, plugin_model = scenario(source, plugin_model)
    if source == "vista":
        prov = ("VISTA 2024-2025 trips, Transport Victoria open data, fitted by "
                "src/vista_sessions.py (data item D4)")
        params = {"see": "data/vista/ev_sessions_summary.json", "plugin_model": plugin_model,
                  "plugin_p": PLUGIN_P.get(plugin_model, 1.0),
                  "warmup_days": WARMUP_DAYS if plugin_model in PLUGIN_P else 0}
    else:
        prov = "PROVISIONAL stand-in distributions"
        params = {"arrival_mean_h": ARRIVAL_MEAN_H, "arrival_sd_h": ARRIVAL_SD_H,
                  "arrival_clip_h": [ARRIVAL_MIN_H, ARRIVAL_MAX_H],
                  "energy_kwh_range": [ENERGY_MIN_KWH, ENERGY_MAX_KWH]}
    path = path_for(seed, tag, source, plugin_model)
    payload = {"seed": seed, "source": source, "provenance": prov, "parameters": params,
               "sessions": [asdict(s) for s in sessions]}
    # write then rename, so a parallel reader never sees a half-written file
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    try:
        os.replace(tmp, path)
    except PermissionError:
        # Windows refuses the rename while another process has the file open. Generation
        # is deterministic, so a file that is already there holds the same sessions.
        os.remove(tmp)
        if not os.path.exists(path):
            raise
    return path


def load(seed, tag="", source=None, plugin_model=None):
    with open(path_for(seed, tag, source, plugin_model), encoding="utf-8") as f:
        payload = json.load(f)
    return [Session(**s) for s in payload["sessions"]]


def load_or_create(feeder, ev_connections, seed, tag="", source=None, plugin_model=None):
    """Frozen sessions are the point: create once, reuse for every run at this seed."""
    if os.path.exists(path_for(seed, tag, source, plugin_model)):
        return load(seed, tag, source, plugin_model)
    s = generate(feeder, ev_connections, seed, source, plugin_model)
    save(s, seed, tag, source, plugin_model)
    return s


class SessionTracker:
    """Follows how much energy each car has had, so cars stop when they are full."""

    def __init__(self, sessions):
        self.sessions = sessions
        self.delivered = {s.ev_name: 0.0 for s in sessions}

    def charging_now(self, minute):
        """Cars plugged in and still wanting energy."""
        return [s.ev_name for s in self.sessions
                if s.present(minute) and self.delivered[s.ev_name] < s.energy_kwh - 1e-9]

    def deliver(self, ev_name, kw, minutes):
        """Record energy, never beyond what the car asked for. Returns the kW actually drawn."""
        s = next(x for x in self.sessions if x.ev_name == ev_name)
        want = s.energy_kwh - self.delivered[ev_name]
        kwh = min(kw * minutes / 60.0, max(want, 0.0))
        self.delivered[ev_name] += kwh
        return kwh * 60.0 / minutes if minutes else 0.0

    @property
    def total_kwh(self):
        return sum(self.delivered.values())

    @property
    def demanded_kwh(self):
        return sum(s.energy_kwh for s in self.sessions)

    def unmet(self):
        return {n: next(s for s in self.sessions if s.ev_name == n).energy_kwh - d
                for n, d in self.delivered.items()}
