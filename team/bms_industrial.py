#!/usr/bin/env python3
"""
Industrial-style BMS supervisory software (simulation, no hardware).

ARCHITECTURE  (modelled on the structure described in the foxBMS 2 docs)
------------------------------------------------------------------------
  Controller (digital twin / EMS)  --Command-->  IndustrialBMS
                                                     |
        +--------------------+-----------------------+---------------------+
        |                    |                       |                     |
   Diag module        State machine            SOF + arbitration     Contactor module
   (debounced         UNINIT>INIT>IDLE>        (envelope, DOE         (precharge sequence,
    limit checks)     STANDBY>PRECHARGE>       intersection, ramp)    fuse-aware opening)
                      NORMAL / ERROR
                                                     |
                                              PackPlant (ESC model, contactors, fuse)

WHAT IS FROM WHERE (provenance, cross-checked against the foxBMS 2 source and docs,
the A123 ANR26650M1A datasheet and Plett's ESC toolbox)
--------------------------------------------------------------------------
* State machine / contactor sequencing / diag-with-delay / system monitor:
  foxBMS 2 (bms.c, bms_cfg.h, soa.c, diag_cfg.h, docs). Same ARCHITECTURE,
  my own Python implementation - NOT a port of their C code.
* MOL / RSL / MSL (max operating / recommended safety / max safety limit):
  confirmed in foxBMS soa.c. foxBMS keeps SEPARATE charge and discharge
  temperature limits; this file does too. The voltage and current values come
  from the A123 datasheet where it gives one (see BMSConfig); the margins between
  levels and the charge-side temperature limits are my assumptions.
* Precharge: foxBMS closes minus -> precharge -> plus, accepts when the voltage
  difference is small AND precharge current is low, and retries a few times
  (PRECHARGE_TRIES=3). Here: voltage criterion + retries (no current sensor in
  the precharge path is modelled).
* SOF: horizon-based voltage-headroom method in the spirit of Plett Vol. II.
* Trust: any trust/uncertainty weighting is applied UPSTREAM (twin / comms node), so the
  DOE limits in a Command are already final. The BMS applies them as received; `trust` is
  validated (0..1) and echoed in telemetry for audit only. valid_until is honoured:
  a stale command goes HOLD then FALLBACK, an expired one is rejected on arrival.
* Setpoint clipping: Reference-Governor idea. DOE handling/ramping: my design
  (foxBMS has nothing equivalent - it takes CAN state requests only).
* SOC: Coulomb counting from an assumed initial SOC, plus a foxBMS-style
  recalibration from the OCV table when the pack has rested AND the OCV curve is
  steep enough to be informative (on the flat LFP plateau it is skipped).
* Cell physics: REAL A123 ESC parameters, 8 temperatures + OCV table, in
  a123_params.json. Verified: they equal a fresh run of Plett's toolbox
  (esctoolbox-python, 1 RC pair) on the raw A123 DYN/OCV data.
  Conventions checked against the toolbox: RC in SECONDS; hysteresis
  h' = fac*h - (1-fac)*sign(i), fac = exp(-|eta*i*G*dt/(3600*Q)|), eta only on
  charge; sign-state s only updates when |i| > Q/100; V = OCV + M0*s + M*h
  - R1*iR - R0*i. KNOWN CAVEAT: G = 1.0 at 5..45 C is the identification's lower
  bound (optimiser hit the limit) and M/G are poorly identifiable when warm.
* Cell V/I/T limits: A123 ANR26650M1A datasheet (see BMSConfig). Charge-side
  temperature limits, charge MSL current and all delays are my assumptions.
* Pack size and PCS rating: the BMSConfig defaults (96S40P, ~29 kWh, 100 kW PCS) are my
  assumptions for the stand-alone demo in this file. The EEE40016 project battery is
  96S156P (~100 kWh, project Table 7) behind a 50 kVA inverter, set in gia_battery.py.
  Not certified, not for real packs.

Sign convention (pack terminals):  I > 0 / P > 0 = discharge,  < 0 = charge.
"""
from __future__ import annotations
import bisect
import json
import math
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


# ============================================================================
# Helpers
# ============================================================================
def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def interp(xs, ys, x):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_right(xs, x) - 1
    return ys[i] + (ys[i + 1] - ys[i]) * (x - xs[i]) / (xs[i + 1] - xs[i])


def interp_tbl(tbl, x):
    return interp([p[0] for p in tbl], [p[1] for p in tbl], x)


# ============================================================================
# Configuration
# ============================================================================
@dataclass
class CellParams:
    """ESC parameters of one cell at one temperature (Plett's notation)."""
    Q: float      # capacity, Ah
    eta: float    # coulombic efficiency on charge
    R0: float     # ohmic resistance, ohm
    R1: float     # RC-branch resistance, ohm
    RC: float     # RC time constant, s
    M0: float     # instantaneous hysteresis, V
    M: float      # dynamic hysteresis magnitude, V
    G: float      # hysteresis rate constant


class CellModel:
    """ESC cell model with temperature-dependent parameters and an OCV table.

    Data comes from a123_params.json, exported from sim-PCM-SCM-python's
    A123modeldyn.pickle (real A123 lab-identified values, 8 temperatures).
    Parameters are linearly interpolated between temperatures."""
    FIELDS = ("Q", "eta", "R0", "R1", "RC", "M0", "M", "G")

    def __init__(self, data: dict):
        self.temps = data["temps"]
        self._tab = {k: data[k] for k in self.FIELDS}
        self.soc_pts, self.ocv0, self.ocvrel = data["soc"], data["ocv0"], data["ocvrel"]

    @classmethod
    def from_json(cls, path=None):
        path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "a123_params.json")
        with open(path) as f:
            return cls(json.load(f))

    def params(self, temp_c: float) -> CellParams:
        return CellParams(**{k: interp(self.temps, self._tab[k], temp_c) for k in self.FIELDS})

    def ocv(self, soc: float, temp_c: float = 25.0) -> float:
        z = clamp(soc, 0.0, 1.0)
        return interp(self.soc_pts, self.ocv0, z) + temp_c * interp(self.soc_pts, self.ocvrel, z)

    def docv_dsoc(self, soc: float, temp_c: float = 25.0) -> float:
        z0, z1 = clamp(soc - 0.005, 0, 1), clamp(soc + 0.005, 0, 1)
        return (self.ocv(z1, temp_c) - self.ocv(z0, temp_c)) / (z1 - z0)

    def soc_from_ocv(self, v: float, temp_c: float = 25.0) -> float:
        """Invert the OCV curve (table is monotonic); nearest of a fine grid."""
        best, bd = 0.0, 1e9
        for k in range(1001):
            z = k / 1000.0
            d = abs(self.ocv(z, temp_c) - v)
            if d < bd: best, bd = z, d
        return best

    @property
    def q_nominal(self) -> float:
        return self.params(25.0).Q


