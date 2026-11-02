"""Path tests for the BMS core (bms_industrial.py): each test drives IndustrialBMS against
the PackPlant (A123 cell model) through one scenario and asserts the expected behaviour:
  A, B  SOC taper near empty / full, no fault        G  OCV recalibration at rest
  C     sustained over-temperature trips ERROR        H  cold pack: charge derated, no ERROR
  D     invalid commands -> CMD_INTEGRITY, open       I  trust is audit metadata only
  E     slow precharge -> 3 tries, then fault         J, K  DOE limit applied, never loosens
  L     stale (HOLD) and expired commands             M  telemetry reports MEASURED power
Test F documents a known limitation (an SOC error on the flat LFP plateau is not detected
by voltage), so it reports rather than asserts.

    python test_bms_paths.py          (from this folder; ends with "TESTS ... PASSED")
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import math
from bms_industrial import *

def run(cfg, soc0, script, t_end, plant_kw=None, bms_soc0=None):
    plant = PackPlant(cfg, soc0=soc0, **(plant_kw or {}))
    bms = IndustrialBMS(cfg, soc0=bms_soc0 if bms_soc0 is not None else soc0)
    seq = 0; rows = []; dt = cfg.dt
    for k in range(int(t_end/dt)+1):
        t = round(k*dt, 6)
        seq_cmds = script(t, plant, bms)
        for c in seq_cmds:
            bms.receive(c, t)
        m = plant.measure(); out = bms.step(m, t); plant.apply(out.p_kw, out.cont_cmd, dt)
        rows.append((t, out, m, plant))
    return bms, rows

def cmd_stream(p, state=ReqState.NORMAL, exp=500, imp=500):
    st = {"seq": 0}
    def f(t, plant, bms):
        if abs(t-round(t)) < 1e-6 and t >= 1:
            st["seq"] += 1
            return [Command(st["seq"], p(t) if callable(p) else p, state if t >= 5 else ReqState.STANDBY, exp, imp, 0.0)]
        return []
    return f

cfg = BMSConfig()

print("TEST A: low SOC (0.13), ask 100 kW discharge -> SOC taper/energy limit, no fault")
bms, rows = run(cfg, 0.13, cmd_stream(100.0), 60)
for t, o, m, p in rows[::100][1:]:
    print(f"  t={t:5.1f} state={o.state.value:7} out={o.p_kw:6.1f} env_hi={o.env_hi:6.1f} soc={p.soc:.3f} vmin={m.v_cell_min:.3f} {o.reasons}")
assert all(o.state != BMSState.ERROR for _, o, _, _ in rows), "unexpected ERROR"
assert min(p.soc for *_, p in rows) > 0.09, "SOC went below window"

print("\nTEST B: high SOC (0.94), ask -100 kW charge -> must taper, no overvoltage trip")
bms, rows = run(cfg, 0.94, cmd_stream(-100.0), 60)
for t, o, m, p in rows[::100][1:]:
    print(f"  t={t:5.1f} state={o.state.value:7} out={o.p_kw:6.1f} env_lo={o.env_lo:7.1f} soc={p.soc:.3f} vmax={m.v_cell_max:.3f} {o.reasons}")
assert all(o.state != BMSState.ERROR for _, o, _, _ in rows), "unexpected ERROR"
assert max(m.v_cell_max for _, _, m, _ in rows) < cfg.v_max_msl

print("\nTEST C: sustained over-temp sensor (65C for 2 s) -> must trip ERROR")
stream = cmd_stream(30.0)
def scr(t, plant, bms):
    if abs(t-20) < 1e-6: plant.sensor_glitch("t_max", 65.0, 2.0)
    return stream(t, plant, bms)
bms, rows = run(cfg, 0.6, scr, 30)
assert bms.state == BMSState.ERROR and "TEMP_HIGH_MSL" in bms.diag.errors(), (bms.state, bms.diag.errors())
print("  OK ->", bms.diag.errors())

print("\nTEST D: 5 consecutive invalid commands -> CMD_INTEGRITY error, contactors open")
stream = cmd_stream(30.0)
def scr(t, plant, bms):
    cs = stream(t, plant, bms)
    if 20 <= t < 26 and abs(t-round(t)) < 1e-6:
        return [Command(1, 30.0)]          # replayed seq -> OUT_OF_ORDER
    return cs if t < 20 else []
bms, rows = run(cfg, 0.6, scr, 40)
assert bms.state == BMSState.ERROR and bms.cont.is_open
print("  OK ->", bms.state.value, bms.cont.state.value)

print("\nTEST E: precharge too slow -> 3 tries, then PRECHARGE_TIMEOUT fault")
stream = cmd_stream(30.0)
def scr(t, plant, bms):
    plant.tau_pre = 20.0
    return stream(t, plant, bms)
bms, rows = run(cfg, 0.6, scr, 40)
assert bms.state == BMSState.ERROR and bms.cont.fault == "PRECHARGE_TIMEOUT", (bms.state, bms.cont.fault)
assert sum("precharge timeout, retry" in m for _, m in bms.events) == 2, "expected 2 retries before the fault"
print("  OK ->", bms.cont.fault, "after", bms.cont.tries, "tries")

print("\nTEST G: rest at steep OCV region -> SOC recalibrated from OCV; on the plateau -> NOT")
bms, rows = run(cfg, 0.03, cmd_stream(0.0, state=ReqState.STANDBY), 320, bms_soc0=0.08)
assert abs(bms.soc_trk.soc - 0.03) < 0.02, bms.soc_trk.soc
print("  steep region: BMS 0.08 -> %.3f (truth 0.03)" % bms.soc_trk.soc)
bms, rows = run(cfg, 0.50, cmd_stream(0.0, state=ReqState.STANDBY), 320, bms_soc0=0.40)
assert abs(bms.soc_trk.soc - 0.40) < 0.01, "must not recalibrate on the plateau"
print("  plateau: stays 0.40 (truth 0.50) - recalibration correctly refuses to guess")

print("\nTEST H: cold pack (-12 C): charge blocked by derating before any limit trips; no ERROR")
bms, rows = run(cfg, 0.6, cmd_stream(-30.0), 30, plant_kw=dict(temp0=-12.0))
assert all(o.state != BMSState.ERROR for _, o, _, _ in rows)
assert max(-o.p_kw for _, o, _, _ in rows) < 1e-6, "charging below ~-10C must be blocked"
print("  OK -> charge power applied: 0 kW")

def trust_stream(p, exp, imp, trust, valid_for=math.inf):
    st = {"seq": 0}
    def f(t, plant, bms):
        if abs(t-round(t)) < 1e-6 and t >= 1:
            st["seq"] += 1
            vu = t + valid_for
            return [Command(st["seq"], p, ReqState.NORMAL if t >= 5 else ReqState.STANDBY,
                            exp, imp, 0.0, trust(t) if callable(trust) else trust, vu)]
        return []
    return f

print("\nTEST I: trust is audit metadata only - it does NOT change the applied power")
bms, rows = run(cfg, 0.6, trust_stream(60.0, 60.0, 60.0, 0.3), 40)
o = rows[-1][1]
assert abs(o.p_kw - 60.0) < 0.5 and "TRUST_CONTRACT" not in o.reasons, (o.p_kw, o.reasons)
assert bms.telemetry()["doe_trust"] == 0.3
print("  OK -> trust 0.3, applied %.1f kW (limit applied as received), echoed in telemetry" % o.p_kw)

print("\nTEST J: the DOE limit as received is applied (60 kW request, 35 kW limit -> 35 kW)")
bms, rows = run(cfg, 0.6, trust_stream(60.0, 35.0, 35.0, 1.0), 40)
assert abs(rows[-1][1].p_kw - 35.0) < 0.5 and "CLIPPED" in rows[-1][1].reasons
print("  OK")

print("\nTEST K: an unlimited DOE never loosens the BMS envelope (SOC 0.13 still tapered)")
bms, rows = run(cfg, 0.13, trust_stream(100.0, math.inf, math.inf, 1.0), 40)
o = rows[-1][1]
assert o.p_kw <= o.env_hi + 1e-6 and o.p_kw < 100.0 and o.state != BMSState.ERROR
print("  OK -> out %.1f kW <= env_hi %.1f kW" % (o.p_kw, o.env_hi))

print("\nTEST L: valid_until short -> command goes stale (HOLD) before the 5 s timeout; expired-on-arrival rejected")
bms, rows = run(cfg, 0.6, trust_stream(30.0, 60.0, 60.0, 1.0, valid_for=2.0), 30)
# commands arrive every 1 s and live 2 s, so they stay fresh
assert "COMM_HOLD" not in rows[-1][1].reasons
stream = trust_stream(30.0, 60.0, 60.0, 1.0, valid_for=2.0)
def scr(t, plant, bms):
    return stream(t, plant, bms) if t < 20 else []
bms, rows = run(cfg, 0.6, scr, 24)
hold_t = next(t for t, o, *_ in rows if o.comm == "HOLD")
assert 21.0 < hold_t < 22.0, hold_t        # last cmd at 19 s, valid until 21 s (not 24 s)
print("  HOLD began at t=%.1f s (valid_until 21 s, plain timeout would have been 24 s)" % hold_t)
ok, why = bms.receive(Command(999, 10.0, ReqState.NORMAL, 60, 60, 0.0, 1.0, valid_until=5.0), 50.0)
assert (ok, why) == (False, "EXPIRED") and bms.invalid_streak == 0
ok, why = bms.receive(Command(1000, 10.0, ReqState.NORMAL, 60, 60, 0.0, 1.5), 50.0)
assert (ok, why) == (False, "TRUST_RANGE")
print("  OK -> expired rejected without counting toward CMD_INTEGRITY; trust 1.5 rejected")

print("\nTEST M: telemetry reports MEASURED power (sensor error + PCS loss), not the commanded value")
bms, rows = run(cfg, 0.5, cmd_stream(50.0), 60)
t, o, m, pl = rows[-1]
tm = bms.telemetry(m, t)
p_dc_true = pl.cfg.n_s * pl._v_cell_mean() * pl.i_true / 1000.0
assert abs(tm["p_dc_kw"] - p_dc_true) / p_dc_true < 0.02, (tm["p_dc_kw"], p_dc_true)  # ~0.5 % gain + 0.3 A offset
assert abs(tm["p_kw"] - tm["p_dc_kw"] * cfg.pcs_efficiency) < 1e-9                     # AC after PCS loss
assert tm["p_kw"] < o.p_kw and tm["seq"] == bms.tx_seq == 1 and bms.telemetry(m, t)["seq"] == 2
assert tm["e_discharged_kwh"] > 0 and tm["e_charged_kwh"] == 0
import json; json.dumps(tm)                                                             # JSON/MQTT-ready
print("  OK -> commanded %.1f kW, reported AC %.1f kW (DC %.1f kW)" % (o.p_kw, tm["p_kw"], tm["p_dc_kw"]))

print("\nTEST F (KNOWN LIMITATION): BMS thinks SOC=0.50, truth is 0.10")
bms, rows = run(cfg, 0.10, cmd_stream(0.0), 40, bms_soc0=0.50)
seen = sorted({w for _, o, _, _ in rows for w in o.warnings})
print("  warnings seen:", seen)
assert "SOC_PLAUSIBILITY" not in seen   # documents that the LFP plateau hides this error
print("  -> a 40-point SOC error is NOT detected: OCV(0.50)-OCV(0.10) is only ~0.12 V on the real A123 curve,")
print("     well under the tolerance (0.08 V + hysteresis M, ~0.26 V). Voltage-based SOC plausibility only catches gross errors.")
print("\nTESTS A-E, G-M PASSED (F documents a known limitation, not a pass)")
