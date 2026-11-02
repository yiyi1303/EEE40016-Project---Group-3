# EEE40016: everything for the Raspberry Pi session

For Gia, from Munir, 12 October 2026. This folder is the whole digital twin project: the
model of the street, the experiments and results, every teammate's part as it stands, and
the tools that run an evening with the Raspberry Pi. You run the session on your laptop
with your Pi. Commands are typed in a terminal opened in this folder (on Windows,
PowerShell or Windows Terminal; on a Mac, type `python3` wherever this says `py`).

## Where each part stands

| Part | Whose | Where | State |
| --- | --- | --- | --- |
| The twin: street model, safe limits, controllers A, B, C | Munir | `src/` | done and checked (V1, V3, V4, V8, V9) |
| Charge-point controller, all 22 chargers | Lomitha | `team/lomitha/`, connected by `team/lomitha_fleet.py` | Lomitha's own code, integrated and tested; runs on the Pi |
| Comms injector and trust score | Hoang | `team/hoang_link.py`; MQTT chat prototype in `team/hoang_prototype/` | still the stand-in; prototype included |
| Battery, BMS and EMS | Gia | `team/gia_battery.py` | still the stand-in; can now run on your Pi |

## 1. Set up your laptop (once)

Install Python 3.10 or newer from python.org (on Windows, tick "Add python.exe to PATH").
Then, in a terminal in this folder:

```
py -m pip install -r requirements_laptop.txt
```

Check it works (it should end with `4 of 4 passed`):

```
py tests/test_node_acceptance.py
```

## 2. Try the whole thing on your laptop first, no Pi

```
py tools/pi_session.py --local --team all --battery-on-pi --static-kw 2.5
```

This runs one evening (16:00 to 22:00 in 5-minute steps, about a minute in all) with the
Pi's program running as a separate program on your laptop. You see a line per step for
the laptop and one starting `Pi |` for the "Pi". It ends with `EQUIVALENT`, which means
the messaging path gave exactly the simulator's answer at every step. If you get that,
your laptop side is right.

## 3. Set up the Pi (once)

- Switch SSH on: on the Pi, `sudo raspi-config`, then Interface Options, then SSH. (Or tick
  it in Raspberry Pi Imager when making the SD card.)
- Put the Pi and your laptop on the same Wi-Fi. A phone hotspot is best: university Wi-Fi
  keeps devices from reaching each other. From the Pi's terminal:
  `sudo nmcli dev wifi connect "<hotspot name>" password "<password>"`
- Nothing to install. The Pi needs only the Python 3 that comes with Raspberry Pi OS; the
  laptop copies everything else across on each run.

## 4. Run an evening with the Pi

Find the Pi's address from the laptop (only on your own hotspot; it tries every address
on the network):

```
py tools/pi_session.py --find
```

A Pi shows up as Debian or Raspbian. Then, with your Pi's user name and that address:

```
py tools/pi_session.py --pi <user>@<Pi address> --static-kw 2.5
```

Type the Pi's password when asked (twice: once to copy, once to start). The laptop copies
the files to the Pi, starts the broker on the laptop and the Pi's program over SSH, runs
the evening and checks it: `EQUIVALENT` again means it worked. Nothing needs allowing
through the laptop's firewall: the Pi reaches the laptop through the SSH connection.

Then the same with every teammate's part, and the battery on the Pi:

```
py tools/pi_session.py --pi <user>@<Pi address> --team all --battery-on-pi --static-kw 2.5
```

The Pi now prints a battery line each step as well. `--static-kw 2.5` skips a minute of
calibration (2.5 kW is the fixed limit for evening 7, the default); leave it out to have it
worked out. `--no-copy` skips copying when nothing has changed (one password fewer).

For the demo, these two show live control working, then struggling:

```
py tools/pi_session.py --pi <user>@<Pi address> --team all --battery-on-pi --controller B --latency 60 --loss 0.1
py tools/pi_session.py --pi <user>@<Pi address> --team all --battery-on-pi --controller C --latency 300 --loss 0.2 --no-copy
```

If the Pi will not connect on the day, step 2's `--local` command gives the same output on
the laptop alone.

## 5. Your battery

Your battery runs on the Pi with `--battery-on-pi`: the Pi program wraps it, and the twin
calls it over MQTT each step (a reset at the start of the evening, then up to six
`response()` calls and one `commit()` per step). Two ways to put your own code in:

- **Simplest:** write your logic into `team/gia_battery.py`. It has three methods with
  their rules written above each: `response()` gives P and Q at a voltage and must change
  nothing, `commit()` runs for a while and is the only place the state of charge changes,
  and `status()`. Check it with `py tests/test_node_acceptance.py --team gia` (V2: volt-var
  and volt-watt follow AS/NZS 4777.2; V7: energy balances), then run it on the Pi with
  `--team gia --battery-on-pi` (or `--team all`). Edit it on the laptop: the laptop copies
  it to the Pi on each run.
- **Your own program on the Pi:** if your battery ends up as its own program (your own
  MQTT code, or hardware), it only has to answer the twin's battery messages. The format is
  in `docs/INTERFACES.md`, under "The battery on the Pi", and the fields are
  `BatteryRequest` and `BatteryReply` in `src/messages.py`.

Either way, the stand-in battery in the package is the backup: it works as it is.

Still waiting on your decisions, for stage S4 (the warning day): when the warning arrives
and what reserve the EMS keeps, which loads are critical, when the outage happens and
whether the street islands, and how survival hours are measured.

## 6. The others' parts

- **Lomitha's** controller is his own code in `team/lomitha/`: one gateway per charger with
  the IEC 61851 rules (6 A minimum, 0.6 A steps, always rounded down), and his car model
  with a taper above 80%. `team/lomitha_fleet.py` connects it to the twin, keeping the
  interface rules (R1 to R5 in `docs/INTERFACES.md`). Two small changes were needed in his
  files, each marked "Changed for integration" where it is: validity intervals that end at
  exactly `valid_until`, and numpy made optional so the Pi needs nothing installed. Check
  it with `py tests/test_lomitha_adapter.py`: PASS, then a table showing his charging rules
  deliver 0.5 to 2.4% less energy than the stand-in, with no extra violations.
- **Hoang's** comms node (the delay and loss injector and the trust score) is still the
  stand-in, `team/hoang_link.py`; his check is `py tests/test_node_acceptance.py --team
  hoang` (V5, V6). His MQTT chat prototype is in `team/hoang_prototype/`, with notes on how
  it fits; it doubles as a quick test that two devices can reach each other.

## 7. The final results with everyone's code

When all three parts pass their checks, rerun the experiments with them. It took about
three hours on Munir's laptop, most of it S1. Keep the laptop plugged in; on Windows, run
`py tools/hold_awake.py` in a second window so it does not go to sleep.

```
py tools/run_parallel.py --arm "team:S1:results/stages_team:--team all"
py tools/run_parallel.py --arm "team:S2:results/stages_team:--team all"
py tools/run_parallel.py --arm "team:S3:results/stages_team:--team all"
py src/stages.py --summarise --team all
py src/plot_stages.py results/stages_team
```

The results go to `results/stages_team/`, next to the stand-in results in
`results/stages/`, never over them. The experiments run the battery inside the twin
whichever way the demo ran it: the same class gives the same answers, much faster.

## 8. If something goes wrong

| What you see | What to do |
| --- | --- |
| ssh or scp: "Connection refused" | SSH is off on the Pi: step 3 |
| "Connection timed out" or "cannot find" the Pi | not on the same hotspot, or a wrong address: `--find` again |
| "Permission denied" | the Pi's user name or password |
| "REMOTE HOST IDENTIFICATION HAS CHANGED" | the Pi was set up again: `ssh-keygen -R <Pi address>`, then run again |
| "already using port 1883" | an old run is still open: close it |
| NOT EQUIVALENT | it lists what differs; send Munir the saved file in `results/hil/` |
| pip cannot find a version | step 1's note in `requirements_laptop.txt` |

More in `docs/Putting_It_Together.pdf`, section 5.

## What else is in here

- `docs/`: three guides. `Digital_Twin_Guide.pdf` (the model and results),
  `Putting_It_Together.pdf` (the Pi and the network, longer than this page) and
  `Your_Files_Explained.pdf` (every file); `INTERFACES.md` has the rules each part follows.
- `team/README.md`: the commands again, ready to copy.
- `notes/AUDIT.md`: every commitment in the research plan, checked, with what is left.
- `results/`: everything the runs produced; `results/hil/` collects the runs with the Pi.
- `models/` and `avd_crosscheck.zip`: the SINCAL cross-check, for the uni computers.

Left out on purpose: run logs, Python caches, and old results from before faults were
fixed (Munir has them).