@dataclass
class BMSConfig:
    dt: float = 0.1                       # control cycle, s
    n_s: int = 96
    n_p: int = 40                          # -> ~29 kWh pack
    cell: CellModel = field(default_factory=CellModel.from_json)

    # --- limits: MOL (max operating) < RSL (recommended safety) < MSL (max safety)
    # Cell figures from the A123 ANR26650M1A datasheet (MD100001-02, Apr 2009):
    #   charge 3.6 V CCCV (the charge voltage, not an absolute maximum) |
    #   recommended pulse-discharge cut-off 1.6 V | 70 A continuous discharge |
    #   120 A / 10 s pulse discharge | 10 A fast charge (no maximum charge
    #   current stated) | operating temperature -30..+60 C.
    # The datasheet gives no separate "absolute maximum" ratings, so the MSL
    # values below are set at (or inside) these figures; MOL/RSL are margins I chose.
    v_max_mol: float = 3.50
    v_max_rsl: float = 3.55
    v_max_msl: float = 3.60                # = datasheet CCCV charge voltage
    v_min_mol: float = 2.50
    v_min_rsl: float = 2.20
    v_min_msl: float = 2.00                # my margin above the 1.6 V pulse cut-off
    # Temperature limits are split by current direction, as in foxBMS soa.c.
    # The datasheet gives one operating range (-30..+60 C) for both directions:
    # discharge MSL uses its +60 C upper end; the narrower charge limits and the
    # discharge low-temperature limits are my assumptions (more conservative).
    t_max_dis_mol: float = 50.0
    t_max_dis_rsl: float = 55.0
    t_max_dis_msl: float = 60.0
    t_min_dis_mol: float = -10.0
    t_min_dis_rsl: float = -15.0
    t_min_dis_msl: float = -20.0
    t_max_chg_mol: float = 45.0
    t_max_chg_rsl: float = 50.0
    t_max_chg_msl: float = 55.0
    t_min_chg_mol: float = 0.0
    t_min_chg_rsl: float = -5.0
    t_min_chg_msl: float = -10.0
    i_direction_thr_a: float = 0.5        # below this |I| the pack counts as resting
    i_dis_mol_cell: float = 70.0           # datasheet: 70 A continuous discharge
    i_chg_mol_cell: float = 10.0           # datasheet: 10 A fast charge (no max stated)
    i_dis_msl_cell: float = 120.0          # datasheet: 120 A / 10 s pulse
    i_chg_msl_cell: float = 12.5           # ASSUMPTION: 1.25 x fast charge

    # --- contactors
    i_break_a: float = 30.0               # max current contactors may open under
    contactor_wait_max_s: float = 3.0
    contactor_fb_timeout_s: float = 1.0
    precharge_dv_v: float = 5.0           # accept when v_pack - v_bus <= this
    precharge_timeout_s: float = 5.0
    precharge_tries: int = 3              # foxBMS BMS_PRECHARGE_TRIES
    opening_delay_s: float = 0.2

    # --- power / SOF
    p_pcs_max_kw: float = 100.0
    pcs_efficiency: float = 0.97          # ASSUMPTION: DC<->AC conversion efficiency
    connection_id: str = "bess01"         # id used in telemetry messages
    soc_min: float = 0.10
    soc_max: float = 0.95
    soc_taper: float = 0.08
    # OCV recalibration at rest (foxBMS-style); only where OCV is informative
    recal_rest_s: float = 300.0
    recal_rest_i_a: float = 1.0
    recal_max_unc: float = 0.06           # max SOC uncertainty from hysteresis band
    recal_min_diff: float = 0.02
    sof_horizon_s: float = 10.0
    sustain_s: float = 60.0
    temp_filter_tau_s: float = 2.0
    temp_derate_chg: tuple = ((-20, 0.0), (-10, 0.0), (0, 0.2), (10, 0.6), (15, 1.0),
                              (40, 1.0), (50, 0.3), (55, 0.0))
    temp_derate_dis: tuple = ((-20, 0.0), (-10, 0.3), (0, 0.7), (10, 1.0),
                              (45, 1.0), (55, 0.3), (60, 0.0))

    # --- command handling
    cmd_timeout_s: float = 5.0
    hold_s: float = 15.0
    standby_after_s: float = 10.0
    fallback_kw: float = 0.0
    ramp_kw_per_s: float = 50.0
    max_cmd_kw: float = 1000.0
    cmd_invalid_limit: int = 5
    max_cycle_s: float = 0.5              # system-monitor: max gap between cycles

    @property
    def q_pack_ah(self): return self.cell.q_nominal * self.n_p
    @property
    def i_dis_mol_pack(self): return self.i_dis_mol_cell * self.n_p
    @property
    def i_chg_mol_pack(self): return self.i_chg_mol_cell * self.n_p
    @property
    def i_dis_msl_pack(self): return self.i_dis_msl_cell * self.n_p
    @property
    def i_chg_msl_pack(self): return self.i_chg_msl_cell * self.n_p


# ============================================================================
# Data exchanged with the outside world
# ============================================================================
class ReqState(Enum):
    STANDBY = "STANDBY"
    NORMAL = "NORMAL"


@dataclass
class Command:
    seq: int
    p_setpoint_kw: float
    state_request: ReqState = ReqState.NORMAL
    doe_export_max_kw: float = math.inf
    doe_import_max_kw: float = math.inf
    site_load_kw: float = 0.0
    trust: float = 1.0                    # 0..1, audit metadata only; the limits above already include it
    valid_until: float = math.inf         # same clock as `now` in receive()/step()


@dataclass
class Measurements:
    """Only what real sensors provide. No internal plant state leaks through."""
    i_pack: float
    v_pack: float
    v_cell_min: float
    v_cell_max: float
    t_min: float
    t_max: float
    v_bus: float
    fb_minus: bool
    fb_plus: bool
    fb_pre: bool
    fuse_ok: bool


@dataclass
class BMSOutput:
    p_kw: float
    state: "BMSState"
    comm: str
    reasons: list
    env_lo: float
    env_hi: float
    cont_cmd: dict
    cont_state: str
    warnings: list
    errors: list
    soc: float


