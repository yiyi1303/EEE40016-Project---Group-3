#!/usr/bin/env python3
"""
Live view of the EV charge-point node (EEE40016 project). The companion of bms_node_ui.py:
everything on screen comes from the MQTT messages the twin (laptop) and the edge node
(Raspberry Pi, run_pi_node.py) exchange, and updates by itself.

Run (Raspberry Pi or laptop, same network as the broker):
    python3 ev_node_ui.py --broker 172.20.10.8          # watch the real MQTT traffic
    python3 ev_node_ui.py --demo                         # no broker: a scripted evening

It only LISTENS; it never publishes, so it cannot disturb the run. Topics:
    eee40016/sync            StepStart    the laptop opens a 5-minute control step
    eee40016/uplink/edge     Measurement  what the Pi reports (cars plugged in, kWh so far)
    eee40016/downlink/edge   Setpoint     the DOE command: envelope, limit, trust, fallback
    eee40016/ack/edge        Ack          what each charge point really drew this step
    eee40016/status/edge     online / offline (retained)

Needs: Python 3 + tkinter, and paho-mqtt for the broker mode. Put this file inside
pi_package/ (paho/ is already there) or pip install "paho-mqtt>=2.1,<3".

Time on screen is SIMULATED time (the evening 16:00-22:00 in the twin), not the wall clock.
"""
import argparse
import json
import math
import os
import random
import sys
import threading
import time
import tkinter as tk
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                     # paho/, messages.py, edge.py when in pi_package

PREFIX = "eee40016"
SCHEMA = 2
FONT, MONO = "DejaVu Sans", "DejaVu Sans Mono"

BG, PANEL, FG, DIM, GRID = "#14181f", "#1c222c", "#e8ecf2", "#8b95a5", "#2a323e"
GREEN, AMBER, RED, BLUE, VIOLET = "#3ecf6e", "#f0b429", "#ef5350", "#4ea1ff", "#b48cff"


# ============================================================================
# Feed: turns messages into one snapshot of "what the charge points are doing now"
# ============================================================================
class Feed:
    def __init__(self, node="edge"):
        self.node = node
        self.lock = threading.Lock()
        self.online = None            # None = unknown, True/False from the retained status
        self.last_rx = None           # wall clock of the last message
        self.schema_warning = ""
        self.n_msgs = 0
        self.evenings = 0
        self.reset_evening()

    def reset_evening(self):
        self.step = None              # current control step
        self.t_from = None
        self.t_to = None              # simulated minutes past midnight
        self.t_start = None           # first t_from of the evening, for the chart
        self.ev = {}                  # ev name -> {"connected", "delivered_kwh", "wanted_kwh"}
        self.draws = {}               # ev name -> kW drawn in the last acknowledged step
        self.ack_step = None
        self.applied_fallback = False  # the Pi charged on its own fallback in the last step
        self.sp = None                # last setpoint dict
        self.history = {}             # step -> dict(t, env, limit, fb, draw)
        self.n_fallback = 0
        self.n_steps = 0

    # topic kind is "sync", "uplink", "downlink", "ack" or "status"
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
            if kind == "sync":
                step = int(d.get("step", 0))
                if self.step is not None and step < self.step:       # a new evening began
                    self.reset_evening()
                    self.evenings += 1
                elif self.step is None:
                    self.evenings = max(self.evenings, 1)
                self.step, self.t_from, self.t_to = step, d.get("t_from"), d.get("t_to")
                if self.t_start is None:
                    self.t_start = self.t_from
            elif kind == "uplink":
                ev = d.get("ev") or {}
                if ev:
                    self.ev = ev
            elif kind == "downlink":
                self.sp = d
                h = self.history.setdefault(int(d.get("step", -1)), {})
                h.update(t=d.get("t_to"), env=float(d.get("envelope_kw", 0.0)),
                         limit=float(d.get("limit_kw", 0.0)), sp_fb=bool(d.get("fallback")))
            elif kind == "ack":
                self.draws = dict(d.get("draws") or {})
                self.ack_step = int(d.get("step", -1))
                self.applied_fallback = bool(d.get("fallback"))
                self.n_steps += 1
                self.n_fallback += 1 if self.applied_fallback else 0
                h = self.history.setdefault(self.ack_step, {})
                h.update(fb=self.applied_fallback, draw=sum(self.draws.values()),
                         cars=sum(1 for v in self.draws.values() if v > 1e-9))
                if h.get("t") is None:
                    h["t"] = self.t_to

    def snapshot(self):
        with self.lock:
            s = dict(self.__dict__)
            s.pop("lock")
            s["ev"] = {k: dict(v) for k, v in self.ev.items()}
            s["draws"] = dict(self.draws)
            s["history"] = {k: dict(v) for k, v in self.history.items()}
            s["age"] = None if self.last_rx is None else time.monotonic() - self.last_rx
            return s


