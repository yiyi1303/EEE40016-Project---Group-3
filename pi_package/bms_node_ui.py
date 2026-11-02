#!/usr/bin/env python3
"""
Live view of the BMS battery node (EEE40016 project). No sliders: everything on screen
comes from the messages the twin and the battery node exchange, and updates by itself.

Run (Raspberry Pi or laptop, same Wi-Fi as the broker):
    python bms_node_ui.py --broker 192.168.1.20            # watch the real MQTT traffic
    python bms_node_ui.py --demo                            # no broker: scripted evening

It only LISTENS (topics eee40016/breq|bresp|status/<node>); it never publishes, so it cannot
disturb the run. Needs: Python + tkinter, and paho-mqtt for the broker mode (the project's
pi_package already ships paho; or pip install "paho-mqtt>=2.1,<3").
--demo needs gia_battery.py, bms_industrial.py and a123_params.json beside this file.

What it can and cannot show: the battery messages carry the terminal voltage, the EMS
request, the power the battery runs at, Q, and the status the node returns (true SOC,
the BMS's own SOC, BMS state, temperature). Cell voltages and currents are not in the
messages, so they are not shown. Time is SIMULATED time: the sum of the `minutes` of the
commit requests since the last reset, not the wall clock.
"""
import argparse
import json
import os
import sys
import threading
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PREFIX = "eee40016"
SCHEMA = 2

BG, FG, DIM = "#14181f", "#e8ecf2", "#8b95a5"
GREEN, AMBER, RED, BLUE, ORANGE = "#3ecf6e", "#f0b429", "#ef5350", "#4ea1ff", "#ff9f43"

STATE_TXT = {
    "UNINIT": "Starting up", "INIT": "Self-test", "IDLE": "Ready",
    "STANDBY": "Waiting for command", "PRECHARGE": "Connecting battery (precharge)",
    "NORMAL": "Running", "ERROR": "FAULT - battery disconnected", "OFF": "Battery disabled",
}


# ============================================================================
# Feed: turns messages into one snapshot of "what the battery is doing now"
# ============================================================================
class Feed:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset_view()
        self.online = None            # None = unknown, True/False from the retained status
        self.last_rx = None           # wall clock of the last battery message
        self.schema_warning = ""
        self.pending = {}             # req -> request dict, to pair replies with their request

    def reset_view(self):
        self.soc = None
        self.soc_reported = None
        self.state = "-"
        self.temp = None
        self.enabled = True
        self.bias = 0.0
        self.sim_min = 0.0            # simulated minutes since the last reset
        self.steps = 0                # commits since the last reset (= control steps)
        self.v = None                 # last terminal voltage asked about, V
        self.setpoint = 0.0           # last EMS request, kW (+ charges)
        self.p_resp = 0.0             # what the battery answered for it, kW
        self.q_resp = 0.0             # kvar (load convention, - supplies vars)
        self.p_run = 0.0              # power of the last commit, kW
        self.error = ""
        self.n_msgs = 0

    # topic kind is "breq", "bresp" or "status"
    def handle(self, kind, payload):
        with self.lock:
            self.last_rx = time.monotonic()
            if kind == "status":
                self.online = (payload == "online")
                return
            d = payload
            if d.get("schema") != SCHEMA:
                self.schema_warning = "schema %r on the wire, this UI expects %d" % (d.get("schema"), SCHEMA)
            self.n_msgs += 1
            if kind == "breq":
                self.pending[d.get("req")] = d
                if len(self.pending) > 50:                      # never grow without bound
                    self.pending.pop(next(iter(self.pending)))
                if d.get("op") == "reset":
                    self.reset_view()
                    self.bias = float(d.get("soc_bias", 0.0))
                    self.enabled = bool(d.get("enabled", True))
            elif kind == "bresp":
                req = self.pending.pop(d.get("req"), None)
                if d.get("error"):
                    self.error = str(d["error"])
                    return
                self.error = ""
                st = d.get("status") or {}
                if st:
                    self.soc = st.get("soc_true", st.get("soc", self.soc))
                    self.soc_reported = st.get("soc_reported", self.soc_reported)
                    self.state = st.get("bms_state", self.state)
                    self.temp = st.get("t_max_c", self.temp)
                    self.enabled = bool(st.get("enabled", self.enabled))
                if req is None:
                    return
                op = req.get("op")
                if op == "response":
                    self.v = req.get("v")
                    self.setpoint = float(req.get("setpoint_kw", 0.0))
                    self.p_resp = float(d.get("p_kw", 0.0))
                    self.q_resp = float(d.get("q_kvar", 0.0))
                elif op == "commit":
                    self.p_run = float(req.get("p_kw", 0.0))
                    self.sim_min += float(req.get("minutes", 0.0))
                    self.steps += 1

    def snapshot(self):
        with self.lock:
            s = dict(self.__dict__)
            s.pop("lock"), s.pop("pending")
            s["age"] = None if self.last_rx is None else time.monotonic() - self.last_rx
            return s


