# Digital twin node — EEE40016

Munir Aslam (104362241). This folder holds my part of the project: the PSS®SINCAL feeder
model, the COM driver, the network-state calculation, the envelope computation, and the
sweep runner.

## Status, 12 October 2026

Final results are in (main case S1 demand, stress case S2), V9 passed on 11 October, and
the kit for running with the Raspberry Pi is ready and rehearsed. Gia runs the Pi session
from `EEE40016_for_Gia.zip` (built by `py tools/make_handover.py`; start with
`README_FIRST.md`).

- **Three guides.** `docs/Digital_Twin_Guide.pdf` explains the models, the method and the
  results. `docs/Putting_It_Together.pdf` covers the Raspberry Pi set-up, the MQTT network
  and where each teammate's code goes. `docs/Your_Files_Explained.pdf` goes through every
  file in this node: what it does, what it is for, and how to run it.
- **Teammates' code drops in by name.** `--team hoang` (or `gia`, `lomitha`, `all`) runs
  each part on the acceptance tests, on the Pi runs and on the full experiments, without
  editing anyone else's code. Lomitha's own controller is integrated (`team/lomitha/`,
  checked by `tests/test_lomitha_adapter.py`); Hoang's and Gia's are still the stand-ins.
  The commands are in `team/README.md`.
- **One command with the Pi:** `py tools/pi_session.py --pi <user>@<Pi address>` copies the
  package, starts the Pi's side over SSH (an SSH tunnel, so no firewall changes), runs an
  evening and ends with EQUIVALENT when the Pi gave the simulator's answer step for step.
  `--battery-on-pi` runs the battery on the Pi too; `--local` runs it all on the laptop.

## Status, 2 October 2026

**Start with `notes/AUDIT.md`:** every commitment in the research plan, checked against the
build, with evidence, results, and what is still outstanding and whose it is. Every design
change and every fault found is in `notes/plan_amendments.md` (items 1 to 28).

What changed on 1-2 October, and why the stage results need regenerating:

- **Setpoints are now schedules** (amendment 25). A held setpoint used to be applied with a
  margin sized for fresher data than it had by then, which caused most of the live
  controllers' violations at long latency and the 0 s anomaly of amendment 24. The fix was
  chosen by a design panel and checked against golden runs of the old code
  (`tests/golden_runs.py`) and `tests/test_setpoint_schedule.py`. Before/after comparisons
  are in `results/paired_main/`, `results/paired_stress/` and `results/mechanism_standin/`,
  and the sensitivity runs in `results/sensitivity/`.
- **Charging sessions now come from VISTA** (D4, amendment 27). Decided 2 October: the main
  case has each car plugging in on about a third of evenings (the metered Melbourne rate),
  and the stress case is the distributor design day (70%). The transformer stays at 150 kVA.
  Evidence in amendment 27 and `notes/demand_scenarios.md`; the choice is
  `cases.study.plugin_model` in `config/study.json`.
- **The SINCAL importer had three silent faults** (amendment 26), found by a 47-node
  cross-check that fits the laptop's licence (`tools/sincal_subset_check.py`). Fixed; the
  full-feeder check for the uni AVD is packaged in `avd_crosscheck.zip`.

Stage results: `results/stages/` is the main case (S1 demand, schedules on);
`results/stress_s2/` is the stress case. Regenerate with `py tools/run_parallel.py` (arms
listed in its docstring) or `py src/stages.py --stage S1 --seed N` per seed, then
`py src/stages.py --summarise` and `py src/plot_stages.py`. Anything in
`results/superseded/` was produced before a fault was fixed or under a superseded scenario
and must not be quoted.

Validation: V1, V3, V4 and V8 pass; V2, V5, V6 and V7 pass against the stand-ins
(`tests/test_node_acceptance.py`); the MQTT path is equivalent at 60 s/10%, 300 s/10% and
0 s/40%. V9 passed on 11 October, eight days after recording.

## For the rest of the team: how your node plugs in

Read `docs/INTERFACES.md`. The short version: write your logic as a plain Python class with
no MQTT inside, following the stand-in for your node; the sweep imports it directly and
the Raspberry Pi runs the same class behind `src/mqtt_edge.py`.

| File | What it is |
| --- | --- |
| `src/messages.py` | the message contract, shared by every node; copy it verbatim |
| `src/edge.py` | stand-in for Lomitha's charge-point controller |
| `src/telemetry.py` | stand-in for Hoang's injector and trust metric |
| `src/mqtt_edge.py` | the MQTT wrapper (Pi side) and the twin's MQTT edge |
| `tests/test_mqtt_equivalence.py` | proves the MQTT path gives exactly the in-process result |
| `team/` | each teammate's starting file, and `README.md` with the commands |
| `tools/run_with_pi.py`, `tools/broker.py` | the laptop side of a run with the Pi; an MQTT broker on the laptop |
| `pi_package.zip` | everything the Pi needs (`tools/make_pi_package.py` rebuilds it) |

Gia's battery has a stand-in in `src/battery.py`; `docs/INTERFACES.md` gives the interface.
**`messages.py` is now schema 2**: every node must move to the new file together.

## Layout

