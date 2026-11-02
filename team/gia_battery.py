"""Gia: the battery, BMS and EMS for the EEE40016 project (team/gia_battery.py).

This file is ONLY the adapter. The BMS itself is bms_industrial.py, unchanged, which sits
beside this file together with a123_params.json. No MQTT inside GiaBattery (project rule);
the Pi's BatteryNode does the messaging. run_mqtt_node() is an optional stand-alone node.
"""
import math
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bms_industrial import (BMSConfig, BMSState, Command, IndustrialBMS, PackPlant,   # noqa: E402
                            ReqState, clamp, compute_sof)

# ============================================================================
# EEE40016 project adapter: the BMS behind the team's battery interface
# ============================================================================
# The twin (the Python digital twin, which solves the feeder power flow in OpenDSS;
# PSS SINCAL is used for the cross-check) talks to a battery through three calls,
# response / commit / status (see the project's docs/INTERFACES.md). This adapter puts the
# real IndustrialBMS + PackPlant behind those calls. There is NO MQTT in this class (project rule: logic
# classes are plain Python; the Pi's BatteryNode in src/mqtt_edge.py does the messaging).
#
# Conventions that differ from the BMS core (converted ONLY here):
#   project  : load convention, AC side, P > 0 charges, Q < 0 supplies vars
#   BMS core : DC side, P > 0 discharges (export)
#
# Inverter set points: the AS/NZS 4777.2:2020 Australia A defaults (volt-var V1-V4 =
# 207/220/240/258 V at +44/0/0/-60 % of rated S; volt-watt 253 V 100 %, 260 V 20 %;
# charging volt-watt for storage 207 V 20 %, 215 V 100 %), checked against the standard's
# Australia A settings as published by the distributors (e.g. Jemena, "EG inverter
# requirements and settings, AS/NZS 4777.2:2020"). tests/test_node_acceptance.py (V2)
# confirms the response follows these curves. The BMS core has no inverter-grid functions,
# so they live in this adapter, in front of the BMS envelope.
_VOLT_VAR = [(207.0, 0.44), (220.0, 0.0), (240.0, 0.0), (258.0, -0.60)]   # Q/S, + supplies
_VOLT_WATT = [(253.0, 1.0), (260.0, 0.2)]                                  # discharge P/Prated
_CHG_VOLT_WATT = [(207.0, 0.2), (215.0, 1.0)]                              # charge P/Prated


def _pw(x, pts):
    """Piecewise-linear lookup, flat beyond the end points."""
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


@dataclass
class BatterySpec:
    """What the twin reads from battery.spec / status(). e_kwh and the efficiencies are
    MEASURED on this model (see GiaBattery.calibrate_spec), not assumed."""
    e_kwh: float = 101.6           # calibrated: sqrt(AC_in/dSOC * AC_out/dSOC) at 40 kW, 25 C
    s_kva: float = 50.0
    p_max_kw: float = 50.0
    # Usable window of TRUE SOC. The BMS limits are 0.10 / 0.95 (BMSConfig) but its SOF
    # taper approaches them asymptotically, so the plant gets within ~2e-4 of them.
    soc_min: float = 0.1002
    soc_max: float = 0.9498
    eta_charge: float = 0.958      # AC<->cells round trip (PCS 0.97 x cell I2R/coulombic)
    eta_discharge: float = 0.958


