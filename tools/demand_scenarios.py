"""How congested each candidate demand scenario makes the feeder, before any power flow.

    py tools/demand_scenarios.py

A screening calculation for the team's decision on demand (plan amendment 27). For each
scenario it simulates many evenings of UNMANAGED charging, every car at 7.2 kW from the
moment it plugs in until it has what it wants, adds the feeder's household demand, and
reports how many cars plug in, how much energy they want inside 16:00-22:00, and the peak
total demand against the 150 kVA transformer. No network model: this says how much load
there is, not where the first limit binds (cable current and unbalance usually bind before
the transformer). Its purpose is to show which scenarios give live control anything to do.

Scenarios (sources in notes/plan_amendments.md, item 27):

    standin   the placeholder the study was built on: every car, arrival N(18:36, 1 h),
              8-26 kWh uniform
    S0        VISTA as currently implemented: every car plugs in every evening wanting that
              day's driving (median 4.7 kWh)
    S1        metered Melbourne behaviour: each car plugs in on an evening with p = 0.34
              (Jemena-led trial), wanting everything driven since its last plug-in; built
              up over a 21-day warm-up, so sessions average about 7.2 / 0.34 = 21 kWh
    S2        distributor design day (UoM/ENA method): p = 0.70, each session two days of
              driving

Penetration is 40% (22 of 55 homes) unless stated; S1 is also run at 60, 80 and 100%.
Arrival times and daily energies are drawn from the VISTA fit (data/vista/), weighted.
Out: notes/demand_scenarios.md
"""
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from vista_sessions import load_empirical, BATTERY_CAP_KWH      # noqa: E402
from sweep import StudyRun                                       # noqa: E402

KW = 7.2
W0, W1 = 960, 1320                 # 16:00-22:00
EVENINGS = 2000
WARMUP_DAYS = 21
TX_KVA = 150.0
OUT = os.path.join(HERE, "notes", "demand_scenarios.md")


def house_profile():
    st = StudyRun()
    # evening household demand, no PV (none after about 18:00 anyway, and PV only lowers it)
    return {m: sum(v for k, v in st.household(m).items() if not k.startswith("PV_"))
            for m in range(W0, W1 + 1)}


def evening_sessions(rng, scenario, n_ev, emp, weights, deficits):
    """[(arrival_min, energy_kwh)] for one evening; updates per-car deficits for S1/S2."""
    out = []
    for car in range(n_ev):
        arrival, day_kwh, _ = rng.choices(emp, weights=weights, k=1)[0]
        if scenario == "standin":
            h = min(max(rng.gauss(18.6, 1.0), 16.1), 21.0)
            out.append((int(round(h * 60)), rng.uniform(8.0, 26.0)))
        elif scenario == "S0":
            out.append((arrival, day_kwh))
        elif scenario == "S1":
            deficits[car] = min(BATTERY_CAP_KWH, deficits[car] + day_kwh)
            if rng.random() < 0.34:
                out.append((arrival, deficits[car]))
                deficits[car] = 0.0
        elif scenario == "S2":
            if rng.random() < 0.70:
                second = rng.choices(emp, weights=weights, k=1)[0][1]
                out.append((arrival, min(BATTERY_CAP_KWH, day_kwh + second)))
    return out


def evening_load(sessions, house):
    """Peak total kW, peak EV kW, cars plugged in during the window, kWh wanted in-window."""
    ev = {m: 0.0 for m in range(W0, W1 + 1)}
    cars, wanted = 0, 0.0
    for arrival, kwh in sessions:
        if arrival > W1:
            continue
        start = max(arrival, W0)
        left = kwh - KW * max(0, W0 - arrival) / 60.0     # charged before the window opened
        if left <= 1e-9:
            continue
        cars += 1
        wanted += left
        m = start
        while left > 1e-9 and m <= W1:
            d = min(KW, left * 60.0)
            ev[m] += d
            left -= d / 60.0
            m += 1
    tot = [house[m] + ev[m] for m in ev]
    return max(tot), max(ev.values()), cars, wanted


def run(scenario, n_ev, house, emp, weights, seed=1):
    rng = random.Random(seed)
    deficits = [0.0] * n_ev
    for _ in range(WARMUP_DAYS):                       # settle the deficits (S1)
        evening_sessions(rng, scenario, n_ev, emp, weights, deficits)
    rows = [evening_load(evening_sessions(rng, scenario, n_ev, emp, weights, deficits), house)
            for _ in range(EVENINGS)]
    peak = sorted(r[0] for r in rows)
    q = lambda xs, p: xs[min(len(xs) - 1, int(p * len(xs)))]   # noqa: E731
    return {"cars": statistics.fmean(r[2] for r in rows),
            "cars_p99": q(sorted(r[2] for r in rows), 0.99),
            "kwh": statistics.fmean(r[3] for r in rows),
            "ev_peak_med": statistics.median(r[1] for r in rows),
            "peak_med": statistics.median(peak), "peak_p95": q(peak, 0.95),
            "over_tx": sum(1 for p in peak if p > TX_KVA * 0.95) / len(peak)}


def main():
    emp = load_empirical()
    weights = [w for _, _, w in emp]
    house = house_profile()
    cases = [("standin", 22), ("S0", 22), ("S1", 22), ("S2", 22), ("S1", 33), ("S1", 44),
             ("S1", 55)]
    lines = ["# Demand scenarios: unmanaged evening load before any control", "",
             "Screening only: no network model, so this is load, not which limit binds first "
             "(cable current and unbalance bind before the transformer on this feeder). "
             "%d evenings each; household peak alone %.0f kW; transformer 150 kVA "
             "(about %.0f kW at the 0.95 power factor the houses run at)." % (
                 EVENINGS, max(house.values()), TX_KVA * 0.95), "",
             "| scenario | EVs | cars charging in window, mean (99th pct) | kWh wanted in window "
             "| EV peak, median | feeder peak, median | feeder peak, 95th pct | evenings over "
             "transformer |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for sc, n in cases:
        r = run(sc, n, house, emp, weights)
        lines.append("| %s | %d | %.1f (%d) | %.0f | %.0f kW | %.0f kW | %.0f kW | %.0f%% |"
                     % (sc, n, r["cars"], r["cars_p99"], r["kwh"], r["ev_peak_med"],
                        r["peak_med"], r["peak_p95"], 100 * r["over_tx"]))
        print(lines[-1], flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