# ============================================================================
# Diagnostics: limit checks with trip delay (debounce) and latching
# ============================================================================
class Sev(Enum):
    WARNING = "WARNING"     # informational / derate, self-clearing
    ERROR = "ERROR"         # latched, forces ERROR state


class Diag:
    def __init__(self, dt, log):
        self.dt, self.log, self.items = dt, log, {}

    def register(self, name, sev, trip_s, clear_s=0.0):
        self.items[name] = dict(sev=sev, trip_s=trip_s, clear_s=clear_s,
                                trip_t=0.0, clear_t=0.0, active=False, raw=False)

    def report(self, name, violated: bool):
        it = self.items[name]
        it["raw"] = violated
        if violated:
            it["clear_t"] = 0.0
            if not it["active"]:
                it["trip_t"] += self.dt
                if it["trip_t"] >= it["trip_s"] - 1e-9:
                    it["active"] = True
                    self.log(f"DIAG {it['sev'].value} SET: {name}")
        else:
            if not it["active"]:
                if it["trip_t"] > 0:
                    self.log(f"DIAG glitch rejected by debounce: {name} "
                             f"(violated {it['trip_t']:.1f}s < {it['trip_s']:.1f}s delay)")
                it["trip_t"] = 0.0
            elif it["sev"] == Sev.WARNING:
                it["clear_t"] += self.dt
                if it["clear_t"] >= it["clear_s"] - 1e-9:
                    it["active"], it["trip_t"] = False, 0.0
                    self.log(f"DIAG WARNING CLEARED: {name}")
            # ERROR severity stays latched until clear_errors()

    def errors(self):
        return [n for n, i in self.items.items() if i["active"] and i["sev"] == Sev.ERROR]

    def warnings(self):
        return [n for n, i in self.items.items() if i["active"] and i["sev"] == Sev.WARNING]

    def clear_errors(self):
        for i in self.items.values():
            if i["sev"] == Sev.ERROR:
                i["active"], i["trip_t"] = False, 0.0


# ============================================================================
# Contactor module: precharge sequencing + fuse-aware opening
# ============================================================================
class CState(Enum):
    OPEN = "OPEN"
    CLOSE_MINUS = "CLOSE_MINUS"
    PRECHARGE = "PRECHARGE"
    CLOSE_PLUS = "CLOSE_PLUS"
    CLOSED = "CLOSED"
    WAIT_CURRENT = "WAIT_CURRENT"     # opening deferred: current too high to break
    OPENING = "OPENING"


class ContactorModule:
    def __init__(self, cfg: BMSConfig, log):
        self.cfg, self.log = cfg, log
        self.state = CState.OPEN
        self.cmd = dict(minus=False, plus=False, pre=False)
        self.t = 0.0
        self.want_closed = False
        self.fault: Optional[str] = None
        self.tries = 0

    @property
    def is_open(self): return self.state == CState.OPEN
    @property
    def is_closed(self): return self.state == CState.CLOSED

    def request_close(self):
        if self.fault is None:
            self.want_closed = True

    def request_open(self):
        self.want_closed = False

    def _set(self, st, why=""):
        if st != self.state:
            self.log(f"CONTACTOR {self.state.value} -> {st.value} {why}".rstrip())
        self.state, self.t = st, 0.0

    def _begin_open(self, m: Measurements):
        if abs(m.i_pack) > self.cfg.i_break_a:
            self._set(CState.WAIT_CURRENT,
                      f"(|I|={abs(m.i_pack):.0f}A > {self.cfg.i_break_a:.0f}A, waiting for fuse/current to clear)")
        else:
            self._do_open()

    def _do_open(self):
        self.cmd["plus"] = False          # break the main (plus) path first
        self.cmd["pre"] = False
        self._set(CState.OPENING)

    def step(self, dt, m: Measurements) -> dict:
        c, s = self.cfg, self.state
        self.t += dt
        if s == CState.OPEN:
            if self.want_closed and self.fault is None:
                self.cmd["minus"] = True
                self._set(CState.CLOSE_MINUS)
        elif s == CState.CLOSE_MINUS:
            if not self.want_closed:
                self._begin_open(m)
            elif m.fb_minus:
                self.cmd["pre"] = True
                self._set(CState.PRECHARGE)
            elif self.t > c.contactor_fb_timeout_s:
                self.fault = "FEEDBACK_TIMEOUT_MINUS"
                self._begin_open(m)
        elif s == CState.PRECHARGE:
            if not self.want_closed:
                self._begin_open(m)
            elif m.fb_pre and (m.v_pack - m.v_bus) <= c.precharge_dv_v:
                self.cmd["plus"] = True
                self._set(CState.CLOSE_PLUS, f"(bus {m.v_bus:.0f}V / pack {m.v_pack:.0f}V)")
            elif self.t > c.precharge_timeout_s:
                self.tries += 1
                if self.tries >= c.precharge_tries:
                    self.fault = "PRECHARGE_TIMEOUT"
                    self.log(f"precharge failed {self.tries}x -> fault")
                else:
                    self.log(f"precharge timeout, retry {self.tries}/{c.precharge_tries}")
                self._begin_open(m)
        elif s == CState.CLOSE_PLUS:
            if m.fb_plus:
                self.cmd["pre"] = False
                self.tries = 0
                self._set(CState.CLOSED)
            elif self.t > c.contactor_fb_timeout_s:
                self.fault = "FEEDBACK_TIMEOUT_PLUS"
                self._begin_open(m)
        elif s == CState.CLOSED:
            if not self.want_closed:
                self._begin_open(m)
        elif s == CState.WAIT_CURRENT:
            if abs(m.i_pack) <= c.i_break_a:
                self._do_open()
            elif self.t > c.contactor_wait_max_s:
                self.fault = "OPENED_UNDER_LOAD"
                self._do_open()
        elif s == CState.OPENING:
            if self.t >= c.opening_delay_s:
                self.cmd["minus"] = False
                self._set(CState.OPEN)
        return dict(self.cmd)


# ============================================================================
# SOC: Coulomb counting from an assumed initial value
# ============================================================================
class SOCTracker:
    def __init__(self, soc0, q_pack_ah, charge_eff=0.995):
        self.soc, self.q, self.eff = soc0, q_pack_ah, charge_eff

    def step(self, i_pack_a, dt):
        eff = 1.0 if i_pack_a > 0 else self.eff
        self.soc = clamp(self.soc - i_pack_a * dt * eff / (3600.0 * self.q), 0.0, 1.0)
        return self.soc


