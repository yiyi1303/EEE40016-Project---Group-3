"""Checks for setpoint schedules (plan amendment 25). Each prints PASS or FAIL.

    py tests/test_setpoint_schedule.py

    a  downlink: which entry governs each step (0, 1, 2 or the default) over 42 cells x 13
       seeds matches the design's table, and a full run counts exactly the same entries and
       fallbacks with the schedule on and off: the channel is untouched
    b  margins: entry k is planned at lag value_lag(age) + 5k, giving the design's table
    e  eager vs lazy: entries computed at issue time, as a real twin would, agree with the
       ones the sweep computes when they are first needed, within one 0.1 kW step
    f  causality: snapshots are never mutated after they are taken, the thermal snapshot
       predates the step's application, and the search and battery are restored after
       every entry is planned
    g  the edge's validity guard never fires, and every entry selected is inside the schedule
    h  select_entry, ChargePointFleet's uncovered-car rule, and the schema-2 Setpoint

c and d (schedule off reproduces the pre-change code exactly; schedule on reproduces it in
cells with no held setpoints) are tests/golden_runs.py --check --flag off / on.
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import controllers                                     # noqa: E402
from edge import ChargePointFleet, select_entry        # noqa: E402
from ev_sessions import Session                        # noqa: E402
from messages import Setpoint, MessageError            # noqa: E402
from sweep import StudyRun                             # noqa: E402
from telemetry import DownlinkChannel                  # noqa: E402

SEEDS = list(range(7, 20))
LATENCIES = [0, 5, 30, 60, 120, 300, 600]
LOSSES = [0.0, 0.01, 0.05, 0.10, 0.20, 0.40]
H, T = 3, 5.0
# the design's table: share of steps on entry 0 / 1 / 2 / default, percent
TABLE = {(0, 0.0): (100, 0, 0, 0), (0, 0.10): (88.9, 9.4, 1.2, 0.5),
         (0, 0.40): (61.9, 23.8, 8.3, 6.0), (60, 0.0): (99.4, 0.6, 0, 0),
         (60, 0.10): (88.5, 10.0, 1.0, 0.5), (60, 0.40): (58.2, 24.5, 9.5, 7.8),
         (120, 0.0): (66.9, 33.0, 0, 0.1), (300, 0.0): (19.4, 62.8, 16.3, 1.4),
         (300, 0.10): (17.5, 57.9, 21.2, 3.4), (300, 0.40): (11.3, 41.8, 26.6, 20.3),
         (600, 0.0): (9.8, 29.6, 39.0, 21.6), (600, 0.10): (8.9, 28.2, 38.0, 24.9),
         (600, 0.40): (4.8, 17.3, 28.2, 49.7)}
results = []


def report(name, ok, detail=""):
    results.append(ok)
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", name, ("  " + detail) if detail else ""))


def entry_shares(lat, loss, seeds=SEEDS, steps=72):
    counts = [0] * (H + 1)
    for seed in seeds:
        d = DownlinkChannel(lat, loss, seed, 15.0)
        for i in range(steps):
            t_to = 965.0 + T * i
            d.send(Setpoint("edge", i, t_to, 1.0, 1.0, 1.0), t_to)
            held, _ = d.in_force(t_to + T / 2)
            counts[H if held is None else select_entry(held.step, i, H)] += 1
    n = sum(counts)
    return [100.0 * c / n for c in counts], counts


def test_a(study):
    worst = 0.0
    for lat in LATENCIES:
        for loss in LOSSES:
            shares, _ = entry_shares(lat, loss)
            if (lat, loss) in TABLE:
                worst = max(worst, max(abs(a - b) for a, b in zip(shares, TABLE[(lat, loss)])))
    report("a  entry shares match the design table (42 cells x 13 seeds)", worst <= 0.06,
           "largest gap %.3f points" % worst)

    # a full run counts the same entries and fallbacks with the schedule on and off, and
    # those counts are the channel's own
    ctl = controllers.build(study.cfg, 2.1)
    same = True
    for c, lat, loss, seed in (("B", 0, 0.10, 8), ("C", 300, 0.0, 7)):
        runs = []
        for on in (False, True):
            study.ctl["setpoint_schedule"] = on
            runs.append(study.run(ctl[c], lat, loss, seed))
        _, ch = entry_shares(lat, loss, [seed])
        same &= (runs[0].entry_counts == runs[1].entry_counts == ch
                 and runs[0].fallbacks == runs[1].fallbacks == ch[H])
    study.ctl["setpoint_schedule"] = True
    report("a  full runs: entry and fallback counts identical on/off and equal the channel's",
           same)


def test_b(study):
    want = {0.0: [(1.0, 0.050), (12.5, 0.535), (16.0, 0.610)],
            0.5: [(7.0, 0.325), (13.5, 0.545), (16.0, 0.640)],
            3.0: [(10.5, 0.455), (15.0, 0.575), (16.5, 0.695)],
            4.5: [(12.5, 0.535), (16.0, 0.610), (17.0, 0.750)]}
    bad = []
    for age, rows in want.items():
        for k, (m, mv) in enumerate(rows):
            gm, gmv = study.planning_margins(age, T * k)
            if abs(100 * gm - m) > 1e-6 or abs(gmv - mv) > 1e-6:
                bad.append("age %g k %d: %.3f%%/%.3f pp, want %.1f%%/%.3f pp"
                           % (age, k, 100 * gm, gmv, m, mv))
    entry0 = all(study.planning_margins(a) == (
        round(study.margin_for_age(a) / 0.005) * 0.005,
        round(study.vuf_margin_for_age(a) / 0.005) * 0.005) for a in (0, 0.5, 3, 4.5, 20))
    report("b  margin at application lag matches the design table", not bad and entry0,
           "; ".join(bad[:3]))


class Instrumented(StudyRun):
    """Computes every entry eagerly at issue time, records the lazy ones, and checks the
    snapshots and the restore discipline as the run goes."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.eager, self.lazy, self.frozen, self.problems = {}, {}, {}, []

    def _snapshot_taken(self, snap, controller, basis, horizon):
        self.frozen[snap.step] = (copy.deepcopy(snap.values), dict(snap.cap),
                                  tuple(snap.charging), snap.thermal.d_oil, snap.thermal.d_hot)
        for k in range(1, horizon):
            self.eager[(snap.step, k)] = StudyRun._plan_entry(self, snap, k, controller, basis)
        self._check_frozen(snap)

    def _plan_entry(self, snap, k, controller, basis):
        before = (self.search.constraints, self.search.ev_setter, self._battery_pq)
        out = super()._plan_entry(snap, k, controller, basis)
        after = (self.search.constraints, self.search.ev_setter, self._battery_pq)
        if before != after:
            self.problems.append("step %d entry %d: search or battery not restored"
                                 % (snap.step, k))
        self.lazy[(snap.step, k)] = out
        self._check_frozen(snap)
        return out

    def _check_frozen(self, snap):
        v, cap, ch, oil, hot = self.frozen[snap.step]
        if (snap.values != v or snap.cap != cap or snap.charging != ch
                or snap.thermal.d_oil != oil or snap.thermal.d_hot != hot):
            self.problems.append("step %d: snapshot changed after it was taken" % snap.step)


