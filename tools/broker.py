"""Run an MQTT broker on this laptop for the Raspberry Pi to connect to.

    py tools/broker.py                  listen on the network (the Pi can connect)
    py tools/broker.py --host 127.0.0.1 this laptop only (a rehearsal without the Pi)

The first time, Windows asks whether to let Python accept connections: allow it on
private networks, or the Pi cannot reach the broker. The alternative is to run the broker
on the Pi itself (Mosquitto, see docs/Putting_It_Together.pdf); then nothing on the laptop
needs allowing. Leave this window open while you work; Ctrl+C stops it.
"""
import argparse
import os
import socket
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from mqtt_edge import start_local_broker          # noqa: E402


def lan_addresses():
    """This laptop's IPv4 addresses other than loopback, for telling the Pi where to go."""
    out = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                out.add(ip)
    except socket.gaierror:
        pass
    try:                                           # the address of the default route
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        out.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=1883)
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)        # show each line straight away
    start_local_broker(a.port, a.host)
    print("MQTT broker running on %s:%d" % (a.host, a.port))
    if a.host == "0.0.0.0":
        addrs = lan_addresses()
        print("tell the Pi to use one of: %s" % (", ".join(addrs) or "(no network found)"))
        print("  e.g. on the Pi:  python3 run_pi_node.py --broker %s"
              % (addrs[0] if addrs else "<laptop address>"))
    print("Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("broker stopped")


if __name__ == "__main__":
    main()