class RestRecalibrator:
    """foxBMS-style: after a long rest, read SOC from the OCV curve - but only
    where the curve is steep enough that hysteresis (+-M) cannot hide a big
    error. On the flat LFP plateau this never fires (honest limitation)."""
    def __init__(self, cfg, log):
        self.cfg, self.log, self.rest_t = cfg, log, 0.0

    def step(self, m, soc, t_mean, trk):
        c = self.cfg
        if abs(m.i_pack) > c.recal_rest_i_a:
            self.rest_t = 0.0
            return
        self.rest_t += c.dt
        if self.rest_t < c.recal_rest_s:
            return
        self.rest_t = 0.0
        v = 0.5 * (m.v_cell_min + m.v_cell_max)
        cp = c.cell.params(t_mean)
        z = c.cell.soc_from_ocv(v, t_mean)
        slope = abs(c.cell.docv_dsoc(z, t_mean))
        unc = (cp.M + cp.M0) / max(slope, 1e-6)
        if unc <= c.recal_max_unc and abs(z - soc) >= c.recal_min_diff:
            self.log(f"SOC recalibrated from OCV at rest: {soc:.3f} -> {z:.3f} "
                     f"(slope {slope:.1f} V/SOC, +-{unc:.3f})")
            trk.soc = z


# ============================================================================
# State of Function (power envelope): what may the pack do right now?
# ============================================================================
def compute_sof(cfg: BMSConfig, m: Measurements, soc, soh, t_min_f, t_max_f):
    """Returns (p_chg_kw, p_dis_kw, reasons); both >= 0.

    Voltage headroom uses the *measured worst cell*, so cell spread automatically
    shrinks the envelope. Over the horizon H the cell resistance seen by a
    current change is R0 + R1*(1-exp(-H/RC)) (Plett-style horizon SOP)."""
    reasons = []
    cp = cfg.cell.params(0.5 * (t_min_f + t_max_f))      # resistance rises when cold
    e = math.exp(-cfg.sof_horizon_s / cp.RC)
    r_cell = cp.R0 + cp.R1 * (1.0 - e)
    r_pack = r_cell * cfg.n_s / cfg.n_p
    i0 = m.i_pack

    dis_head = max(0.0, m.v_cell_min - cfg.v_min_mol)
    chg_head = max(0.0, cfg.v_max_mol - m.v_cell_max)
    i_dis_v = max(0.0, i0 + dis_head * cfg.n_p / r_cell)
    i_chg_v = max(0.0, -i0 + chg_head * cfg.n_p / r_cell)

    f_t_dis = min(interp_tbl(cfg.temp_derate_dis, t_min_f), interp_tbl(cfg.temp_derate_dis, t_max_f))
    f_t_chg = min(interp_tbl(cfg.temp_derate_chg, t_min_f), interp_tbl(cfg.temp_derate_chg, t_max_f))
    f_s_dis = clamp((soc - cfg.soc_min) / cfg.soc_taper, 0.0, 1.0)
    f_s_chg = clamp((cfg.soc_max - soc) / cfg.soc_taper, 0.0, 1.0)

    i_dis_static = cfg.i_dis_mol_pack * f_t_dis * f_s_dis * soh
    i_chg_static = cfg.i_chg_mol_pack * f_t_chg * f_s_chg * soh
    i_dis, i_chg = min(i_dis_v, i_dis_static), min(i_chg_v, i_chg_static)

    # flag voltage only when it is the tighter of the two current limits
    if i_dis_v < i_dis_static: reasons.append("VOLT_DIS")
    if i_chg_v < i_chg_static: reasons.append("VOLT_CHG")
    if f_t_dis < 1: reasons.append("TEMP_DIS")
    if f_t_chg < 1: reasons.append("TEMP_CHG")
    if f_s_dis < 1: reasons.append("SOC_TAPER_DIS")
    if f_s_chg < 1: reasons.append("SOC_TAPER_CHG")

    v_dis = m.v_pack - r_pack * (i_dis - i0)
    v_chg = m.v_pack + r_pack * (i_chg + i0)
    p_dis = max(0.0, i_dis * v_dis / 1000.0)
    p_chg = max(0.0, i_chg * v_chg / 1000.0)

    e_cap_kwh = cfg.n_s * 3.2 * cfg.q_pack_ah / 1000.0 * soh
    p_dis_e = max(0.0, (soc - cfg.soc_min) * e_cap_kwh * 3600.0 / cfg.sustain_s)
    p_chg_e = max(0.0, (cfg.soc_max - soc) * e_cap_kwh * 3600.0 / cfg.sustain_s)
    if p_dis_e < p_dis: p_dis = p_dis_e; reasons.append("ENERGY_DIS")
    if p_chg_e < p_chg: p_chg = p_chg_e; reasons.append("ENERGY_CHG")

    if p_dis > cfg.p_pcs_max_kw: p_dis = cfg.p_pcs_max_kw; reasons.append("PCS_DIS")
    if p_chg > cfg.p_pcs_max_kw: p_chg = cfg.p_pcs_max_kw; reasons.append("PCS_CHG")
    return p_chg, p_dis, reasons


# ============================================================================
# The BMS
# ============================================================================
class BMSState(Enum):
    UNINIT = "UNINIT"
    INIT = "INIT"
    IDLE = "IDLE"
    STANDBY = "STANDBY"
    PRECHARGE = "PRECHARGE"
    NORMAL = "NORMAL"
    ERROR = "ERROR"


