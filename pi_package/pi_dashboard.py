#!/usr/bin/env python3
"""
Both live views on one screen: the EV charge points (ev_node_ui.py) and the battery
(bms_node_ui.py), sized and placed side by side (or one above the other on a tall screen).

    python3 pi_dashboard.py --broker 172.20.10.8
    python3 pi_dashboard.py --demo                 # no broker: both scripted

Keep this file next to ev_node_ui.py and bms_node_ui.py (inside pi_package/, so paho/ is
found). Both views only LISTEN, so they cannot disturb the run. Close either window to quit.
F11 toggles full screen on a window, Esc leaves it.
"""
import argparse
import os
import sys
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ev_node_ui as EV          # noqa: E402
import bms_node_ui as BMS        # noqa: E402

PAD = 24                          # canvas padding + window border, per window


def main():
    ap = argparse.ArgumentParser(description="EV + BMS live views on one screen")
    ap.add_argument("--broker", default="127.0.0.1", help="MQTT broker address")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--demo", action="store_true", help="no broker: scripted evenings")
    ap.add_argument("--layout", choices=("auto", "side", "stack"), default="auto")
    ap.add_argument("--scale", type=float, default=None, help="force a scale for both, e.g. 0.8")
    a = ap.parse_args()

    root = tk.Tk()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    ew, eh = EV.App.BASE_W, EV.App.BASE_H
    bw, bh = BMS.App.BASE_W, BMS.App.BASE_H
    usable_h = sh - 70                                     # taskbar + title bars
    k_side = min((sw - 2 * PAD) / float(ew + bw), (usable_h - PAD) / float(max(eh, bh)))
    k_stack = min((sw - PAD) / float(max(ew, bw)), (usable_h - 2 * PAD - 30) / float(eh + bh))
    layout = a.layout if a.layout != "auto" else ("side" if k_side >= k_stack else "stack")
    k = a.scale or min(1.0, k_side if layout == "side" else k_stack)

    ev_feed, bms_feed = EV.Feed("edge"), BMS.Feed()
    if a.demo:
        ev_src = EV.start_demo(ev_feed)
        try:
            BMS.start_demo(bms_feed)
            bms_src = "DEMO (scripted, not MQTT)"
        except Exception as e:                             # its demo needs extra files
            bms_src = "demo unavailable: %s" % e
        ev_link = None
    else:
        ev_link = EV.start_mqtt(ev_feed, a.broker, a.port, "edge")
        BMS.start_mqtt(bms_feed, a.broker, a.port, "battery")
        ev_src = bms_src = "broker %s:%d" % (a.broker, a.port)

    EV.App(root, ev_feed, k, "edge", ev_src, ev_link)
    root.geometry("+0+0")
    top = tk.Toplevel(root)
    BMS.App(top, bms_feed, k, "battery", bms_src)
    if layout == "side":
        top.geometry("+%d+0" % int(ew * k + PAD))
    else:
        top.geometry("+0+%d" % int(eh * k + PAD + 30))
    for w in (root, top):
        w.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
