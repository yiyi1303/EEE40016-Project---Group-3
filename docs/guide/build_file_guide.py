"""Build docs/Your_Files_Explained.pdf: what every file in the twin node does and what it
is for, folder by folder, with a map of how the files work together.

    py docs/guide/build_file_guide.py

Uses the layout, styles and helpers of build_guide.py. The diagram is drawn at print size.
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

bg.TITLE = "Your files, explained"
bg.FOOTER = "Your files, explained  ·  EEE40016"
OUT = os.path.join(bg.PROJECT, "docs", "Your_Files_Explained.pdf")
plt = bg.plt
p, h1, h2, bullets, numbered, callout, table, figure = (bg.p, bg.h1, bg.h2, bg.bullets,
                                                         bg.numbered, bg.callout, bg.table,
                                                         bg.figure)
GREY_BOX = dict(face="#F6F6F6", edge="#9A9A9A")
NAME = ParagraphStyle("name", parent=bg.BODY, fontName="Courier-Bold", fontSize=10.2,
                      leading=13, spaceBefore=8, spaceAfter=2, textColor=bg.INK)
RUN = ParagraphStyle("run", parent=bg.BODY, fontSize=9.8, leading=13.5, spaceAfter=4,
                     textColor="#333333")


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def c(t, size=9.2, nb=True):
    """Inline code; nb keeps a short command on one line."""
    t = _esc(t)
    return "<font name='Courier' size='%s'>%s</font>" % (size, t.replace(" ", "&nbsp;")
                                                        if nb else t)


def cw(t):
    """Code in a table cell, free to wrap at spaces."""
    return c(t, size=8.4, nb=False)


def card(name, tag, text, run=None):
    """One file: its name and a short tag, what it does, and how to run it. Never split
    across two pages."""
    head = _esc(name)
    if tag:
        head += ("&nbsp;&nbsp;&nbsp;<font name='Cal-B' size='8.2' color='%s'>%s</font>"
                 % ("#C8102E" if tag.startswith("STAND-IN") else "#8A8A8A", tag))
    flow = [Paragraph(head, NAME), Paragraph(text, bg.BODY)]
    for r in ([run] if isinstance(run, str) else run or []):
        flow.append(Paragraph("<font name='Cal-B'>Run:</font>&nbsp; " + c(r), RUN))
    bg.story.append(KeepTogether(flow))


def together(*builders):
    """Run each builder and keep everything they add on one page, so a heading or a lead-in
    never sits at the foot of a page with its table or figure on the next. Inner
    KeepTogethers are unwrapped (a nested one always forces a page break) and the headings'
    own CondPageBreaks dropped."""
    start = len(bg.story)
    for b in builders:
        b()
    chunk = []
    for f in bg.story[start:]:
        if isinstance(f, KeepTogether):
            chunk.extend(f._content)
        elif not isinstance(f, CondPageBreak):
            chunk.append(f)
    del bg.story[start:]
    bg.story.append(KeepTogether(chunk))


# ------------------------------------------------------------------ diagram

def fig_map(path):
    fig, ax = bg._canvas(6.6, 5.4, 100, 82)
    kw = dict(tsize=8.6, bsize=7.4)

    def frame(x, y, w, h, title, sub, edge):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.5",
                                    linewidth=1.3, edgecolor=edge, facecolor="white"))
        ax.text(x + 1.6, y + h - 1.2, title, fontsize=9.2, fontweight="bold", va="top",
                color=bg.INK)
        ax.text(x + 1.6, y + h - 4.0, sub, fontsize=7.2, va="top", color=bg.GREY,
                style="italic")

    bg._box(ax, 2, 71, 96, 9, "Settings and inputs", "config/study.json (every setting)  ·  "
            "config/cable_ratings.json  ·  data/: the IEEE street, the cars, the sun, the "
            "weather", **kw)
    frame(2, 30, 61.5, 34.5, "One simulated evening:  src/sweep.py",
          "every 5 minutes, 72 times, 16:00 to 22:00", bg.RED)
    red = dict(face=bg.TINT, edge=bg.RED, **kw)
    bg._box(ax, 4, 44.5, 18, 11, "solver.py", "the street,\nsolved in OpenDSS", **red)
    bg._box(ax, 24, 44.5, 18, 11, "envelope.py", "searches for the\nsafe charging limit",
            **red)
    bg._box(ax, 44, 44.5, 18, 11, "controllers.py", "A, B and C turn it\ninto the limit sent",
            **red)
    bg._box(ax, 4, 32, 18, 10.5, "ev_sessions.py", "which cars plug in,\nwhen, how much",
            **red)
    bg._box(ax, 24, 32, 18, 10.5, "network_state.py", "the five network\nchecks", **red)
    ax.text(53, 37.5, "each evening ends as\none result: energy\ndelivered, limits broken",
            ha="center", va="center", fontsize=7.2, color=bg.GREY, style="italic",
            linespacing=1.2)
    frame(70, 30, 28, 34.5, "Teammates' parts", "stand-ins until their code arrives",
          "#9A9A9A")
    bg._box(ax, 72, 49.4, 24, 8, "telemetry.py", "Hoang: comms link, trust", **kw)
    bg._box(ax, 72, 40.2, 24, 8, "edge.py", "Lomitha: charge points", **kw)
    bg._box(ax, 72, 31, 24, 8, "battery.py", "Gia: battery", **kw)
    # plugged into the evening; small heads so the short arrow keeps its shape
    ax.annotate("", xy=(69.6, 47), xytext=(63.9, 47),
                arrowprops=dict(arrowstyle="<|-|>", color="#444444", lw=1.1,
                                mutation_scale=8, shrinkA=0, shrinkB=0))
    bg._box(ax, 2, 3, 31, 16.5, "Experiments", "stages.py runs S1, S2, S3;\n"
            "tools/run_parallel.py runs\n12 at a time  →  results/\n→  plot_stages.py "
            "figures", **kw)
    bg._box(ax, 35, 3, 30.5, 16.5, "Checks", "tests/: V1 to V9, the\nteammates' acceptance "
            "tests,\ngolden runs, the MQTT test", **kw)
    bg._box(ax, 67.5, 3, 30.5, 16.5, "Running with the Pi", "messages.py and mqtt_edge.py\n"
            "carry the messages;\ntools/pi_session.py runs it,\npi_package/ goes on the Pi",
            **kw)
    bg._arrow(ax, 33, 70.7, 33, 65.1, lw=1.2)
    for x, label in ((17.5, "runs it thousands of times"), (50, "checks each piece")):
        bg._arrow(ax, x, 29.6, x, 20.1, lw=1.2)
        ax.text(x + 1.2, 24.8, label, fontsize=7, color=bg.GREY, va="center")
    bg._arrow(ax, 84, 29.6, 84, 20.1, lw=1.2)
    ax.text(85.2, 24.8, "edge.py runs on the Pi", fontsize=7, color=bg.GREY, va="center")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ------------------------------------------------------------------ content

def build(fig):
    s = bg.story
    s.append(Spacer(1, 3.0 * cm))
    s.append(Paragraph("Your files, explained", ParagraphStyle(
        "t", fontName="Cal-B", fontSize=30, leading=36, textColor=bg.INK)))
    s.append(Spacer(1, 6))
    s.append(Paragraph("What every file in the digital twin node does, and what it is for",
                       ParagraphStyle("st", fontName="Cal", fontSize=15, leading=20,
                                      textColor=bg.GREY)))
    s.append(Spacer(1, 22))
    s.append(Paragraph("EEE40016 Design of Smart Power Grids<br/>Node: digital twin server "
                       "(Munir Aslam)<br/>12 October 2026",
                       ParagraphStyle("cov", parent=bg.BODY, fontSize=11.5, leading=17)))
    s.append(Spacer(1, 1.5 * cm))
    callout("A walk through the project folder, " + c("Downloads\\EEE40016\\project") + ", "
            "one folder at a time: what each file does, why it exists, and how to run it when "
            "it is something you run. The models and results are explained in "
            "<font name='Cal-B'>Digital_Twin_Guide.pdf</font>, and the Raspberry Pi set-up in "
            "<font name='Cal-B'>Putting_It_Together.pdf</font>.", **GREY_BOX)
    s.append(NextPageTemplate("body"))
    s.append(PageBreak())
    s.append(Paragraph("Contents", ParagraphStyle("toctitle", parent=bg.H1)))
    toc = TableOfContents()
    toc.levelStyles = [bg.TOC1, bg.TOC2]
    s.append(toc)
    s.append(PageBreak())

    # ---- 1
    h1("1. How the folder is organised")
    p("Every file has a home, and the folder names say what kind of thing lives there.")
    table([["Folder", "What is in it"],
           [c("config/"), "the settings: every number the study uses, in two files"],
           [c("data/"), "the inputs: the IEEE street, the cars, the sun and the weather"],
           [c("src/"), "the model itself: the code that simulates an evening"],
           [c("tests/"), "the checks that prove each piece works (V1 to V9 and more)"],
           [c("tools/"), "helpers: running many experiments at once, the Raspberry Pi, the "
            "SINCAL cross-check"],
           [c("team/"), "each teammate's starting file"],
           [c("results/"), "everything the runs produced: numbers and figures"],
           [c("notes/"), "written findings: the audit, the 28 design changes, each check's "
            "result"],
           [c("docs/"), "the three guides, and the rules teammates' code must follow"],
           [c("pi_package/"), "what goes on the Raspberry Pi"],
           [c("models/") + ", " + c("logs/"), "SINCAL projects; logs from long runs"]],
          [0.24, 0.76])
    callout("<font name='Cal-B'>If you only open five files:</font> "
            + c("notes/AUDIT.md") + " (every plan commitment checked, with the results and "
            "what is left), " + c("config/study.json") + " (all the settings), "
            + c("src/sweep.py") + " (one simulated evening, the heart of the model), "
            + c("src/stages.py") + " (runs the experiments) and "
            + c("results/stages/summary.txt") + " (the main results as numbers).")

    # ---- 2
    together(lambda: h1("2. How the files work together"),
             lambda: p("Most of the code exists to run one simulated evening, and most of the "
                       "rest runs that evening many times or checks it. Figure 1 shows how "
                       "the pieces connect."),
             lambda: figure(fig, "Figure 1. The settings and inputs feed one simulated "
                            "evening in sweep.py, which uses the files in red and plugs in the "
                            "three teammates' parts. Experiments run it thousands of times, "
                            "the tests check each piece, and the Pi path carries the same "
                            "evening over MQTT."))
    h2("One evening, file by file")
    p("When you run an evening, this is what happens and which file does it:")
    numbered([c("sweep.py") + " reads the settings from " + c("config/study.json") + ", and "
              + c("feeder_csv.py") + " and " + c("solver.py") + " build the street in "
              "OpenDSS.",
              c("ev_sessions.py") + " loads the cars for that seed from " +
              c("data/sessions/") + ": who plugs in, when, and how much energy they want.",
              "Every 5 minutes, the street is set to its true state: house demand, solar, "
              "and the battery's response (" + c("battery.py") + ").",
              "The meter readings go through Hoang's comms link (" + c("telemetry.py") +
              "), which delays, drops or freezes them and scores how far they can be trusted.",
              c("envelope.py") + " finds the highest safe charging limit from what arrived, "
              "asking " + c("network_state.py") + " whether each try breaks a limit.",
              c("controllers.py") + " turns that into the limit sent (A, B or C), which goes "
              "back down the link to the charge points (" + c("edge.py") + ").",
              "The chargers draw power, the true street is solved again, and " +
              c("network_state.py") + " records any limit that broke.",
              "After 72 steps, " + c("sweep.py") + " returns one result: the energy "
              "delivered, the steps with a violation, the mean trust, and so on."])

    # ---- 3
    h1("3. Which file do I open when...")
    table([["I want to", "Open or run"],
           ["change a setting (the time window, limits, margins, timeouts)",
            c("config/study.json")],
           ["see the final results", c("results/stages/summary.txt") + " and " +
            c("stage_S1.png") + " (main case); " + c("results/stress_s2/") + " (stress)"],
           ["run one evening and watch it step by step",
            cw("py src/sweep.py --controller B --latency 60 --loss 0.1 --seed 7 --trace")],
           ["redraw the result figures", cw("py src/plot_stages.py")],
           ["check a teammate's code", cw("py tests/test_node_acceptance.py --team hoang")],
           ["run an evening with the Raspberry Pi",
            cw("py tools/pi_session.py --pi <user>@<Pi address>")],
           ["... with everyone's parts and the battery on the Pi",
            cw("py tools/pi_session.py --pi <user>@<Pi address> --team all --battery-on-pi")],
           ["hand the whole project to a teammate", cw("py tools/make_handover.py")],
           ["prove a change did not alter any result",
            cw("py tests/golden_runs.py --check --flag on")],
           ["find out why a design decision was made", c("notes/plan_amendments.md")],
           ["see what is left to do", c("notes/AUDIT.md") + ", last section"],
           ["see the rules teammates' code must follow", c("docs/INTERFACES.md")]],
          [0.42, 0.58], size=9.4)

    # ---- 4
    together(lambda: h1("4. The settings (config/)"), lambda: card(
        "config/study.json", "SETTINGS", "Every number the study depends on, in one file, so "
        "nothing is hidden in the code. Change a number here, never in the code, then run the "
        "golden runs to see what it moved. Many entries have a " + c("_note") + " beside them "
        "saying where the number came from. The main sections:"), lambda: table([
           ["Section", "What it sets"],
           [c("cases"), "the two network set-ups: " + c("benchmark") + " (the published IEEE "
            "case, 800 kVA, used only by V1; never change it) and " + c("study") + " (150 kVA "
            "transformer, 1.00 pu source, 22 EV charge points, demand case s1, stress case "
            "s2)"],
           [c("network"), "the IEEE European LV feeder: 906 buses, 55 houses"],
           [c("study_window"), "16:00 to 22:00, a control step every 5 minutes (72 steps), "
            "meter readings every 30 seconds"],
           [c("constraints"), "the five limits: voltage 216.2 to 253 V, cable current, "
            "transformer loading 100%, transformer hot spot, voltage unbalance 2%"],
           [c("controllers"), "the names of A, B and C, as in Table 2 of the plan"],
           [c("envelope"), "the safe-limit search: 0 to 7.2 kW per car, to within 0.1 kW, "
            "with margins that grow with the age of the data"],
           [c("controller_settings"), "the 1.4 kW fallback, the 15-minute timeouts, the trust "
            "formula, setpoint schedules on"],
           [c("sweep"), "the delays (0 to 600 s) and loss levels (0 to 40%) of stage S1"],
           [c("sincal"), "settings for building the SINCAL copy of the street"]],
          [0.27, 0.73], size=9.2))
    card("config/cable_ratings.json", "SETTINGS", "The current rating of each cable type, and "
         "the transformer's thermal data for the hot-spot model. The IEEE package gives no "
         "cable ratings, so these were estimated from the conductor sizes and are marked "
         "provisional. Checking them against AS/NZS 3008.1.1 is still on your list, and it "
         "matters: cable current is one of the two limits that bind most often.")

    # ---- 5
    h1("5. The input data (data/)")
    card("data/feeder/", "INPUT", "The official IEEE European LV Test Feeder package, "
         "unmodified: the line and load tables (" + c("European_LV_CSV/") + "), the published "
         "solutions that V1 compares against (" + c("Solutions/") + "), and the IEEE's "
         "description of the feeder.")
    card("data/sessions/", "INPUT", "The charging sessions: which car plugs in, when, and how "
         "much energy it wants. One file per seed (7 to 19) and demand case, made once and "
         "frozen, so every run at a seed sees exactly the same cars. The name tells you which: "
         + c("seed_7_n22_s1.json") + " is seed 7, 22 charge points, main case; " + c("_s2") +
         " is the stress case. Files without " + c("s1") + " or " + c("s2") + ", and the " +
         c("_standin") + " ones, belong to earlier scenarios and are kept so old results can "
         "be regenerated.")
    card("data/vista/", "INPUT", "The VISTA 2024-25 travel survey (open data from Transport "
         "Victoria), and the arrival times and energy needs worked out from it ("
         + c("ev_sessions_empirical.csv") + ", " + c("ev_sessions_summary.json") + ").")
    card("data/pv_profile.csv", "INPUT", "Rooftop solar output for every minute of the day, "
         "from a clear-sky model for Melbourne with one cloud passing in the afternoon.")
    card("data/ambient.csv, data/weather/", "INPUT", "The outdoor temperature for every "
         "minute, from Bureau of Meteorology observations, for the transformer's hot-spot "
         "model. " + c("weather/") + " holds the raw BoM download it was made from.")
    card("data/scenario_provenance.json", "INPUT", "Where the solar and temperature data came "
         "from and how they were made, so the inputs can be traced.")

    # ---- 6
    h1("6. The model (src/)")
    p("These are the files that simulate the street. The ones marked "
      "<font name='Cal-B' color='#C8102E'>STAND-IN</font> are placeholders for your "
      "teammates' parts; everything else is yours.")
    h2("The heart of one evening")
    card("sweep.py", "CORE", "Runs one simulated evening, 16:00 to 22:00, for one controller "
         "and one comms condition (a delay and a loss rate), following the steps in Section 2. "
         "It returns one result: the energy delivered, the steps that broke a limit, the mean "
         "trust and more. It also finds controller A's fixed limit for each seed (" +
         c("calibrate_static") + ": the largest fixed limit that never breaks anything all "
         "evening). Everything else in " + c("src/") + " exists to serve this file.",
         "py src/sweep.py --controller B --latency 60 --loss 0.1 --seed 7")
    card("envelope.py", "CORE", "The twin's main calculation: the highest charging power "
         "every connected car could draw right now without breaking a limit (the "
         "\"envelope\"). It tries a value, solves the street, asks " + c("network_state.py") +
         " whether anything broke, and halves the range each time (a bisection) until it is "
         "within 0.1 kW. It also picks which 22 houses have an EV charger. V3 and V4 check it.")
    card("network_state.py", "CORE", "Turns a solved power flow into a pass or a fail. It "
         "checks the five limits (voltage, cable current, transformer loading, transformer "
         "hot-spot temperature, voltage unbalance), says which one is closest to breaking, "
         "and carries the transformer's temperature from one step to the next (IEC 60076-7).")
    card("solver.py", "CORE", "The power-flow engine behind one simple interface: set the "
         "loads, solve, read the voltages and currents. It runs the street in OpenDSS, which "
         "is free and has no size limit. A SINCAL version is also here for cross-checks, but "
         "the laptop's SINCAL licence stops at 50 nodes, so the full street can't run in it.")
    card("feeder_csv.py", "CORE", "Reads the IEEE feeder package into Python and checks it "
         "hard before anything uses it: units, bus references, every line and load. Run on "
         "its own, it writes the checks to " + c("notes/feeder_validation.md") + ".",
         "py src/feeder_csv.py")
    card("controllers.py", "CORE", "The three controllers the study compares, named as in "
         "Table 2 of the plan. A: one fixed limit all evening, ignoring the data. B: slides "
         "between the envelope and 1.4 kW depending on how far the data can be trusted. C: "
         "the full envelope while the data is fresh, then straight back to the fixed limit "
         "once the 15-minute timeout passes, as the Australian trials do.")
    h2("The cars")
    card("ev_sessions.py", "CORE", "Decides which cars plug in, when, and how much energy "
         "they want, then freezes the result in " + c("data/sessions/") + ". It also follows "
         "each car through the evening: energy delivered so far, and when it is full. The two "
         "demand cases are made here: s1, where a car plugs in on about a third of evenings "
         "(the main case), and s2, where it plugs in on 70% (the stress case).")
    card("vista_sessions.py", "DATA PREPARATION", "Builds the car data from the VISTA travel "
         "survey: when each driver last got home, and how far they drove that day, turned "
         "into kWh (0.17 kWh per km, 90% charger efficiency, at most 60 kWh). Writes "
         + c("data/vista/") + ".")
    h2("Your teammates' parts")
    card("telemetry.py", "STAND-IN FOR HOANG", "What the twin actually knows, as opposed to "
         "what is true. Meter readings are sent every 30 seconds and get delayed, dropped or "
         "frozen on the way, in simulated time, and a trust score falls from 1 to 0 as the "
         "data gets older. The downlink is here too: the limits sent back can also arrive "
         "late or not at all. Hoang's code replaces it.")
    card("edge.py", "STAND-IN FOR LOMITHA", "The charge points and their controller. It "
         "applies the limit to each of the 22 chargers, picks the right schedule entry when "
         "new limits stop arriving, falls back to 1.4 kW when everything is too old, and "
         "reports what each car drew. The Pi runs this same class. Lomitha's code replaces "
         "it.")
    card("battery.py", "STAND-IN FOR GIA", "A 100 kWh, 50 kVA battery in the middle of the "
         "street (bus 686), with the volt-var and volt-watt response AS/NZS 4777.2 asks for "
         "and a state-of-charge model with losses. Gia's code replaces it.")
    card("plugins.py", "INTEGRATION", "Swaps a teammate's class in by name, so nobody edits "
         "anyone else's code. This is what makes " + c("--team hoang") + " (or " + c("gia") +
         ", " + c("lomitha") + ", " + c("all") + ") work on the tests, the Pi runs and the "
         "experiments.")
    h2("Talking to the Raspberry Pi")
    card("messages.py", "SHARED", "The message contract: every message between the laptop and "
         "the Pi, with its fields, units and a check, now at version 2, including the two "
         "battery messages used when the battery runs on the Pi. The laptop and the Pi must "
         "use the identical file, which is why it is copied into the Pi package and nobody "
         "re-types it.")
    card("mqtt_edge.py", "PI LINK", "The MQTT layer, in two pairs. " + c("PiNode") + " runs "
         "on the Pi and wraps the charge-point controller; " + c("MqttEdge") + " runs in the "
         "twin and behaves exactly like the in-process edge, so " + c("sweep.py") + " cannot "
         "tell whether the chargers are simulated or on the Pi. " + c("BatteryNode") + " and "
         + c("RemoteBattery") + " do the same for the battery. Each part ignores messages "
         "that are not addressed to it, which the laptop's broker sometimes hands out.")
    h2("Running the experiments")
    card("stages.py", "YOU RUN THIS", "Runs the experiments as the plan's Table 9 defines "
         "them: S1 (7 delays by 6 loss levels, controllers A, B and C), S2 (data frozen for "
         "0, 2, 5 or 8 minutes), S3 (the battery switched off) and S1H (the six cells where "
         "schedules matter most). One seed per run; the results go to " +
         c("results/stages/") + ", and " + c("--summarise") + " turns them into " +
         c("summary.txt") + ". S4 is not built yet: it needs decisions from Gia.",
         ["py src/stages.py --stage S1 --seed 7", "py src/stages.py --summarise"])
    card("timeout_sensitivity.py", "EXTRA ANALYSIS", "Tests how much the answer depends on "
         "the 15-minute timeout, by rerunning with other timeouts on the seven congested "
         "seeds. Results and a figure in " + c("results/timeout_sensitivity/") + ".",
         "py src/timeout_sensitivity.py --all")
    card("refine_crossover.py", "EARLIER WORK", "From the first crossover study in late "
         "September: it refined the grid around the break-even point. " + c("stages.py") +
         " replaced it, and its results are in " + c("results/superseded/") + ".")
    h2("Figures")
    card("plot_stages.py", "YOU RUN THIS", "Draws the result figures from a results folder: "
         + c("stage_S1.png") + " (where B and C beat the fixed limit, across delay and loss), "
         + c("stage_S2.png") + " (frozen data) and " + c("stage_S3.png") + " (battery on "
         "against off). It reads " + c("results/stages/") + " unless you give it another "
         "folder.", ["py src/plot_stages.py", "py src/plot_stages.py results/stress_s2"])
    card("plot_crossover.py, plot_safe_comparison.py, plot_trust_comparison.py",
         "EARLIER WORK", "Figures from the first crossover and trust-formula experiments. "
         "The results they read have been superseded, so they are not used for the report.")
    h2("Data preparation and SINCAL")
    card("make_scenario_data.py", "DATA PREPARATION", "Made " + c("data/pv_profile.csv") +
         " (solar) and " + c("data/ambient.csv") + " (temperature). It has already run; rerun "
         "it only if the scenario changes.", "py src/make_scenario_data.py")
    card("build_sincal_model.py", "SINCAL", "Writes the street into a SINCAL project by "
         "filling SINCAL's own database directly, because 906 buses is too many to draw. Used "
         "for the SINCAL cross-check.")
    card("inspect_sincal_schema.py", "SINCAL", "Read out the layout of SINCAL's database so "
         + c("build_sincal_model.py") + " could be written. Its output is "
         + c("notes/sincal_schema.md") + ".")

    # ---- 7
    h1("7. The checks (tests/)")
    p("The V checks each test a piece of the model against an answer that does not come from "
      "the simulator itself. They all pass at the moment: V2, V5, V6 and V7 against the "
      "stand-ins, until the teammates' code arrives.")
    card("v1_benchmark.py", "V1", "The street model against the IEEE's published voltages: "
         "the worst node is 0.0002% out, against a limit of 0.5%. Writes "
         + c("notes/v1_result.md") + ".", "py tests/v1_benchmark.py")
    card("v3_envelope.py", "V3", "The safe-limit search finds the true answer: at 30 random "
         "points, compared with a slow step-by-step search, it is always within 0.1 kW.",
         "py tests/v3_envelope.py")
    card("v4_tightness.py", "V4", "The safe limits are safe, and as large as they can be: "
         "applying one breaks nothing, and one step more would break something.",
         "py tests/v4_tightness.py")
    card("v8_known_answer.py", "V8", "The whole chain against an answer worked out by hand: "
         "every house charging at full power, and simple arithmetic predicts the main cable "
         "first overloads at 16:40. The simulation agrees.", "py tests/v8_known_answer.py")
    card("v9_reproducibility.py", "V9", "The same runs give identical logs a week later. It "
         "passed on 11 October. " + c("--record") + " stores a new baseline, " + c("--check")
         + " compares against it a week on.", "py tests/v9_reproducibility.py --check")
    card("test_node_acceptance.py", "V2, V5, V6, V7", "The teammates' hand-over tests: V2 "
         "and V7 for Gia's battery (the AS/NZS 4777.2 response, energy balance), V5 and V6 "
         "for Hoang's comms link (the delay and loss asked for, sensible trust). They run on "
         "the stand-ins, or on a teammate's file with " + c("--team") + ".",
         "py tests/test_node_acceptance.py --team hoang")
    card("test_mqtt_equivalence.py", "MQTT", "Runs one evening in process and again through "
         "a real MQTT broker on this laptop, and requires every step to match. It is what "
         "makes the simulated results valid for the hardware.",
         "py tests/test_mqtt_equivalence.py")
    card("test_setpoint_schedule.py", "SCHEDULES", "Checks that the setpoint-schedule fix "
         "(amendment 25) works as designed: the right entry at each step, the right margins, "
         "and nothing else disturbed.", "py tests/test_setpoint_schedule.py")
    card("test_lomitha_adapter.py", "LOMITHA", "Checks Lomitha's controller as integrated. "
         "With his pilot rules and the car's taper switched off it must give the stand-in's "
         "answer exactly (it does, on five evenings); then it shows what the real rules "
         "change: 0.5 to 2.4% less energy, no extra violations.",
         "py tests/test_lomitha_adapter.py")
    card("golden_runs.py", "SAFETY NET", "Reference runs stored in " + c("results/golden/") +
         ". After any code change, " + c("--check") + " reruns them and compares every field "
         "step by step, which proves the change did not alter a result.",
         ["py tests/golden_runs.py --check --flag off",
          "py tests/golden_runs.py --check --flag on"])
    card("check_model.py", "SINCAL", "Checks a SINCAL database for broken references before "
         "SINCAL opens it.")
    card("solve_timing.py", "SPEED", "Measures the seconds per power flow. It decided early "
         "on whether stage S1 could run on this laptop at all.")

    # ---- 8
    h1("8. The helpers (tools/)")
    h2("For the Raspberry Pi")
    card("pi_session.py", "YOU RUN THIS", "One command for a whole run with the Pi. It "
         "rebuilds the Pi package, copies it over SSH, starts the broker here and the Pi's "
         "program there (through an SSH tunnel, so nothing needs allowing through the "
         "firewall), runs the evening, compares it with the simulator and stops the Pi's "
         "program. " + c("--find") + " finds the Pi on a hotspot; " + c("--local") + " runs "
         "everything on the laptop alone; " + c("--battery-on-pi") + " puts the battery on "
         "the Pi too.",
         ["py tools/pi_session.py --find",
          "py tools/pi_session.py --pi <user>@<Pi address> --team all --battery-on-pi"])
    card("run_with_pi.py", "LAPTOP SIDE", "The laptop side of a run with the Pi, which "
         + c("pi_session.py") + " starts for you. It waits for the Pi to report in, runs an "
         "evening over MQTT showing every step, and with " + c("--compare") + " checks the "
         "Pi gave the simulator's answer (EQUIVALENT), saying what differs if not. Each run "
         "is saved in " + c("results/hil/") + ".")
    card("pi/run_pi_node.py", "THE PI SIDE", "The program that runs on the Pi: it loads the "
         "cars for the seed, starts the charge-point controller (Lomitha's with " +
         c("--team lomitha") + ") and answers the laptop; with " + c("--battery") + " it runs "
         "the battery too (Gia's with " + c("--team gia") + "). It waits until the broker has "
         "really accepted it before saying \"connected\", and stops by itself after the "
         "evening when started by " + c("pi_session.py") + ".")
    card("broker.py", "PI NETWORK", "An MQTT broker on the laptop, for when it is not running "
         "on the Pi. It prints the laptop's address to give the Pi.", "py tools/broker.py")
    card("make_pi_package.py", "PI PACKAGE", "Builds " + c("pi_package/") + " and " +
         c("pi_package.zip") + ": the message contract, the charge-point controller (the "
         "stand-in and Lomitha's code), the battery (the stand-in and Gia's file), the MQTT "
         "wrapper, the runner, the cars for every seed, and a copy of the MQTT library, so "
         "the Pi needs nothing installed. " + c("pi_session.py") + " rebuilds it on every "
         "run.", "py tools/make_pi_package.py")
    card("make_handover.py", "HANDOVER", "Builds " + c("EEE40016_for_Gia.zip") + ": the "
         "whole project for a teammate to run with a Pi, with " + c("README_FIRST.md") +
         " on top. Leaves out logs, caches and superseded results.",
         "py tools/make_handover.py")
    h2("For the experiments")
    card("run_parallel.py", "YOU RUN THIS", "Runs many " + c("stages.py") + " processes at "
         "once, 12 by default, each with its own log: for example all 13 seeds of S1. The "
         "final results were made with it.",
         'py tools/run_parallel.py --arm "team:S1:results/stages_team:--team all"')
    card("hold_awake.py", "HELPER", "Stops Windows going to sleep while experiments are "
         "running, then lets go when they finish.", "py tools/hold_awake.py")
    card("calibrate_preview.py", "HELPER", "A quick look at controller A's fixed limit for "
         "each seed in each demand case: a seed at 7.2 kW has no congestion, so live control "
         "has nothing to win there.")
    card("demand_scenarios.py", "HELPER", "The screening that picked the demand cases "
         "(amendment 27): how much load unmanaged charging puts on the street, without any "
         "network model. Explained in " + c("notes/demand_scenarios.md") + ".")
    card("compare_paired.py, compare_sensitivity.py", "HELPER", "Scored the setpoint-schedule "
         "fix: the same runs with schedules off and on, against criteria fixed before they "
         "ran. Their reports are the " + c("comparison.md") + " files in " +
         c("results/paired_main/") + ", " + c("paired_stress/") + " and " +
         c("sensitivity/") + ".")
    h2("For the SINCAL cross-check")
    card("sincal_subset_check.py", "SINCAL", "SINCAL against OpenDSS on a 47-node cut of the "
         "street, small enough for the laptop's licence. They agree within 0.1%.")
    card("make_avd_package.py, avd_solve.py, avd_compare.py", "SINCAL", "The full-street "
         "check on the uni computers (the AVD), which have the full licence. "
         + c("make_avd_package.py") + " builds " + c("avd_crosscheck.zip") + ", "
         + c("avd_solve.py") + " solves it on the AVD, and " + c("avd_compare.py") +
         " compares the answer with OpenDSS back on the laptop. Still to be done.")
    card("sincal_repoint.py", "SINCAL", "Fixes a copied SINCAL project's link to its own "
         "database, which breaks when a project moves to another computer.")

    # ---- 9
    h1("9. Teammates' files (team/)")
    p("Each teammate's part plugs in here. Hoang's and Gia's files still inherit the "
      "stand-ins, so they work before a line changes, and each replaces the methods with "
      "their own code; Lomitha's own code is already in.")
    card("hoang_link.py", "HOANG", c("HoangLink") + " (the uplink and the trust score) and "
         + c("HoangDownlink") + " (the downlink), still the stand-in. Must pass V5 and V6, "
         "and rules R6 and R7.")
    card("hoang_prototype/", "HOANG", "Hoang's MQTT chat prototype (a publisher, a subscriber "
         "and a Mosquitto setting), with " + c("NOTES.md") + " on how it fits: it is a "
         "connection test, not part of a run. Two small changes, listed in the notes.")
    card("lomitha/", "LOMITHA", "Lomitha's own code: " + c("ev_charge_point_gateway.py") +
         " (one charge point: the limit, the IEC 61851 pilot rules, metering, faults, the "
         "fallback) and " + c("charging_session.py") + " (the car, with a taper above 80%, "
         "and Lomitha's own test runner). Two small changes, marked in the files.")
    card("lomitha_fleet.py", "LOMITHA", c("LomithaFleet") + ", the adapter that runs one of "
         "Lomitha's gateways and cars per charge point, all 22 from one object, and keeps "
         "rules R1 to R5. Runs on the Pi; must give EQUIVALENT.")
    card("gia_battery.py", "GIA", c("GiaBattery") + ", the battery, BMS and EMS, still the "
         "stand-in. Must pass V2 and V7; runs in the twin, or on the Pi with " +
         c("--battery-on-pi") + ".")
    card("README.md", "COMMANDS", "Every command for the integration session, ready to copy "
         "and paste.")
    card("__init__.py", "", "An empty marker that lets Python load the files in this folder "
         "by name. Leave it there.")

    # ---- 10
    h1("10. Results (results/)")
    table([["Folder", "What it holds"],
           [c("stages/"), "the main case (s1 demand): S1, S2, S3 and S1H for each seed, "
            + c("summary.txt") + " and the three figures"],
           [c("stress_s2/"), "the stress case (s2 demand)"],
           [c("paired_main/") + ", " + c("paired_stress/"), "the schedule fix: the same runs "
            "with schedules off, and the comparison"],
           [c("mechanism_standin/"), "the schedule fix tested on the older demand, before "
            "and after"],
           [c("sensitivity/"), "two variations of the schedule fix, and the comparison"],
           [c("timeout_sensitivity/"), "the timeout test: summary and figure"],
           [c("golden/"), "the reference runs for " + c("golden_runs.py")],
           [c("v9/"), "the V9 baseline"],
           [c("hil/"), "runs with the Raspberry Pi; " + c("rehearsal/") + " holds the laptop "
            "rehearsals of 11 October"],
           [c("sincal_subset_check.json"), "the 47-node SINCAL comparison"],
           [c("stages_team/"), "appears after the final runs with everyone's code"],
           [c("superseded/"), "results from before a fault was fixed, or from an old "
            "scenario. Never quote these"]],
          [0.34, 0.66], size=9.2)
    h2("Reading summary.txt")
    p("Each cell is one delay and loss level, and reads like "
      "<font name='Courier'>+6.5 13/13</font>: at that setting, controller B delivered 6.5% "
      "more energy than the fixed limit on average, and all 13 evenings broke no limit. "
      "<font name='Courier'>-1.6 12/13</font> means 1.6% less than the fixed limit, with one "
      "evening of the 13 breaking a limit; an evening that breaks a limit is left out of the "
      "average, as the plan says. The last lines count the runs with a violation and list the "
      "fixed limit found for each seed.")
    together(lambda: h2("What one result holds"),
             lambda: p("Each JSON file holds one record per run. The fields you will use "
                       "most:"), lambda: table([
           ["Field", "Meaning"],
           [c("controller") + ", " + c("latency_s") + ", " + c("loss") + ", " + c("seed"),
            "which run it was"],
           [c("energy_kwh"), "the main measure: EV energy delivered over the evening"],
           [c("demanded_kwh"), "the energy the cars wanted"],
           [c("violations"), "the number of steps that broke at least one limit"],
           [c("violation_types"), "which limits broke, and how often"],
           [c("counted"), "false if any limit broke; such a run does not count"],
           [c("mean_trust"), "the average trust score over the evening"],
           [c("fallbacks"), "the steps where the chargers fell back to 1.4 kW"],
           [c("static_kw") + ", " + c("static_kwh"), "controller A's fixed limit for that "
            "seed, and the energy it delivers"]],
          [0.42, 0.58], size=9.2))

    # ---- 11
    together(lambda: h1("11. Notes and documents"), lambda: h2("notes/"), lambda: table([
           ["File", "What it is"],
           [c("AUDIT.md"), "start here: every commitment in the research plan against the "
            "build, the results, and what is left"],
           [c("plan_amendments.md"), "all 28 design changes and faults found, each with the "
            "reason and the evidence"],
           [c("demand_scenarios.md"), "why s1 is the main case and s2 the stress case"],
           [c("feeder_validation.md"), "the checks on the IEEE feeder package"],
           [c("v1_result.md") + ", " + c("v3_result.md") + ", " + c("v4_result.md") + ", "
            + c("v8_result.md"), "each check's result in detail"],
           [c("first_crossover.md"), "the first, preliminary result; superseded, kept for the "
            "record"],
           [c("sincal_subset_check.md") + ", " + c("sincal_schema.md") + ", "
            + c("importer_open_items.md") + ", " + c("BLOCKER_licence.md"),
            "the SINCAL work: the 47-node check, SINCAL's database layout, importer issues, "
            "and the 50-node licence limit"]],
          [0.42, 0.58], size=9.2))
    together(lambda: h2("docs/"), lambda: table([
           ["File", "What it is"],
           [c("Digital_Twin_Guide.pdf"), "the models, the method and the results, explained"],
           [c("Putting_It_Together.pdf"), "the Raspberry Pi set-up and the network"],
           [c("Your_Files_Explained.pdf"), "this guide"],
           [c("INTERFACES.md"), "the rules teammates' code must follow (R1 to R7), with "
            "example messages"],
           [c("guide/"), "the scripts that build the three PDFs, and " +
            c("render_pages.ps1") + ", which turns PDF pages into pictures for checking"]],
          [0.42, 0.58], size=9.2))

    # ---- 12
    h1("12. Everything else in the project folder")
    table([["File or folder", "What it is"],
           [c("README_FIRST.md"), "the steps for running everything with the Pi, for "
            "Gia; on top of the handover zip"],
           [c("requirements_laptop.txt"), "the Python packages the laptop side needs, one "
            "pip command"],
           [c("README.md"), "the project's front page: status, layout, decisions"],
           [c("EEE40016_for_Gia.zip"), "the handover zip, built by " +
            c("tools/make_handover.py")],
           [c("pi_package/") + ", " + c("pi_package.zip"), "everything that goes on the Pi; "
            "built by " + c("tools/make_pi_package.py")],
           [c("avd_crosscheck.zip"), "the SINCAL check for the uni computers"],
           [c("models/"), "the SINCAL projects; the files starting with ~ are SINCAL's own "
            "backups"],
           [c("logs/"), "the logs from long runs, one per process"],
           [c("LOG/") + ", " + c("Log.db"), "SINCAL's own log files"]],
          [0.42, 0.58], size=9.2)


def main():
    fig = os.path.join(HERE, "figF1_map.png")
    fig_map(fig)
    build(fig)
    doc = bg.GuideDoc(OUT)
    doc.multiBuild(bg.story)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
