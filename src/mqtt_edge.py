"""The edge over MQTT: hardware in the loop, speaking the protocol in messages.py.

Two halves, one per machine:

    PiNode     runs on the Raspberry Pi. Wraps a controller object, by default the
               ChargePointFleet stand-in, behind MQTT. Lomitha's controller goes in the
               same way and this wrapper stays as it is. There is no control logic in here,
               only message handling, which is the point.

    MqttEdge   runs in the twin. Presents the same two calls as InProcessEdge,
               start_step() and apply(), so the sweep cannot tell which it is using.

And the same pair for the battery, when it runs on the Pi instead of inside the twin:

    BatteryNode    on the Pi: wraps a battery object (the stand-in, or Gia's class) and
                   answers the twin's battery calls
    RemoteBattery  in the twin: the battery slot (StudyRun.battery_cls), each call one
                   round trip to the BatteryNode, so the twin cannot tell it apart either

One control step, lock-step as Section V-C of the plan specifies:

    twin  -> sync             StepStart: open step k, here is what your meters read
    edge  -> uplink/<node>    Measurement: meter readings and car status, seq-numbered
    twin                      injector ages it in simulated time, trust, envelope
    twin  -> downlink/<node>  Setpoint: the limit and the trust index
    edge  -> ack/<node>       Ack: what was actually drawn. The twin waits for this,
                              with a wall-clock timeout that logs a miss, not a stall

Physical LAN latency never enters the simulated delay. It is measured and logged so its
size can be reported, which the plan requires.

Run the Pi side:   py src/mqtt_edge.py --broker <pc address> --seed 7
"""
import argparse
import os
import queue
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import messages as M                       # noqa: E402

try:
    import paho.mqtt.client as mqtt
except ImportError:                        # the sweep never needs MQTT; only HIL does
    mqtt = None


def _client(client_id):
    if mqtt is None:
        raise RuntimeError("paho-mqtt is not installed: pip install paho-mqtt")
    if hasattr(mqtt, "CallbackAPIVersion"):          # paho-mqtt 2.x
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    return mqtt.Client(client_id=client_id)          # paho-mqtt 1.x, e.g. Raspberry Pi OS apt


def _decode_for(msg, *topics):
    """The message if it arrived on one of `topics` and decodes, else None. Brokers can
    hand a client messages it never asked for: the laptop's broker (amqtt) delivers other
    nodes' retained "online" status to new subscribers. Callbacks that raised would kill
    the client's network thread, so anything unexpected is skipped here instead."""
    if msg.topic not in topics:
        return None
    try:
        return M.decode(msg.payload)
    except (ValueError, TypeError):           # MessageError and JSON errors are ValueErrors
        return None


# ---------------------------------------------------------------------- edge side

