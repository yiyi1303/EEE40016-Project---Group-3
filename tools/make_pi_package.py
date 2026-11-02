"""Build the folder that goes on the Raspberry Pi: pi_package/ and pi_package.zip.

    py tools/make_pi_package.py

Everything the Pi needs and nothing it does not: no OpenDSS, no feeder data, no numpy. It
holds the shared message contract, the charge-point controller (stand-in and Lomitha's
starting point), the MQTT wrapper, a runner, the charging sessions for every seed in both
demand cases (exported from this laptop so the Pi and the twin use identical sessions), and
a copy of the MQTT library itself (paho-mqtt, pure Python, with its licence), so the Pi
needs nothing but the Python 3 that Raspberry Pi OS ships with: no pip, no internet.
Rebuild after any change to src/messages.py, src/edge.py, src/mqtt_edge.py, Lomitha's file
or the sessions. tools/pi_session.py rebuilds it for you before copying it to the Pi.
"""
import json
import os
import shutil
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
OUT = os.path.join(HERE, "pi_package")
SEEDS = range(7, 20)
SCENARIOS = ("s1", "s2")

README = """EEE40016 - the Raspberry Pi edge node
=====================================

This folder runs the EV charge-point controller on the Pi. One controller object runs all
22 charge points (they are virtual), the way a site controller runs many chargers.
Nothing to install: the MQTT library (paho-mqtt) is included in paho/, so the Python 3
that comes with Raspberry Pi OS is enough.

The easy way is to let the laptop do everything over SSH (it copies this folder, starts
the broker and this program, runs the evening and stops it again):
       py tools/pi_session.py --pi <user>@<Pi address>
   run on the laptop, from the project folder.

By hand instead:

1. Start it, pointing at the MQTT broker (the laptop's address, or localhost if the broker
   runs on this Pi):
       python3 run_pi_node.py --broker <broker address>
   It should print "connected". Leave it running.

2. On the laptop:
       py tools/run_with_pi.py --broker <broker address> --compare
   The Pi prints one line per 5-minute step; the laptop ends with EQUIVALENT.

Use the same --seed and --scenario on both sides (defaults: seed 7, s1).
The battery can run here too: add --battery (Gia's battery with --team gia, both parts
with --team all), and --battery-on-pi on the laptop side.

Lomitha's controller: edit team/lomitha/ on the LAPTOP (pi_session.py copies a
fresh package across each time, so edits made here on the Pi are replaced; the previous
copy is kept as pi_package.prev). Then add
       --team lomitha
here on the Pi, and the same --team lomitha on the laptop when comparing.

Broker on the Pi instead of the laptop (nothing to allow on the laptop's firewall):
       sudo apt install mosquitto
       printf 'listener 1883\\nallow_anonymous true\\n' | sudo tee /etc/mosquitto/conf.d/eee40016.conf
       sudo systemctl restart mosquitto
   then use --broker localhost here, and the Pi's address on the laptop
   (find it with: hostname -I).

Full guide: docs/Putting_It_Together.pdf in the project folder.
Built %s from the project on the laptop.
"""