class IndustrialBMS:
    def __init__(self, cfg: BMSConfig, soc0: float, soh: float = 1.0):
        self.cfg, self.soh = cfg, soh
        self.events: list = []
        self.now = 0.0
        self.diag = Diag(cfg.dt, self._log)
        self.cont = ContactorModule(cfg, self._log)
        self.soc_trk = SOCTracker(soc0, cfg.q_pack_ah)
        self.recal = RestRecalibrator(cfg, self._log)
        self.state = BMSState.UNINIT
        self.last_cmd: Optional[Command] = None
        self.rx_time = None
        self.last_seq = -1
        self.invalid_streak = 0
        self._stale_age = self.cfg.cmd_timeout_s
        # telemetry / metering (uplink toward the twin and, through it, the network model)
        self.tx_seq = 0
        self.sensor_hook: Optional[Callable[[dict, float], dict]] = None
        self.e_discharged_kwh = 0.0          # AC energy exported, from MEASURED power
        self.e_charged_kwh = 0.0             # AC energy imported, from MEASURED power
        self.p_prev = 0.0
        self.shutdown_pending = False
        self.t_min_f = self.t_max_f = None
        self.last_step_time = None
        self.last_meas: Optional[Measurements] = None
        self._register_diag()

    # ---- logging -------------------------------------------------------
    def _log(self, msg):
        self.events.append((self.now, msg))

    def _to(self, st: BMSState, why=""):
        if st != self.state:
            self._log(f"STATE {self.state.value} -> {st.value} {why}".rstrip())
            self.state = st

    # ---- diagnostics setup -----------------------------------------------
    def _register_diag(self):
        r, E, W = self.diag.register, Sev.ERROR, Sev.WARNING
        for n, t in (("CELL_OV_MSL", .5), ("CELL_UV_MSL", .5), ("TEMP_HIGH_MSL", 1.0),
                     ("TEMP_LOW_MSL", 1.0), ("OVERCURRENT_DIS_MSL", .2),
                     ("OVERCURRENT_CHG_MSL", .2), ("FUSE_BLOWN", 0.0),
                     ("CONTACTOR_FAULT", 0.0), ("SENSOR_IMPLAUSIBLE", .5),
                     ("CMD_INTEGRITY", 0.0), ("SYS_MONITOR", 0.0)):
            r(n, E, t)
        for n, t, c in (("CELL_OV_RSL", .5, 1.0), ("CELL_UV_RSL", .5, 1.0),
                        ("TEMP_HIGH_RSL", .5, 2.0), ("TEMP_LOW_RSL", .5, 2.0),
                        ("CURRENT_DIS_ABOVE_MOL", .5, 1.0), ("CURRENT_CHG_ABOVE_MOL", .5, 1.0),
                        ("SOC_PLAUSIBILITY", 5.0, 2.0)):
            r(n, W, t, c)

    # ---- command intake ---------------------------------------------------
    def receive(self, cmd: Command, now: float):
        self.now = now
        why = None
        if not all(map(math.isfinite, (cmd.p_setpoint_kw, cmd.site_load_kw))):
            why = "NAN"
        elif math.isnan(cmd.trust) or math.isnan(cmd.valid_until):
            why = "NAN"
        elif not 0.0 <= cmd.trust <= 1.0:
            why = "TRUST_RANGE"
        elif abs(cmd.p_setpoint_kw) > self.cfg.max_cmd_kw:
            why = "RANGE"
        elif cmd.doe_export_max_kw < 0 or cmd.doe_import_max_kw < 0:
            why = "DOE_NEGATIVE"
        elif cmd.seq <= self.last_seq:
            why = "OUT_OF_ORDER"
        if why is None and now > cmd.valid_until:
            # Late, not malicious: reject without counting toward CMD_INTEGRITY.
            self._log(f"CMD rejected (EXPIRED on arrival, valid_until={cmd.valid_until:.1f})")
            return False, "EXPIRED"
        if why:
            self.invalid_streak += 1
            self._log(f"CMD rejected ({why}), invalid streak {self.invalid_streak}")
            return False, why
        self.invalid_streak = 0
        self.last_seq, self.last_cmd, self.rx_time = cmd.seq, cmd, now
        return True, "OK"

    def _comm(self, now):
        c = self.cfg
        if self.last_cmd is None:
            return "NONE", None, c.fallback_kw, 0.0
        age = now - self.rx_time
        # stale at whichever comes first: valid_until passes or cmd_timeout_s without news
        self._stale_age = min(c.cmd_timeout_s, self.last_cmd.valid_until - self.rx_time)
        if age > self._stale_age + c.hold_s:
            return "FALLBACK", self.last_cmd, c.fallback_kw, age
        if age > self._stale_age:
            return "HOLD", self.last_cmd, self.last_cmd.p_setpoint_kw, age
        return "OK", self.last_cmd, self.last_cmd.p_setpoint_kw, age

    def _effective_request(self, comm, cmd, age):
        c = self.cfg
        if comm == "NONE":
            return ReqState.STANDBY
        if comm == "FALLBACK" and age > self._stale_age + c.hold_s + c.standby_after_s:
            return ReqState.STANDBY       # comms lost for long: shut down cleanly
        return cmd.state_request

    # ---- diagnostics evaluation ---------------------------------------------
    def _run_diag(self, m: Measurements, soc, now):
        c, d = self.cfg, self.diag
        if self.last_step_time is not None:
            d.report("SYS_MONITOR", now - self.last_step_time > c.max_cycle_s)
        self.last_step_time = now

        implausible = (m.v_cell_min > m.v_cell_max + 1e-6 or m.t_min > m.t_max + 1e-6 or
                       not (0.5 < m.v_cell_min < 5.0) or not (0.5 < m.v_cell_max < 5.0) or
                       not (-40 < m.t_min < 120) or not (-40 < m.t_max < 120))
        d.report("SENSOR_IMPLAUSIBLE", implausible)
        d.report("CELL_OV_MSL", m.v_cell_max >= c.v_max_msl)
        d.report("CELL_UV_MSL", m.v_cell_min <= c.v_min_msl)
        d.report("CELL_OV_RSL", m.v_cell_max >= c.v_max_rsl)
        d.report("CELL_UV_RSL", m.v_cell_min <= c.v_min_rsl)
        chg = m.i_pack < -c.i_direction_thr_a      # rest counts as "discharge" (as foxBMS)
        pre = "chg" if chg else "dis"
        lim = lambda n, lvl: getattr(c, f"{n}_{pre}_{lvl}")
        d.report("TEMP_HIGH_MSL", m.t_max >= lim("t_max", "msl"))
        d.report("TEMP_LOW_MSL", m.t_min <= lim("t_min", "msl"))
        d.report("TEMP_HIGH_RSL", m.t_max >= lim("t_max", "rsl"))
        d.report("TEMP_LOW_RSL", m.t_min <= lim("t_min", "rsl"))
        d.report("OVERCURRENT_DIS_MSL", m.i_pack >= c.i_dis_msl_pack)
        d.report("OVERCURRENT_CHG_MSL", -m.i_pack >= c.i_chg_msl_pack)
        d.report("CURRENT_DIS_ABOVE_MOL", m.i_pack > c.i_dis_mol_pack)
        d.report("CURRENT_CHG_ABOVE_MOL", -m.i_pack > c.i_chg_mol_pack)
        d.report("FUSE_BLOWN", not m.fuse_ok)
        d.report("CONTACTOR_FAULT", self.cont.fault is not None)
        d.report("CMD_INTEGRITY", self.invalid_streak >= c.cmd_invalid_limit)
        # SOC plausibility: does mean cell voltage agree with OCV(SOC) - IR?
        i_cell = m.i_pack / c.n_p
        t_mean = 0.5 * (self.t_min_f + self.t_max_f)
        cp = c.cell.params(t_mean)
        expect = c.cell.ocv(soc, t_mean) - (cp.R0 + cp.R1) * i_cell
        tol = 0.08 + cp.M                      # hysteresis can legitimately shift V by up to M
        d.report("SOC_PLAUSIBILITY", abs(0.5 * (m.v_cell_min + m.v_cell_max) - expect) > tol)

    # ---- one control cycle ---------------------------------------------------
    def step(self, m: Measurements, now: float) -> BMSOutput:
        c = self.cfg
        self.now, self.last_meas = now, m
        self._meter(m, c.dt)

        # sensor conditioning (temperature low-pass for derating decisions)
        if self.t_max_f is None:
            self.t_min_f, self.t_max_f = m.t_min, m.t_max
        else:
            a = c.dt / (c.temp_filter_tau_s + c.dt)
            self.t_min_f += a * (m.t_min - self.t_min_f)
            self.t_max_f += a * (m.t_max - self.t_max_f)

        soc = self.soc_trk.step(m.i_pack, c.dt)
        if not (m.fb_minus and m.fb_plus):          # only with pack disconnected from load
            self.recal.step(m, soc, 0.5 * (self.t_min_f + self.t_max_f), self.soc_trk)
            soc = self.soc_trk.soc
        self._run_diag(m, soc, now)
        comm, cmd, p_req, age = self._comm(now)
        req = self._effective_request(comm, cmd, age)
        errors = self.diag.errors()

        # ---- state machine ----
        if self.state != BMSState.ERROR and errors:
            self._to(BMSState.ERROR, f"(errors: {', '.join(errors)})")
            self.cont.request_open()
            self.shutdown_pending = False

        st = self.state
        if st == BMSState.UNINIT:
            self._to(BMSState.INIT)
        elif st == BMSState.INIT:
            self._to(BMSState.IDLE, "(self-test passed)")
        elif st == BMSState.IDLE:
            if comm != "NONE":
                self._to(BMSState.STANDBY)
        elif st == BMSState.STANDBY:
            if req == ReqState.NORMAL:
                self.cont.request_close()
                self._to(BMSState.PRECHARGE)
        elif st == BMSState.PRECHARGE:
            if req != ReqState.NORMAL:
                self.cont.request_open()
                self._to(BMSState.STANDBY)
            elif self.cont.is_closed:
                self._to(BMSState.NORMAL)
        elif st == BMSState.NORMAL:
            if req == ReqState.STANDBY:
                if not self.shutdown_pending:
                    self._log("shutdown requested: ramping power to zero before opening contactors")
                self.shutdown_pending = True
            elif self.shutdown_pending:
                self.shutdown_pending = False
            if (self.shutdown_pending and abs(self.p_prev) < 0.5
                    and abs(m.i_pack) <= c.i_break_a):
                self.cont.request_open()
                self._to(BMSState.STANDBY)
                self.shutdown_pending = False
        elif st == BMSState.ERROR:
            self.cont.request_open()

        # ---- power arbitration (only meaningful in NORMAL) ----
        reasons: list = []
        p_chg, p_dis, env_reasons = compute_sof(c, m, soc, self.soh, self.t_min_f, self.t_max_f)
        env_lo, env_hi = -p_chg, p_dis
        if self.state == BMSState.NORMAL and cmd is not None:
            reasons += env_reasons
            if comm in ("HOLD", "FALLBACK"):
                reasons.append("COMM_" + comm)
            if self.shutdown_pending:
                p_req = 0.0
            lo, hi = env_lo, env_hi
            if comm != "FALLBACK":     # stale DOE ignored while ramping to safe state
                doe_hi = cmd.doe_export_max_kw + cmd.site_load_kw
                doe_lo = cmd.site_load_kw - cmd.doe_import_max_kw
                lo, hi = max(env_lo, doe_lo), min(env_hi, doe_hi)
            if lo > hi:                  # DOE unsatisfiable inside BMS envelope: BMS wins
                reasons.append("DOE_UNAVOIDABLE_VIOLATION")
                p_target = env_hi if lo > env_hi else env_lo
                p_target = clamp(p_target, env_lo, env_hi)
            else:
                p_target = clamp(p_req, lo, hi)
                if abs(p_target - p_req) > 1e-9:
                    reasons.append("CLIPPED")
            step_max = c.ramp_kw_per_s * c.dt
            p_out = clamp(p_target, self.p_prev - step_max, self.p_prev + step_max)
            p_out = clamp(p_out, env_lo, env_hi)       # tightened limits apply instantly
            if abs(p_out - p_target) > 1e-9:
                reasons.append("RAMP")
        else:
            p_out = 0.0                  # not in NORMAL: no power
        self.p_prev = p_out

        cmds = self.cont.step(c.dt, m)
        return BMSOutput(p_out, self.state, comm, reasons, env_lo, env_hi, cmds,
                         self.cont.state.value, self.diag.warnings(), self.diag.errors(), soc)

    # ---- uplink: measured values, not commanded ones -------------------------
    def measured_power_kw(self, m: Measurements):
        """(P_dc, P_ac) in kW from the SENSORS. Discharge/export > 0, charge/import < 0.
        AC side = what the network model needs; it differs from DC by PCS losses."""
        p_dc = m.v_pack * m.i_pack / 1000.0
        eff = self.cfg.pcs_efficiency
        p_ac = p_dc * eff if p_dc > 0 else p_dc / eff
        return p_dc, p_ac

    def _meter(self, m: Measurements, dt: float):
        _, p_ac = self.measured_power_kw(m)
        if p_ac > 0:
            self.e_discharged_kwh += p_ac * dt / 3600.0
        else:
            self.e_charged_kwh += -p_ac * dt / 3600.0

    def telemetry(self, m: Optional[Measurements] = None, now: Optional[float] = None) -> dict:
        """One uplink message. Same layout idea as the EV gateway's I1 message.
        Sign: p_kw > 0 = BMS exports (discharges) to the grid, < 0 = imports (charges).
        The EV gateway uses the opposite sign (import > 0): convert at the twin, one place.
        Power comes from V and I as MEASURED; the commanded power is never used here."""
        m = m or self.last_meas
        now = self.now if now is None else now
        p_dc, p_ac = self.measured_power_kw(m)
        d = {
            "seq": self.tx_seq + 1,
            "timestamp": float(now),
            "connection_id": self.cfg.connection_id,
            "v_pack": float(m.v_pack),
            "i_pack": float(m.i_pack),
            "p_dc_kw": float(p_dc),
            "p_kw": float(p_ac),              # AC at the connection point, export > 0
            "q_kvar": 0.0,                    # unity power factor assumed (as the EV plant does)
            "soc": float(self.soc_trk.soc),
            "state": self.state.value,
            "doe_trust": float(self.last_cmd.trust) if self.last_cmd else None,
            "t_max": float(m.t_max),
            "e_discharged_kwh": float(self.e_discharged_kwh),
            "e_charged_kwh": float(self.e_charged_kwh),
        }
        if self.sensor_hook is not None:      # lets a comms/degradation node corrupt or age it
            d = self.sensor_hook(d, now)
        self.tx_seq += 1
        return d

    # ---- operator error acknowledge ---------------------------------------
    def acknowledge_error(self):
        if self.state != BMSState.ERROR:
            return False, "NOT_IN_ERROR"
        m = self.last_meas
        if not self.cont.is_open or m.fb_minus or m.fb_plus or m.fb_pre:
            return False, "CONTACTORS_NOT_OPEN"
        persist = [n for n in self.diag.errors()
                   if self.diag.items[n]["raw"] and n != "CONTACTOR_FAULT"]
        if persist:
            return False, "CONDITION_PERSISTS: " + ", ".join(persist)
        self.cont.fault = None
        self.diag.clear_errors()
        self.invalid_streak = 0
        self._log("operator acknowledged error")
        self._to(BMSState.STANDBY)
        return True, "OK"


