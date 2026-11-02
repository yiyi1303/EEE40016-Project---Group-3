# Audit: the research plan against the build

Checked 1 October 2026 and updated 2 October, item by item, against the submitted plan (`Smart Power Grids Research
Plan final (150 kVA).docx`). Every row gives the evidence, so any of it can be re-checked.

**Status key:** ✅ done and validated · 🟡 done, provisional or with a stated limit · ❌ not
done · ⛔ blocked on someone else

## Verdict

Everything the **twin** owns is built and validated, and the study runs end to end with every
variable and every base-case element the plan specifies. Stages S1, S2 and S3 run in full.
What remains is either **other people's nodes** (where working stand-ins hold the place and
acceptance tests define the hand-over), **S4**, which can't be built until the team makes
scenario decisions, and **the things only you can do**, listed at the end. The results
below are the final runs of 2 October, on the decided demand (amendment 27) with setpoint
schedules (amendment 25).

## Results of the final run

The final runs of 2 October: setpoint schedules on (amendment 25), the decided demand
(amendment 27), 13 seeds, every element of Table 7 in the model. Tables are in
`results/stages/summary.txt` (main case) and `results/stress_s2/summary.txt` (stress case);
figures are `stage_S1.png`, `stage_S2.png` and `stage_S3.png` in `results/stages/`, and
`stage_S1.png` in `results/stress_s2/`.

**S1, main case (about a third of EVs plug in each evening).** Six of the 13 seeds never
congest. Their static limit is the full 7.2 kW, so live control has nothing to win on them,
and they pull every average towards zero. On the other seven the static limit is 2.5–6.4 kW.

- B, trust-weighted, beats the static limit by 15% at 0 s with no loss, and by 5–9% from 5 to
  60 s at 1% loss or less. It breaks even between 60 and 120 s at low loss and at about 5 s
  once loss reaches 20%, and it is behind everywhere at 40% loss. It broke a limit in 9 of
  546 runs, all of them voltage unbalance.
- C, binary fallback, delivers a little more than B on good links (10–15% ahead up to 60 s)
  but broke a limit in 82 of 546 runs. From 300 s it is unsafe in up to 7 of 13 seeds per
  cell.
- A, the static limit, broke nothing, by construction.

**S1, stress case (the distributor design day, 70% plug in).** Twelve of 13 seeds congest,
most with static limits of 2.9–4.7 kW. B is 21% ahead at 0 s, 10–17% ahead from 5 to 60 s at
10% loss or less, still ahead at 300 s with 5% loss or less, and behind at 600 s and at 40%
loss. B broke a limit in 20 of 546 runs and C in 140 of 546; beyond 60 s, C's cells typically
have only 7 or 8 of 13 seeds safe.

On both demand cases trust-weighting gives up a little energy to binary fallback on good
links and breaks limits seven to nine times less often. That is the plan's central
comparison.

**S2, stale data (main case).** A 5- or 8-minute hold of frozen values with fresh timestamps
left B safe in only 7 or 8 of 13 seeds at the good link (5 s, 1%) and 10 of 13 at 60 s and
10%; C fell to 6 or 7 of 13. A 2-minute hold was mostly tolerated (B 12 of 13). At 300 s and
20% loss B was unaffected, because its trust was already low. Age-based trust cannot see
frozen data that carries fresh timestamps, which bears out the plan's hypothesis that stale
data does more damage than packet loss.

**S3, the battery (main case).** Without the battery the static limit falls on 3 of 13 seeds
(seed 8 from 7.2 to 5.9 kW, 11 from 5.7 to 3.8, 16 from 5.0 to 3.8), and B's advantage over
its own network's static limit rises by 3–4 points in every cell. The battery's volt-var
response raises the safe fixed limit more than it helps B, so with the battery there is
less for live control to win.

**The setpoint-schedule fix (amendment 25), before and after on the same runs.** The pass
marks were set by the design panel before anything ran.