class PiNode:
    """A controller behind MQTT. The controller does the work; this only carries messages.

    `controller` needs status(t) -> {ev: {...}} and apply(limit_kw or None, t, minutes,
    node, step, issued_at=None, valid_from=None, valid_until=None) -> messages.Ack, where t
    is the step's t_to in simulated minutes and the three keywords may be None (a fallback
    or a pre-schema-2 setpoint). ChargePointFleet has exactly that shape.
    """

    def __init__(self, controller, node="edge", broker="127.0.0.1", port=1883,
                 step_min=5.0, setpoint_timeout_s=5.0, sample_min=0.5):
        self.controller = controller
        self.sample_min = sample_min
        self.node = node
        self.step_min = step_min
        self.timeout = setpoint_timeout_s
        self.seq = 0
        self.pending = None                  # (step, t_to, deadline) awaiting a setpoint
        self.lock = threading.Lock()
        # set once the broker has accepted the connection (CONNACK), not merely when a
        # socket opened: through an SSH tunnel the socket opens before any broker answers
        self.connected = threading.Event()
        self.c = _client("pi-%s" % node)
        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message
        # if the Pi drops off the network, the broker tells the twin it is offline
        self.c.will_set(M.topic("status", node), "offline", qos=1, retain=True)
        self.c.connect(broker, port)
        self.log = []

    def _on_connect(self, c, userdata, flags, rc, props=None):
        c.subscribe(M.topic("sync"), qos=1)
        c.subscribe(M.topic("downlink", self.node), qos=1)
        c.publish(M.topic("status", self.node), "online", qos=1, retain=True)
        if getattr(rc, "value", rc) == 0:        # int in paho 1.x, ReasonCode in 2.x
            self.connected.set()

    def _on_disconnect(self, c, userdata, *args):  # the signature differs in paho 1.x / 2.x
        self.connected.clear()

    def _on_message(self, c, userdata, msg):
        m = _decode_for(msg, M.topic("sync"), M.topic("downlink", self.node))
        if isinstance(m, M.StepStart):
            with self.lock:
                self._act_on_fallback_if_overdue()
                status = self.controller.status(m.t_to)
                out, t = [], m.t_from
                while True:                         # one measurement per 30-second sample
                    t = round(t + self.sample_min, 9)
                    if t > m.t_to + 1e-9:
                        break
                    readings = m.profile.get(str(int(t + 1e-9)), m.readings)
                    out.append(M.Measurement(node=self.node, seq=self.seq, sent=t,
                                             readings=readings, ev=status))
                    self.seq += 1
                self.pending = (m.step, m.t_to, time.monotonic() + self.timeout)
            for meas in out:
                c.publish(M.topic("uplink", self.node), meas.to_json(), qos=1)
        elif isinstance(m, M.Setpoint):
            with self.lock:
                if not self.pending or self.pending[0] != m.step:
                    self.log.append(("stale setpoint", m.step))
                    return
                step, t_to, _ = self.pending
                self.pending = None
                limit = None if m.fallback else m.limit_kw
                ack = self.controller.apply(limit, t_to, self.step_min, self.node, step,
                                            issued_at=m.t_to, valid_from=m.valid_from,
                                            valid_until=m.valid_until)
            c.publish(M.topic("ack", self.node), ack.to_json(), qos=1)

    def _act_on_fallback_if_overdue(self):
        """No setpoint arrived for the last step in time: charge on the local fallback."""
        if self.pending and time.monotonic() > self.pending[2]:
            step, t_to, _ = self.pending
            self.pending = None
            ack = self.controller.apply(None, t_to, self.step_min, self.node, step)
            self.c.publish(M.topic("ack", self.node), ack.to_json(), qos=1)
            self.log.append(("fallback", step))

    def serve_forever(self):
        self.c.loop_forever()

    def start(self):
        self.c.loop_start()
        return self

    def stop(self):
        try:
            self.c.publish(M.topic("status", self.node), "offline", qos=1,
                           retain=True).wait_for_publish(2)
        except Exception:                               # already gone; the will covers it
            pass
        self.c.loop_stop()
        self.c.disconnect()