# ============================================================================
# Plant: stands in for the real pack, contactors, fuse and sensors
# ============================================================================
class PackPlant:
    def __init__(self, cfg: BMSConfig, soc0, temp0=25.0, cell_spread_v=0.010,
                 i_fuse_a=1000.0, fuse_t_s=0.3, i_sensor_gain=1.005, i_sensor_offset_a=0.3):
        self.cfg, self.soc, self.temp, self.spread = cfg, soc0, temp0, cell_spread_v
        self.iR = self.h = self.s = 0.0
        self.i_true = 0.0
        self.mech = {k: dict(cmd=False, fb=False, t=0.0) for k in ("minus", "plus", "pre")}
        self.v_bus = 0.0
        self.fuse_blown, self.fuse_t = False, 0.0
        self.i_fuse_a, self.fuse_t_s = i_fuse_a, fuse_t_s
        self.inj_i: Optional[float] = None
        self.glitches: list = []
        self.gain, self.offset = i_sensor_gain, i_sensor_offset_a
        self.t = 0.0
        self.log = lambda msg: None
        self.tau_pre = 0.5
        self.c_th = cfg.n_s * cfg.n_p * 85.0       # J/K
        self.ua = 60.0                              # W/K

    # --- fault / disturbance injection
    def inject_current(self, a): self.inj_i = a
    def replace_fuse(self): self.fuse_blown, self.fuse_t = False, 0.0
    def sensor_glitch(self, field_name, value, duration_s):
        self.glitches.append((field_name, value, self.t + duration_s))

    def _v_cell_mean(self):
        c = self.cfg.cell
        cp = c.params(self.temp)
        return (c.ocv(self.soc, self.temp) + cp.M0 * self.s + cp.M * self.h
                - cp.R1 * self.iR - cp.R0 * self.i_true / self.cfg.n_p)

    def measure(self) -> Measurements:
        cfg = self.cfg
        v = self._v_cell_mean()
        d = dict(i_pack=self.i_true * self.gain + self.offset,
                 v_pack=cfg.n_s * v, v_cell_min=v - self.spread, v_cell_max=v + self.spread,
                 t_min=self.temp - 1.0, t_max=self.temp + 1.0, v_bus=self.v_bus,
                 fb_minus=self.mech["minus"]["fb"], fb_plus=self.mech["plus"]["fb"],
                 fb_pre=self.mech["pre"]["fb"], fuse_ok=not self.fuse_blown)
        for f, val, until in self.glitches:
            if self.t < until:
                d[f] = val
        return Measurements(**d)

    def apply(self, p_kw, cmds: dict, dt):
        cfg, c = self.cfg, self.cfg.cell
        cp = c.params(self.temp)
        self.t += dt
        for k, m in self.mech.items():                 # contactor mechanics
            m["cmd"] = cmds[k]
            if m["cmd"] != m["fb"]:
                m["t"] += dt
                if m["t"] >= (0.05 if m["cmd"] else 0.03):
                    m["fb"], m["t"] = m["cmd"], 0.0
            else:
                m["t"] = 0.0
        conducting = self.mech["minus"]["fb"] and self.mech["plus"]["fb"] and not self.fuse_blown

        r_pack = (cp.R0 + cp.R1) * cfg.n_s / cfg.n_p
        ocv_pack = cfg.n_s * (c.ocv(self.soc, self.temp) + cp.M0 * self.s + cp.M * self.h)
        if not conducting:
            i = 0.0
        elif self.inj_i is not None:
            i = self.inj_i
        else:
            P = p_kw * 1000.0
            disc = max(0.0, ocv_pack ** 2 - 4 * r_pack * P)
            i = (ocv_pack - math.sqrt(disc)) / (2 * r_pack) if abs(P) > 1e-9 else 0.0

        if conducting and abs(i) > self.i_fuse_a:      # fuse model
            self.fuse_t += dt
            if self.fuse_t >= self.fuse_t_s:
                self.fuse_blown, i, self.inj_i = True, 0.0, None
        else:
            self.fuse_t = max(0.0, self.fuse_t - dt)

        i_cell = i / cfg.n_p
        if abs(i_cell) > cp.Q / 100.0:                 # toolbox: sik updates only above Q/100
            self.s = math.copysign(1.0, i_cell)
        a_rc = math.exp(-dt / cp.RC)
        eta = 1.0 if i_cell > 0 else cp.eta
        ah = math.exp(-abs(eta * i_cell * cp.G * dt / (cp.Q * 3600.0)))
        self.iR = a_rc * self.iR + (1 - a_rc) * i_cell
        if abs(i_cell) > 1e-9:
            self.h = ah * self.h - (1 - ah) * math.copysign(1.0, i_cell)
        self.soc = clamp(self.soc - dt * eta * i_cell / (cp.Q * 3600.0), 0.0, 1.0)
        self.i_true = i

        heat = i * i * r_pack
        self.temp += (heat - self.ua * (self.temp - 25.0)) * dt / self.c_th

        v_pack = cfg.n_s * self._v_cell_mean()         # bus voltage
        if self.mech["minus"]["fb"] and self.mech["plus"]["fb"]:
            self.v_bus = v_pack
        elif self.mech["minus"]["fb"] and self.mech["pre"]["fb"]:
            self.v_bus += (ocv_pack - self.v_bus) * (1 - math.exp(-dt / self.tau_pre))
        else:
            self.v_bus *= math.exp(-dt / 20.0)