| | main (S1) | stress (S2) | stand-in (heavy) |
| --- | --- | --- | --- |
| channel untouched, hold-free runs identical | pass | pass | pass |
| B, violating steps on held setpoints | 39 → 8 | 67 → 13 | 139 → 28 |
| C, violating steps on held setpoints | 199 → 86 | 315 → 117 | 826 → 226 |
| margin-tail violations at least 80% fewer, B | 77%, fail | 82%, pass | 78%, fail |
| the same, C | 56%, fail | 65%, fail | 71%, fail |
| a held step no riskier than a fresh one, per cell | fail | fail | fail |
| B as safe at 0 s as at 5 s | pass | one seed short at 10% loss | pass |
| B's energy cost on good links under 5% | pass | pass | pass |

The fix removes most of the violations it targets and costs B almost nothing; under the heavy
stand-in demand it cut cable overloads from 55 to 2 for B and from 638 to 140 for C. It misses
the 80% bar for C in all three cases and narrowly for B in two, and a held setpoint is still
riskier per step than a fresh one. What is left is almost all voltage unbalance on C, which
charges at the full envelope with only a 95th-percentile margin, and one schedule now covers
up to three steps, so a bad draw can repeat. Two sensitivity runs ruled out the obvious
adjustments. Making late cars wait at 0 kW changed almost nothing (the pre-registered
trigger was not met). Scoring trust at the time of use cost B 15% of its energy to remove two
violating steps. Details: `results/paired_main/`, `results/paired_stress/`,
`results/mechanism_standin/`, `results/sensitivity/`.

**What these results depend on:** provisional cable ratings, stand-ins for three teammates'
nodes, the 15-minute stale timeout (rerun on the final model, amendment 8: at 10% loss the
crossing moves from 20 s with a 5-minute timeout to 149 s with a 60-minute one, while unsafe
runs rise from 0 to 9 of 168), margins sized at the 95th percentile of
measured drift, and the S1 demand model, which draws each day's driving afresh, so a heavy
driver is not heavy every day.

## Research design

| Plan commitment | Status | Evidence / note |
| --- | --- | --- |
| Primary question: where B stops beating the static limit | ✅ | S1 complete, 13 seeds; results above |
| Metric: EV energy delivered, runs with any violation do not count | ✅ | `RunResult.energy_kwh`, `counted` in `src/sweep.py` |
| Controller A, static limit (Table 2) | 🟡 | Calibrated per seed to the largest always-safe limit, not 7.2 kW: amendment 1 |
| Controller B, trust-weighted towards a conservative floor | ✅ | `TrustWeighted` in `src/controllers.py`, floor 1.4 kW |
| Controller C, full envelope until timeout, then static | ✅ | `BinaryFallback`; labels corrected to Table 2 today, amendment 17 |
| Secondary question: warning-day survival hours | ⛔ | Needs S4 decisions, see below |

## Variables (Table 8)

| | Plan | Status | Evidence |
| --- | --- | --- | --- |
| V1 | latency 0 to 600 s, **uplink and downlink** | ✅ | `TelemetryLink` and `DownlinkChannel`; downlink added today, amendment 18 |
| V2 | loss 0 to 40%, per message | ✅ | both directions; V5 test confirms within 1 pp |
| V3 | stale hold: off, 2, 5, 8 min, fresh timestamps | ✅ | `stale_hold_min`; added today; trust stays 1.0 while values lag, as intended |
| V4 | SoC error 0, ±3, ±8, ±15% | 🟡 | `soc_bias` in the battery stand-in; only used by S4, which is blocked |
| V5 | battery on or off | ✅ | `battery_enabled`; S3 |

## Stages (Table 9)

| | Plan | Status | Evidence |
| --- | --- | --- | --- |
| S1 | 7 × 6 grid, A, B, C | ✅ | `src/stages.py --stage S1`, 13 seeds; main case in `results/stages/`, stress case in `results/stress_s2/`, run 2 Oct |
| S2 | V3 at 4 levels, 3 S1 points, A, B, C | ✅ | `--stage S2`, main case; points at 5 s/1%, 60 s/10%, 300 s/20% |
| S3 | battery off, 3 × 3 subset, A, B | ✅ | `--stage S3`, main case; static limit recalibrated without the battery |
| S4 | warning day, V4 × 3 × 3, survival hours | ⛔ | Not built. Undefined in the plan: when the warning arrives, the reservation target, which loads are critical, when the outage happens and whether the feeder islands, and how survival hours are measured. Gia and Munir to decide |

