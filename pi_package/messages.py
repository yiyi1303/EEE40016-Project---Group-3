"""The message contract between the twin and the edge nodes. Everyone shares this file.

Every message on every topic is defined here, with its fields, units and a validator, so
the format lives in one place and cannot drift between four people's code. Copy this file
verbatim onto the Raspberry Pi; do not re-type the field names.

Topics, following Section V-B and V-C of the research plan:

    eee40016/sync            twin -> edge    start of a control step, with the plant readings
    eee40016/uplink/<node>   edge -> twin    measurements, through the degradation injector
    eee40016/downlink/<node> twin -> edge    the operating limit and the trust index
    eee40016/ack/<node>      edge -> twin    what the edge actually applied, bypasses the injector
    eee40016/status/<node>   edge -> twin    "online" or "offline", retained, so the twin can
                                             check the edge is there before it starts

Only when the battery runs on the Raspberry Pi instead of inside the twin (optional):

    eee40016/breq/<node>     twin -> battery one call on the battery interface (BatteryRequest)
    eee40016/bresp/<node>    battery -> twin the answer (BatteryReply)

Payloads are JSON. Times are simulated minutes past midnight, never wall-clock time: the
edge runs against the simulation timestamp carried in each message (plan, Section V-C).
Field names mirror the IEEE 2030.5 / CSIP-AUS resources they stand in for, as the plan
states, but the transport is MQTT and the encoding is JSON, a declared simplification.

Units: kW, kvar, kWh, volts line-to-neutral, minutes.
"""
import json
from dataclasses import dataclass, field, asdict

SCHEMA_VERSION = 2     # 2: Setpoint carries its schedule entry and validity interval
PREFIX = "eee40016"


def topic(kind, node=None):
    if kind == "sync":
        return "%s/sync" % PREFIX
    if kind in ("uplink", "downlink", "ack", "status", "breq", "bresp"):
        if not node:
            raise ValueError("%s topics are per node" % kind)
        return "%s/%s/%s" % (PREFIX, kind, node)
    raise ValueError("unknown topic kind %r" % kind)


class MessageError(ValueError):
    pass


def _check(cond, msg):
    if not cond:
        raise MessageError(msg)


@dataclass
class _Msg:
    def to_json(self):
        d = asdict(self)
        d["type"] = type(self).__name__
        d["schema"] = SCHEMA_VERSION
        return json.dumps(d, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw):
        d = json.loads(raw)
        _check(d.pop("type", None) == cls.__name__, "expected a %s message" % cls.__name__)
        _check(d.pop("schema", None) == SCHEMA_VERSION,
               "schema version mismatch; both ends must share the same messages.py")
        m = cls(**d)
        m.validate()
        return m


@dataclass
class StepStart(_Msg):
    """twin -> edge, on eee40016/sync. Opens control step `step`.

    `readings` is what each connection-point meter reads over the window just ended: the
    plant is the twin's power flow, so the twin has to tell the edge what its meters see.
    The edge's measurement pipeline then publishes these as telemetry, through the
    injector, exactly as a real meter would.
    """
    step: int
    t_from: float
    t_to: float
    readings: dict                    # connection name -> kW at t_to
    # minute (as a string, JSON keys) -> {connection: kW}, covering the window, so the edge
    # can publish each 30-second sample with the reading at its own time. Readings named
    # PV_<connection> are PV output, positive.
    profile: dict = field(default_factory=dict)

    def validate(self):
        _check(self.step >= 0, "step must be non-negative")
        _check(self.t_to > self.t_from, "t_to must be after t_from")
        _check(all(isinstance(v, (int, float)) and v >= 0 for v in self.readings.values()),
               "readings must be non-negative kW")
        for minute, r in self.profile.items():
            _check(all(v >= 0 for v in r.values()), "profile readings must be non-negative")


@dataclass
class Measurement(_Msg):
    """edge -> twin, on eee40016/uplink/<node>. One telemetry sample.

    `seq` increases by one per sample from each node, and `sent` is the simulated send
    time. The trust metric needs both to tell a lost message from a late one.
    """
    node: str
    seq: int
    sent: float
    readings: dict                    # connection name -> kW
    ev: dict = field(default_factory=dict)  # ev name -> {"connected", "delivered_kwh", "wanted_kwh"}

    def validate(self):
        _check(self.seq >= 0, "seq must be non-negative")
        _check(all(v >= 0 for v in self.readings.values()), "readings must be non-negative")
        for name, s in self.ev.items():
            _check({"connected", "delivered_kwh", "wanted_kwh"} <= set(s),
                   "ev status for %s is missing fields" % name)
            _check(s["delivered_kwh"] <= s["wanted_kwh"] + 1e-6,
                   "%s has delivered more energy than it wanted" % name)


