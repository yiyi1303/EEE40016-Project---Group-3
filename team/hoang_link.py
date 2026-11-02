"""Hoang: the comms injector and the trust metric. START HERE.

These two classes run on the laptop, inside the twin. They start as exact copies of the
stand-ins (they inherit from them), so everything works before you change a line. Replace
the methods one at a time with your own versions; delete the `super()` calls as you go.

Plug them in (--team hoang picks both classes in this file):
    py tests/test_node_acceptance.py --team hoang
    py tools/run_with_pi.py --broker <address> --compare --team hoang

To pass: V5 (the link delivers the delay and loss asked for) and V6 (trust behaves at the
extremes and in between), both in tests/test_node_acceptance.py.
Rules from docs/INTERFACES.md: R6 (a downlink message is lost or delayed as a whole, one draw
each, never retransmitted) and R7 (trust() is a pure function, never rising with age).
"""
from telemetry import TelemetryLink, DownlinkChannel, Observation   # noqa: F401


class HoangLink(TelemetryLink):
    """The uplink: meter readings from the street to the twin, degraded on the way.

    Built by the twin as
        HoangLink(latency_s, loss, period_s=30, seed=7, stale_timeout_min=15,
                  trust_loss_weight=1.0, stale_hold_min=0.0)
    so keep that constructor signature, even if you ignore some arguments.
    """

    def publish_window(self, truth, from_min, to_min):
        """Put every sample generated in (from_min, to_min] in flight, one every 30 s.
        truth(t) gives the readings {connection: kW} at time t. Delay each message by your
        latency model and drop it with probability `loss`, in simulated time.
        stale_hold_min > 0: values stop changing for that long but keep fresh timestamps."""
        return super().publish_window(truth, from_min, to_min)

    def observe(self, now_min, truth):
        """What the twin holds at now_min. Return a telemetry.Observation with:
        values (newest arrived readings), age_min (age of the newest reading, inf if none),
        loss_rate (your estimate), received, expected, delay_p95_min.
        Remember: a late message is not a lost one (plan amendment 7)."""
        return super().observe(now_min, truth)

    def trust(self, obs, plausible=True):
        """A number from 0 to 1 for how far the twin can believe `obs`. Must not rise as
        age rises (R7). The stand-in: (1 - age/15) x (1 - loss) x (0.5 if implausible)."""
        return super().trust(obs, plausible)


class HoangDownlink(DownlinkChannel):
    """The downlink: charging limits from the twin back to the charge points.

    Built by the twin as HoangDownlink(latency_s, loss, seed, fallback_timeout_min)."""

    def send(self, setpoint, t_sent):
        """One message: lose it with probability `loss`, otherwise delay it. One draw each,
        never retransmitted (R6)."""
        return super().send(setpoint, t_sent)

    def in_force(self, t):
        """(setpoint, sent_time) the charge points act on at time t: the newest that has
        arrived. (None, None) if nothing has, (None, sent) if the newest is older than the
        fallback timeout."""
        return super().in_force(t)