# ============================================================================
# Sources of messages
# ============================================================================
def start_mqtt(feed, broker, port, node):
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        raise SystemExit("paho-mqtt not found: put this file inside pi_package/ (it ships paho/), "
                         'or pip install "paho-mqtt>=2.1,<3"')
    cid = "ev-node-ui-%04x" % random.randrange(0x10000)      # unique: two UIs may watch at once
    try:
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid)
    except AttributeError:                                     # paho 1.x
        c = mqtt.Client(client_id=cid)
    topics = {"%s/sync" % PREFIX: "sync",
              "%s/uplink/%s" % (PREFIX, node): "uplink",
              "%s/downlink/%s" % (PREFIX, node): "downlink",
              "%s/ack/%s" % (PREFIX, node): "ack",
              "%s/status/%s" % (PREFIX, node): "status"}
    state = {"connected": False}

    def on_connect(cl, ud, flags, rc, props=None):
        state["connected"] = getattr(rc, "value", rc) == 0
        for t in topics:                                       # re-subscribe after reconnects
            cl.subscribe(t, qos=1)

    def on_disconnect(cl, ud, *args):
        state["connected"] = False

    def on_message(cl, ud, msg):
        kind = topics.get(msg.topic)                           # brokers may hand us strays
        if kind is None:
            return
        try:
            raw = msg.payload.decode()
            feed.handle(kind, raw if kind == "status" else json.loads(raw))
        except Exception:                                      # never kill the network thread
            pass

    c.on_connect, c.on_disconnect, c.on_message = on_connect, on_disconnect, on_message
    c.reconnect_delay_set(1, 10)
    c.connect_async(broker, port)
    c.loop_start()
    return state


def start_demo(feed, node="edge"):
    """A scripted evening that feeds Feed the same message dicts MQTT would. Uses the
    project's own ChargePointFleet and session file when they sit beside this file (as in
    pi_package/), otherwise 22 made-up cars. One control step ~ 0.5 s, repeats forever."""
    try:
        from edge import ChargePointFleet
        path = os.path.join(HERE, "sessions", "seed_7_s1.json")
        sessions = [SimpleNamespace(**s) for s in json.load(open(path, encoding="utf-8"))["sessions"]]
        make = lambda: ChargePointFleet(sessions, 1.4, 1.4)
        make()
    except Exception:
        make = None

    def fake_fleet():
        rnd = random.Random(7)
        cars = {"EV_LOAD%d" % (i + 1): (960 + rnd.choice([0, 0, 30, 60, 90, 120, 150]),
                                       round(rnd.uniform(3, 14), 2)) for i in range(22)}

        class F:
            delivered = {n: 0.0 for n in cars}

            def status(self, t):
                return {n: {"connected": a <= t, "delivered_kwh": round(self.delivered[n], 6),
                            "wanted_kwh": w} for n, (a, w) in cars.items()}

            def apply(self, limit, t, minutes, *a, **k):
                kw, draws = (1.4 if limit is None else limit), {}
                for n, (arr, w) in cars.items():
                    want = w - self.delivered[n]
                    if arr <= t and want > 1e-9:
                        draws[n] = min(kw, want * 60.0 / minutes)
                        self.delivered[n] += draws[n] * minutes / 60.0
                return SimpleNamespace(draws=draws, fallback=limit is None)
        return F()

    def run():
        feed.handle("status", "online")
        rnd = random.Random(11)
        while True:
            f = make() if make else fake_fleet()
            for step in range(72):                              # 16:00-22:00, 5-minute steps
                t_from, t_to = 960 + 5 * step, 965 + 5 * step
                feed.handle("sync", {"type": "StepStart", "schema": SCHEMA, "step": step,
                                     "t_from": t_from, "t_to": t_to, "readings": {}})
                feed.handle("uplink", {"type": "Measurement", "schema": SCHEMA, "node": node,
                                       "seq": step, "sent": t_to, "readings": {},
                                       "ev": f.status(t_to)})
                peak = math.exp(-((t_to - 1110) / 55.0) ** 2)    # the 18:30 evening peak
                env = round(max(1.0, 7.2 - 5.6 * peak), 1)
                trust = round(max(0.0, min(1.0, 0.85 + rnd.uniform(-0.35, 0.15))), 2)
                lost = rnd.random() < 0.12
                limit = round(1.4 + trust * (env - 1.4), 1)
                feed.handle("downlink", {"type": "Setpoint", "schema": SCHEMA, "node": node,
                                         "step": step, "t_to": t_to, "limit_kw": limit,
                                         "trust": trust, "envelope_kw": env, "fallback": lost})
                ack = f.apply(None if lost else limit, t_to, 5.0, node, step)
                feed.handle("ack", {"type": "Ack", "schema": SCHEMA, "node": node, "step": step,
                                    "draws": ack.draws, "fallback": ack.fallback})
                time.sleep(0.5)
            time.sleep(4.0)

    threading.Thread(target=run, daemon=True).start()
    return "DEMO (scripted, not MQTT)" + ("" if make else " - made-up cars")