@dataclass
class Setpoint(_Msg):
    """twin -> edge, on eee40016/downlink/<node>. The limit for this control step.

    `limit_kw` is per charge point (equal share, assumption A8). `trust` is the data trust
    index alpha in [0, 1] from Section V-B, sent so the edge can log it and so a local
    fallback decision can use it.
    """
    node: str
    step: int
    t_to: float
    limit_kw: float
    trust: float
    envelope_kw: float
    # True when, in simulated time, no setpoint has reached the charge point recently enough
    # to act on. The edge then charges at its local fallback. Sent explicitly because the
    # downlink delay and loss are applied in simulated time; the physical message still
    # arrives, so the edge needs to be told what the simulation says it would have seen.
    fallback: bool = False
    # Schema 2 (plan amendment 25). The twin plans a schedule of 5-minute entries, an IEEE
    # 2030.5 DERControlList, and the edge acts on the entry for the current interval.
    #   issued_step   the step the schedule was planned at (2030.5 creationTime)
    #   entry         which entry of that schedule this is; -1 on a fallback setpoint
    #   valid_from    interval.start, simulated minutes
    #   valid_until   interval.start + interval.duration. The edge executes the limit only
    #                 inside [valid_from, valid_until) and reverts to its default outside it
    issued_step: int = -1
    entry: int = 0
    valid_from: float = None
    valid_until: float = None

    def validate(self):
        _check(0.0 <= self.limit_kw <= 22.0, "limit_kw out of range")
        _check(0.0 <= self.trust <= 1.0, "trust must be in [0, 1]")
        _check(self.entry >= -1, "entry must be -1 (fallback) or a schedule index")
        if self.valid_from is not None:
            _check(self.valid_until is not None and self.valid_until > self.valid_from
                   >= self.t_to - 1e-9,
                   "validity interval must start at or after t_to and have positive length")
        if self.issued_step >= 0:
            _check(self.issued_step <= self.step, "a setpoint cannot be issued after its step")


@dataclass
class Ack(_Msg):
    """edge -> twin, on eee40016/ack/<node>. What the edge actually did this step.

    Bypasses the injector, per the plan: it is the lock-step signal, not telemetry. The
    twin advances only once every node has acknowledged, with a wall-clock timeout that
    logs a miss instead of stalling the run.

    `draws` is the kW each charge point is really drawing, which can be less than the
    limit when a car is nearly full. `fallback` is true if the edge acted on its own
    local fallback because no setpoint arrived in time.
    """
    node: str
    step: int
    draws: dict                       # ev name -> kW actually drawn this step
    fallback: bool = False

    def validate(self):
        _check(all(0.0 <= v <= 22.0 for v in self.draws.values()), "draw out of range")


@dataclass
class BatteryRequest(_Msg):
    """twin -> battery node, on eee40016/breq/<node>. One call on the battery interface,
    for a battery that runs on the Raspberry Pi (mqtt_edge.BatteryNode) instead of inside
    the twin. The three operations are the battery class's own calls:

        reset      a new evening: build the battery with soc_bias and enabled
        response   P and Q at terminal voltage v for the EMS request setpoint_kw; must have
                   no side effects (the twin asks up to six times per step while the power
                   flow settles)
        commit     run at p_kw for `minutes`; the only call that changes the state of charge

    `req` numbers the requests; the reply carries the same number.
    """
    node: str
    req: int
    op: str
    v: float = 0.0              # response: terminal voltage, V line to neutral
    setpoint_kw: float = 0.0    # response: EMS request, positive charges
    p_kw: float = 0.0           # commit: power to run at, load convention
    minutes: float = 0.0        # commit
    soc_bias: float = 0.0       # reset: BMS estimation error (variable V4)
    enabled: bool = True        # reset: battery present (variable V5)

    def validate(self):
        _check(self.op in ("reset", "response", "commit"), "unknown battery op %r" % self.op)
        _check(self.req >= 0, "req must be non-negative")
        if self.op == "response":
            _check(0.0 < self.v < 1000.0, "terminal voltage out of range")
        if self.op == "commit":
            _check(self.minutes >= 0.0, "minutes must be non-negative")


@dataclass
class BatteryReply(_Msg):
    """battery node -> twin, on eee40016/bresp/<node>. The answer to request `req`.

    response: p_kw and q_kvar (load convention: positive kW charges, negative kvar supplies
    vars). reset and commit: `status`, which carries at least "soc" (the true state of
    charge the twin records) and "enabled". `error` is set, and nothing else, if the battery
    code raised; the twin then stops the run rather than carry on with a wrong battery.
    """
    node: str
    req: int
    p_kw: float = 0.0
    q_kvar: float = 0.0
    status: dict = field(default_factory=dict)
    error: str = ""

    def validate(self):
        _check(self.req >= 0, "req must be non-negative")
        _check(abs(self.p_kw) <= 1000.0 and abs(self.q_kvar) <= 1000.0,
               "battery P or Q out of range")


def decode(raw):
    """Decode any message by its declared type."""
    t = json.loads(raw).get("type")
    for cls in (StepStart, Measurement, Setpoint, Ack, BatteryRequest, BatteryReply):
        if cls.__name__ == t:
            return cls.from_json(raw)
    raise MessageError("unknown message type %r" % t)