# ============================================================================
# Sources of messages
# ============================================================================
def start_mqtt(feed, broker, port, node):
    import paho.mqtt.client as mqtt
    try:
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bms-node-ui")
    except AttributeError:                                     # paho 1.x
        c = mqtt.Client(client_id="bms-node-ui")
    topics = {"%s/breq/%s" % (PREFIX, node): "breq", "%s/bresp/%s" % (PREFIX, node): "bresp",
              "%s/status/%s" % (PREFIX, node): "status"}

    def on_connect(cl, ud, flags, rc, props=None):
        for t in topics:                                       # re-subscribe after reconnects
            cl.subscribe(t, qos=1)

    def on_message(cl, ud, msg):
        kind = topics.get(msg.topic)
        if kind is None:
            return
        try:
            raw = msg.payload.decode()
            feed.handle(kind, raw if kind == "status" else json.loads(raw))
        except Exception:                                      # never kill the network thread
            pass

    c.on_connect, c.on_message = on_connect, on_message
    c.connect_async(broker, port)
    c.loop_start()
    return c


def start_demo(feed, node="battery"):
    """A scripted evening: a stand-in 'twin' drives the real GiaBattery and feeds the same
    message dicts into Feed that MQTT would. Repeats forever (one control step ~ 0.4 s)."""
    from gia_battery import GiaBattery
    import math

    def run():
        feed.handle("status", "online")
        req = 0
        while True:
            req += 1
            # demo only: starts at 80% with a 3-point SOC error so the screen has
            # something to show; the study runs start at 60% with no error.
            b = GiaBattery(soc0=0.8, soc_bias=0.03)
            feed.handle("breq", {"type": "BatteryRequest", "schema": SCHEMA, "node": node,
                                 "req": req, "op": "reset", "soc_bias": 0.03, "enabled": True})
            feed.handle("bresp", {"type": "BatteryReply", "schema": SCHEMA, "node": node,
                                  "req": req, "status": dict(b.status(), soc=b.soc), "error": ""})
            for step in range(72):                              # 6 h in 5-minute steps
                if step < 30:   sp = 0.0
                elif step < 54: sp = -40.0                      # EMS asks the battery to discharge
                else:           sp = 25.0                       # then recharge
                v = 236.0 + 24.0 * max(0.0, math.sin(step / 72.0 * math.pi * 2.0))
                for _ in range(2):
                    req += 1
                    p, q = b.response(v, sp)
                    feed.handle("breq", {"type": "BatteryRequest", "schema": SCHEMA, "node": node,
                                         "req": req, "op": "response", "v": v, "setpoint_kw": sp})
                    feed.handle("bresp", {"type": "BatteryReply", "schema": SCHEMA, "node": node,
                                          "req": req, "p_kw": p, "q_kvar": q, "status": {}, "error": ""})
                req += 1
                b.commit(p, 5)
                feed.handle("breq", {"type": "BatteryRequest", "schema": SCHEMA, "node": node,
                                     "req": req, "op": "commit", "p_kw": p, "minutes": 5.0})
                feed.handle("bresp", {"type": "BatteryReply", "schema": SCHEMA, "node": node,
                                      "req": req, "status": dict(b.status(), soc=b.soc), "error": ""})
                time.sleep(0.4)
            time.sleep(3.0)

    threading.Thread(target=run, daemon=True).start()


