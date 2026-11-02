"""Build the two scenario inputs the plan specifies and the model was missing.

D5  ambient temperature for the transformer thermal model, from Bureau of Meteorology
    observations, interpolated from half-hourly to one-minute resolution.
D3  rooftop PV output, from the Ineichen-Perez clear-sky model at Melbourne's latitude,
    with the single scripted afternoon cloud transient that Table 7 calls for.

Run:  py src/make_scenario_data.py
Out:  data/ambient.csv, data/pv_profile.csv, data/scenario_provenance.json
"""
import csv
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

# --- D5: ambient --------------------------------------------------------------------
BOM_FILE = os.path.join(DATA, "weather", "bom_IDV60901_95936.json")
AMBIENT_DAY = "20260930"      # warmest of the three evenings in the record: conservative for
                              # the thermal limit, since a warmer ambient leaves less headroom

# --- D3: PV -------------------------------------------------------------------------
PV_DATE = "2026-11-18"        # a late-spring Wednesday, as Table 7 specifies
LAT, LON, ALT = -37.8136, 144.9631, 31.0        # Melbourne
TZ = "Australia/Melbourne"                      # AEDT in November, UTC+11
TILT, AZIMUTH = 20.0, 0.0                       # typical roof pitch, facing north
DC_KW, AC_KW = 6.6, 5.0                         # the usual Australian 6.6 kW array on a 5 kW inverter
SYSTEM_LOSS = 0.85                              # soiling, temperature, wiring, inverter
CLOUD_FROM, CLOUD_TO, CLOUD_FACTOR = "16:40", "16:55", 0.25


def hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def ambient():
    d = json.load(open(BOM_FILE, encoding="utf-8"))["observations"]
    station = d["header"][0]["name"]
    pts = sorted((int(o["local_date_time_full"][8:10]) * 60 + int(o["local_date_time_full"][10:12]),
                  float(o["air_temp"]))
                 for o in d["data"]
                 if o["local_date_time_full"].startswith(AMBIENT_DAY) and o["air_temp"] is not None)
    if len(pts) < 20:
        raise SystemExit("not enough observations for %s in %s" % (AMBIENT_DAY, BOM_FILE))
    xs, ys = zip(*pts)
    minutes = np.arange(0, 1440)
    temp = np.interp(minutes, xs, ys)
    with open(os.path.join(DATA, "ambient.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["minute", "air_temp_c"])
        for m, t in zip(minutes, temp):
            w.writerow([int(m), round(float(t), 2)])
    ev = temp[16 * 60:22 * 60]
    return {"source": "Bureau of Meteorology, latest observations product IDV60901, station %s "
                      "(95936)" % station,
            "date": AMBIENT_DAY, "observations_used": len(pts),
            "resolution": "half-hourly observed, linearly interpolated to 1 minute",
            "evening_16_22_range_c": [round(float(ev.min()), 1), round(float(ev.max()), 1)],
            "copyright": "Commonwealth of Australia 2026, Bureau of Meteorology",
            "note": "An early-spring observation standing in for the late-spring day of Table 7, "
                    "because a November record does not exist yet. Replace with a November "
                    "observation when one is available; the file format stays the same."}


def pv():
    import pandas as pd
    import pvlib
    times = pd.date_range("%s 00:00" % PV_DATE, periods=1440, freq="1min", tz=TZ)
    site = pvlib.location.Location(LAT, LON, tz=TZ, altitude=ALT)
    cs = site.get_clearsky(times, model="ineichen")
    sp = site.get_solarposition(times)
    poa = pvlib.irradiance.get_total_irradiance(TILT, AZIMUTH, sp["apparent_zenith"],
                                                sp["azimuth"], cs["dni"], cs["ghi"], cs["dhi"])
    poa_w = poa["poa_global"].fillna(0.0).clip(lower=0.0).to_numpy()

    minutes = np.arange(1440)
    cloud = (minutes >= hhmm(CLOUD_FROM)) & (minutes < hhmm(CLOUD_TO))
    poa_w = np.where(cloud, poa_w * CLOUD_FACTOR, poa_w)
    ac_kw = np.minimum(AC_KW, DC_KW * poa_w / 1000.0 * SYSTEM_LOSS)

    with open(os.path.join(DATA, "pv_profile.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["minute", "poa_w_m2", "ac_kw_per_system"])
        for m, p, a in zip(minutes, poa_w, ac_kw):
            w.writerow([int(m), round(float(p), 2), round(float(a), 4)])

    sunset = int(np.max(np.nonzero(ac_kw > 0.01)))
    return {"model": "Ineichen-Perez clear sky, pvlib %s" % pvlib.__version__,
            "date": PV_DATE, "site": "Melbourne, lat %.4f lon %.4f" % (LAT, LON),
            "plane": "tilt %g deg, facing north" % TILT,
            "system": "%.1f kW DC on a %.1f kW inverter, %.0f%% system efficiency"
                      % (DC_KW, AC_KW, SYSTEM_LOSS * 100),
            "cloud_transient": "%s-%s, irradiance at %.0f%% of clear sky"
                               % (CLOUD_FROM, CLOUD_TO, CLOUD_FACTOR * 100),
            "output_at_16_00_kw": round(float(ac_kw[960]), 2),
            "output_ends": "%02d:%02d" % divmod(sunset, 60),
            "note": "System size and orientation are not specified in the plan; these are the "
                    "commonest Australian residential arrangement. PV runs at unity power factor "
                    "with no volt-var or volt-watt response, which the plan does not ask for."}


def main():
    prov = {"D5_ambient": ambient(), "D3_pv": pv()}
    with open(os.path.join(DATA, "scenario_provenance.json"), "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=2)
    a, p = prov["D5_ambient"], prov["D3_pv"]
    print("ambient  %s, %s: %d obs, evening %.1f-%.1f C"
          % (a["source"].split(",")[-1].strip(), a["date"], a["observations_used"],
             *a["evening_16_22_range_c"]))
    print("pv       %s, %s: %.2f kW per system at 16:00, generation ends %s, cloud %s"
          % (p["model"], p["date"], p["output_at_16_00_kw"], p["output_ends"],
             p["cloud_transient"]))
    print("wrote data/ambient.csv, data/pv_profile.csv, data/scenario_provenance.json")


if __name__ == "__main__":
    main()
