"""What the twin actually knows, as opposed to what is true.

STAND-IN. The degradation injector and the trust metric belong to the communication and
integrity layer, which is Hoang's node. This module exists so the twin can be built and
stage S1 can run end to end before that node is ready, and so there is a settled interface
for it to arrive behind. Replace the internals, keep `publish_window()`, `observe()` and
`trust()`.

The model, following assumption A2, degrades in simulated time rather than over the real
LAN, so runs are deterministic and repeatable.

    telemetry is published every 30 s, each message carrying a sequence number and its
    send time, as the plan's uplink topic specifies
    each message is delayed by |N(mean, 0.6 mean)|
    each message is dropped independently with probability `loss`
    messages sit in flight until their arrival time, and are delivered whenever that is,
    including after later messages (reordering) and in a later control period
    the twin holds the newest message it has received, by send time: hold-last-value, as
    the SA Power Networks trial describes

Age and loss are kept separate, as assumption A14 treats them. The first version of this
module conflated them: a message arriving one second after its own control period was
counted as lost for good, and anything later than a whole period was never delivered at
all. With no loss configured it reported 10% loss at 1 s latency and 100% at 600 s, which
biased every trust score low. See notes/plan_amendments.md, item 7.

Loss is now estimated the way the twin could actually estimate it from what it holds.
It measures its own delivery delays from the send timestamps on the messages it has
received, and counts a message as lost only once it is older than the 95th percentile of
those delays and still has not arrived. A message still plausibly in flight is not lost
yet, it is just late, and lateness is already priced by the age term.

The trust score is a transparent function of measurement age, estimated loss rate and a
plausibility test, monotonic in each, as A14 requires. Nothing is fitted or tuned; each
term is a straight line between a good case and a useless one.
"""
import math
import random
from dataclasses import dataclass



