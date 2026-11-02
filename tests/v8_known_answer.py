"""Validation item V8: the whole chain gives the right answer where the answer is known.

Plan wording: run at 0% EV penetration, and at 100% with the static limit disabled. Zero
violations in the first; violations at the predicted time in the second.

The prediction has to come from somewhere other than the simulator, or the test only
proves the simulator agrees with itself. So the second case is predicted by hand
arithmetic that never touches a power flow:

    the head of the feeder is 70 mm2 aluminium cable, rated 175 A per phase
    charge points are single-phase, so each phase carries its own cars
    per-phase current is apparent power over 230 V
    the first violation is the first control step where any phase exceeds 175 A

The simulator then runs the same evening through the full chain, unbalanced three-phase
power flow, thermal model, telemetry and all, and has to land on the same step.

The arithmetic ignores voltage drop, which lowers the voltage and so raises the current
slightly for the same power. That can only make the simulator violate a little earlier
than predicted, never later, so a small tolerance is allowed in that one direction.

The arithmetic predicts head-cable current and nothing else, so the simulator is judged on
its first head-cable overload. Other limits the arithmetic does not model can break first:
with the VISTA sessions, cars home before 16:00 are already charging when the window opens,
and voltage unbalance trips at 16:25, before the cable. That is reported, not judged
(plan amendment 28). With the earlier stand-in sessions the cable happened to break first,
so the two readings coincided.

Run:  py tests/v8_known_answer.py
Out:  notes/v8_result.md
"""
import copy
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from sweep import StudyRun                                        # noqa: E402
from controllers import FixedLimit, TrustWeighted                 # noqa: E402
from ev_sessions import load_or_create                            # noqa: E402
from build_sincal_model import profile_kw                         # noqa: E402

REPORT = os.path.join(HERE, "notes", "v8_result.md")
HEAD_CODE = "4c_70"
PHASE_V = 230.0
EARLY_TOLERANCE_STEPS = 2


def study_with(n_evs):
    cfg = json.load(open(os.path.join(HERE, "config", "study.json"), encoding="utf-8"))
    cfg = copy.deepcopy(cfg)
    cfg["cases"]["study"]["ev_connections"] = n_evs
    # V8 is a check of the chain, not of demand: it needs an overload to predict, so it keeps
    # every car plugging in, as when its known answer was recorded
    cfg["cases"]["study"]["plugin_model"] = "daily"
    return StudyRun(cfg)


def predict_first_violation(study, kw_per_car, head_rating_a):
    """Hand arithmetic only. No power flow anywhere in here."""
    sessions = load_or_create(study.feeder, study.ev_connections, 7,
                              tag="_n%d" % len(study.ev_connections), **study.session_args)
    phase_of_load = {l.name: l.phase for l in study.feeder.loads}
    pf = study.feeder.loads[0].pf
    tan_house = math.tan(math.acos(pf))
    delivered = {s.ev_name: 0.0 for s in sessions}
    step = study.step_min
    for i in range(study.n_steps):
        t = study.start_min + (i + 1) * step
        p = {"A": 0.0, "B": 0.0, "C": 0.0}
        q = {"A": 0.0, "B": 0.0, "C": 0.0}
        for ld in study.feeder.loads:
            kw = profile_kw(HERE, study.feeder.shapes[ld.shape], t)
            p[ld.phase] += kw
            q[ld.phase] += kw * tan_house
        # rooftop PV offsets demand on its own phase, at unity power factor
        for ld in study.pv_sites:
            p[ld.phase] -= study.pv_kw.get(t, 0.0)
        charging = {"A": 0, "B": 0, "C": 0}
        for s in sessions:
            if s.arrival_min <= t and delivered[s.ev_name] < s.energy_kwh - 1e-9:
                draw = min(kw_per_car, (s.energy_kwh - delivered[s.ev_name]) * 60.0 / step)
                p[s.phase] += draw
                delivered[s.ev_name] += draw * step / 60.0
                charging[s.phase] += 1
        # Only phases importing power are predicted. Under import the voltage at the head
        # is at or below 230 V, so dividing by 230 V can only understate the current, and
        # the simulator can only be early, never late. Under export from rooftop PV the
        # voltage rises well above 230 V and the same arithmetic overstates the current by
        # about 6%, predicting overloads that do not happen. Reverse-flow current needs the
        # voltage rise, which only a power flow can give; case 1 already shows PV export on
        # its own breaks nothing.
        amps = {ph: 1000.0 * math.hypot(p[ph], q[ph]) / PHASE_V
                for ph in p if p[ph] > 0}
        if not amps:
            continue
        worst = max(amps, key=amps.get)
        if amps[worst] > head_rating_a:
            return i, t, worst, amps[worst], charging
    return None, None, None, None, None


def run_case(study, controller):
    # The battery is switched off for this check: the hand arithmetic has no model of its
    # volt-var response, and V8 tests the chain, not the battery. PV stays on and is in the
    # prediction above.
    trace = []
    r = study.run(controller, 0.0, 0.0, 7, trace, battery_enabled=False)
    first = next((t for t in trace if not t["ok"]), None)
    return r, trace, first