def test_e_f_g(study_cls):
    st = pinned(study_cls)
    ctl = controllers.build(st.cfg, 2.1)
    held_steps, agree, worst = 0, 0, 0.0
    validity = 0
    for c, lat, loss, seed in (("C", 300, 0.0, 7), ("B", 300, 0.0, 7), ("B", 0, 0.40, 8)):
        st.eager, st.lazy, st.frozen = {}, {}, {}
        edge = st.make_edge(seed)
        st.run(ctl[c], lat, loss, seed, edge=edge)
        validity += getattr(edge.fleet, "validity_fallbacks", 0)
        for key, (lim, env, _, _, _) in st.lazy.items():
            e_lim, e_env, _, _, _ = st.eager[key]
            held_steps += 1
            gap = max(abs(lim - e_lim), abs(env - e_env))
            worst = max(worst, gap)
            agree += gap <= 0.1 + 1e-9
    report("e  eager and lazy entries agree within 0.1 kW",
           held_steps > 0 and agree == held_steps,
           "%d of %d held entries, largest gap %.2f kW" % (agree, held_steps, worst))
    report("f  snapshots frozen, search and battery restored", not st.problems,
           "; ".join(st.problems[:3]))
    report("g  edge validity guard never fired", validity == 0, "%d times" % validity)


def test_h():
    s = [Session("LOAD1", "EV_A", 900, 30.0, "1", "A"),
         Session("LOAD2", "EV_B", 1000, 30.0, "2", "B")]
    ok = select_entry(10, 10, 3) == 0 and select_entry(10, 12, 3) == 2
    ok &= select_entry(10, 13, 3) is None and select_entry(10, 9, 3) is None
    report("h  select_entry", ok)

    f = ChargePointFleet(s, 1.4)
    a = f.apply(5.0, 1005, 5, issued_at=990)           # EV_B arrived after issue
    f2 = ChargePointFleet(s, 1.4, uncovered_kw=0.0)
    b = f2.apply(5.0, 1005, 5, issued_at=990)
    c = f2.apply(None, 1005, 5, issued_at=990)         # default: everyone at 1.4
    ok = (a.draws == {"EV_A": 5.0, "EV_B": 1.4} and b.draws == {"EV_A": 5.0, "EV_B": 0.0}
          and c.draws == {"EV_A": 1.4, "EV_B": 1.4} and c.fallback)
    report("h  uncovered cars draw uncovered_kw under an entry, the fallback under the default",
           ok)

    f3 = ChargePointFleet(s, 1.4)
    inside = f3.apply(5.0, 1005, 5, issued_at=990, valid_from=1005, valid_until=1010)
    outside = f3.apply(5.0, 1010, 5, issued_at=990, valid_from=1005, valid_until=1010)
    report("h  the edge executes a limit only inside its interval",
           not inside.fallback and outside.fallback)

    sp = Setpoint("edge", 12, 1000.0, 3.2, 0.8, 4.0, issued_step=10, entry=2,
                  valid_from=1010.0, valid_until=1015.0)
    rt = Setpoint.from_json(sp.to_json())
    bad = 0
    for kw in ({"valid_from": 995.0, "valid_until": 1000.0},          # before t_to
               {"valid_from": 1010.0, "valid_until": 1010.0},         # zero length
               {"issued_step": 13}, {"entry": -2}):
        try:
            Setpoint.from_json(Setpoint(**{**sp.__dict__, **kw}).to_json())
        except MessageError:
            bad += 1
    report("h  schema-2 Setpoint round-trips and rejects bad intervals", rt == sp and bad == 4,
           "%d of 4 bad messages rejected" % bad)


def pinned(cls=StudyRun):
    """The schedule checks run on every-evening VISTA sessions, the heaviest realistic
    demand, so the held entries they test actually have cars to plan for."""
    st = cls()
    st.session_source, st.plugin_model = "vista", "daily"
    return st


def main():
    study = pinned()
    test_h()
    test_b(study)
    test_a(study)
    test_e_f_g(Instrumented)
    print("\n%d of %d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