## Base case (Table 7)

| Element | Status | Evidence / note |
| --- | --- | --- |
| IEEE European LV feeder, 55 connections | ✅ | V1 passes, worst error 0.0002% over 2,721 nodes |
| Transformer re-rated to 150 kVA | ✅ | assumption A17 in the plan |
| Simulated day: late spring weekday | 🟡 | PV for 18 Nov 2026; ambient is an early-spring BOM observation standing in, amendment 19 |
| 16:00 to 22:00, 5-minute steps | ✅ | 72 steps |
| 40% EV penetration, 22 connections | ✅ | seeded selection |
| 7.2 kW charge points, 0.1 kW increments | ✅ | envelope bisects on the 0.1 kW grid, V3 |
| Sessions from a travel survey | ✅ | fitted to VISTA 2024-25 (D4, amendment 27). Plug-in behaviour decided 2 Oct: main case S1 (a third of evenings, the metered Melbourne rate), stress case S2 (the distributor design day) |
| Battery at the electrical midpoint, ~2 h of peak, 4777.2 response | 🟡 | bus 686, 100 kWh, 50 kVA; stand-in, set points provisional for Gia |
| Rooftop PV on 60%, clear sky, one cloud transient | ✅ | 33 systems, pvlib Ineichen, cloud 16:40 to 16:55; added today |
| Constraints: voltage, cable current, transformer, hot spot, unbalance | 🟡 | all five enforced; cable ratings provisional, see D1 |

## Data (Table 11)

| | Item | Status | Evidence / note |
| --- | --- | --- | --- |
| D1 | topology, impedances, ratings | 🟡 | topology and impedances from the IEEE package, validated. **The package has no cable current ratings.** Sizes established from the line codes and confirmed against resistance; ampere values provisional in `config/cable_ratings.json` until checked against AS/NZS 3008.1.1. Cable current binds most often, so these decide the result |
| D2 | 55 one-minute customer profiles | ✅ | from the package |
| D3 | PV profile, Ineichen-Perez, Melbourne | ✅ | `data/pv_profile.csv`, provenance in `data/scenario_provenance.json` |
| D4 | session distribution fitted to VISTA | ✅ | `src/vista_sessions.py`: arrival home and daily driving energy, weighted, 1,765 person-days; plug-in model S1 (p = 0.34, accumulated deficit) for the main case and S2 (p = 0.70) for the stress case, `config/study.json` |
| D5 | BOM ambient temperature | 🟡 | real BOM data, `data/ambient.csv`; early spring standing in for late spring |
| D6 | AS/NZS 4777.2 characteristic points | 🟡 | Australia A defaults in `src/battery.py`, for Gia to confirm against the standard |
| D7 | IEC 60076-7 thermal parameters | 🟡 | the standard's typical distribution-transformer values, `config/cable_ratings.json`; confirm against a datasheet |
| D8 | battery specification | 🟡 | stand-in sizing; Gia's datasheet to replace it |
| D9 | static baseline | 🟡 | calibrated rather than 7.2 kW, amendment 1 |

## Validation (Table 12)

