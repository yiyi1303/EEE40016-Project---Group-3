"""Run an evening with the Raspberry Pi with one command: the laptop does everything.

    py tools/pi_session.py --find                      which address is the Pi on? (on your
                                                       own phone hotspot only)
    py tools/pi_session.py --pi <user>@<Pi address>    the real Pi, over SSH
    py tools/pi_session.py --local                     no Pi: everything on this laptop

Run it from PowerShell or Windows Terminal, which can ask for the Pi's password.

With --pi the laptop rebuilds pi_package.zip from its own files, copies it to the Pi,
starts the MQTT broker here and the Pi's program over SSH, runs the evening and compares
it with the simulation; the Pi's program stops when the session ends. Type the Pi's
password when asked: once to copy, once to start (--no-copy skips the copy). The Pi needs
only what Raspberry Pi OS already has (Python 3), SSH switched on, and the same Wi-Fi.

The Pi reaches the broker through the SSH connection itself (an SSH tunnel), so Windows
never has to accept an incoming connection and nothing needs allowing through the firewall.
--direct makes the Pi connect straight to the broker across the Wi-Fi instead (plain MQTT
on port 1883; Windows asks to allow Python the first time). The results are identical.

With --local the Pi's program runs on this laptop instead, from pi_package/: the plan B for
a demo when the Pi will not connect. Same output, same EQUIVALENT check.

Passed on to the run: --controller, --latency, --loss, --seed, --plugin-model (s1, s2),
--static-kw, --team (with lomitha or all, the Pi runs Lomitha's controller too). Also:
    --battery-on-pi  run the battery on the Pi as well (the stand-in, or Gia's with --team gia
                     or all); the twin calls it over MQTT and EQUIVALENT covers it too
    --no-copy        the Pi already has the current package: skip rebuilding and copying
    --no-compare     skip the check against the simulation (a shorter demo)
    --direct         plain MQTT across the Wi-Fi instead of the SSH tunnel
    --port 1883      the broker's port on this laptop
    --tunnel-port 18830   the port the tunnel opens on the Pi
    --dry-run        print what would run, run nothing
"""
import argparse
import ipaddress
import json
import os
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, os.path.join(HERE, "tools"))

PY = sys.executable
PKG = os.path.join(HERE, "pi_package")
ZIP = os.path.join(HERE, "pi_package.zip")
SEEDS = range(7, 20)       # the seeds make_pi_package.py exports
SSH_OPTS = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10"]
IDLE_EXIT_S = 30           # the Pi's program stops by itself this long after the evening

SSH_HELP = """Things to check:
  - the Pi is switched on and on the same Wi-Fi as this laptop (py tools/pi_session.py --find)
  - SSH is switched on on the Pi (once, on the Pi: sudo raspi-config, Interface Options, SSH)
  - the user name and password are the ones made when the Pi was set up
  - the address is right (on the Pi, hostname -I shows it)
  - "REMOTE HOST IDENTIFICATION HAS CHANGED" means the Pi was set up again: run
    ssh-keygen -R <Pi address> once, then run this again"""

TUNNEL_HINT = """  - "remote port forwarding failed": something on the Pi already uses the tunnel's port;
    add --tunnel-port 18831"""

FIREWALL_HELP = """The Pi's program never reached the broker on this laptop. The usual cause is the
Windows firewall. Open Windows Security, Firewall & network protection, "Allow an app
through firewall", and tick Python for both Private and Public; or set this Wi-Fi to
Private in Settings, Network & internet, Wi-Fi. Or leave out --direct: the SSH tunnel
needs no firewall changes."""

TUNNEL_HELP = """The Pi's program never reached the broker through the SSH tunnel (see the Pi | lines
above for the reason). Try again with --direct, which connects across the Wi-Fi instead."""


def say(msg):
    print(">> " + msg, flush=True)


def die(msg):
    print("\n" + msg, flush=True)
    raise SystemExit(1)


def port_busy(port):
    """True if something on this laptop already answers on the port, e.g. an old broker."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def ip_towards(ip):
    """This laptop's address on the network that reaches `ip`. No packet is sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((ip, 9))
        return s.getsockname()[0]
    finally:
        s.close()