class BatteryNode:
    """A battery behind MQTT, on the Raspberry Pi. Answers the twin's three battery calls
    (messages.BatteryRequest) by calling a battery object, and nothing else.

    `make_battery(soc_bias=..., enabled=...)` builds the battery for each evening: the
    stand-in BatteryStandIn, or Gia's class. `narrate`, if given, is called after each
    commit with (battery, p_kw, q_kvar) so the Pi's screen can show what it is doing.
    """

    def __init__(self, make_battery, node="battery", broker="127.0.0.1", port=1883,
                 narrate=None):
        self.make_battery = make_battery
        self.node = node
        self.narrate = narrate
        self.battery = None
        self.last = None                  # time.monotonic() of the last request
        self._q = 0.0                     # Q from the latest response, for narrate
        self.lock = threading.Lock()
        self.connected = threading.Event()
        self.c = _client("pi-%s" % node)
        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message
        self.c.will_set(M.topic("status", node), "offline", qos=1, retain=True)
        self.c.connect(broker, port)

    def _on_connect(self, c, userdata, flags, rc, props=None):
        c.subscribe(M.topic("breq", self.node), qos=1)
        c.publish(M.topic("status", self.node), "online", qos=1, retain=True)
        if getattr(rc, "value", rc) == 0:
            self.connected.set()

    def _on_disconnect(self, c, userdata, *args):
        self.connected.clear()

    def _status(self):
        b = self.battery
        try:
            st = {k: v for k, v in dict(b.status()).items()
                  if isinstance(v, (bool, int, float, str))}
        except Exception:                            # status() is optional detail
            st = {}
        st["soc"] = float(b.soc)                     # what the twin records as battery.soc
        st["enabled"] = bool(b.enabled)
        return st

    def _on_message(self, c, userdata, msg):
        m = _decode_for(msg, M.topic("breq", self.node))
        if not isinstance(m, M.BatteryRequest):
            return
        self.last = time.monotonic()
        with self.lock:
            try:
                if m.op == "reset":
                    self.battery = self.make_battery(soc_bias=m.soc_bias, enabled=m.enabled)
                    reply = M.BatteryReply(self.node, m.req, status=self._status())
                elif self.battery is None:
                    reply = M.BatteryReply(self.node, m.req,
                                           error="no evening started on this battery yet")
                elif m.op == "response":
                    p, q = self.battery.response(m.v, m.setpoint_kw)
                    self._q = float(q)
                    reply = M.BatteryReply(self.node, m.req, p_kw=float(p), q_kvar=float(q))
                else:
                    self.battery.commit(m.p_kw, m.minutes)
                    reply = M.BatteryReply(self.node, m.req, status=self._status())
                    if self.narrate:
                        self.narrate(self.battery, m.p_kw, self._q)
            except Exception as e:                   # reported to the twin, which stops
                reply = M.BatteryReply(self.node, m.req, error="%s: %s"
                                       % (type(e).__name__, e))
        c.publish(M.topic("bresp", self.node), reply.to_json(), qos=1)

    def start(self):
        self.c.loop_start()
        return self

    def stop(self):
        try:
            self.c.publish(M.topic("status", self.node), "offline", qos=1,
                           retain=True).wait_for_publish(2)
        except Exception:
            pass
        self.c.loop_stop()
        self.c.disconnect()


# ---------------------------------------------------------------------- twin side