| | Checks | Owner | Status | Result |
| --- | --- | --- | --- | --- |
| V1 | model matches the published feeder | Twin | ✅ | worst 0.0002%, limit 0.5% |
| V2 | volt-var and volt-watt follow 4777.2 | Battery | 🟡 | passes against the stand-in; Gia's model must pass the same test |
| V3 | bisection finds the true envelope | Twin | ✅ | worst 0.05 kW, limit 0.1; feasibility monotonic at every point (A9) |
| V4 | envelopes safe and maximal | Twin | ✅ | zero violations, every envelope maximal; the 1% clause conflicts with 0.1 kW steps, amendment 2 |
| V5 | injector delivers what was commanded | Comms | 🟡 | passes against the stand-in, latency 2.9%, loss 0.95 pp; Hoang's must pass the same |
| V6 | trust behaves at the extremes and between | Comms | 🟡 | passes against the stand-in; Hoang's must pass the same |
| V7 | SoC model conserves energy | Battery | 🟡 | passes against the stand-in, closes to 0.0000% through both SoC limits |
| V8 | the whole chain gives a known answer | EV | ✅ | rerun 3 Oct on the final code: predicted and simulated first head-cable overload agree to the step, 16:40 (112% vs 113% of rating); V8 now judges only the limit its arithmetic predicts, amendment 28 |
| V9 | results regenerate a week later | All | ✅ | recorded 3 Oct on the final code and demand; checked 11 Oct, eight days later: all three logs identical. Re-recorded 12 Oct after the integration changes and a label fix in `config/study.json` (its descriptive `controllers` section still had the pre-amendment-17 names; no code reads it), with the same three log hashes; an optional re-check is due from 19 Oct |

## Integration

| Item | Status | Evidence |
| --- | --- | --- |
| Message contract | ✅ | `src/messages.py`, version 2 (schedule entry and validity interval on `Setpoint`), validated; every node must move to it together. 12 Oct: two battery messages added (`BatteryRequest`, `BatteryReply`) for the battery on the Pi; the existing messages are unchanged |
| MQTT path equivalent to the in-process path | ✅ | `tests/test_mqtt_equivalence.py`: identical at 60 s/10%, 300 s/10% and 0 s/40%, including the schedule entry applied at each step |
| Hoang's injector and trust metric | ⛔ | stand-in in `src/telemetry.py`; starting file `team/hoang_link.py`; acceptance tests V5, V6. Hoang's MQTT chat prototype (12 Oct) is in `team/hoang_prototype/` with notes: a connection test, not the injector |
| Lomitha's charge-point controller | ✅ | Lomitha's own code (12 Oct) in `team/lomitha/`: an `EVChargePointGateway` per charge point with the IEC 61851 pilot rules, and the `EVSessionPlant` car model. `team/lomitha_fleet.py` connects it and keeps R1 to R5; two marked changes in Lomitha's files (half-open validity, optional numpy). `tests/test_lomitha_adapter.py`: with the pilot rules and taper off it gives the stand-in's answer exactly on five evenings (energy, violations, fallbacks); with them on, 0.5 to 2.4% less energy and no extra violations. EQUIVALENT over MQTT |
| Gia's battery | ⛔ | stand-in in `src/battery.py`; starting file `team/gia_battery.py`; acceptance tests V2, V7. Can run on the Pi (12 Oct): `BatteryNode` there, `RemoteBattery` in the twin; every battery call matched bit for bit over MQTT, and `--team all --battery-on-pi` is EQUIVALENT, state of charge included |
| Plug-in slots for teammates' code | ✅ | `src/plugins.py`; `--team` (or `--link/--downlink/--battery/--fleet module:Class`) on the acceptance tests, `tools/run_with_pi.py`, `src/stages.py` and the Pi's runner, so no one edits anyone else's code. The three starting files pass V2, V5, V6, V7, and an S1H run on all three matched the main results to the last digit of energy (11 Oct) |
| Raspberry Pi kit | ✅ | `tools/pi_session.py` runs a whole evening with the Pi in one command over SSH (rebuild, copy, start, run, compare, stop), with the Pi reaching the laptop's broker through an SSH tunnel, so no firewall changes; `--local` for the laptop alone. `pi_package.zip` carries its own paho-mqtt, so the Pi needs only Python 3 (tested with every installed package hidden). Rehearsed 11-12 Oct: EQUIVALENT at B 60 s/10% and C 300 s/20% (seed 7), C 300 s/20% stress case (seed 9), Lomitha's controller, all three parts with the battery on the Pi, and through a stand-in for the tunnel. Fixed on the way: the Pi now says "connected" only once the broker accepts it, and every listener skips messages not addressed to it (the laptop's broker, amqtt, hands new subscribers other nodes' retained status) |
| Real Pi, SSH and the tunnel over a real network | 🟡 | supported in the code, first met when Gia runs the session with her Pi; steps in `README_FIRST.md` and `docs/Putting_It_Together.pdf` |
| Handover to Gia | ✅ | `EEE40016_for_Gia.zip` (built by `tools/make_handover.py`): the whole project with `README_FIRST.md` and `requirements_laptop.txt`, tested unpacked in a fresh folder |
| Interface document for the team | ✅ | `docs/INTERFACES.md` |
| SINCAL cross-check | 🟡 | on a 47-node cut that fits the laptop's licence, every node within 0.10% of OpenDSS after three importer faults were fixed (amendment 26, `notes/sincal_subset_check.md`). The full feeder needs the AVD: `avd_crosscheck.zip`, then `tools/avd_compare.py` |