# ============================================================================
# The window
# ============================================================================
class App:
    BASE_W, BASE_H = 760, 450

    def __init__(self, root, feed, scale=None, node="battery", source=""):
        self.root, self.feed, self.node, self.source = root, feed, node, source
        root.title("BMS node - live view")
        root.configure(bg=BG)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        if scale is None:
            scale = min(1.0, (sw - 20) / self.BASE_W, (sh - 90) / self.BASE_H)
        self.k = max(0.4, scale)
        root.bind("<F11>", lambda e: root.attributes("-fullscreen", not root.attributes("-fullscreen")))
        root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))
        self.cv = tk.Canvas(root, width=int(self.BASE_W * self.k), height=int(self.BASE_H * self.k),
                            bg=BG, highlightthickness=0)
        self.cv.pack(padx=8, pady=8)
        self.phase = 0.0
        self.tick()

    def tick(self):
        self.phase = (self.phase + 0.12) % 1.0
        self.draw(self.feed.snapshot())
        self.root.after(100, self.tick)

    def draw(self, s):
        c = self.cv
        c.delete("all")
        fonts = {}

        def txt(*a, **kw):
            i = c.create_text(*a, **kw)
            fonts[i] = kw["font"]
            return i

        have = s["soc"] is not None
        soc = max(0.0, min(1.0, s["soc"])) if have else 0.0
        fault = s["state"] == "ERROR" or bool(s["error"])
        col = RED if fault or soc < 0.15 else AMBER if soc < 0.30 else GREEN

        # battery body: fill = TRUE soc; white tick = what the BMS believes (shows the V4 bias)
        x0, y0, x1, y1 = 250, 60, 510, 380
        c.create_rectangle(x0 + 85, y0 - 18, x1 - 85, y0, fill="#3a4454", outline="")
        c.create_rectangle(x0, y0, x1, y1, outline="#c9d1dd", width=4)
        inner = y1 - y0 - 12
        if have:
            c.create_rectangle(x0 + 6, y1 - 6, x1 - 6, y1 - 6 - inner * soc, fill=col, outline="")
        if s["soc_reported"] is not None:
            ry = y1 - 6 - inner * max(0.0, min(1.0, s["soc_reported"]))
            c.create_line(x0 - 12, ry, x1 + 12, ry, fill="#ffffff", width=2, dash=(4, 3))
        txt((x0 + x1) / 2, (y0 + y1) / 2 - 10, text=("%.1f%%" % (soc * 100)) if have else "--",
            fill="#ffffff", font=("Segoe UI", 44, "bold"))
        txt((x0 + x1) / 2, (y0 + y1) / 2 + 36, text="SOC (true, from the plant)",
            fill="#ffffff", font=("Segoe UI", 12))
        if s["soc_reported"] is not None:
            txt((x0 + x1) / 2, (y0 + y1) / 2 + 58, fill="#ffffff", font=("Segoe UI", 10),
                text="BMS believes %.1f%%  (dashed line)" % (100 * s["soc_reported"]))

        # arrows follow the power the battery runs at (project convention: + = charging)
        p = s["p_run"]
        if abs(p) > 0.5 and have:
            charging = p > 0
            for i in range(3):
                f = (self.phase + i / 3) % 1.0
                x = 40 + f * 170 if charging else 530 + f * 170
                c.create_polygon(x, 200, x + 24, 215, x, 230, x + 8, 215,
                                 fill=BLUE if charging else ORANGE, outline="")
            colr = BLUE if charging else ORANGE
            txt(125 if charging else 615, 170, text="CHARGING" if charging else "DISCHARGING",
                fill=colr, font=("Segoe UI", 14, "bold"))
            txt(125 if charging else 615, 255, text="%.1f kW" % abs(p), fill=colr,
                font=("Segoe UI", 20, "bold"))
        else:
            txt(125, 215, text="idle", fill=DIM, font=("Segoe UI", 14))

        # header: link / BMS state / simulated time
        if s["online"] is False:
            head, hcol = "Battery node OFFLINE", RED
        elif s["error"]:
            head, hcol = "Node error: " + s["error"][:60], RED
        elif not s["enabled"]:
            head, hcol = STATE_TXT["OFF"], AMBER
        else:
            head, hcol = STATE_TXT.get(s["state"], s["state"]), RED if s["state"] == "ERROR" else FG
        txt(20, 14, anchor="w", text=head, fill=hcol, font=("Segoe UI", 14, "bold"))
        hh, mm = int(s["sim_min"] // 60), int(s["sim_min"] % 60)
        txt(740, 14, anchor="e", fill=DIM, font=("Consolas", 12),
            text="sim %02d:%02d   step %d" % (hh, mm, s["steps"]))

        # what the twin asked and what the battery answered
        v = "-" if s["v"] is None else "%.1f V" % s["v"]
        txt(380, 398, fill=FG, font=("Segoe UI", 12),
            text="EMS asked: %+.1f kW   |   battery answers: %+.1f kW, %+.1f kvar   |   at %s"
                 % (s["setpoint"], s["p_resp"], s["q_resp"], v))
        notes = []
        if s["v"] is not None and s["v"] > 253.0 and s["setpoint"] < 0:
            notes.append("volt-watt is limiting discharge")
        if abs(s["q_resp"]) > 0.5:
            notes.append("volt-var is %s vars" % ("supplying" if s["q_resp"] < 0 else "absorbing"))
        if abs(s["p_resp"] - s["setpoint"]) > 0.5 and not notes:
            notes.append("BMS envelope limits the power")
        if notes:
            txt(380, 416, text="; ".join(notes), fill=AMBER, font=("Segoe UI", 11))
        # link health: wall-clock silence is only a hint, the project runs on simulated time
        age = s["age"]
        if s["schema_warning"]:
            txt(380, 434, text=s["schema_warning"], fill=RED, font=("Segoe UI", 11))
        elif age is None:
            txt(380, 434, text="waiting for the first message on %s/*/%s ..." % (PREFIX, self.node),
                fill=DIM, font=("Segoe UI", 11))
        elif age > 5.0:
            txt(380, 434, text="no battery messages for %.0f s (run finished or paused?)" % age,
                fill=AMBER, font=("Segoe UI", 11))
        else:
            txt(380, 434, text="%s  |  %d messages" % (self.source, s["n_msgs"]),
                fill=DIM, font=("Segoe UI", 10))

        # left panel
        info = [("Temperature", "-" if s["temp"] is None else "%.1f C" % s["temp"]),
                ("Initial SOC error", "%+.0f %%" % (100 * s["bias"])),
                ("Evening so far", "%.1f h" % (s["sim_min"] / 60.0))]
        for i, (k, val) in enumerate(info):
            y = 60 + i * 52
            txt(20, y, anchor="w", text=k, fill=DIM, font=("Segoe UI", 11))
            txt(20, y + 20, anchor="w", text=val, fill=FG, font=("Segoe UI", 16, "bold"))

        k = self.k
        if abs(k - 1.0) > 1e-6:
            c.scale("all", 0, 0, k, k)
            for i, f in fonts.items():
                c.itemconfigure(i, font=(f[0], max(6, round(f[1] * k))) + tuple(f[2:]))


def main():
    ap = argparse.ArgumentParser(description="Live view of the BMS battery node")
    ap.add_argument("--broker", default="127.0.0.1", help="MQTT broker address")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--node", default="battery", help="battery node name (default: battery)")
    ap.add_argument("--demo", action="store_true", help="no broker: a scripted evening")
    ap.add_argument("--scale", type=float, default=None, help="force a canvas scale, e.g. 0.7")
    a = ap.parse_args()
    feed = Feed()
    if a.demo:
        start_demo(feed, a.node)
        source = "DEMO (scripted, not MQTT)"
    else:
        start_mqtt(feed, a.broker, a.port, a.node)
        source = "broker %s:%d" % (a.broker, a.port)
    root = tk.Tk()
    App(root, feed, a.scale, a.node, source)
    root.mainloop()


if __name__ == "__main__":
    main()
