EEE40016 - live views on the Raspberry Pi screen
================================================

Files (copy all four into pi_package/, next to run_pi_node.py, so paho/ is found):
    ev_node_ui.py    EV charge points: DOE envelope and limit, trust, fallback, 22 points
    bms_node_ui.py   the battery (unchanged copy of team/bms_node_ui.py)
    pi_dashboard.py  opens both windows side by side, sized to the screen
    start_ui.sh      starts pi_dashboard.py on the Pi's screen, also from SSH

Both views only LISTEN to MQTT. They never publish, so they cannot change the run.

Run order (three terminals on the Pi, or two plus SSH):
 1. laptop 1:  py -3.14 tools/broker.py
 2. Pi:        cd ~/EEE40016/EEE40016_project/pi_package
               python3 run_pi_node.py --broker 172.20.10.8 --team lomitha,gia --battery --retry 60
 3. Pi:        cd ~/EEE40016/EEE40016_project/pi_package
               python3 pi_dashboard.py --broker 172.20.10.8
               (or from SSH: sh start_ui.sh 172.20.10.8)
 4. laptop 2:  py tools/run_with_pi.py --broker 172.20.10.8 ... --battery-on-pi

One window only:  python3 ev_node_ui.py --broker 172.20.10.8
                  python3 bms_node_ui.py --broker 172.20.10.8
Try without the laptops:  python3 ev_node_ui.py --demo
Layout: pi_dashboard.py --layout side|stack, --scale 0.8.  F11 full screen, Esc leaves it.
If "No module named tkinter":  sudo apt install python3-tk