```
config/study.json     every number the study depends on. Nothing downstream hard-codes them.
data/feeder/          the official IEEE package, unmodified (CSVs, load profiles, solutions)
src/                  the code
tests/                validation items V1, V3, V4, V9
results/              run outputs, one folder per sweep point
logs/                 message and solver logs
notes/                findings worth keeping, including the SINCAL schema dump
```

## Decision log

**28 Sep 2026 — transformer re-rated from 800 kVA to 150 kVA for the study case.**
The published feeder ships an 800 kVA unit. Evening peak with 40% EV penetration reaches
about 169 kW, which is 21% of 800 kVA, so transformer thermal loading could never bind and
the IEC 60076-7 criterion in the validation plan would be inert. At 150 kVA the evening peak
sits just above nameplate and thermal becomes a live constraint, which is what the research
design needs. Percentage impedance stays at 4%, so ohmic series impedance rises with the
smaller rating — correct behaviour for a smaller unit.

**The benchmark case keeps 800 kVA.** Validation item V1 compares against the published IEEE
solution, which was solved with the original transformer. Changing it would make V1
meaningless. So `config/study.json` carries two cases: `benchmark` (800 kVA, no EVs, no
battery, no PV — for V1 only) and `study` (150 kVA — everything else).

## How the model gets built

906 nodes and 905 lines is too many to draw by hand. SINCAL keeps its model in a plain
SQLite database, so the importer writes rows into that database directly and COM is used
only for running and reading results, which is what it is good at.

The schema came out of Lab1's database, a small model SINCAL built and solved itself, so it
is a reliable template. Full dump in `notes/sincal_schema.md`. The shape of it:

- `Element` — one row per device. `Element_ID` is the key, `Type` is the type name as a string.
- A type table per device — `Line`, `Load`, `TwoWindingTransformer` — sharing that `Element_ID`.
- `Terminal` — links `Element_ID` to `Node_ID` with a `TerminalNo`. This is the connectivity.
- `Node` — the buses. `Un` is nominal voltage in kV.
- `Graphic*` — the drawing. Needed for a usable diagram, not for solving.

Units to confirm on the first import: `Load.P` looks like MW, `TwoWindingTransformer.Sn`
like MVA, `Line.l` like km with `r`/`x` in ohm/km. Lab 1 values are consistent with that
but it gets verified against the V1 result before anything else is built on top.

## Validation I own

| | Checks | Passes when |
| --- | --- | --- |
| V1 | the model matches the published feeder | every node voltage within 0.5% — **passed**, worst 0.0002% over 2721 nodes |
| V3 | bisection finds the true envelope | within 0.1 kW of an exhaustive 0.05 kW sweep, 30 random points — **passed**, worst 0.05 kW |
| V4 | envelopes safe and not needlessly conservative | zero violations, envelope maximal on the 0.1 kW grid — **passed** (see amendment 2 on the 1% clause) |
| V8 | the whole chain gives a known answer | 0% EVs clean; 100% EVs violate at the hand-predicted step — **passed**, predicted and simulated both step 16, 17:25 |
| V9 | results can be regenerated | three sweep points re-run a week later give identical logs |

V1 has a proper reference: the official package ships solved node voltages at minute 566
("on peak") from both OpenDSS and GridLAB-D, in `data/feeder/Solutions/`.

## Runtime — measured, and not a problem

Measured 28 Sep 2026 over 300 solves of the full 906-node feeder with the loads varied
between solves (`tests/solve_timing.py`):

| | |
| --- | --- |
| median | 0.0002 s |
| p95 | 0.0006 s |
| max | 0.0014 s |

Stage S1 is about 27,000 solves, which comes to well under a minute even sizing on the p95.
The plan's runtime mitigation sequence is not going to be needed. OpenDSS warm-starts from
the previous solution, which is exactly the access pattern a sweep has.

This removes the biggest delivery risk in the schedule.

## Engine

**OpenDSS is the engine.** SINCAL on this machine runs the free Xplore licence, capped at
50 nodes for simulation, and no fuller licence is available. The feeder has 906. See
`notes/BLOCKER_licence.md`.

`src/solver.py` keeps both behind one interface, so the twin never talks to an engine
directly. The SINCAL backend still works and is kept for small models and for the record;
the SINCAL importer still builds a correct project that SINCAL loads without complaint.

Choosing OpenDSS also makes V1 an exact check rather than a cross-tool comparison, because
the published reference solution is itself an OpenDSS result.

## Order of work

1. ~~Import the feeder and converge a power flow~~ done
2. ~~Pass V1 against the published snapshot at minute 566~~ done, worst error 0.0002%
3. ~~Time the solve~~ done, see above
4. ~~Re-rate to 150 kVA and add the 22 EV charge points~~ done
5. ~~Network-state calculation: voltage, cable current, transformer loading, hot-spot, unbalance~~ done
6. ~~Envelope by bisection, V3~~ done, worst disagreement 0.05 kW. V4 (tightness) still to do
7. Sweep runner and results store, then S1
8. PV, battery and the warning-day scenario for S3 and S4

## Sources

- IEEE PES Test Feeder Working Group, European Low Voltage Test Feeder — `data/feeder/`
- Siemens, PSS®SINCAL Automation Manual — for the COM interface
- SA Power Networks, "Flexible exports for solar PV: final trial report," v1.3, Oct 2023 (ARENA)