# ============================================================================
# The window
# ============================================================================
def short_name(n):
    for p in ("EV_LOAD", "EV_", "LOAD"):
        if n.startswith(p) and n[len(p):]:
            return "#" + n[len(p):]
    return n[:7]


def name_key(n):
    digits = "".join(ch for ch in n if ch.isdigit())
    return (int(digits) if digits else 1 << 30, n)


def hhmm(t):
    if t is None:
        return "--:--"
    t = int(round(t))
    return "%02d:%02d" % ((t // 60) % 24, t % 60)


class App:
    BASE_W, BASE_H = 800, 480

    def __init__(self, root, feed, scale=None, node="edge", source="", link=None):
        self.root, self.feed, self.node, self.source, self.link = root, feed, node, source, link
        root.title("EV charge points - live view")
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
        self.tick()

    def tick(self):
        try:
            self.draw(self.feed.snapshot())
        finally:
            self.root.after(250, self.tick)

    def draw(self, s):
        c = self.cv
        c.delete("all")
        fonts = {}

        def txt(*a, **kw):
            i = c.create_text(*a, **kw)
            fonts[i] = kw["font"]
            return i

        sp = s["sp"] or {}
        fb_now = s["applied_fallback"] or bool(sp.get("fallback"))

        # ---------------------------------------------------------------- header
        txt(20, 18, anchor="w", text="EV charge points", fill=FG, font=(FONT, 15, "bold"))
        if s["online"] is True:
            chip, ccol = "Pi node ONLINE", GREEN
        elif s["online"] is False:
            chip, ccol = "Pi node OFFLINE", RED
        else:
            chip, ccol = "Pi node: no status yet", DIM
        c.create_oval(236, 12, 248, 24, fill=ccol, outline="")
        txt(254, 18, anchor="w", text=chip, fill=ccol, font=(FONT, 11, "bold"))
        txt(780, 18, anchor="e", fill=DIM, font=(MONO, 12),
            text="sim %s   step %s" % (hhmm(s["t_to"]), "-" if s["step"] is None else s["step"]))

        # ---------------------------------------------------------------- tiles
        def tile(x, title, value, sub, col=FG, bar=None, bar_col=None):
            w = 182
            c.create_rectangle(x, 40, x + w, 132, fill=PANEL, outline="")
            txt(x + 12, 54, anchor="w", text=title, fill=DIM, font=(FONT, 10))
            txt(x + 12, 84, anchor="w", text=value, fill=col, font=(FONT, 22, "bold"))
            txt(x + 12, 116, anchor="w", text=sub, fill=DIM, font=(FONT, 9))
            if bar is not None:
                c.create_rectangle(x + 12, 102, x + w - 12, 106, fill=GRID, outline="")
            if bar:
                c.create_rectangle(x + 12, 102, x + 12 + (w - 24) * max(0.0, min(1.0, bar)), 106,
                                   fill=bar_col or col, outline="")

        have_sp = bool(sp)
        tile(20, "DOE envelope (per point)",
             "%.1f kW" % sp["envelope_kw"] if have_sp else "--",
             "what the network allows", VIOLET)
        if fb_now:
            tile(213, "Applied on the Pi", "FALLBACK", "Pi uses its local 1.4 kW", AMBER)
        else:
            tile(213, "DOE limit (per point)",
                 "%.1f kW" % sp["limit_kw"] if have_sp else "--",
                 "command sent to the Pi", BLUE)
        tr = sp.get("trust") if have_sp else None
        tcol = DIM if tr is None else GREEN if tr >= 0.7 else AMBER if tr >= 0.4 else RED
        tile(406, "Data trust (alpha)", "--" if tr is None else "%.2f" % tr,
             "1 = fresh data, 0 = none", tcol, bar=tr if tr is not None else 0.0)
        total = sum(s["draws"].values())
        charging = sum(1 for v in s["draws"].values() if v > 1e-9)
        plugged = sum(1 for e in s["ev"].values() if e.get("connected"))
        tile(599, "Drawn by all %d points" % len(s["ev"]) if s["ev"] else "Drawn by all points",
             "%.1f kW" % total if s["ack_step"] is not None else "--",
             "%d charging  -  %d plugged in" % (charging, plugged), GREEN)

        # ---------------------------------------------------------------- charge points
        names = sorted(set(s["ev"]) | set(s["draws"]), key=name_key)
        gx0, gy0, gx1, gy1 = 20, 146, 780, 320
        if names:
            cols = min(11, len(names))
            rows = int(math.ceil(len(names) / float(cols)))
            gap = 6
            cw = (gx1 - gx0 - gap * (cols - 1)) / float(cols)
            ch = min(84.0, (gy1 - gy0 - gap * (rows - 1)) / float(rows))
            for i, n in enumerate(names):
                r, col = divmod(i, cols)
                x, y = gx0 + col * (cw + gap), gy0 + r * (ch + gap)
                e = s["ev"].get(n, {})
                draw = s["draws"].get(n, 0.0)
                want = float(e.get("wanted_kwh", 0.0) or 0.0)
                got = float(e.get("delivered_kwh", 0.0) or 0.0)
                frac = 0.0 if want <= 0 else max(0.0, min(1.0, got / want))
                if draw > 1e-9:
                    fill, edge, state, scol = "#163a27", GREEN, "%.1f kW" % draw, GREEN
                elif want > 0 and got >= want - 1e-6:
                    fill, edge, state, scol = "#14304f", BLUE, "full", BLUE
                elif e.get("connected"):
                    fill, edge, state, scol = "#3a3014", AMBER, "waiting", AMBER
                else:
                    fill, edge, state, scol = PANEL, GRID, "away", DIM
                c.create_rectangle(x, y, x + cw, y + ch, fill=fill, outline=edge, width=1)
                txt(x + cw / 2, y + 13, text=short_name(n), fill=FG, font=(FONT, 10, "bold"))
                txt(x + cw / 2, y + ch / 2 - 4, text=state, fill=scol, font=(FONT, 10, "bold"))
                bx0, bx1, by = x + 6, x + cw - 6, y + ch - 10
                c.create_rectangle(bx0, by, bx1, by + 5, fill=GRID, outline="")
                if frac > 0:
                    c.create_rectangle(bx0, by, bx0 + (bx1 - bx0) * frac, by + 5, fill=scol if
                                       scol != DIM else FG, outline="")
                txt(x + cw / 2, y + ch - 20, text="%.1f/%.1f" % (got, want) if want else "",
                    fill=DIM, font=(FONT, 7))
        else:
            c.create_rectangle(gx0, gy0, gx1, gy1, fill=PANEL, outline="")
            txt((gx0 + gx1) / 2, (gy0 + gy1) / 2, fill=DIM, font=(FONT, 12),
                text="charge points appear when the Pi sends its first measurement")

        # ---------------------------------------------------------------- history chart
        hx0, hy0, hx1, hy1 = 64, 344, 780, 446
        c.create_rectangle(hx0, hy0, hx1, hy1, fill=PANEL, outline="")
        hist = sorted((k, v) for k, v in s["history"].items() if v.get("t") is not None)
        t0 = s["t_start"] if s["t_start"] is not None else 960.0
        t_end = max(t0 + 360.0, max([v["t"] for _, v in hist] or [t0]))
        ymax = max([7.2] + [v.get("env", 0.0) for _, v in hist] + [v.get("limit", 0.0) for _, v in hist])
        X = lambda t: hx0 + (t - t0) / (t_end - t0) * (hx1 - hx0)
        Y = lambda kw: hy1 - kw / ymax * (hy1 - hy0 - 6)
        for kw in (0, 2, 4, 6):
            if kw <= ymax:
                c.create_line(hx0, Y(kw), hx1, Y(kw), fill=GRID)
                txt(hx0 - 6, Y(kw), anchor="e", text="%d" % kw, fill=DIM, font=(FONT, 8))
        txt(hx0 - 6, hy0 - 9, anchor="e", text="kW", fill=DIM, font=(FONT, 8))
        h = int(math.ceil(t0 / 60.0)) * 60
        while h <= t_end:
            txt(X(h), hy1 + 9, text=hhmm(h), fill=DIM, font=(FONT, 8))
            h += 60

        def series(key, colr, dash=None, width=2):
            pts = [(X(v["t"]), Y(v[key])) for _, v in hist if key in v]
            if len(pts) >= 2:
                flat = [p for xy in pts for p in xy]
                c.create_line(*flat, fill=colr, width=width, dash=dash)
            elif len(pts) == 1:
                x, y = pts[0]
                c.create_oval(x - 2, y - 2, x + 2, y + 2, fill=colr, outline="")

        series("env", VIOLET, dash=(4, 3))
        series("limit", BLUE)
        for _, v in hist:
            if v.get("fb"):
                x = X(v["t"])
                c.create_rectangle(x - 1.5, hy1 - 8, x + 1.5, hy1, fill=AMBER, outline="")
        lx, ly = hx0 + 4, hy0 - 9
        c.create_line(lx, ly, lx + 18, ly, fill=VIOLET, width=2, dash=(4, 3))
        txt(lx + 24, ly, anchor="w", text="envelope", fill=DIM, font=(FONT, 8))
        c.create_line(lx + 90, ly, lx + 108, ly, fill=BLUE, width=2)
        txt(lx + 114, ly, anchor="w", text="DOE limit", fill=DIM, font=(FONT, 8))
        c.create_rectangle(lx + 230, ly - 4, lx + 233, ly + 4, fill=AMBER, outline="")
        txt(lx + 239, ly, anchor="w", fill=DIM, font=(FONT, 8),
            text="fallback step (%d of %d)" % (s["n_fallback"], s["n_steps"]))

        # ---------------------------------------------------------------- footer
        age = s["age"]
        if s["schema_warning"]:
            foot, fcol = s["schema_warning"], RED
        elif self.link is not None and not self.link["connected"]:
            foot, fcol = "not connected to the broker at %s - is broker.py running?" % self.source, RED
        elif age is None:
            foot, fcol = "connected to %s - waiting for the laptop to start an evening ..." % self.source, DIM
        elif age > 10.0:
            foot, fcol = "no messages for %.0f s (evening finished or paused?)  -  %s" % (age, self.source), AMBER
        else:
            foot, fcol = "%s  -  %d messages  -  evening %d" % (self.source, s["n_msgs"], s["evenings"]), DIM
        txt(400, 470, text=foot, fill=fcol, font=(FONT, 9))

        k = self.k
        if abs(k - 1.0) > 1e-6:
            c.scale("all", 0, 0, k, k)
            for i, f in fonts.items():
                c.itemconfigure(i, font=(f[0], max(6, round(f[1] * k))) + tuple(f[2:]))


def main():
    ap = argparse.ArgumentParser(description="Live view of the EV charge-point node")
    ap.add_argument("--broker", default="127.0.0.1", help="MQTT broker address")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--node", default="edge", help="edge node name (default: edge)")
    ap.add_argument("--demo", action="store_true", help="no broker: a scripted evening")
    ap.add_argument("--scale", type=float, default=None, help="force a canvas scale, e.g. 0.7")
    a = ap.parse_args()
    feed = Feed(a.node)
    link = None
    if a.demo:
        source = start_demo(feed, a.node)
    else:
        link = start_mqtt(feed, a.broker, a.port, a.node)
        source = "broker %s:%d" % (a.broker, a.port)
    root = tk.Tk()
    App(root, feed, a.scale, a.node, source, link)
    root.mainloop()


if __name__ == "__main__":
    main()