class MqttEdge:
    """The twin's view of a remote edge. Same interface as InProcessEdge."""

    def __init__(self, meter_readings, node="edge", broker="127.0.0.1", port=1883,
                 step_min=5.0, reply_timeout_s=10.0):
        self.meter_readings = meter_readings
        self.node = node
        self.step_min = step_min
        self.timeout = reply_timeout_s
        self.inbox = {"uplink": queue.Queue(), "ack": queue.Queue()}
        self.total_kwh = 0.0
        self.demanded_kwh = 0.0
        self.misses = []
        self.lan_ms = []                    # physical round trips, logged not simulated
        self.edge_online = threading.Event()
        self.c = _client("twin")
        self.c.on_connect = lambda c, u, f, rc, p=None: (
            c.subscribe(M.topic("uplink", node), qos=1),
            c.subscribe(M.topic("ack", node), qos=1),
            c.subscribe(M.topic("status", node), qos=1))
        self.c.on_message = self._on_message
        self.c.connect(broker, port)
        self.c.loop_start()
        self._t_to = None

    def _on_message(self, c, userdata, msg):
        # by the exact topic: another node's retained status (say the battery's) must never
        # count as this edge being online
        if msg.topic == M.topic("status", self.node):
            if msg.payload == b"online":
                self.edge_online.set()
            else:
                self.edge_online.clear()
            return
        for kind in self.inbox:
            m = _decode_for(msg, M.topic(kind, self.node))
            if m is not None:
                self.inbox[kind].put(m)
                return

    def wait_for_edge(self, timeout_s=30.0):
        """True once the edge node has said it is online (its retained status message)."""
        return self.edge_online.wait(timeout_s)

    def _wait(self, kind, match):
        deadline = time.monotonic() + self.timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            try:
                m = self.inbox[kind].get(timeout=left)
            except queue.Empty:
                return None
            if match(m):
                return m

    def start_step(self, step, t_from, t_to, period_min=0.5):
        self._t_to = t_to
        sent = time.perf_counter()
        profile = {str(mm): self.meter_readings(mm)
                   for mm in range(int(t_from), int(t_to) + 1)}
        self.c.publish(M.topic("sync"),
                       M.StepStart(step, t_from, t_to, self.meter_readings(int(t_to)),
                                   profile).to_json(), qos=1)
        want = int(round((t_to - t_from) / period_min))
        got = []
        while len(got) < want:
            m = self._wait("uplink", lambda x: t_from < x.sent <= t_to + 1e-9)
            if m is None:
                self.misses.append(("measurement", step))
                raise TimeoutError("edge %s sent %d of %d samples for step %d"
                                   % (self.node, len(got), want, step))
            got.append(m)
        self.lan_ms.append(1000.0 * (time.perf_counter() - sent))
        got.sort(key=lambda x: x.sent)
        if not self.demanded_kwh:
            self.demanded_kwh = sum(s["wanted_kwh"] for s in got[-1].ev.values())
        return [(x.sent, x.readings) for x in got], got[-1].ev

    def apply(self, setpoint):
        sent = time.perf_counter()
        self.c.publish(M.topic("downlink", self.node), setpoint.to_json(), qos=1)
        ack = self._wait("ack", lambda x: x.step == setpoint.step)
        if ack is None:
            # logged, not stalled: the edge will have fallen back on its own
            self.misses.append(("ack", setpoint.step))
            return M.Ack(node=self.node, step=setpoint.step, draws={}, fallback=True)
        self.lan_ms.append(1000.0 * (time.perf_counter() - sent))
        self.total_kwh += sum(ack.draws.values()) * self.step_min / 60.0
        return ack

    def close(self):
        self.c.loop_stop()
        self.c.disconnect()


class RemoteBattery:
    """The battery slot of the twin (StudyRun.battery_cls) for a battery on the Pi.

    Same interface as BatteryStandIn: built with soc_bias and enabled, then response(),
    commit(), status(), .soc and .enabled. Each call is one MQTT round trip to a
    BatteryNode, so the twin runs exactly as it does with the battery in process; the
    values travel as JSON, which carries floats exactly. Connect once before the first
    evening:

        RemoteBattery.connect(broker, port)
        RemoteBattery.wait_online(60)
        study.battery_cls = RemoteBattery
    """

    _client = None
    _node = "battery"
    _timeout = 10.0
    _req = 0
    _replies = queue.Queue()
    online = threading.Event()
    round_trips_ms = []

    @classmethod
    def connect(cls, broker="127.0.0.1", port=1883, node="battery", timeout_s=10.0):
        cls._node, cls._timeout = node, timeout_s

        def on_connect(c, userdata, flags, rc, props=None):
            c.subscribe(M.topic("bresp", node), qos=1)
            c.subscribe(M.topic("status", node), qos=1)

        def on_message(c, userdata, msg):
            if msg.topic == M.topic("status", node):
                (cls.online.set if msg.payload == b"online" else cls.online.clear)()
                return
            r = _decode_for(msg, M.topic("bresp", node))
            if isinstance(r, M.BatteryReply):
                cls._replies.put(r)

        cls._client = _client("twin-battery")
        cls._client.on_connect = on_connect
        cls._client.on_message = on_message
        cls._client.connect(broker, port)
        cls._client.loop_start()

    @classmethod
    def wait_online(cls, timeout_s=30.0):
        """True once the battery node has said it is online (its retained status)."""
        return cls.online.wait(timeout_s)

    @classmethod
    def close(cls):
        if cls._client is not None:
            cls._client.loop_stop()
            cls._client.disconnect()
            cls._client = None

    def __init__(self, soc_bias=0.0, enabled=True):
        self._take(self._call(op="reset", soc_bias=soc_bias, enabled=enabled).status)

    def _call(self, **kw):
        cls = type(self)
        if cls._client is None:
            raise RuntimeError("RemoteBattery.connect(broker, port) must be called first")
        cls._req += 1
        req = M.BatteryRequest(node=cls._node, req=cls._req, **kw)
        sent = time.perf_counter()
        cls._client.publish(M.topic("breq", cls._node), req.to_json(), qos=1)
        deadline = time.monotonic() + cls._timeout
        while True:
            left = deadline - time.monotonic()
            try:
                if left <= 0:
                    raise queue.Empty
                r = cls._replies.get(timeout=left)
            except queue.Empty:
                raise RuntimeError("the battery on the Pi did not answer request %d (%s) "
                                   "within %.0f s" % (req.req, req.op, cls._timeout))
            if r.req == req.req:                     # anything else is a stale reply
                break
        if r.error:
            raise RuntimeError("the battery on the Pi failed: %s" % r.error)
        cls.round_trips_ms.append(1000.0 * (time.perf_counter() - sent))
        return r

    def _take(self, status):
        self._status = dict(status)
        self.soc = float(status.get("soc", 0.0))
        self.enabled = bool(status.get("enabled", True))

    def response(self, v_local, setpoint_kw=0.0):
        r = self._call(op="response", v=v_local, setpoint_kw=setpoint_kw)
        return r.p_kw, r.q_kvar

    def commit(self, p_kw, minutes):
        self._take(self._call(op="commit", p_kw=p_kw, minutes=minutes).status)

    def status(self):
        return dict(self._status)