def stable_seed(*parts):
    """A random seed that is identical in every process and on every machine.

    Python's built-in hash() is randomised per process for strings, so seeding with
    hash(("down", seed, ...)) gave a different random stream every run and made results
    impossible to regenerate. Found by V9's same-day self-check. SHA-256 of the parts'
    text is stable everywhere.
    """
    import hashlib
    digest = hashlib.sha256(repr(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")

@dataclass
class Observation:
    values: dict       # what the twin believes, per load name
    age_min: float     # age of the newest held measurement at the decision instant
    loss_rate: float   # estimated fraction of settled messages that never arrived
    received: int      # messages in the loss window that did arrive
    expected: int      # messages in the loss window
    delay_p95_min: float  # the twin's own estimate of its delivery delay


@dataclass
class _Msg:
    seq: int
    sent: float        # minutes past midnight
    arrives: float     # math.inf if dropped
    values: dict


class TelemetryLink:
    """One feeder's worth of telemetry, degraded by a latency and a loss rate."""

    LOSS_WINDOW_MIN = 20.0     # loss is estimated over the most recent 20 settled minutes

    def __init__(self, latency_s=0.0, loss=0.0, period_s=30.0, seed=7,
                 stale_timeout_min=15.0, trust_loss_weight=1.0, stale_hold_min=0.0):
        self.latency_s = float(latency_s)
        self.loss = float(loss)
        self.period_s = float(period_s)
        self.stale_timeout_min = float(stale_timeout_min)
        # 1.0 penalises loss linearly on top of age; 0.0 is an age-only trust score.
        # Age already captures what loss does to freshness, so the loss term is a
        # judgement that a lossy link is a warning sign in its own right.
        self.trust_loss_weight = float(trust_loss_weight)
        # V3, the stale-data hold: a meter that keeps republishing a frozen value with a
        # fresh timestamp. Values refresh only every `stale_hold_min` minutes while every
        # message still carries its true send time, so the age the twin computes looks
        # healthy while the values describe the past. 0 disables it.
        self.stale_hold_min = float(stale_hold_min)
        self._held, self._held_until = None, -math.inf
        self.rng = random.Random(stable_seed("up", seed, float(latency_s), float(loss)))
        self._msgs = []
        self._seq = 0
        self._last_sent = None

    def _values_for(self, t, truth):
        """What a meter publishes at time t: the truth then, or a frozen value under V3."""
        current = truth(t) if callable(truth) else truth
        if self.stale_hold_min <= 0:
            return dict(current)
        if t >= self._held_until - 1e-9:
            self._held = dict(current)
            self._held_until = t + self.stale_hold_min
        return dict(self._held)

    def publish_window(self, truth, from_min, to_min):
        """Send every telemetry message generated in (from_min, to_min].

        `truth` is either a function of time giving the readings at that instant, which is
        how the sweep calls it, or a fixed dict. Each sample carries the reading at its own
        send time, as Section V-C of the plan specifies ("sampled every 30 s, taking P and Q
        from the one-minute profiles"). An earlier version stamped every sample in a window
        with the end-of-window value, so a late sample was no less accurate than a fresh
        one; see notes/plan_amendments.md, item 15.

        Messages are only put in flight here. Nothing is delivered until `observe`, and a
        message is delivered whenever its arrival time has passed, whichever window it was
        sent in.
        """
        step = self.period_s / 60.0
        t = from_min if self._last_sent is None else max(from_min, self._last_sent)
        while True:
            t = round(t + step, 9)
            if t > to_min + 1e-9:
                break
            dropped = self.rng.random() < self.loss
            delay = abs(self.rng.gauss(self.latency_s, 0.6 * self.latency_s)) / 60.0
            self._seq += 1
            self._msgs.append(_Msg(self._seq, t, math.inf if dropped else t + delay,
                                   self._values_for(t, truth)))
            self._last_sent = t

    def observe(self, now_min, truth):
        """What the twin holds at this decision instant."""
        got = [m for m in self._msgs if m.arrives <= now_min + 1e-9]
        if not got:
            return Observation(values=dict(truth), age_min=math.inf, loss_rate=1.0,
                               received=0, expected=0, delay_p95_min=math.inf)

        newest = max(got, key=lambda m: m.sent)
        age = max(0.0, now_min - newest.sent)

        # the twin's own view of its delivery delay, from timestamps it has received
        recent = sorted(got, key=lambda m: m.arrives)[-40:]
        delays = sorted(m.arrives - m.sent for m in recent)
        p95 = delays[min(int(0.95 * len(delays)), len(delays) - 1)]

        # loss over messages old enough to have settled: sent at least p95 ago
        settle = now_min - p95
        window = [m for m in self._msgs
                  if settle - self.LOSS_WINDOW_MIN < m.sent <= settle]
        if window:
            arrived = sum(1 for m in window if m.arrives <= now_min + 1e-9)
            loss_rate = 1.0 - arrived / len(window)
        else:
            arrived, loss_rate = 0, 0.0

        # drop history nobody will look at again
        horizon = settle - self.LOSS_WINDOW_MIN - 1.0
        if len(self._msgs) > 400:
            self._msgs = [m for m in self._msgs if m.sent > horizon or m.arrives > now_min]

        return Observation(values=dict(newest.values), age_min=age, loss_rate=loss_rate,
                           received=arrived, expected=len(window), delay_p95_min=p95)

    # -- the trust score ---------------------------------------------------------

    def trust(self, obs, plausible=True):
        """0 means the picture is useless, 1 means it is fresh and complete.

        Monotonic and decreasing in age, decreasing in loss rate, and reduced by a failed
        plausibility test. A product of simple terms rather than a fitted function, so the
        control law can be explained and audited.
        """
        if obs.age_min == math.inf:
            return 0.0
        age_term = max(0.0, 1.0 - obs.age_min / self.stale_timeout_min)
        loss_term = max(0.0, 1.0 - self.trust_loss_weight * obs.loss_rate)
        plausibility_term = 1.0 if plausible else 0.5
        return max(0.0, min(1.0, age_term * loss_term * plausibility_term))

    @staticmethod
    def plausible(values, previous, max_jump_ratio=5.0):
        """A crude sanity test: total demand should not leap by more than a set factor."""
        if not previous:
            return True
        a, b = sum(values.values()), sum(previous.values())
        if b <= 1e-6:
            return True
        r = a / b
        return (1.0 / max_jump_ratio) <= r <= max_jump_ratio


class DownlinkChannel:
    """The return path: setpoints from the twin to the charge points, degraded in simulated
    time by the same latency and loss as the uplink (Table 8: V1 and V2 apply to both).

    STAND-IN, part of Hoang's injector. A setpoint sent at the decision instant arrives after
    a delay, or never. The charge point acts on the newest setpoint that has arrived. If the
    newest it holds is older than its own fallback timeout, or nothing has arrived at all, it
    charges at its local fallback instead.

    Which setpoint governs a 5-minute control step is read at the middle of the step: the
    model is quasi-static at 5 minutes (assumption A1), so a setpoint arriving in the first
    half of the step is treated as governing it, and one arriving later as governing the
    next. The error is at most half a control step, the same resolution as everything else.

    One publication is one message, whatever it carries: since amendment 25 a setpoint is a
    schedule of several entries, and it is still lost or delayed as a whole, with one loss
    draw and one delay draw from this channel's own stream, and never retransmitted
    (INTERFACES.md, R6). That is what keeps a given loss rate meaning the same thing.
    """

    def __init__(self, latency_s=0.0, loss=0.0, seed=7, fallback_timeout_min=15.0):
        self.latency_s = float(latency_s)
        self.loss = float(loss)
        self.fallback_timeout_min = float(fallback_timeout_min)
        # a separate stream from the uplink, so the two directions are independent
        self.rng = random.Random(stable_seed("down", seed, float(latency_s), float(loss)))
        self._inflight = []            # (arrives, sent, setpoint)
        self.sent = 0
        self.dropped = 0

    def send(self, setpoint, t_sent):
        self.sent += 1
        if self.rng.random() < self.loss:
            self.dropped += 1
            return
        delay = abs(self.rng.gauss(self.latency_s, 0.6 * self.latency_s)) / 60.0
        self._inflight.append((t_sent + delay, t_sent, setpoint))

    def in_force(self, t):
        """(setpoint, sent time) the charge point acts on at time t, or (None, None) when it
        should be on its local fallback."""
        arrived = [(s, sp) for a, s, sp in self._inflight if a <= t + 1e-9]
        if not arrived:
            return None, None
        sent, sp = max(arrived, key=lambda x: x[0])
        if t - sent > self.fallback_timeout_min + 1e-9:
            return None, sent
        # anything older than the newest arrival will never govern again
        self._inflight = [x for x in self._inflight if x[1] >= sent]
        return sp, sent