def first_head_overload(study, trace):
    """(trace row, violation text) of the first step where a head-cable line (the line code
    the arithmetic models) is over its rating, or (None, None)."""
    head_lines = {ln.name.lower() for ln in study.feeder.lines if ln.linecode == HEAD_CODE}
    for t in trace:
        for v in t["violations"]:
            parts = v.split()
            if parts[0] == "cable" and len(parts) > 1 and parts[1].lower() in head_lines:
                return t, v
    return None, None


def main():
    lines = ["# V8 — known-answer check", ""]
    ok_all = True

    # ---------------------------------------------------------------- case 1
    s0 = study_with(0)
    r0, trace0, first0 = run_case(s0, TrustWeighted())
    case1 = r0.violations == 0
    ok_all &= case1
    print("case 1  0% EV penetration, full chain")
    print("        %d control steps, %d violating  ->  %s"
          % (len(trace0), r0.violations, "PASS" if case1 else "FAIL"))
    lines += ["## Case 1 — no EVs at all", "",
              "The full chain: telemetry, trust, envelope search, power flow, thermal model.",
              "With no charging the feeder should never break a limit.", "",
              "| | |", "| --- | --- |",
              "| Control steps | %d |" % len(trace0),
              "| Violating steps | %d |" % r0.violations,
              "| Peak hot spot | %.1f C |" % r0.peak_hot_spot_c, "",
              "**%s**" % ("PASS" if case1 else "FAIL"), ""]

    # ---------------------------------------------------------------- case 2
    s1 = study_with(len(s0.feeder.loads))
    head_a = s1.cs.line_rating(HEAD_CODE)
    kw = s1.env_cfg["max_kw"]
    p_step, p_min, p_phase, p_amps, p_charging = predict_first_violation(s1, kw, head_a)

    r1, trace1, first_any = run_case(s1, FixedLimit(kw))
    first1, head_v = first_head_overload(s1, trace1)
    if first1 is None or p_step is None:
        case2, gap = False, None
    else:
        gap = first1["step"] - p_step          # negative means the simulator was early
        case2 = -EARLY_TOLERANCE_STEPS <= gap <= 0
    ok_all &= case2

    print()
    print("case 2  100%% EV penetration, %.1f kW each, no envelope" % kw)
    if p_step is not None:
        print("        predicted  step %2d  %02d:%02d  phase %s at %.0f A (limit %.0f A), "
              "cars charging A/B/C = %d/%d/%d"
              % (p_step, p_min // 60, p_min % 60, p_phase, p_amps, head_a,
                 p_charging["A"], p_charging["B"], p_charging["C"]))
    if first1:
        print("        simulated  step %2d  %02d:%02d  %s"
              % (first1["step"], first1["minute"] // 60, first1["minute"] % 60, head_v))
    if first_any and (first1 is None or first_any["step"] < first1["step"]):
        print("        (not judged: %s first, at step %d %02d:%02d, outside the arithmetic)"
              % (first_any["violations"][0], first_any["step"], first_any["minute"] // 60,
                 first_any["minute"] % 60))
    print("        violating steps %d of %d, types %s"
          % (r1.violations, len(trace1), r1.violation_types))
    print("        gap %s step(s)  ->  %s" % (gap, "PASS" if case2 else "FAIL"))

    lines += ["## Case 2 — every connection charging at %.1f kW, no envelope" % kw, "",
              "Predicted by hand arithmetic with no power flow: per-phase apparent power "
              "over 230 V at the head cable, against its %.0f A rating. Then simulated "
              "through the full chain." % head_a, "",
              "| | Predicted | Simulated |", "| --- | --- | --- |"]
    if p_step is not None and first1:
        lines += ["| First violating step | %d | %d |" % (p_step, first1["step"]),
                  "| Time | %02d:%02d | %02d:%02d |" % (p_min // 60, p_min % 60,
                                                        first1["minute"] // 60,
                                                        first1["minute"] % 60),
                  "| Constraint | head cable, phase %s at %.0f A (%.0f%% of rating) | %s |"
                  % (p_phase, p_amps, 100.0 * p_amps / head_a, head_v),
                  "| Cars charging, phase A / B / C | %d / %d / %d | |"
                  % (p_charging["A"], p_charging["B"], p_charging["C"])]
    if first_any and first1 and first_any["step"] < first1["step"]:
        lines += ["", "Not judged: %s at step %d (%02d:%02d), earlier than the cable. The "
                  "arithmetic models head-cable current only; with the VISTA sessions cars home "
                  "before 16:00 are already charging when the window opens (amendment 28)."
                  % (first_any["violations"][0], first_any["step"], first_any["minute"] // 60,
                     first_any["minute"] % 60)]
    lines += ["", "Allowed: the simulator up to %d steps earlier than predicted, never later. "
              "The arithmetic ignores voltage drop, which only ever raises current." %
              EARLY_TOLERANCE_STEPS, "",
              "Violating steps over the evening: %d of %d. Types: %s"
              % (r1.violations, len(trace1), r1.violation_types), "",
              "**%s**" % ("PASS" if case2 else "FAIL"), ""]

    lines.insert(2, "**Overall: %s**\n" % ("PASS" if ok_all else "FAIL"))
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print()
    print("V8 %s" % ("PASS" if ok_all else "FAIL"))
    print("wrote", REPORT)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