class GiaBattery:
    """Built by the twin as GiaBattery(soc_bias=..., enabled=...).
    Attributes the twin reads: .enabled, .soc (TRUE state of charge, from the plant)."""

    N_P_100KWH = 156          # 96s x 156p A123 ANR26650M1A ~ 100 kWh (project Table 7)

    # soc0 = 0.6: the same starting state of charge as the project's stand-in battery
    # (src/battery.py), so the twin's normal-day results are directly comparable.

    def __init__(self, spec=None, soc0=0.6, soc_bias=0.0, enabled=True, dt=1.0,
                 sensor_error=False, bms_soc_bias_is_estimate=True):
        self.spec = spec or BatterySpec()
        self.enabled = enabled
        self.soc_bias = soc_bias
        cfg = BMSConfig(n_p=self.N_P_100KWH, dt=dt,
                        p_pcs_max_kw=self.spec.p_max_kw / 0.97 + 1.0,
                        cmd_timeout_s=1e9, hold_s=1e9, max_cycle_s=5.0 * dt)
        self.cfg = cfg
        gain, off = (1.005, 0.3) if sensor_error else (1.0, 0.0)
        self.plant = PackPlant(cfg, soc0=soc0, i_sensor_gain=gain, i_sensor_offset_a=off)
        # V4: the BMS only KNOWS its own estimate; it starts wrong by soc_bias
        est0 = clamp(soc0 + (soc_bias if bms_soc_bias_is_estimate else 0.0), 0.0, 1.0)
        self.bms = IndustrialBMS(cfg, soc0=est0)
        # the BMS knows the cell's coulombic efficiency (characterisation), so it tracks the
        # plant's charge efficiency exactly, apart from the V4 offset and sensor errors
        self.bms.soc_trk.eff = cfg.cell.params(25.0).eta
        self.t = 0.0
        self.seq = 0
        self._last_out = None
        self._e0 = (0.0, 0.0)
        if enabled:
            self._warm_up()
        self._e0 = (self.bms.e_charged_kwh, self.bms.e_discharged_kwh)

    # -- internals --------------------------------------------------------------------
    def _cycle(self, p_dc_kw):
        """One BMS control cycle against the plant. p_dc_kw: BMS-side request, export > 0."""
        self.seq += 1
        self.bms.receive(Command(self.seq, p_dc_kw, ReqState.NORMAL, valid_until=math.inf),
                         self.t)
        m = self.plant.measure()
        out = self.bms.step(m, self.t)
        self.plant.apply(out.p_kw, out.cont_cmd, self.cfg.dt)
        self.t += self.cfg.dt
        self._last_out = out
        return out

    def _warm_up(self, max_s=60.0):
        """Close the contactors through precharge before the first request (as at start-up)."""
        n = int(max_s / self.cfg.dt)
        for _ in range(n):
            out = self._cycle(0.0)
            if out.state == BMSState.NORMAL:
                break

    @staticmethod
    def calibrate_spec(p_kw=40.0, minutes=30, soc0=0.5):
        """Re-measure e_kwh and the (symmetric) efficiency on this model, for BatterySpec.
        Run after changing the pack size, PCS efficiency or cell parameters."""
        def seg(p):
            b = GiaBattery(soc0=soc0)
            s0 = b.soc
            for _ in range(minutes // 5):
                b.commit(p, 5)
            return abs(b.soc - s0), b
        d_c, bc = seg(p_kw)
        d_d, bd = seg(-p_kw)
        k_c, k_d = bc.energy_in_kwh / d_c, bd.energy_out_kwh / d_d   # e/eta_c and e*eta_d
        e = math.sqrt(k_c * k_d)
        return {"e_kwh": e, "eta": e / k_c}

    @property
    def ready(self):
        return (self.enabled and self._last_out is not None
                and self._last_out.state == BMSState.NORMAL)

    # -- the project's interface -------------------------------------------------------
    def response(self, v_local, setpoint_kw=0.0):
        """(p_kw, q_kvar) at terminal voltage v_local. NO side effects: it reads the BMS's
        latest envelope (compute_sof on the last measurement) and does not step anything."""
        if not self.ready:
            return 0.0, 0.0
        s, eff = self.spec, 0.97
        m = self.plant.measure()
        soc = self.bms.soc_trk.soc
        p_chg_dc, p_dis_dc, _ = compute_sof(self.cfg, m, soc, self.bms.soh,
                                            self.bms.t_min_f, self.bms.t_max_f)
        chg_cap = min(s.p_max_kw, p_chg_dc / eff)          # AC import the BMS allows
        dis_cap = min(s.p_max_kw, p_dis_dc * eff)          # AC export the BMS allows
        p = clamp(setpoint_kw, -dis_cap, chg_cap)          # + charges
        if p < 0:                                          # discharging: volt-watt
            p = max(p, -s.p_max_kw * _pw(v_local, _VOLT_WATT))
        elif p > 0:                                        # charging: low-voltage cut
            p = min(p, s.p_max_kw * _pw(v_local, _CHG_VOLT_WATT))
        q_frac = _pw(v_local, _VOLT_VAR)
        q_room = max(0.0, s.s_kva ** 2 - p ** 2) ** 0.5
        q_supply = clamp(q_frac * s.s_kva, -q_room, q_room)
        return p, -q_supply                                # load convention: - supplies

    def commit(self, p_kw, minutes):
        """Run the real BMS closed loop at p_kw (AC, + charges) for `minutes`. The only call
        that changes state; SOC moves by what the plant's cells really took."""
        if not self.enabled or minutes <= 0 or not self.ready:
            return
        eff = 0.97
        p_ac_export = -p_kw
        p_dc = p_ac_export / eff if p_ac_export > 0 else p_ac_export * eff
        for _ in range(int(round(minutes * 60.0 / self.cfg.dt))):
            self._cycle(p_dc)

    @property
    def soc(self):                       # TRUE state of charge (plant), what the twin records
        return self.plant.soc

    @property
    def soc_reported(self):              # what the BMS believes (V4: wrong by soc_bias at start)
        return self.bms.soc_trk.soc

    @property
    def energy_in_kwh(self):             # AC energy imported since construction, from MEASURED P
        return self.bms.e_charged_kwh - self._e0[0]

    @property
    def energy_out_kwh(self):
        return self.bms.e_discharged_kwh - self._e0[1]

    def status(self):
        return {"soc_true": self.soc, "soc_reported": self.soc_reported,
                "e_kwh": self.spec.e_kwh, "p_max_kw": self.spec.p_max_kw,
                "s_kva": self.spec.s_kva, "enabled": self.enabled,
                "bms_state": self.bms.state.value if self.enabled else "OFF",
                "t_max_c": float(self.plant.temp)}


# ----------------------------------------------------------------------------
# Optional stand-alone MQTT node (only if you do NOT use the project's Pi program).
# Normally you don't need this: the project's run_pi_node.py + src/mqtt_edge.BatteryNode
# already wrap any class with response/commit/status (use team/gia_battery.py).
# paho-mqtt and the project's messages.py are imported lazily, so the BMS core stays
# dependency-free.
# ----------------------------------------------------------------------------
def run_mqtt_node(node="battery", broker="127.0.0.1", port=1883, messages_dir=None):
    import os, sys, threading
    if messages_dir:
        sys.path.insert(0, messages_dir)
    import messages as M                                     # project file, copied verbatim
    import paho.mqtt.client as mqtt
    try:
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bms-" + node)
    except AttributeError:                                   # paho 1.x
        c = mqtt.Client(client_id="bms-" + node)
    lock, state = threading.Lock(), {"b": None}

    def status():
        b = state["b"]
        st = {k: v for k, v in b.status().items() if isinstance(v, (bool, int, float, str))}
        st["soc"], st["enabled"] = float(b.soc), bool(b.enabled)
        return st

    def on_connect(cl, ud, flags, rc, props=None):
        cl.subscribe(M.topic("breq", node), qos=1)
        cl.publish(M.topic("status", node), "online", qos=1, retain=True)

    def on_message(cl, ud, msg):
        try:
            m = M.BatteryRequest.from_json(msg.payload.decode())
        except Exception:
            return
        with lock:
            try:
                if m.op == "reset":
                    state["b"] = GiaBattery(soc_bias=m.soc_bias, enabled=m.enabled)
                    rep = M.BatteryReply(node, m.req, status=status())
                elif state["b"] is None:
                    rep = M.BatteryReply(node, m.req, error="no evening started yet")
                elif m.op == "response":
                    p, q = state["b"].response(m.v, m.setpoint_kw)
                    rep = M.BatteryReply(node, m.req, p_kw=float(p), q_kvar=float(q))
                else:
                    state["b"].commit(m.p_kw, m.minutes)
                    rep = M.BatteryReply(node, m.req, status=status())
            except Exception as e:
                rep = M.BatteryReply(node, m.req, error="%s: %s" % (type(e).__name__, e))
        cl.publish(M.topic("bresp", node), rep.to_json(), qos=1)

    c.on_connect, c.on_message = on_connect, on_message
    c.will_set(M.topic("status", node), "offline", qos=1, retain=True)
    c.connect(broker, port)
    print("BMS battery node '%s' on %s:%d (Ctrl-C to stop)" % (node, broker, port))
    c.loop_forever()


if __name__ == "__main__":
    # python gia_battery.py [broker] [node] [folder_with_messages.py]
    a = sys.argv[1:]
    run_mqtt_node(node=a[1] if len(a) > 1 else "battery",
                  broker=a[0] if a else "127.0.0.1",
                  messages_dir=a[2] if len(a) > 2 else None)
