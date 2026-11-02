EEE40016 - the Raspberry Pi edge node
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
       printf 'listener 1883\nallow_anonymous true\n' | sudo tee /etc/mosquitto/conf.d/eee40016.conf
       sudo systemctl restart mosquitto
   then use --broker localhost here, and the Pi's address on the laptop
   (find it with: hostname -I).

Full guide: docs/Putting_It_Together.pdf in the project folder.
Built 2026-10-12 13:32 from the project on the laptop.
