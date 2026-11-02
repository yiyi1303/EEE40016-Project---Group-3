"""Find the largest equal-share charging limit the network can carry right now.

This is the twin's core calculation. At each control step it asks: what is the highest kW
every connected charge point could draw without breaking voltage, cable current,
transformer loading, hot-spot temperature or unbalance?

The search is a bisection, which relies on feasibility being monotonic in the limit: if
7.2 kW each is safe then 5 kW each certainly is. That holds because raising charging power
on a radial feeder can only raise currents and lower voltages. Assumption A9 in the plan
claims the bisection finds the true limit; validation item V3 tests that claim against an
exhaustive sweep.

Two shortcuts keep the solve count down, and neither changes the answer:

    the full limit is tried first, because on a healthy feeder it is usually feasible and
    then no bisection is needed at all

    zero is tried next, because if the network is already in violation with no charging at
    all, no limit can fix it and the search should say so rather than return a number
"""
import math
import os
import random
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from network_state import NetworkState  # noqa: E402


@dataclass
class EnvelopeResult:
    kw: float                 # the limit, per charge point
    state: NetworkState       # the network at that limit
    solves: int               # power flows used
    binding: str              # which constraint stopped it going higher
    at_ceiling: bool          # the full limit was feasible, nothing was binding
    infeasible_at_zero: bool  # already in violation with no charging

    def __str__(self):
        if self.infeasible_at_zero:
            return "0.00 kW (network already in violation: %s)" % "; ".join(
                self.state.violations[:2])
        tag = " (ceiling)" if self.at_ceiling else " (%s binding)" % self.binding
        return "%.2f kW%s in %d solves" % (self.kw, tag, self.solves)


def choose_ev_connections(feeder, n, seed):
    """Pick which connections have an EV. Seeded, so every run uses the same houses."""
    if n > len(feeder.loads):
        raise ValueError("asked for %d EVs but the feeder has %d connections"
                         % (n, len(feeder.loads)))
    return sorted(random.Random(seed).sample(feeder.loads, n), key=lambda l: l.name)


class EnvelopeSearch:
    def __init__(self, solver, constraints, min_kw=0.0, max_kw=7.2, tolerance_kw=0.1,
                 ev_setter=None):
        self.solver = solver
        self.constraints = constraints
        self.min_kw = min_kw
        self.max_kw = max_kw
        self.tol = tolerance_kw
        self.solves = 0
        # How a trial limit becomes per-charge-point draws. The default loads every charge
        # point equally, which is right when every car is charging (V3, V4). In a real
        # evening it is wrong: cars that have not arrived draw nothing, and cars nearly
        # full draw less than the limit. The search must plan with exactly the draws the
        # network will then see, or planning and reality diverge. For cable current that
        # only costs energy; for unbalance it is unsafe, because the phantom load sits on
        # different phases from the real load. See notes/plan_amendments.md, item 10.
        self.ev_setter = ev_setter

    # -- one trial -------------------------------------------------------------

    def trial(self, kw, thermal=None, minutes=None, ambient_c=None):
        """Set the limit, solve, and judge, without committing the thermal state.

        The thermal model is copied for every trial. Stepping the real one would let the
        search heat the transformer a dozen times over for a single five-minute step.
        """
        if self.ev_setter is not None:
            self.ev_setter(kw)
        else:
            self.solver.set_ev_power(kw)
        self.solver.solve()
        self.solves += 1
        th = thermal.copy() if thermal is not None else None
        return self.constraints.evaluate(self.solver, th, minutes, ambient_c)

    # -- the search ------------------------------------------------------------

    def find(self, thermal=None, minutes=None, ambient_c=None):
        self.solves = 0
        kw_args = dict(thermal=thermal, minutes=minutes, ambient_c=ambient_c)

        top = self.trial(self.max_kw, **kw_args)
        if top.ok:
            return EnvelopeResult(self.max_kw, top, self.solves, "none", True, False)

        bottom = self.trial(self.min_kw, **kw_args)
        ok = lambda st: st.ok                                     # noqa: E731
        relaxed = []
        if not bottom.ok:
            # Do no harm. The network already breaches something with no charging at all,
            # typically the upper voltage limit at 16:00 when rooftop PV is exporting hard.
            # Refusing to charge would be exactly wrong there, because charging pulls the
            # voltage down. So a trial passes if every constraint is either within its limit
            # or no worse than it was with no charging: charging may not deepen a breach it
            # did not cause. See notes/plan_amendments.md, item 16.
            m0 = bottom.detail.get("margins", {})
            relaxed = sorted(k for k, m in m0.items() if m < 0)

            def ok(st):
                return all(m >= 0 or m >= m0.get(k, 0.0) - 1e-9
                           for k, m in st.detail.get("margins", {}).items())
            if ok(top):
                r = EnvelopeResult(self.max_kw, top, self.solves, "none", True, True)
                r.relaxed = relaxed
                return r

        # Bisect on the grid the charge point can actually act on, counting in whole
        # 0.1 kW steps rather than in kW. Bisecting in continuous kW and rounding down
        # afterwards is wrong: the search can settle just under a grid boundary while the
        # true limit sits just above it, and the answer comes out a full step low.
        # Working in grid indices makes the result exactly the largest feasible setting.
        steps = int(round((self.max_kw - self.min_kw) / self.tol))
        lo, hi = 0, steps                      # lo known feasible, hi known infeasible
        best = bottom
        while hi - lo > 1:
            mid = (lo + hi) // 2
            st = self.trial(self.min_kw + mid * self.tol, **kw_args)
            if ok(st):
                lo, best = mid, st
            else:
                hi = mid

        kw = self.min_kw + lo * self.tol
        r = EnvelopeResult(round(kw, 4), best, self.solves, best.binding, False,
                           bool(relaxed))
        r.relaxed = relaxed
        return r

    # -- the slow, obviously-correct version, for validation -------------------

    def exhaustive(self, step_kw=0.05, thermal=None, minutes=None, ambient_c=None):
        """Walk the whole range in small steps. Used only by V3.

        This does not stop at the first infeasible step. Scanning all the way to the top
        is the only way to catch feasibility that is not monotonic in the limit, which is
        the assumption the bisection rests on. `non_monotonic` reports any feasible point
        found above an infeasible one.
        """
        self.solves = 0
        kw_args = dict(thermal=thermal, minutes=minutes, ambient_c=ambient_c)
        best_kw, best, seen_infeasible, non_monotonic = None, None, False, []
        # the same do-no-harm rule as find(), or the two would disagree for a reason that
        # has nothing to do with the bisection
        m0 = self.trial(self.min_kw, **kw_args).detail.get("margins", {})

        def ok(st):
            return all(m >= 0 or m >= m0.get(k, 0.0) - 1e-9
                       for k, m in st.detail.get("margins", {}).items())
        n = int(round((self.max_kw - self.min_kw) / step_kw)) + 1
        for i in range(n):
            kw = self.min_kw + i * step_kw
            st = self.trial(kw, **kw_args)
            if ok(st):
                if seen_infeasible:
                    non_monotonic.append(kw)
                best_kw, best = kw, st
            else:
                seen_infeasible = True
        if best_kw is None:
            st = self.trial(self.min_kw, **kw_args)
            r = EnvelopeResult(self.min_kw, st, self.solves, st.binding, False, True)
        else:
            r = EnvelopeResult(round(best_kw, 4), best, self.solves, best.binding,
                               best_kw >= self.max_kw - 1e-9, False)
        r.non_monotonic = non_monotonic
        return r
