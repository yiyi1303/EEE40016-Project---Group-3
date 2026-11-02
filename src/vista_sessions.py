"""Charging sessions fitted to the Victorian Integrated Survey of Travel and Activity (D4).

Data item D4 in the plan: session arrival and energy from a distribution fitted to VISTA,
sampled per seed. This builds that distribution from VISTA 2024-2025 trips, published by
Transport Victoria (data/vista/trips_vista_2024_2025.csv, open data).

The model, stated plainly so it can be argued with:

    who            weekday person-days in Greater Melbourne households where the person drove
                   at least 1 km as a vehicle driver
    plug-in        the person's last arrival home that day (destination purpose "At Home")
    energy wanted  that day's kilometres driven as a vehicle driver x 0.17 kWh/km, divided by
                   0.90 charger efficiency, capped at 60 kWh (one typical battery)
    weighting      VISTA's post-stratification weight, so the sample represents the population

Simplifications, each conservative or neutral for the comparison:

    every simulated EV drove that day, which overstates demand slightly against a random day
    an EV is charged once, from its last arrival home; an afternoon plug-in followed by another
    drive is not modelled separately
    0.17 kWh/km is a mid-size EV at urban speeds; 0.90 is a typical AC charger and onboard loss

Run:  py src/vista_sessions.py        (writes data/vista/ev_sessions_empirical.csv and a summary)
"""
import csv
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIPS = os.path.join(HERE, "data", "vista", "trips_vista_2024_2025.csv")
EMPIRICAL = os.path.join(HERE, "data", "vista", "ev_sessions_empirical.csv")
SUMMARY = os.path.join(HERE, "data", "vista", "ev_sessions_summary.json")

KWH_PER_KM = 0.17
CHARGER_EFFICIENCY = 0.90
BATTERY_CAP_KWH = 60.0
MIN_DRIVER_KM = 1.0


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build():
    by_person = defaultdict(list)
    with open(TRIPS, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["dayType"] != "Weekday" or r["homeregion_ASGS"] != "Greater Melbourne":
                continue
            by_person[r["persid"]].append(r)

    sessions, dropped = [], defaultdict(int)
    for pid, trips in by_person.items():
        trips.sort(key=lambda r: int(r["tripno"]))
        km = 0.0
        for r in trips:
            for i in range(1, 10):
                if r["mode%d" % i] == "Vehicle Driver":
                    d = _num(r["dist%d" % i])
                    if d:
                        km += d
        if km < MIN_DRIVER_KM:
            dropped["did not drive"] += 1
            continue
        home = [r for r in trips if r["destpurp1"] == "At Home"]
        if not home:
            dropped["never arrived home"] += 1
            continue
        last = home[-1]
        if last is not trips[-1]:
            # the person's day ended away from home: no evening plug-in at home
            dropped["day ended away from home"] += 1
            continue
        arr = _num(last["arrtime"])
        w = _num(last["trippoststratweight"])
        if arr is None or not w:
            dropped["missing time or weight"] += 1
            continue
        kwh = min(BATTERY_CAP_KWH, km * KWH_PER_KM / CHARGER_EFFICIENCY)
        sessions.append((int(arr), round(kwh, 3), w, round(km, 2)))

    with open(EMPIRICAL, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["arrival_min", "energy_kwh", "weight", "driver_km"])
        wr.writerows(sessions)

    tot = sum(s[2] for s in sessions)

    def wq(vals_w, q):
        vs = sorted(vals_w)
        acc = 0.0
        for v, w in vs:
            acc += w
            if acc >= q * tot:
                return v
        return vs[-1][0]

    arr = [(s[0], s[2]) for s in sessions]
    kwh = [(s[1], s[2]) for s in sessions]
    in_window = sum(w for a, w in arr if 960 <= a <= 1320) / tot
    before = sum(w for a, w in arr if a < 960) / tot
    summary = {
        "source": "VISTA 2024-2025 trips, Transport Victoria open data",
        "person_days_used": len(sessions),
        "excluded": dict(dropped),
        "model": {"kwh_per_km": KWH_PER_KM, "charger_efficiency": CHARGER_EFFICIENCY,
                  "battery_cap_kwh": BATTERY_CAP_KWH, "min_driver_km": MIN_DRIVER_KM},
        "arrival_home_weighted": {"p10": wq(arr, 0.10), "p25": wq(arr, 0.25), "median": wq(arr, 0.5),
                                  "p75": wq(arr, 0.75), "p90": wq(arr, 0.90)},
        "share_arriving_16_22": round(in_window, 3),
        "share_arriving_before_16": round(before, 3),
        "energy_kwh_weighted": {"p10": wq(kwh, 0.10), "median": wq(kwh, 0.5),
                                "mean": round(sum(k * w for k, w in kwh) / tot, 2),
                                "p90": wq(kwh, 0.90)},
    }
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def load_empirical():
    """[(arrival_min, energy_kwh, weight)] from the fitted file, building it if needed."""
    if not os.path.exists(EMPIRICAL):
        build()
    with open(EMPIRICAL, newline="") as f:
        return [(int(r["arrival_min"]), float(r["energy_kwh"]), float(r["weight"]))
                for r in csv.DictReader(f)]


if __name__ == "__main__":
    s = build()
    a, e = s["arrival_home_weighted"], s["energy_kwh_weighted"]
    hm = lambda m: "%02d:%02d" % divmod(int(m), 60)   # noqa: E731
    print("person-days used: %d   excluded: %s" % (s["person_days_used"], s["excluded"]))
    print("last arrival home (weighted): p10 %s  p25 %s  median %s  p75 %s  p90 %s"
          % (hm(a["p10"]), hm(a["p25"]), hm(a["median"]), hm(a["p75"]), hm(a["p90"])))
    print("arriving 16:00-22:00: %.0f%%   before 16:00: %.0f%%"
          % (100 * s["share_arriving_16_22"], 100 * s["share_arriving_before_16"]))
    print("energy wanted (weighted): p10 %.1f  median %.1f  mean %.1f  p90 %.1f kWh"
          % (e["p10"], e["median"], e["mean"], e["p90"]))