# ============================================================================
# Scenario: exercises every mechanism, prints a status table + event log
# ============================================================================
def twin_profile(t):
    """What the digital twin / EMS asks for. Returns (p_kw, export_max, import_max)."""
    if t < 10:   return 0.0, 90.0, 60.0
    if t < 60:   return 60.0, 90.0, 60.0
    if t < 110:  return -80.0, 90.0, 40.0 if 70 <= t < 90 else 60.0
    if t < 175:  return 120.0, 150.0 if 130 <= t < 140 else 90.0, 60.0
    return 50.0, 90.0, 60.0


def demo(t_end=240.0, verbose=True, plot_path=None):
    cfg = BMSConfig()
    dt = cfg.dt
    plant = PackPlant(cfg, soc0=0.60)
    bms = IndustrialBMS(cfg, soc0=0.60)          # BMS assumes the right initial SOC
    seq, printed, violations = 0, 0, 0
    acked = {"try1": False, "fix": False, "try2": False}
    hist = []

    if verbose:
        print(f"{'t':>6} {'state':>9} {'comm':>8} {'req':>6} {'out':>6} {'env[lo,hi]':>16} "
              f"{'I(A)':>7} {'SOC_bms':>8} {'SOC_true':>8} {'Tmax':>5} {'contactor':>12}  flags")

    for k in range(int(t_end / dt) + 1):
        t = round(k * dt, 6)
        req_p, exp_max, imp_max = twin_profile(t)

        # ---- scripted disturbances ----
        if abs(t - 105.0) < 1e-6:
            plant.sensor_glitch("t_max", 65.0, 0.3)      # 0.3 s over-temp sensor glitch
        if abs(t - 200.0) < 1e-6:
            plant.inject_current(5000.0)                  # hard overcurrent event
        comms_up = not (140.0 <= t < 175.0)               # comms outage window

        if comms_up and abs(t - round(t)) < 1e-6 and t >= 1.0:   # 1 Hz commands
            seq += 1
            state_req = ReqState.STANDBY if t < 5 else ReqState.NORMAL
            bms.receive(Command(seq, req_p, state_req, exp_max, imp_max, site_load_kw=5.0), t)

        # operator actions after the overcurrent trip
        if t >= 215.0 and not acked["try1"]:
            ok, why = bms.acknowledge_error(); acked["try1"] = True
            bms._log(f"operator ack attempt #1 -> {ok} ({why})")
        if t >= 225.0 and not acked["fix"]:
            plant.replace_fuse(); acked["fix"] = True
            bms._log("service action: fuse replaced")
        if t >= 225.5 and not acked["try2"]:
            ok, why = bms.acknowledge_error(); acked["try2"] = True
            bms._log(f"operator ack attempt #2 -> {ok} ({why})")

        meas = plant.measure()
        out = bms.step(meas, t)
        plant.apply(out.p_kw, out.cont_cmd, dt)
        hist.append(dict(t=t, state=out.state.value, p_req=req_p, p_out=out.p_kw, env_lo=out.env_lo,
                         env_hi=out.env_hi, i=meas.i_pack, v=meas.v_pack, vmin=meas.v_cell_min,
                         vmax=meas.v_cell_max, soc_bms=out.soc, soc_true=plant.soc, temp=plant.temp))

        if out.state == BMSState.NORMAL and not (out.env_lo - 1e-6 <= out.p_kw <= out.env_hi + 1e-6):
            violations += 1                                # invariant: output inside envelope

        if verbose:
            for ev_t, msg in bms.events[printed:]:
                print(f"       [{ev_t:7.1f}s] {msg}")
            printed = len(bms.events)
            if k % 50 == 0:                                # every 5 s
                flags = ",".join(dict.fromkeys(out.reasons + out.warnings + out.errors))
                print(f"{t:6.1f} {out.state.value:>9} {out.comm:>8} {req_p:>6.0f} {out.p_kw:>6.1f} "
                      f"[{out.env_lo:6.0f},{out.env_hi:6.0f}] {meas.i_pack:>7.0f} "
                      f"{out.soc:>8.4f} {plant.soc:>8.4f} {plant.temp:>5.1f} {out.cont_state:>12}  {flags}")

    print(f"\nInvariant check: output left the BMS envelope in {violations} NORMAL-state cycles "
          f"(expected 0).")
    if plot_path:
        plot_history(hist, plot_path)
    return violations


