"""Build docs/Putting_It_Together.pdf: the Raspberry Pi set-up, the communication network,
where each teammate plugs in, and a map of every file in the twin node.

    py docs/guide/build_integration_guide.py

Uses the layout, styles and helpers of build_guide.py. The two diagrams are drawn at print
size, so their text prints at the size it is set.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_guide as bg                                          # noqa: E402
from matplotlib.patches import FancyBboxPatch                     # noqa: E402
from reportlab.platypus import (PageBreak, Paragraph, Spacer, NextPageTemplate,  # noqa: E402
                                KeepTogether, CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents   # noqa: E402
from reportlab.lib.styles import ParagraphStyle                   # noqa: E402
from reportlab.lib.units import cm                                # noqa: E402

bg.TITLE = "Putting it together"
bg.FOOTER = "Putting it together: the Pi, the network and the files  ·  EEE40016"
OUT = os.path.join(bg.PROJECT, "docs", "Putting_It_Together.pdf")
plt = bg.plt
p, h1, h2, bullets, numbered, callout, table, figure = (bg.p, bg.h1, bg.h2, bg.bullets,
                                                         bg.numbered, bg.callout, bg.table,
                                                         bg.figure)
# 8.6 pt Courier fits 88 characters across the frame; every command below is shorter, so
# none is ever broken across two lines
CODE = ParagraphStyle("code", fontName="Courier", fontSize=8.6, leading=11.8,
                      textColor="#1A1A1A", backColor="#F3F3F3", borderPadding=(5, 6, 5, 6),
                      leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=9)
GREY_BOX = dict(face="#F6F6F6", edge="#9A9A9A")
_lead = []        # the paragraph introducing the next command block, held until it comes


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def code(*lines):
    """A command block, never split across two pages, and on the same page as the
    paragraph that introduces it (keepWithNext does not hold onto a KeepTogether)."""
    bg.story.append(KeepTogether(_lead + [Paragraph(
        "<br/>".join(_esc(l).replace(" ", "&nbsp;") for l in lines), CODE)]))
    _lead.clear()


def lead(t):
    """A paragraph that introduces the command block after it."""
    _lead.append(Paragraph(t, bg.BODY))


def c(t, size=9.2, nb=True):
    """Inline code. nb keeps a short command on one line; the file map lets lists wrap."""
    t = _esc(t)
    return "<font name='Courier' size='%s'>%s</font>" % (size, t.replace(" ", "&nbsp;")
                                                        if nb else t)


def ct(t):
    return c(t, size=8.4)


# ------------------------------------------------------------------ diagrams

def fig_setup(path):
    fig, ax = bg._canvas(6.6, 3.3, 100, 50)
    ax.add_patch(FancyBboxPatch((0.6, 1), 42, 47.2, boxstyle="round,pad=0.3,rounding_size=1.5",
                                linewidth=1.3, edgecolor=bg.RED, facecolor="white"))
    ax.text(2.6, 46.6, "Laptop  (Munir)", fontsize=9.5, fontweight="bold", va="top",
            color=bg.INK)
    kw = dict(tsize=9, bsize=7.6)
    bg._box(ax, 3, 31.2, 37.2, 11, "Digital twin", "street model, safe-limit search,\n"
            "controllers A, B and C, experiments", face=bg.TINT, edge=bg.RED, **kw)
    bg._box(ax, 3, 17, 37.2, 11, "Hoang's comms link and trust",
            "delays, drops and freezes messages;\nruns inside the twin", **kw)
    bg._box(ax, 3, 2.8, 37.2, 11, "Gia's battery", "in the street model, or on the Pi\n"
            "with --battery-on-pi", **kw)
    bg._box(ax, 53.5, 16, 17, 18, "MQTT broker", "passes each\nmessage on;\nruns on the\n"
            "laptop", **kw)
    bg._box(ax, 79.5, 13.5, 20, 23, "Raspberry Pi", "Lomitha's\ncharge-point\ncontroller for\n"
            "22 chargers;\nGia's battery\n(optional)", face=bg.TINT, edge=bg.RED, **kw)
    top, bot = 27.5, 22.5
    bg._arrow(ax, 43.2, top, 53.0, top, lw=1.3)
    bg._arrow(ax, 71.0, top, 79.0, top, lw=1.3)
    bg._arrow(ax, 53.0, bot, 43.2, bot, lw=1.3)
    bg._arrow(ax, 79.0, bot, 71.0, bot, lw=1.3)
    ax.text(48.1, top + 0.9, "sync,\ndownlink", ha="center", va="bottom", fontsize=7,
            color=bg.GREY, linespacing=1.15)
    ax.text(48.1, bot - 0.9, "uplink, ack,\nstatus", ha="center", va="top", fontsize=7,
            color=bg.GREY, linespacing=1.15)
    ax.text(76.5, 10.5, "all on one Wi-Fi network,\nfor example a phone hotspot",
            ha="center", va="top", fontsize=7.6, color=bg.GREY, style="italic")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_sequence(path):
    fig, ax = bg._canvas(6.6, 3.9, 100, 60)
    xs = {"twin": 13, "broker": 50, "pi": 87}
    for key, title in (("twin", "Laptop (twin)"), ("broker", "MQTT broker"),
                       ("pi", "Raspberry Pi")):
        x, end = xs[key], key != "broker"
        ax.add_patch(FancyBboxPatch((x - 10, 53.5), 20, 5.5,
                                    boxstyle="round,pad=0.25,rounding_size=1.2", linewidth=1.3,
                                    edgecolor=bg.RED if end else "#9A9A9A",
                                    facecolor=bg.TINT if end else bg.LIGHT))
        ax.text(x, 56.25, title, ha="center", va="center", fontsize=9, fontweight="bold",
                color=bg.INK)
        ax.plot([x, x], [9, 53.2], color="#BBBBBB", lw=1.0, ls=(0, (4, 3)), zorder=0)
    # a white backing keeps the dashed lifelines out of the words
    halo = dict(facecolor="white", edgecolor="none", pad=1.5)

    def msg(y, a, b, num, label):
        bg._arrow(ax, xs[a], y, xs[b], y, color=bg.INK, lw=1.2)
        ax.plot([xs["broker"]], [y], marker="o", ms=3.2, color=bg.GREY, zorder=3)
        ax.text(50, y + 1.0, "%d   %s" % (num, label), ha="center", va="bottom",
                fontsize=7.8, color=bg.INK, bbox=halo, zorder=4)

    def note(y, who, num, label):
        left = who == "twin"
        ax.text(xs[who] + (1.5 if left else -1.5), y, "%d   %s" % (num, label),
                ha="left" if left else "right", va="center", fontsize=7.8, color=bg.RED,
                style="italic", bbox=halo, zorder=4)

    msg(48, "twin", "pi", 1, "sync: open step k, and what every house's meter reads")
    msg(42, "pi", "twin", 2, "uplink ×10: meter readings and car status, one every 30 s")
    note(36.5, "twin", 3, "Hoang's link ages the data; the twin works out the limit")
    msg(31, "twin", "pi", 4, "downlink: the limit, its schedule entry, valid from and until")
    note(25.5, "pi", 5, "the controller applies it to all 22 chargers")
    msg(20, "pi", "twin", 6, "ack: what each charger actually drew")
    note(14.5, "twin", 7, "the draws go on the true street; the five limits are checked")
    ax.text(50, 4.5, "repeated every 5 simulated minutes: 72 steps make one evening, about 10 "
            "seconds of real time", ha="center", va="center", fontsize=7.4, color=bg.GREY)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ------------------------------------------------------------------ content

def build(figs):
    s = bg.story
    s.append(Spacer(1, 3.0 * cm))
    s.append(Paragraph("Putting it together", ParagraphStyle(
        "t", fontName="Cal-B", fontSize=30, leading=36, textColor=bg.INK)))
    s.append(Spacer(1, 6))
    s.append(Paragraph("The Raspberry Pi, the communication network, and every file in your "
                       "node", ParagraphStyle("st", fontName="Cal", fontSize=15, leading=20,
                                              textColor=bg.GREY)))
    s.append(Spacer(1, 22))
    s.append(Paragraph("EEE40016 Design of Smart Power Grids<br/>Node: digital twin server "
                       "(Munir Aslam)<br/>12 October 2026, for the integration session",
                       ParagraphStyle("cov", parent=bg.BODY, fontSize=11.5, leading=17)))
    s.append(Spacer(1, 1.5 * cm))
    callout("How to run everything together with the Raspberry Pi, step by step; how the "
            "laptop, the broker and the Pi talk to each other; where each teammate's code "
            "goes; what to do when something does not connect; and what every file in your "
            "node is for. To copy and paste the commands, use "
            "<font name='Cal-B'>team/README.md</font>. The street model and the results are "
            "explained in <font name='Cal-B'>Digital_Twin_Guide.pdf</font>.", **GREY_BOX)
    s.append(NextPageTemplate("body"))
    s.append(PageBreak())
    s.append(Paragraph("Contents", ParagraphStyle("toctitle", parent=bg.H1)))
    toc = TableOfContents()
    toc.levelStyles = [bg.TOC1, bg.TOC2]
    s.append(toc)
    s.append(PageBreak())

    # ---- 1
    h1("1. The short version")
    p("The four parts run together for the first time, with real messages going between the "
      "laptop and the Raspberry Pi. Everything that can be prepared on the laptop is ready and "
      "has been rehearsed, and the laptop can drive the whole run by itself.")
    table([["What", "Runs on", "Whose"],
           ["The digital twin: street model, safe-limit search, controllers, experiments",
            "laptop", "Munir"],
           ["The comms injector and trust score", "laptop, inside the twin", "Hoang"],
           ["The battery, BMS and EMS", "laptop, or the Pi (optional)", "Gia"],
           ["The charge-point controller for all 22 chargers", "Raspberry Pi", "Lomitha"],
           ["The MQTT broker, which passes messages between them", "the laptop",
            "shared"]], [0.58, 0.26, 0.16])
    p("Gia runs the session on her laptop with her Pi, from the handover zip; its "
      + c("README_FIRST.md") + " has the same steps as this guide.")
    p("The easy way, in five moves:")
    numbered(["Put the laptop and the Pi on the same phone hotspot, with SSH switched on on "
              "the Pi (Section 3).",
              "Find the Pi's address from the laptop: " + c("py tools/pi_session.py --find") +
              ".",
              "Run " + c("py tools/pi_session.py --pi <user>@<Pi address>") + " and type the "
              "Pi's password when asked. It ends with EQUIVALENT.",
              "Add the teammates' parts with " + c("--team") + ", one at a time, then all "
              "together with the battery on the Pi: " + c("--team all --battery-on-pi") + ".",
              "If the Pi will not connect, " + c("py tools/pi_session.py --local") + " runs "
              "the same evening on the laptop alone, for the demo."])
    p("Nothing has to be installed on the Pi, and nothing needs allowing through the "
      "laptop's firewall. Section 3 has the details, and the by-hand route.")
    h2("Already tested")
    bullets(["A full rehearsal on the laptop, with the Pi package unzipped into a separate "
             "folder and run as its own program standing in for the Pi: one evening over "
             "MQTT, EQUIVALENT to the simulator at every step, with replies in 5 to 12 ms.",
             "The same with Python told to ignore every installed package, which proves the "
             "Pi's program needs only the MQTT library it carries with it.",
             "Lomitha's own code (one gateway per charger, with the IEC 61851 pilot rules), "
             "on both sides with " + c("--team lomitha") + ": EQUIVALENT. Switched to ideal "
             "settings it gives the stand-in's answer exactly; with its real settings, 0.5 to "
             "2.4% less energy and no extra violations.",
             "All three parts with the battery on the Pi (" + c("--team all --battery-on-pi") +
             "): EQUIVALENT, battery state of charge included, about 1 ms per battery call.",
             "The SSH tunnel, with a stand-in for it that accepts the connection before any "
             "broker answers, as the real one does: the Pi waits, connects, EQUIVALENT.",
             "The one-command run with " + c("--local") + ", and its error messages for a "
             "wrong address, no SSH, and a typo in " + c("--team") + ".",
             "Pulling the Pi offline: the laptop refuses to start and prints a checklist.",
             "Each teammate's starting file passes the acceptance tests (V2, V5, V6, V7), "
             "and one experiment run on all three files matches the main results exactly.",
             "None of these changes altered a single result: all golden runs identical, and "
             "V9 passed on 11 October, eight days after it was recorded."])
    callout("<font name='Cal-B'>Not tested yet</font>, because it needs the real hardware: the "
            "Raspberry Pi itself, SSH into it from the laptop, and the tunnel over a real "
            "network. The commands are written for all three, but the first run with the Pi "
            "is the first time they meet.")

    # ---- 2
    h1("2. How the parts talk to each other")
    p("Everything goes through an <font name='Cal-B'>MQTT broker</font>, a small program that "
      "receives each message and passes it on to whoever has asked for that kind of message "
      "(that is, has subscribed to that topic). The laptop and the Pi never connect to each "
      "other directly; both connect to the broker.")
    figure(figs["setup"], "Figure 1. What runs where. Hoang's code runs inside the twin on "
           "the laptop; the charge-point controller is on the Pi, and Gia's battery can be "
           "either.")
    h2("How the Pi reaches the broker")
    p("By default the Pi reaches the broker through the SSH connection the laptop opens to "
      "start it (an SSH tunnel): the Pi connects to its own end of the tunnel, and SSH carries "
      "the messages to the broker on the laptop. Windows never sees an incoming connection, so "
      "nothing needs allowing through the firewall, and the messages travel encrypted. With "
      + c("--direct") + " the Pi connects straight to the broker across the Wi-Fi instead, as "
      "plain MQTT on port 1883; Windows then asks to allow Python the first time. Either way "
      "the messages are the same and so are the results.")
    h2("The topics")
    table([["Topic", "From → to", "What it carries", "How often"],
           [ct("eee40016/sync"), "laptop → Pi", "opens a step; what each house's meter "
            "reads", "every step"],
           [ct("eee40016/uplink/edge"), "Pi → laptop", "meter readings and every car's "
            "status", "10 per step"],
           [ct("eee40016/downlink/edge"), "laptop → Pi", "the charging limit, its schedule "
            "entry and when it is valid", "every step"],
           [ct("eee40016/ack/edge"), "Pi → laptop", "what each charger actually drew",
            "every step"],
           [ct("eee40016/status/edge"), "Pi → laptop", "\"online\" or \"offline\", kept by "
            "the broker so the laptop can check the Pi is there", "on connect and "
            "disconnect"],
           [ct("eee40016/breq/battery"), "laptop → Pi", "battery on the Pi only: a call on "
            "the battery (reset, response, commit)", "up to 7 per step"],
           [ct("eee40016/bresp/battery"), "Pi → laptop", "battery on the Pi only: the answer",
            "one per call"]],
          [0.3, 0.15, 0.4, 0.15], size=9)
    p("Every message is a small piece of JSON defined in " + c("src/messages.py") + ". That "
      "file is the contract: the laptop and the Pi must have the same version (version 2), or "
      "messages are rejected rather than half-read. The Pi package always carries the right "
      "copy.")
    h2("One step, in order", need=bg.fig_cm(figs["sequence"]) + 1.0)
    figure(figs["sequence"], "Figure 2. The messages in one 5-minute step. The laptop waits "
           "for the Pi's reply before moving on, so the two stay in step.")
    h2("Two kinds of delay, kept apart")
    p("The study's delay and packet loss (for example 60 seconds and 10%) are "
      "<font name='Cal-B'>simulated</font> inside the twin by Hoang's comms link, in simulated "
      "time. The real network between the laptop and the Pi adds only a few milliseconds. That "
      "real delay is measured and reported, but never added to the study. The Pi runs on the "
      "simulated clock carried in each message, not its own clock. This is why a whole evening "
      "takes about ten seconds, and why the Pi run can match the simulator exactly.")
    callout("The electricity network itself (the street, its cables and transformer) is "
            "explained in <font name='Cal-B'>Digital_Twin_Guide.pdf</font>, section 3. This "
            "guide is about the communication network between the devices.", **GREY_BOX)

    # ---- 3
    h1("3. Step by step")
    h2("Before you start")
    bullets(["<font name='Cal-B'>On the Pi, once</font> (the only part that needs a keyboard "
             "and screen on it): switch SSH on with " + c("sudo raspi-config") + ", Interface "
             "Options, SSH (or tick it in Raspberry Pi Imager when making the SD card), and "
             "join the phone hotspot.",
             "Have a phone hotspot ready. University Wi-Fi (eduroam) usually blocks devices "
             "from talking to each other.",
             "Nothing to install on the Pi: the Pi package carries its own copy of the MQTT "
             "library, so the Python 3 that comes with Raspberry Pi OS is enough. A laptop new "
             "to the project needs one command, once: " +
             c("py -m pip install -r requirements_laptop.txt") + ". SSH is built into "
             "Windows 10 and 11 and macOS."])
    lead("To join the hotspot from the Pi's terminal (recent Raspberry Pi OS):")
    code('sudo nmcli dev wifi connect "<hotspot name>" password "<password>"')
    h2("The easy way: one command from the laptop")
    lead("With the laptop and the Pi on the hotspot, find the Pi's address from the laptop:")
    code("py tools/pi_session.py --find")
    p("It lists the devices on the hotspot that answer SSH; a Raspberry Pi says Debian or "
      "Raspbian. Use it on the hotspot, not on university Wi-Fi.")
    lead("Then run an evening:")
    code("py tools/pi_session.py --pi <user>@<Pi address>")
    p("The user is the one made when the Pi was set up. The command rebuilds the Pi package "
      "from the laptop's files, copies it to the Pi, starts the broker on the laptop and the "
      "Pi's program over SSH, runs the evening, compares it with the simulator and stops the "
      "Pi's program again. Type the Pi's password when asked: once to copy, once to start. The "
      "Pi's lines start with " + c("Pi |") + ". With the battery on the Pi too, the Pi also "
      "prints one battery line per step.")
    lead("Everything at once, with every teammate's part and the battery on the Pi:")
    code("py tools/pi_session.py --pi <user>@<Pi address> --team all --battery-on-pi")
    table([["Option", "Meaning", "Default"],
           [ct("--controller"), "A fixed, B trust-weighted, C binary fallback", "B"],
           [ct("--latency"), "simulated delay, seconds, both directions", "60"],
           [ct("--loss"), "simulated packet loss, 0 to 1", "0.10"],
           [ct("--seed"), "which simulated evening (7 to 19); both sides get it", "7"],
           [ct("--plugin-model"), "s1 main case, s2 stress case; both sides get it", "s1"],
           [ct("--team"), "teammates' files instead of the stand-ins (Section 4)", "none"],
           [ct("--static-kw"), "the fixed limit for A and C; left out, it is calibrated "
            "(about a minute; 2.5 for seed 7)", "none"],
           [ct("--no-copy"), "the Pi already has the current package: skip the copy and "
            "one password", "off"],
           [ct("--no-compare"), "skip the check against the simulator, for a shorter demo",
            "off"],
           [ct("--battery-on-pi"), "run the battery on the Pi as well (Gia's class with "
            + ct("--team gia") + " or " + ct("all") + ")", "off"],
           [ct("--direct"), "plain MQTT across the Wi-Fi instead of the SSH tunnel "
            "(Windows asks to allow Python)", "off"],
           [ct("--dry-run"), "print what would run, run nothing", "off"]],
          [0.22, 0.62, 0.16], size=9.2)
    lead("<font name='Cal-B'>Plan B.</font> If the Pi will not connect, the same evening runs "
         "with the Pi's program on the laptop, with the same output and the same check:")
    code("py tools/pi_session.py --local")
    h2("By hand, if you prefer")
    p("The same run as separate steps. Find the addresses with " + c("ipconfig") + " on the "
      "laptop and " + c("hostname -I") + " on the Pi.")
    numbered(["Start the broker on the laptop with " + c("py tools/broker.py") + " and leave "
              "it open (allow Python through the firewall when asked).",
              "Copy " + c("pi_package.zip") + " to the Pi (USB stick, or " +
              c("scp pi_package.zip <user>@<Pi address>:") + ") and unzip it there.",
              "On the Pi, in " + c("pi_package") + ": " +
              c("python3 run_pi_node.py --broker <laptop address>") + ". It says "
              "\"connected\". Add " + c("--battery") + " to run the battery there too "
              "(and " + c("--battery-on-pi") + " on the laptop).",
              "On the laptop: " + c("py tools/run_with_pi.py --broker 127.0.0.1 --compare") +
              ". Use the same " + c("--seed") + ", scenario and " + c("--team lomitha") +
              " on both sides."])
    lead("To run the broker on the Pi instead (then nothing on the laptop needs allowing "
         "through the firewall, and both sides use the Pi's address):")
    code("sudo apt install mosquitto",
         "printf 'listener 1883\\nallow_anonymous true\\n' | \\",
         "    sudo tee /etc/mosquitto/conf.d/eee40016.conf",
         "sudo systemctl restart mosquitto")
    h2("Swap in each teammate's code")
    p("One person at a time, so a problem is easy to trace: Lomitha first, then Hoang and Gia. "
      "Add " + c("--team lomitha") + " (then " + c("hoang") + ", " + c("gia") + ", " +
      c("all") + ") to the command and run again. Section 4 has the details.")
    h2("The demo")
    lead("A good pair to show, where " + c("<pi>") + " is " + c("<user>@<Pi address>") + ": "
         "B at 60 s and 10% loss (live control working), then C at 300 s and 20% (where the "
         "all-or-nothing approach struggles):")
    code("py tools/pi_session.py --pi <pi> --controller B --latency 60 --loss 0.1",
         "py tools/pi_session.py --pi <pi> --controller C --latency 300 --loss 0.2 --no-copy")

    # ---- 4
    h1("4. Where each teammate's code goes")
    p("Each teammate has a starting file in " + c("team/") + ". It already works as it is, "
      "because it inherits everything from the stand-in. They replace the methods with their "
      "own, one at a time, and run their test after each change. They keep the class name and "
      "the constructor arguments, and keep it plain Python with no networking inside.")
    table([["Who", "Starting file", "Runs on", "Plug it in with", "Must pass"],
           ["Hoang", ct("team/hoang_link.py"), "laptop", ct("--team hoang"), "V5, V6"],
           ["Lomitha", ct("team/lomitha/") + " (Lomitha's code) and " +
            ct("team/lomitha_fleet.py"), "the Pi", ct("--team lomitha"), "EQUIVALENT"],
           ["Gia", ct("team/gia_battery.py"), "laptop, or the Pi", ct("--team gia") + "; on "
            "the Pi add " + ct("--battery-on-pi"), "V2, V7"]],
          [0.11, 0.27, 0.11, 0.36, 0.15], size=9)
    lead(c("--team") + " also takes a list, such as " + c("--team hoang,gia") + ", or " +
      c("--team all") + ". Each person checks their own part with the acceptance tests "
      "before joining:")
    code("py tests/test_node_acceptance.py --team hoang",
         "py tests/test_node_acceptance.py --team gia")
    p("To bring their code in, a teammate copies their one file into " + c("team/") + " on "
      "your laptop. " + c("pi_session.py") + " copies Lomitha's file to the Pi for you on "
      "every run, so edit it on the laptop, not on the Pi. Nothing else changes. The rules "
      "each part must follow (R1 to R7) are in " + c("docs/INTERFACES.md") + " and at the "
      "top of each starting file.")
    callout("<font name='Cal-B'>What EQUIVALENT proves for Lomitha.</font> It shows "
            "Lomitha's controller gives the same answer over MQTT on the Pi as inside the "
            "simulator, so the messaging is right. Whether the controller follows the rules "
            "is checked by R1 to R5 and by the experiments themselves, which run the same "
            "class directly.",
            **GREY_BOX)
    h2("The final runs with everyone's code", need=7)
    lead("When all three parts pass, rerun the three experiments with the real code, one after "
         "the other. They take about three hours in all, S1 most of it, so keep the laptop "
         "plugged in, and in a second window run " + c("py tools/hold_awake.py") + " so Windows "
         "does not go to sleep mid-run.")
    code('py tools/run_parallel.py --arm "team:S1:results/stages_team:--team all"',
         'py tools/run_parallel.py --arm "team:S2:results/stages_team:--team all"',
         'py tools/run_parallel.py --arm "team:S3:results/stages_team:--team all"')
    lead("Then put the summary together:")
    code("py src/stages.py --summarise --team all")
    p("The results go to " + c("results/stages_team") + ", so they can never overwrite the "
      "stand-in results, and each file records which classes made it.")

    # ---- 5
    h1("5. When something goes wrong")
    table([["What you see", "Most likely cause", "What to do"],
           ["\"REMOTE HOST IDENTIFICATION HAS CHANGED\"", "the Pi was set up again with "
            "the same address", "run ssh-keygen -R &lt;Pi address&gt; once, then again"],
           ["\"remote port forwarding failed\"", "something on the Pi uses the tunnel's "
            "port", "add --tunnel-port 18831"],
           ["\"the battery on the Pi did not report in\"", "the Pi program was started "
            "without --battery", "use pi_session.py with --battery-on-pi, which starts it "
            "right"],
           ["ssh or scp: \"Connection refused\"", "SSH is switched off on the Pi",
            "once, on the Pi: sudo raspi-config, Interface Options, SSH"],
           ["\"Connection timed out\" or \"cannot find\" the Pi", "the Pi is not on the "
            "hotspot, or the address is wrong", "py tools/pi_session.py --find; check the "
            "Pi joined the hotspot"],
           ["\"Permission denied\"", "wrong user name or password", "the user and password "
            "made when the Pi was set up"],
           ["\"The Pi's program never reached the broker on this laptop\"", "only with "
            "--direct: the Windows firewall, often because the hotspot counts as Public",
            "leave out --direct (the tunnel needs no firewall changes), or allow Python for "
            "Private and Public"],
           ["\"already using port 1883\"", "an old broker or run is still open",
            "close it, then run again"],
           ["Laptop: \"the Pi did not report in\"", "the Pi program is not running or not "
            "connected", "look at the Pi | lines; same network"],
           ["\"schema version mismatch\"", "an old messages.py on one side",
            "run with pi_session.py, which copies a fresh package"],
           ["NOT EQUIVALENT", "different seed, scenario or controller on the two sides",
            "pi_session.py keeps them the same; by hand, match --seed, scenario and --team"],
           ["\"edge sent 3 of 10 samples\"", "the Pi program crashed or stalled mid-run",
            "read the error in the Pi | lines, fix, run again"],
           ["\"no teammate called ...\"", "a typo after --team", "use hoang, gia, lomitha "
            "or all"],
           ["\"no sessions for seed\"", "a seed outside 7 to 19", "use 7 to 19"],
           ["Ping from the Pi to the laptop fails", "Windows ignores pings by default",
            "ping from the laptop to the Pi instead"]],
          [0.3, 0.33, 0.37], size=9)

    # ---- 6
    h1("6. Every file in your node")
    p("Grouped by folder, inside " + c("Downloads\\EEE40016\\project") + ". The three "
      "<font name='Cal-B'>stand-ins</font> are working placeholders for teammates' parts, "
      "to be replaced by their own code.")
    groups = [
        ("Settings", [("config/study.json", "every setting of the study: time window, limits, "
                       "margins, controllers, demand case"),
                      ("config/cable_ratings.json", "cable ratings (provisional) and the "
                       "transformer's thermal data")]),
        ("Data", [("data/feeder/", "the IEEE European LV Test Feeder package and its "
                   "published solutions"),
                  ("data/sessions/", "charging sessions per seed and demand case, frozen so "
                   "every run uses the same ones"),
                  ("data/vista/", "the VISTA travel survey and the arrival and energy fit "
                   "taken from it"),
                  ("data/pv_profile.csv, ambient.csv, weather/", "solar output per minute and "
                   "Bureau of Meteorology temperatures")]),
        ("The model (src/)", [("sweep.py", "one simulated evening, step by step: the heart of "
                               "the study; also calibrates the fixed limit"),
                              ("envelope.py", "the safe-limit search (bisection on 0.1 kW "
                               "steps); picks which houses have EVs"),
                              ("network_state.py", "the five network checks and the "
                               "transformer temperature model"),
                              ("solver.py", "the street in OpenDSS (and SINCAL for "
                               "cross-checks)"),
                              ("feeder_csv.py", "reads the IEEE feeder package"),
                              ("controllers.py", "controllers A, B and C"),
                              ("ev_sessions.py, vista_sessions.py", "who plugs in, when, and "
                               "how much energy they want"),
                              ("stages.py", "runs and summarises the experiments S1, S2, S3"),
                              ("messages.py", "the shared message contract (version 2); "
                               "everyone uses this exact file"),
                              ("mqtt_edge.py", "MQTT: the Pi side and the laptop side"),
                              ("plugins.py", "drops a teammate's class in by name; the "
                               "--team option"),
                              ("telemetry.py", "STAND-IN for Hoang: comms injector and "
                               "trust score"),
                              ("edge.py", "STAND-IN for Lomitha: the charge-point controller"),
                              ("battery.py", "STAND-IN for Gia: the battery and its voltage "
                               "response"),
                              ("timeout_sensitivity.py, refine_crossover.py", "extra analyses: "
                               "the timeout test, crossover refinement"),
                              ("build_sincal_model.py, inspect_sincal_schema.py", "write the "
                               "street into SINCAL; read SINCAL's database layout"),
                              ("make_scenario_data.py, plot_*.py", "build the solar and "
                               "weather files; draw the figures")]),
        ("Tests (tests/)", [("test_lomitha_adapter.py", "Lomitha's controller keeps the "
                             "interface, and what its charging rules change"),
                            ("v1_benchmark.py ... v9_reproducibility.py", "the validation "
                             "checks V1, V3, V4, V8, V9"),
                            ("test_node_acceptance.py", "V2, V5, V6, V7: the teammates' "
                             "hand-over tests"),
                            ("test_mqtt_equivalence.py", "the MQTT path gives the simulator's "
                             "answer"),
                            ("test_setpoint_schedule.py, golden_runs.py", "the schedule fix; "
                             "proof that a change did not alter results"),
                            ("check_model.py, solve_timing.py", "the feeder model's structure; "
                             "speed")]),
        ("Tools (tools/)", [("pi_session.py", "one command for a whole run with the Pi, "
                             "or on the laptop alone (--local); --find finds the Pi"),
                            ("run_with_pi.py", "the laptop side of a run with the Pi"),
                            ("pi/run_pi_node.py", "the Pi side (copied into the Pi "
                             "package); --battery serves the battery too"),
                            ("make_handover.py", "builds the zip for a teammate, with "
                             "README_FIRST.md"),
                            ("broker.py", "an MQTT broker on the laptop"),
                            ("make_pi_package.py", "builds pi_package/ and pi_package.zip, "
                             "with its own copy of the MQTT library"),
                            ("run_parallel.py", "the experiment queue, many runs in parallel"),
                            ("compare_paired.py, compare_sensitivity.py", "before-and-after "
                             "checks of the schedule fix"),
                            ("calibrate_preview.py, demand_scenarios.py", "fixed limit per "
                             "seed; the demand screening"),
                            ("hold_awake.py", "keeps Windows awake during long runs"),
                            ("sincal_*.py, avd_*.py, make_avd_package.py", "the SINCAL "
                             "cross-check, here and on the uni computers")]),
        ("Teammates (team/)", [("hoang_link.py, gia_battery.py",
                                "Hoang's and Gia's starting files (still the stand-ins)"),
                               ("lomitha/, lomitha_fleet.py", "Lomitha's own code, and the "
                                "adapter that connects it to the twin"),
                               ("hoang_prototype/", "Hoang's MQTT chat prototype, with notes"),
                               ("README.md", "the commands for tomorrow, to copy and paste")]),
        ("Documents", [("docs/INTERFACES.md", "what each teammate must build (rules R1 to R7)"),
                       ("docs/Digital_Twin_Guide.pdf", "the models and the results, explained"),
                       ("docs/Putting_It_Together.pdf", "this guide"),
                       ("docs/Your_Files_Explained.pdf", "every file here, explained one by "
                        "one"),
                       ("docs/guide/", "the scripts that build the three guides"),
                       ("notes/AUDIT.md", "every plan commitment checked, with the final "
                        "results"),
                       ("notes/plan_amendments.md", "all 28 design changes and faults, with "
                        "reasons"),
                       ("notes/*.md (others)", "the result notes for each check and the "
                        "SINCAL notes"),
                       ("README.md", "the project's front page")]),
        ("Results (results/)", [("stages/, stress_s2/", "the main-case and stress-case results "
                                 "and figures"),
                                ("paired_main/, paired_stress/, mechanism_standin/, "
                                 "sensitivity/", "the schedule fix, before and after"),
                                ("timeout_sensitivity/", "the timeout test"),
                                ("hil/", "runs with the Raspberry Pi; the laptop "
                                 "rehearsals of 11 October are in hil/rehearsal/"),
                                ("golden/, v9/", "reference runs for the checks"),
                                ("superseded/", "old results; never quote these")]),
        ("Packages", [("pi_package/, pi_package.zip", "everything that goes on the Pi"),
                      ("avd_crosscheck.zip", "the SINCAL check for the uni computers"),
                      ("models/", "SINCAL projects"),
                      ("logs/, LOG/, Log.db", "run logs and SINCAL's own log files")]),
    ]
    # one table per folder group, each starting where its heading and first rows fit
    for gname, items in groups:
        bg.story.append(CondPageBreak(3.2 * cm))
        table([[gname, "What it is"]] + [[c(f, size=8.6, nb=False), d] for f, d in items],
              [0.42, 0.58], size=9)


def main():
    figs = {"setup": os.path.join(HERE, "figI1_setup.png"),
            "sequence": os.path.join(HERE, "figI2_sequence.png")}
    fig_setup(figs["setup"])
    fig_sequence(figs["sequence"])
    build(figs)
    assert not _lead, "a lead() paragraph has no command block after it"
    doc = bg.GuideDoc(OUT)
    doc.multiBuild(bg.story)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