## Faults found and fixed during the build

Recorded because each one changed the results, and a reader should know the model was
checked this hard. Details in `notes/plan_amendments.md`.

| Fault | Effect | Amendment |
| --- | --- | --- |
| Static baseline of 7.2 kW violates 44 of 72 steps | the research question could not be answered | 1 |
| Source at 1.05 pu left 0.2 V of headroom | baselines a factor of four apart between near-identical seeds | 5 |
| No security margin | violations worst when the data was best | 6 |
| Telemetry counted late messages as lost | trust too low everywhere, crossover biased low | 7 |
| Envelope planned with cars not charging | unbalance violations with perfect data, 19% of energy lost | 10 |
| Zero margin on fresh data | solver tolerance alone tipped envelopes over | 13 |
| Samples stamped with end-of-window values | latency below 5 min never affected accuracy | 15 |
| Controller labels reversed against Table 2 | earlier figures contradict the report | 17 |
| Downlink not degraded | half of V1 missing | 18 |
| Random seed differed per process | results could not be regenerated (found by V9) | 23 |
| Unbalance margin a third of its one-minute drift | most fresh-data runs broke unbalance | 21 |
| Held setpoint applied to newly arrived cars | one lost message pushed the cable to 106% | 22 |
| Profiles re-read from disk on every call | 75% of run time; results unchanged by the fix | 23 |
| Held setpoints applied with a margin for fresher data than they had | most live-control violations at 120 s and beyond, and B less safe at 0 s than at 5 s | 24, 25 |
| SINCAL importer: phase codes, vector group, zero-sequence switch | SINCAL saw 6 kW of a 57 kW feeder; no error raised | 26 |
| Stand-in sessions three times heavier than any evidence | the feeder looked far more congested than realistic demand makes it | 27 |

## Things only you can do

1. **Check the cable ratings** in `config/cable_ratings.json` against AS/NZS 3008.1.1. Cable
   current is the binding constraint most of the time, so these numbers decide the answer.
2. **Take the amendments to the team and convener.** Several change what the plan says: the
   static baseline (1), V4's pass criterion (2), the source voltage (5), the security margin
   (6, 11, 13), and the controller labels (17). They need agreeing, then writing into the
   report.
3. **Run the SINCAL cross-check on the uni AVD.** Unzip `avd_crosscheck.zip` there and
   follow its README (one script, or a few clicks in SINCAL using the *unbalanced* load
   flow), bring the two `_files` folders back, and run `tools/avd_compare.py` on each. It
   turns "we used OpenDSS because of the licence" into "two engines agree".
4. **Get S4 decided** with Gia: the five scenario questions in the S4 row above.
5. **V9 passed on 11 October.** The baseline was re-recorded on 12 October on the final
   code; an optional re-check from 19 October is `py tests/v9_reproducibility.py --check`.
6. **Tell the team the demand decision** (amendment 27: S1 main, S2 stress, 150 kVA kept),
   and that the 1 October results are superseded.
7. **Send Lomitha and Hoang the schema-2 change** and requirements R1-R7 in
   `docs/INTERFACES.md`.
8. **Send Gia the handover zip** (`EEE40016_for_Gia.zip`): she runs the Pi session with her
   Pi from `README_FIRST.md`. When all three parts pass, the experiments are rerun with
   `--team all` (results in `results/stages_team/`).

Also outstanding, but not blocking: updating the slides and report to the corrected
controller labels, the calibrated baseline and the final results.
