#!/bin/sh
# Open the EV + BMS live views on the Pi's own screen, even when started over SSH.
#   sh start_ui.sh 172.20.10.8
# The address is the MQTT broker (laptop 1). Without one: 127.0.0.1.
cd "$(dirname "$0")"
export DISPLAY="${DISPLAY:-:0}"
exec python3 pi_dashboard.py --broker "${1:-127.0.0.1}"