def main():
    from sweep import StudyRun
    from ev_sessions import load_or_create, path_for

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "sessions"))
    os.makedirs(os.path.join(OUT, "team"))
    os.makedirs(os.path.join(OUT, "team", "lomitha"))
    for src, dst in (("src/messages.py", "messages.py"), ("src/edge.py", "edge.py"),
                     ("src/battery.py", "battery.py"),
                     ("src/mqtt_edge.py", "mqtt_edge.py"),
                     ("tools/pi/run_pi_node.py", "run_pi_node.py"),
                     ("team/__init__.py", "team/__init__.py"),
                     ("team/lomitha_fleet.py", "team/lomitha_fleet.py"),
                     ("team/gia_battery.py", "team/gia_battery.py"),
                     ("team/lomitha/ev_charge_point_gateway.py",
                      "team/lomitha/ev_charge_point_gateway.py"),
                     ("team/lomitha/charging_session.py",
                      "team/lomitha/charging_session.py")):
        shutil.copyfile(os.path.join(HERE, src), os.path.join(OUT, dst))

    # Gia's BMS core, beside team/gia_battery.py, which imports it from its own folder.
    # Optional so the package still builds without it; the Pi then needs --team without gia
    # (the stand-in battery) until the two files are added to team/ here.
    missing = []
    for fn in ("bms_industrial.py", "a123_params.json"):
        p = os.path.join(HERE, "team", fn)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(OUT, "team", fn))
        else:
            missing.append(fn)
    if missing:
        print("NOTE: team/%s not found: Gia's battery (--team gia) will not run on the Pi "
              "until they are added to team/ and the package is rebuilt; the stand-in "
              "battery (--battery without gia) still works" % " and team/".join(missing))
    # the live views (EV + BMS), at the top of the package so they find paho/
    for fn in ("ev_node_ui.py", "bms_node_ui.py", "pi_dashboard.py", "start_ui.sh",
               "README_UI.txt"):
        p = os.path.join(HERE, "team", fn)
        if os.path.exists(p):
            shutil.copyfile(p, os.path.join(OUT, fn))

    # the MQTT library, so the Pi needs nothing installed; pure Python, works on any Pi
    import paho
    from importlib import metadata
    shutil.copytree(os.path.dirname(paho.__file__), os.path.join(OUT, "paho"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    dist = metadata.distribution("paho-mqtt")
    for f in dist.files or []:
        if "LICENSE" in str(f).upper():
            shutil.copyfile(f.locate(), os.path.join(OUT, "paho", os.path.basename(str(f))))

    st = StudyRun()
    tag = "_n%d" % len(st.ev_connections)
    n = 0
    for scen in SCENARIOS:
        for seed in SEEDS:
            load_or_create(st.feeder, st.ev_connections, seed, tag=tag,
                           source=st.session_source, plugin_model=scen)
            src = path_for(seed, tag, st.session_source, scen)
            shutil.copyfile(src, os.path.join(OUT, "sessions",
                                              "seed_%d_%s.json" % (seed, scen)))
            n += 1

    ctl, win = st.ctl, st.window
    cfg = {"fallback_kw": ctl.get("fallback_kw", 1.4),
           "uncovered_kw": ctl.get("uncovered_kw", ctl.get("fallback_kw", 1.4)),
           "control_period_minutes": win["control_period_minutes"],
           "sample_min": win["telemetry_period_seconds"] / 60.0,
           "default_scenario": st.plugin_model if st.plugin_model in SCENARIOS else "s1",
           "ev_connections": len(st.ev_connections),
           "paho_mqtt": dist.version,
           "built": time.strftime("%Y-%m-%d %H:%M")}
    with open(os.path.join(OUT, "pi_config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    with open(os.path.join(OUT, "requirements_pi.txt"), "w", encoding="utf-8") as f:
        f.write("# Not needed: a copy of paho-mqtt is included in paho/. Kept for anyone who\n"
                "# prefers an installed one; the copy in paho/ is used first either way.\n"
                "paho-mqtt>=1.6\n")
    with open(os.path.join(OUT, "README_PI.txt"), "w", encoding="utf-8") as f:
        f.write(README % cfg["built"])

    zpath = os.path.join(HERE, "pi_package.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(OUT):
            for fn in files:
                if fn.endswith(".pyc"):
                    continue
                p = os.path.join(root, fn)
                z.write(p, os.path.join("pi_package", os.path.relpath(p, OUT)))
    print("wrote %s and %s (%d session files, %.0f kB)"
          % (os.path.relpath(OUT, HERE), os.path.relpath(zpath, HERE), n,
             os.path.getsize(zpath) / 1024))


if __name__ == "__main__":
    main()