def plot_history(hist, path):
    """Save a 5-panel overview of a run (needs matplotlib; skipped if missing)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed - plot skipped")
        return
    col = lambda k: [h[k] for h in hist]
    t = col("t")
    fig, ax = plt.subplots(5, 1, figsize=(11, 12), sharex=True)
    ax[0].plot(t, col("p_req"), "--", label="requested (twin/EMS)")
    ax[0].plot(t, col("p_out"), label="applied by BMS")
    ax[0].fill_between(t, col("env_lo"), col("env_hi"), alpha=0.12, label="BMS envelope")
    ax[0].set_ylabel("power kW"); ax[0].legend(loc="upper right", fontsize=8)
    ax[1].plot(t, col("v"), color="tab:green"); ax[1].set_ylabel("pack V")
    a2 = ax[1].twinx(); a2.plot(t, col("i"), color="tab:red", alpha=0.6); a2.set_ylabel("current A")
    ax[2].plot(t, col("vmin"), label="min cell"); ax[2].plot(t, col("vmax"), label="max cell")
    ax[2].set_ylabel("cell V"); ax[2].legend(loc="upper right", fontsize=8)
    ax[3].plot(t, col("soc_bms"), label="BMS estimate (Coulomb counting)")
    ax[3].plot(t, col("soc_true"), "--", label="true (plant)")
    ax[3].set_ylabel("SOC"); ax[3].legend(loc="upper right", fontsize=8)
    names = [s.value for s in BMSState]
    ax[4].step(t, [names.index(h["state"]) for h in hist], where="post")
    ax[4].set_yticks(range(len(names))); ax[4].set_yticklabels(names, fontsize=8)
    ax[4].set_ylabel("BMS state"); ax[4].set_xlabel("time s")
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)
    print(f"plot saved: {path}")


if __name__ == "__main__":
    import sys
    demo(plot_path=sys.argv[1] if len(sys.argv) > 1 else None)
