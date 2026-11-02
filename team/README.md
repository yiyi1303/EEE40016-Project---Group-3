# Teammates' code, and the commands for running with the Raspberry Pi

Each teammate's part plugs in here, and nobody edits anyone else's files. `--team` picks
the parts by name: `hoang`, `gia`, `lomitha`, a list such as `lomitha,gia`, or `all`.
Commands run from the project folder on the laptop (on a Mac, type `python3` for `py`).
The full walk-through is `docs/Putting_It_Together.pdf`.

| Part | Whose | Files | Runs on | Its check |
| --- | --- | --- | --- | --- |
| Comms injector and trust | Hoang | `hoang_link.py` (still the stand-in); MQTT chat prototype in `hoang_prototype/` | laptop, inside the twin | V5, V6 |
| Charge-point controller | Lomitha | Lomitha's own code in `lomitha/`, connected by `lomitha_fleet.py` | Raspberry Pi | EQUIVALENT over MQTT |
| Battery, BMS, EMS | Gia | `gia_battery.py` (still the stand-in) | laptop, or the Pi with `--battery-on-pi` | V2, V7 |

## Check a part on its own

```
py tests/test_node_acceptance.py --team hoang
py tests/test_node_acceptance.py --team gia
py tests/test_lomitha_adapter.py
```

The first two end with `4 of 4 passed`; the third with `PASS`, then shows what Lomitha's
charging rules change.

## Run an evening with the Raspberry Pi: one command

The Pi needs SSH switched on and the same Wi-Fi as the laptop (a phone hotspot; eduroam
keeps devices apart). Nothing needs installing on the Pi, and nothing needs allowing through
the laptop's firewall: the Pi reaches the laptop through the SSH connection.

```
py tools/pi_session.py --find
py tools/pi_session.py --pi <user>@<Pi address>
py tools/pi_session.py --pi <user>@<Pi address> --team all --battery-on-pi
```

The first lists the devices on the hotspot that answer SSH (a Pi says Debian or Raspbian).
The second runs an evening with the stand-ins; the third with everyone's parts and the
battery on the Pi. Type the Pi's password when asked. Each ends with `EQUIVALENT`: the Pi
gave exactly the simulator's answer, step by step.

Useful additions: `--static-kw 2.5` skips a minute of calibration for seed 7; `--no-copy`
skips copying the files again (one password fewer); `--controller C --latency 300 --loss
0.2` for the demo's second case; `--direct` for a plain MQTT connection across the Wi-Fi
instead of through SSH (Windows then asks to allow Python).

No Pi, or it will not connect? The same evening runs on the laptop alone, same output:

```
py tools/pi_session.py --local --team all --battery-on-pi --static-kw 2.5
```

## The battery on the Pi

With `--battery-on-pi` the battery runs on the Pi next to the charge points, and the twin
calls it over MQTT each step: a reset at the start of the evening, then up to six
`response()` calls and one `commit()` per step. The stand-in battery runs there by default;
`--team gia` (or `all`) runs Gia's class from `gia_battery.py` instead. With `--compare` (on
by default in `pi_session.py`) the same battery class then runs on the laptop too, so
`EQUIVALENT` proves the battery on the Pi gives the twin exactly the same answers.

Gia's own battery program can take the stand-in's place on the Pi in two ways: put the
logic into `gia_battery.py` (simplest: the Pi program does the messaging), or write a
program that answers the battery messages itself (format in `docs/INTERFACES.md`, "The
battery on the Pi").

## Bring your code in

Copy your file over the starting file, keeping its name. Lomitha's code lives in
`lomitha/`; `pi_session.py` copies everything to the Pi on each run, so edit on the laptop,
not on the Pi.

## The final runs with everyone's code

When all three parts pass:

```
py tools/run_parallel.py --arm "team:S1:results/stages_team:--team all"
py tools/run_parallel.py --arm "team:S2:results/stages_team:--team all"
py tools/run_parallel.py --arm "team:S3:results/stages_team:--team all"
py src/stages.py --summarise --team all
```

About three hours on Munir's laptop, most of it S1. Keep the laptop plugged in and run
`py tools/hold_awake.py` in a second window (Windows) so it does not sleep. The results go
to `results/stages_team/`, never over the stand-in results, and each file records which
classes made it. The experiments run the battery inside the twin, whichever way the demo
ran it: same class, same answers, much faster.

## Any other class

`--link`, `--downlink`, `--battery` and `--fleet` name any class as `module:Class`, for
example `--battery team.gia_battery:GiaBattery`, and win over `--team`. The acceptance tests
take the first three; `tools/run_with_pi.py` and `src/stages.py` take all four; the Pi's
`run_pi_node.py` takes `--fleet`.