def network_category(local_ip):
    """'Public' or 'Private' for the Windows network that owns local_ip; '' if unknown.
    Only reads the setting."""
    if os.name != "nt":
        return ""
    ps = ("$a = (Get-NetIPAddress -IPAddress '%s' -ErrorAction SilentlyContinue)"
          ".InterfaceAlias; if ($a) { (Get-NetConnectionProfile -InterfaceAlias $a "
          "-ErrorAction SilentlyContinue).NetworkCategory }" % local_ip)
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def pump(proc, prefix, events):
    """Print a child's output line by line with a prefix, and set each (marker, Event)
    whose marker appears."""
    for raw in iter(proc.stdout.readline, b""):
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        print(prefix + line, flush=True)
        for marker, ev in events:
            if marker in line:
                ev.set()


def stop(node, reader):
    """Stop the Pi's program. It would stop by itself after IDLE_EXIT_S, but there is no
    need to wait. Over SSH, ending the session ends the program on the Pi (it runs on a
    terminal there, so it is hung up on)."""
    try:
        node.wait(3)
    except subprocess.TimeoutExpired:
        node.terminate()
        try:
            node.wait(10)
        except subprocess.TimeoutExpired:
            node.kill()
    reader.join(5)


def laptop_cmd(a, broker_host, wait):
    cmd = [PY, os.path.join(HERE, "tools", "run_with_pi.py"), "--start-broker",
           "--broker-host", broker_host, "--broker", "127.0.0.1", "--port", str(a.port),
           "--wait", str(wait), "--controller", a.controller, "--latency", str(a.latency),
           "--loss", str(a.loss), "--seed", str(a.seed), "--plugin-model", a.plugin_model]
    if a.static_kw is not None:
        cmd += ["--static-kw", str(a.static_kw)]
    if a.team:
        cmd += ["--team", a.team]
    if not a.no_compare:
        cmd.append("--compare")
    if a.battery_on_pi:
        cmd.append("--battery-on-pi")
    return cmd


def node_args(a, broker, port, retry):
    args = ["--broker", broker, "--port", str(port), "--seed", str(a.seed),
            "--scenario", a.plugin_model, "--retry", str(retry),
            "--idle-exit", str(IDLE_EXIT_S)]
    names = {n.strip().lower() for n in (a.team or "").split(",") if n.strip()}
    on_pi = [n for n in ("lomitha", "gia") if n in names or "all" in names]
    if not a.battery_on_pi and "gia" in on_pi:
        on_pi.remove("gia")             # without --battery-on-pi Gia's battery runs here
    if on_pi:
        args += ["--team", ",".join(on_pi)]
    if a.battery_on_pi:
        args.append("--battery")
    return args


def rebuild(a):
    cmd = [PY, os.path.join(HERE, "tools", "make_pi_package.py")]
    say("rebuilding the Pi package from this laptop's files")
    if a.dry_run:
        print("   " + subprocess.list2cmdline(cmd))
    elif subprocess.call(cmd):
        die("rebuilding the package failed (see above)")


def start_node(cmd, cwd=None):
    """Start the Pi's program (here, or over SSH) with its output shown as 'Pi | ...'."""
    started, connected = threading.Event(), threading.Event()
    node = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    reader = threading.Thread(target=pump, daemon=True, args=(
        node, "Pi | ", [("connecting to the broker", started), ("connected.", connected)]))
    reader.start()
    return node, reader, started, connected


def wait_started(node, reader, started, limit_s, help_text):
    t0 = time.monotonic()
    while not started.wait(1):
        if node.poll() is not None:
            reader.join(2)
            die("the Pi's program did not start (see the Pi | lines above).\n" + help_text)
        if time.monotonic() - t0 > limit_s:
            node.terminate()
            die("no answer from the Pi's program after %d s.\n%s" % (limit_s, help_text))


# ---------------------------------------------------------------------- the three modes

