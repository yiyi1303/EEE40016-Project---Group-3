"""The three charging controllers the study compares, labelled as in Table 2 of the plan.

    A  static limit          a fixed limit per charge point all evening, no telemetry
    B  trust-weighted        the envelope, contracted continuously towards a conservative
                             floor as the trust in the data falls
    C  binary fallback       the full envelope while telemetry is healthy, and immediate
                             reversion to the static limit once a communication timeout
                             expires: the practice documented in the Australian DOE trials

The plan wrote the static limit as 7.2 kW. Run on this feeder that limit breaks a constraint
at 44 of 72 control steps, so the static limit used for A, and the limit C reverts to, is
the largest fixed limit that never violates over the evening, calibrated per seed
(notes/plan_amendments.md, item 1).

Every controller is given the same three things at each control step: the envelope the twin
computed from whatever telemetry arrived, the trust score for that telemetry, and the age of
the newest measurement. What each does with them is the experiment. The crossover the study
reports is where B stops beating A.
"""
from dataclasses import dataclass


@dataclass
class Command:
    kw: float
    controller: str
    trust: float
    envelope_kw: float       # what the envelope search returned from the believed state
    reason: str


def _quantise(kw, step, lo, hi):
    """Charge points act in fixed increments, so round down to one they can take."""
    kw = max(lo, min(hi, kw))
    n = int(kw / step + 1e-9)
    return round(n * step, 4)


class StaticLimit:
    """A. The baseline: one fixed limit all evening. Consumes no telemetry, so it is the same
    at every latency and loss rate, and forms the horizontal reference in the result."""

    name = "A"
    label = "static limit"

    def __init__(self, kw):
        self.kw = kw

    def command(self, envelope_kw, trust, age_min=None, step_kw=0.1, max_kw=7.2):
        return Command(_quantise(self.kw, step_kw, 0.0, max_kw), self.name, trust,
                       envelope_kw, "static limit")


class TrustWeighted:
    """B. The proposal: contract the envelope continuously towards a conservative floor.

    At trust 1 the envelope is allowed in full; at trust 0 the limit is the floor. The floor
    is the edge's own local fallback, 1.4 kW, the lowest setting a typical AC charge point
    accepts, so that a controller with no faith in its data asks for no more than a charge
    point would take on its own.
    """

    name = "B"
    label = "trust-weighted"

    def __init__(self, floor_kw=1.4):
        self.floor_kw = floor_kw

    def command(self, envelope_kw, trust, age_min=None, step_kw=0.1, max_kw=7.2):
        kw = self.floor_kw + trust * (envelope_kw - self.floor_kw)
        return Command(_quantise(kw, step_kw, 0.0, max_kw), self.name, trust, envelope_kw,
                       "trust %.2f between floor %.1f and envelope %.1f"
                       % (trust, self.floor_kw, envelope_kw))


class BinaryFallback:
    """C. Deployed practice: trust the envelope fully until the communication timeout
    expires, then revert at once to the static limit.

    "Timeout" is the age of the newest measurement against the same stale timeout the trust
    score uses, so B and C draw the line between usable and unusable data in the same place.
    The difference between them is the shape of the response, not where it starts.
    """

    name = "C"
    label = "binary fallback"

    def __init__(self, static_kw, timeout_min=15.0):
        self.static_kw = static_kw
        self.timeout_min = timeout_min

    def command(self, envelope_kw, trust, age_min=None, step_kw=0.1, max_kw=7.2):
        if age_min is not None and age_min <= self.timeout_min:
            return Command(_quantise(envelope_kw, step_kw, 0.0, max_kw), self.name, trust,
                           envelope_kw, "data %.1f min old, envelope in full" % age_min)
        return Command(_quantise(self.static_kw, step_kw, 0.0, max_kw), self.name, trust,
                       envelope_kw, "timeout expired, static limit")


# kept so older scripts that imported FixedLimit still run
FixedLimit = StaticLimit


def build(config, static_kw):
    """The three controllers. `static_kw` is the calibrated static limit for this seed."""
    c = config.get("controller_settings", {})
    return {"A": StaticLimit(static_kw),
            "B": TrustWeighted(c.get("fallback_kw", 1.4)),
            "C": BinaryFallback(static_kw, c.get("stale_timeout_min", 15.0))}