# ---------------------------------------------------------------------- local broker

def start_local_broker(port=1883, host="127.0.0.1"):
    """A pure-Python broker in a background thread, for tests and a laptop-only demo.

    host "0.0.0.0" listens on the network so a Raspberry Pi can connect (Windows asks
    whether to let Python through the firewall). Mosquitto on the Pi is the alternative;
    nothing else changes. Standalone: py tools/broker.py
    """
    import asyncio
    import logging
    logging.getLogger("amqtt").setLevel(logging.ERROR)
    logging.getLogger("transitions").setLevel(logging.ERROR)
    from amqtt.broker import Broker
    ready = threading.Event()
    cfg = {"listeners": {"default": {"type": "tcp", "bind": "%s:%d" % (host, port)}},
           "sys_interval": 0, "auth": {"allow-anonymous": True}}

    def run():
        async def main():
            b = Broker(cfg)
            await b.start()
            ready.set()
            while True:
                await asyncio.sleep(3600)
        asyncio.run(main())

    threading.Thread(target=run, daemon=True).start()
    if not ready.wait(15):
        raise RuntimeError("local MQTT broker did not start")
    return port


def main():
    ap = argparse.ArgumentParser(description="Run the edge node: a charge-point "
                                 "controller behind MQTT. This is the Raspberry Pi side.")
    ap.add_argument("--broker", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--node", default="edge")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    from feeder_csv import load_feeder
    from envelope import choose_ev_connections
    from ev_sessions import load_or_create
    from edge import ChargePointFleet
    import json
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = json.load(open(os.path.join(here, "config", "study.json"), encoding="utf-8"))
    f = load_feeder()
    evs = choose_ev_connections(f, cfg["cases"]["study"]["ev_connections"],
                                cfg["sweep"]["seeds"][0])
    case = cfg["cases"]["study"]
    fleet = ChargePointFleet(load_or_create(f, evs, a.seed, tag="_n%d" % len(evs),
                                            source=case.get("session_source", "vista"),
                                            plugin_model=case.get("plugin_model", "daily")),
                             cfg["controller_settings"]["fallback_kw"],
                             cfg["controller_settings"].get("uncovered_kw"))
    print("edge node %s: %d charge points, broker %s:%d"
          % (a.node, len(fleet.sessions), a.broker, a.port))
    PiNode(fleet, a.node, a.broker, a.port,
           cfg["study_window"]["control_period_minutes"]).serve_forever()


if __name__ == "__main__":
    main()