def run_local(a):
    node_cmd = ([PY, "-I", os.path.join(PKG, "run_pi_node.py")]
                + node_args(a, "127.0.0.1", a.port, 60))
    run_cmd = laptop_cmd(a, "127.0.0.1", 60)
    if a.dry_run:
        if not a.no_copy:
            rebuild(a)
        for c in (node_cmd, run_cmd):
            print("   " + subprocess.list2cmdline(c))
        return 0
    if port_busy(a.port):
        die("something on this laptop is already using port %d (an old broker or run still "
            "open?). Close it, or add --port 18833." % a.port)
    if not a.no_copy:
        rebuild(a)
    say("starting the Pi's program here on the laptop (its lines start with 'Pi |')")
    node, reader, started, _ = start_node(node_cmd, cwd=PKG)
    try:
        wait_started(node, reader, started, 30, "")
        say("starting the broker and the evening")
        rc = subprocess.call(run_cmd)
    finally:
        stop(node, reader)
    return rc


def run_pi(a):
    if "@" not in a.pi:
        die("give the Pi as <user>@<address>, e.g. --pi lomitha@192.168.43.57 (the user made "
            "when the Pi was set up)")
    host = a.pi.split("@", 1)[1]
    try:
        pi_ip = socket.getaddrinfo(host, 22, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
    except socket.gaierror:
        die("cannot find '%s' on the network. Is the Pi on the same Wi-Fi as this laptop? "
            "Use its number address: py tools/pi_session.py --find" % host)
    me = ip_towards(pi_ip)
    if a.direct:      # the Pi connects across the Wi-Fi to the broker on this laptop
        broker, port, laptop_host, forward = me, a.port, "0.0.0.0", []
        help_text = SSH_HELP
    else:             # the Pi connects to its own end of the tunnel; SSH carries it here
        broker, port, laptop_host = "127.0.0.1", a.tunnel_port, "127.0.0.1"
        forward = ["-o", "ExitOnForwardFailure=yes",
                   "-R", "%d:127.0.0.1:%d" % (a.tunnel_port, a.port)]
        help_text = SSH_HELP + "\n" + TUNNEL_HINT
    run_node = ("python3 -V && exec python3 -u run_pi_node.py "
                + " ".join(node_args(a, broker, port, 300)))
    if a.no_copy:
        remote = "cd pi_package && " + run_node
    else:   # a fresh copy each time; the previous one is kept as pi_package.prev
        remote = ("rm -rf pi_package.prev; if [ -d pi_package ]; then mv pi_package "
                  "pi_package.prev; fi; python3 -m zipfile -e pi_package.zip . && "
                  "cd pi_package && " + run_node)
    scp_cmd = ["scp"] + SSH_OPTS + [ZIP, a.pi + ":pi_package.zip"]
    ssh_cmd = (["ssh", "-tt"] + SSH_OPTS + ["-o", "ServerAliveInterval=5"] + forward
               + [a.pi, remote])
    run_cmd = laptop_cmd(a, laptop_host, 90)
    say("the Pi is at %s; this laptop is %s on that network" % (pi_ip, me))
    if a.dry_run:
        if not a.no_copy:
            rebuild(a)
        for c in ([] if a.no_copy else [scp_cmd]) + [ssh_cmd, run_cmd]:
            print("   " + subprocess.list2cmdline(c))
        return 0
    if port_busy(a.port):
        die("something on this laptop is already using port %d (an old broker or run still "
            "open?). Close it and run this again." % a.port)
    if a.direct:
        if network_category(me) == "Public":
            say("Windows treats this Wi-Fi as a Public network. When it asks whether to let "
                "Python accept connections, tick Public networks as well, or the Pi cannot "
                "connect.")
        else:
            say("if Windows asks whether to let Python accept connections, click Allow")
    else:
        say("the Pi will reach the broker through the SSH connection: nothing to allow "
            "through the firewall")
    if not a.no_copy:
        rebuild(a)
        say("copying pi_package.zip to the Pi (type the Pi's password if asked)")
        if subprocess.call(scp_cmd, stdin=subprocess.DEVNULL):
            die("copying to the Pi failed.\n" + SSH_HELP)
    say("starting the Pi's program over SSH (type the Pi's password if asked); "
        "its lines start with 'Pi |'")
    node, reader, started, connected = start_node(ssh_cmd)
    try:
        wait_started(node, reader, started, 240, help_text)
        say("starting the broker on this laptop and the evening")
        rc = subprocess.call(run_cmd)
    finally:
        stop(node, reader)
    if not connected.is_set():
        print("\n" + (FIREWALL_HELP if a.direct else TUNNEL_HELP))
    return rc


def ssh_banner(ip, timeout=0.4):
    """The SSH greeting of whatever answers on port 22 at ip, or None."""
    try:
        with socket.create_connection((ip, 22), timeout=timeout) as s:
            s.settimeout(1.0)
            try:
                return s.recv(80).decode("ascii", "replace").strip() or "SSH"
            except OSError:
                return "SSH"
    except OSError:
        return None


def find(a):
    """Look for SSH on the network this laptop uses (its default route): on a phone hotspot,
    that is the hotspot, and the Pi will be among the answers."""
    try:
        mine = [ip_towards("8.8.8.8")]       # no packet is sent
    except OSError:
        from broker import lan_addresses
        mine = lan_addresses()
    nets = []
    for ip in mine:
        addr = ipaddress.ip_address(ip)
        if addr.is_private and not (addr.is_loopback or addr.is_link_local):
            nets.append((ip, ipaddress.ip_network(ip + "/24", strict=False)))
    if not nets:
        die("this laptop is not on a local network: join the phone hotspot first")
    print("This tries to reach SSH on every address of %s, the network this laptop is on."
          % ", ".join(str(n) for _, n in nets))
    print("Only do this on your own phone hotspot, never on university or work Wi-Fi.")
    if not a.yes:
        if not sys.stdin.isatty():
            die("add --yes to go ahead without being asked")
        if input("Go ahead? [y/N] ").strip().lower() not in ("y", "yes"):
            print("stopped")
            return 1
    found = 0
    for me, net in nets:
        hosts = [str(h) for h in net.hosts() if str(h) != me]
        say("looking for SSH on %s (this laptop is %s) ..." % (net, me))
        with ThreadPoolExecutor(64) as ex:
            banners = list(ex.map(ssh_banner, hosts))
        for h, b in zip(hosts, banners):
            if b:
                found += 1
                try:
                    name = socket.gethostbyaddr(h)[0]
                except OSError:
                    name = ""
                print("   %-15s  %-26s  %s" % (h, name, b))
    if found:
        print("\nA Raspberry Pi usually says Debian or Raspbian. Then:\n"
              "   py tools/pi_session.py --pi <user>@<that address>")
    else:
        print("\nNothing answered on SSH. The phone's hotspot settings also list the devices "
              "connected to it.\n" + SSH_HELP)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pi", metavar="USER@ADDRESS")
    mode.add_argument("--local", action="store_true")
    mode.add_argument("--find", action="store_true")
    ap.add_argument("--controller", default="B", choices=list("ABC"))
    ap.add_argument("--latency", type=float, default=60.0)
    ap.add_argument("--loss", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--plugin-model", choices=("s1", "s2"), default=None)
    ap.add_argument("--static-kw", type=float, default=None)
    ap.add_argument("--team", default=None)
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--tunnel-port", type=int, default=18830)
    ap.add_argument("--direct", action="store_true")
    ap.add_argument("--battery-on-pi", action="store_true")
    ap.add_argument("--no-copy", action="store_true")
    ap.add_argument("--no-compare", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="--find without asking first")
    a = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    if a.find:
        return find(a)
    if a.seed not in SEEDS:
        die("--seed must be %d to %d: those are the evenings the Pi package carries"
            % (SEEDS[0], SEEDS[-1]))
    if a.team:                                    # catch a typo before anything is copied
        import plugins
        plugins.specs(argparse.Namespace(team=a.team))
    if a.plugin_model is None:
        case = json.load(open(os.path.join(HERE, "config", "study.json"),
                              encoding="utf-8"))["cases"]["study"]
        a.plugin_model = case.get("plugin_model", "s1")
    try:
        return run_local(a) if a.local else run_pi(a)
    except KeyboardInterrupt:
        print("\nstopped")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
