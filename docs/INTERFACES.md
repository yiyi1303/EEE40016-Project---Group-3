# How the four nodes connect

For Lomitha, Gia and Hoang. This is the contract your code has to meet to plug into the
twin. It follows Section V-B and V-C of the research plan and adds the detail the plan
left open. If something here conflicts with what you have already built, say so now,
before Checkpoint 1, rather than after.

## The one rule that decides whether integration works

**Write your logic as a plain Python class with no MQTT inside it. Put MQTT in a thin
wrapper around it.**

The sweep runs the full study thousands of times: 13 seeds, 72 control steps each, every
combination of latency and packet loss. It does that in process, because it has to be fast
and exactly repeatable. It will import your class and call it directly.

The Raspberry Pi runs the same class behind MQTT, for the hardware demonstration.

If your logic lives inside MQTT callbacks, the sweep cannot run it, and the results in the
report will describe a controller that none of us built. The reference implementations
below all follow this pattern. Copy the shape.

This has been tested, not just claimed. `tests/test_mqtt_equivalence.py` runs one evening
in process and again over a real MQTT broker with the edge in a separate client. All 72
control steps match exactly, energy agrees to 6 × 10⁻¹⁴ kWh, 936 messages, no missed
replies.

**Acceptance tests for your node** are in `tests/test_node_acceptance.py`: V2 and V7 for the
battery, V5 and V6 for the comms layer, with the plan's pass criteria. They pass against the
stand-ins and against your starting file in `team/` today. Run them on your file with
`py tests/test_node_acceptance.py --team hoang` (or `--team gia`); there is no need to edit
the test. Passing them is the hand-over condition.

## Who owns what

| Node | Owner | Status | Reference in `src/` |
| --- | --- | --- | --- |
| Digital twin, clock, envelope | Munir | built and validated (V1, V3, V4, V8) | `sweep.py`, `envelope.py` |
| EV charge-point controller | Lomitha | **stand-in**, replace with yours | `edge.py` → `ChargePointFleet` |
| Degradation injector, trust metric | Hoang | **stand-in**, replace with yours | `telemetry.py` → `TelemetryLink` |
| Battery, BMS, EMS | Gia | **stand-in**, replace with yours | `battery.py` → `BatteryStandIn` |
| Message format | shared | fixed, version 2 (schedule fields, 2 Oct) | `messages.py` |

## Where your code goes

Each of you has a starting file in `team/`: `hoang_link.py` (`HoangLink`, `HoangDownlink`),
`lomitha_fleet.py` (`LomithaFleet`) and `gia_battery.py` (`GiaBattery`). Each inherits the
stand-in and already works unchanged. Replace its methods with yours, keep the class name
and the constructor arguments, and run your test after each change.

Nothing else needs editing to bring your class in. `--team hoang` (or `gia`, `lomitha`, a
comma-separated list, or `all`) selects the files in `team/` on the acceptance tests, on
`tools/run_with_pi.py` and `tools/pi_session.py`, on `src/stages.py` for the full
experiments, and (`lomitha`, `gia`) on the Pi's `run_pi_node.py`. `--link`, `--downlink`,
`--battery` and `--fleet` name any other class as `module:Class`. The commands, ready to
copy, are in `team/README.md`; the hardware walk-through is `docs/Putting_It_Together.pdf`.

Where each part stands (12 October):

- **Lomitha's controller is in.** Lomitha's own code (`team/lomitha/`: one
  `EVChargePointGateway` per charge point, with the IEC 61851 pilot rules, and the
  `EVSessionPlant` car model) runs behind `team/lomitha_fleet.py`, which keeps R1 to R5. Two
  small changes were made in Lomitha's files, marked there: validity intervals half-open
  (R1) and numpy optional (the Pi has none). `tests/test_lomitha_adapter.py` shows the
  adapter gives the stand-in's answer exactly when the pilot rules are switched off, and
  what they change when they are on (0.5 to 2.4% less energy, no extra violations).
- **Hoang's** MQTT chat prototype is in `team/hoang_prototype/` (see its `NOTES.md`). The
  injector and trust class, `team/hoang_link.py`, is still the stand-in.
- **Gia's** battery class, `team/gia_battery.py`, is still the stand-in. It can now run on
  the Raspberry Pi as well as in the twin (see "The battery on the Pi" below).

## Lomitha — the charge-point controller

Your class needs exactly two methods. `ChargePointFleet` in `src/edge.py` is a working
example.

```python
class YourController:
    def status(self, t):
        """t: simulated minutes past midnight. Return every charge point you control:
        {"EV_LOAD17": {"connected": True, "delivered_kwh": 6.25, "wanted_kwh": 18.4}, ...}"""

    def apply(self, limit_kw, t, minutes, node, step, issued_at=None,
              valid_from=None, valid_until=None):
        """Charge for `minutes` at up to `limit_kw` per charge point.
        issued_at: when the setpoint's schedule was computed; cars that arrived after it
            draw uncovered_kw (1.4 kW, the fallback, unless configured otherwise).
        valid_from, valid_until: the interval this limit was planned for. Execute it only
            inside [valid_from, valid_until); outside it, use your local fallback.
        limit_kw is None when no setpoint arrived in time: use your local fallback.
        Return messages.Ack(node=node, step=step, draws={ev: kW actually drawn}, fallback=...)"""
```

**New on 2 Oct: setpoints are schedules (amendment 25).** Each downlink message is now a
short schedule, the way an IEEE 2030.5 server sends a DERControlList: one limit for each of
the next three 5-minute intervals. Each entry is planned with the safety margin for the age
its data will have when it is applied, so a limit you are still holding ten minutes later
was planned for that. Before this, when a message was lost the charge points kept applying
the last limit, planned for fresh data, to a network that had moved on, and that is where
most of the live controllers' violations came from. What it asks of your controller:

- **R1. Execute a limit only inside its interval,** `[valid_from, valid_until)`.
- **R2. The newest issue time wins.** A newer schedule replaces an older one.
- **R3. When the schedule runs out, revert to the default** (the 1.4 kW fallback). Keep the
  15-minute timeout as a backstop; with three 5-minute entries the two coincide.
- **R4. A schedule covers only the cars connected when it was issued** (`issued_at`). Cars
  that plugged in later draw `uncovered_kw`, which is 1.4 kW. A sensitivity run with 0 kW
  (late cars wait for a schedule that covers them) changed almost nothing, so 1.4 kW is
  recommended, but it is your call.
- **R5. No derating of your own.** The twin plans the margin for each entry; scaling limits
  down again at the edge would count the same risk twice.

In the harness the twin works out which entry governs each step and sends you that one, so
the Pi sees one `Setpoint` per step as before, now carrying `entry`, `valid_from` and
`valid_until`. On a real device the whole list would arrive at once, as a 2030.5
DERControlList or an OCPP ChargingSchedule with periods at 0, 300 and 600 s and a validTo,
and the device would pick the entry by its own clock.

What the twin relies on:

- **Report the energy each car still wants.** The twin plans each envelope with exactly the
  draws your controller will produce, including cars that draw less because they are
  nearly full. When the twin planned with the wrong draws, the network broke its
  unbalance limit with perfect data (`notes/plan_amendments.md`, item 10). Your `status()`
  is how the twin knows.
- **Draws must be honest.** Report what each car actually drew, which can be less than the
  limit. The twin applies your reported draws to the power flow.
- **Local fallback.** If no setpoint arrives within the timeout, charge at the fallback
  (1.4 kW, `config/study.json`) and set `fallback=True`. `PiNode` in `src/mqtt_edge.py`
  already detects the timeout and calls `apply(None, ...)`; you implement what happens.
- **Run on simulated time**, from the timestamps in the messages, never your wall clock.
- **A setpoint covers only the cars connected when it was issued** (R4). Every `Setpoint`
  carries `t_to`, the time its schedule was computed. Without this, one lost message during
  fleet growth let a limit computed for 10 cars be applied to 12, and the head cable reached
  106% (amendment 22). `PiNode` passes `issued_at`, `valid_from` and `valid_until` to your
  `apply()`; honour all three.
- **Setpoints arrive late or not at all.** Latency and loss apply to the downlink too
  (Table 8). In simulated time the twin works out which setpoint would have reached you, and
  sends a `Setpoint` with `fallback: true` when none recent enough would have. Treat that
  exactly like a timeout: charge at the fallback.

To run on the Pi: `py src/mqtt_edge.py --broker <PC address> --seed 7`, after swapping your
class in for `ChargePointFleet` in `main()`.

## Hoang — the injector and the trust metric

Three methods. `TelemetryLink` in `src/telemetry.py` is a working example.

```python
class YourLink:
    def publish_window(self, truth, t_from, t_to):
        """Put every telemetry sample generated in (t_from, t_to] in flight.
        truth: {connection: kW}. Delay and drop them in simulated time."""

    def observe(self, now, truth):
        """What the twin holds at the decision instant. Return telemetry.Observation:
        values, age_min, loss_rate, received, expected, delay_p95_min."""

    def trust(self, obs, plausible=True):
        """A number in [0, 1]."""
```

Three things found while building the stand-in that your design should take into account:

1. **A late message is not a lost message.** The first stand-in counted any message that
   missed its own 5-minute window as lost forever. With no loss configured at all it
   reported 38% loss at 120 s latency and 100% at 600 s. That biased every result. Count a
   message as lost only once it is older than the delays you actually observe (the stand-in
   uses the 95th percentile of measured delay). Details: amendment 7.
2. **The stale timeout moves the answer by a factor of five.** Median crossing latency at
   20% loss was 43 s with a 5-minute timeout and beyond 600 s with a 30-minute one, on an
   identical network. Whatever timeout you choose, it has to be justified and reported
   with the result. Amendment 8.
3. **Don't use a loss penalty as a proxy for staleness.** With 30-second telemetry, losing
   40% of messages barely ages the picture, so penalising loss directly makes live control
   look worse than it is. But removing the penalty let old data be trusted too much at long
   latency, and violations rose eightfold. The recommendation is age-only trust plus a
   security margin that grows with data age, which targets the real hazard. Amendment 9.
   The final comparison is running now.

Two requirements from the setpoint schedules (amendment 25). Both are documentation only;
no code of yours changes:

- **R6. On the downlink, the unit of loss and delay is the publication.** A schedule is one
  message: it is lost or delayed as a whole, with one draw from your loss and delay
  processes, never entry by entry, and it is never retransmitted. That is what keeps "10%
  downlink loss" meaning the same thing before and after the change.
- **R7. `trust(obs, plausible)` stays a pure function,** non-increasing in age. The twin calls
  it with an older age to score a schedule's later entries in one sensitivity variant.

## Gia — the battery

A stand-in now exists in `src/battery.py`, placed by the twin at the feeder's electrical
midpoint (bus 686), so stage S3 can run. It is mine, not yours: the sizing and the AS/NZS
4777.2 set points in it are marked provisional and need you to confirm or replace them.

Your class needs three calls, split this way on purpose:

```python
class YourBattery:
    def response(self, v_local, setpoint_kw):
        """P and Q at this terminal voltage. NO side effects.
        v_local: volts line-to-neutral at your terminals. setpoint_kw: what the EMS asks
        for, positive charging. Return (p_kw, q_kvar) in load convention: positive kW
        charges, negative kvar supplies vars."""

    def commit(self, p_kw, minutes):
        """Run at p_kw for `minutes`; update your SoC here and only here."""

    def status(self):
        """{"soc_true", "soc_reported", "e_kwh", "p_max_kw", "s_kva", "enabled"}
        soc_reported = soc_true + your estimation bias (axis V4)."""
```

Why `response` and `commit` are separate: volt-var settles in seconds, so within a 5-minute
step it is at steady state, and the steady state depends on the voltage the battery itself
helps set. The twin iterates `response()` against the power flow until Q stops moving, then
calls `commit()` once. A single call that both answered and changed the SoC could not be
iterated.

One early result you should know about: on the normal day the stand-in's EMS asks for
nothing, so the battery's only effect is volt-var. AS/NZS 4777.2's dead band runs from
220 V to 240 V, and this feeder spends most of the evening inside it, so the battery supplies
only about 1.5 kvar on average. If V5 is meant to show a measurable effect, the battery
probably needs an EMS that does something on a normal day. That is a design decision for you.

### The battery on the Pi (optional)

The battery can run on the Raspberry Pi instead of inside the twin, for the demonstration.
The class stays the same; only where it runs changes. On the Pi, `run_pi_node.py --battery`
(`--team gia` for your class) wraps it in a `BatteryNode`; on the laptop, `--battery-on-pi`
puts a `RemoteBattery` in the twin's battery slot, which forwards each call:

```
twin -> eee40016/breq/battery    BatteryRequest  op "reset", "response" or "commit", numbered req
battery -> eee40016/bresp/battery BatteryReply   the same req; P and Q, or the status
battery -> eee40016/status/battery "online"/"offline", retained, as for the charge points
```

`reset` starts an evening (fields `soc_bias`, `enabled`: build the battery afresh).
`response` carries `v` (volts) and `setpoint_kw`, and must have no side effects; the reply
carries `p_kw` and `q_kvar`. `commit` carries `p_kw` and `minutes`; the reply carries
`status`, which must include `soc` (the true state of charge) and `enabled`. A reply with
`error` set stops the run. Per step the twin sends up to six `response` requests and one
`commit`, so a Pi on the same Wi-Fi adds a few milliseconds a step. JSON carries the numbers
exactly, and `tools/run_with_pi.py --compare` checks the result against the same class run
in the twin.

If your battery ends up as its own program on the Pi (your own MQTT code, or hardware), it
only has to answer these messages; the field definitions are `BatteryRequest` and
`BatteryReply` in `src/messages.py`. The stand-in battery node is the backup: it works as
it is.

**Still to decide with me, and blocking S4:** what the warning day looks like (when the
warning arrives, what reservation target the EMS sets), which loads are critical, when the
outage happens and whether the feeder islands, and how survival hours are measured. Stage
S4 can't be built until these are fixed.

## Messages

Every message is defined in `src/messages.py` with a validator. **Copy that file
verbatim.** Don't re-type field names; a typo in a field name is the most likely way for
the twin and the Pi to silently disagree. Each message carries `"schema": 2`, and a
mismatch is rejected rather than half-read, so the twin, the Pi and your code must all move
to the new `messages.py` together.

Units are kW, kvar, kWh, volts line-to-neutral and simulated minutes past midnight.

### One control step

```
twin  → eee40016/sync             StepStart     open step k; here is what your meters read,
                                                minute by minute across the window
edge  → eee40016/uplink/<node>    Measurement   ten of them, one per 30-second sample, each
                                                with the reading at its own time
twin                                            injector ages it, trust, envelope
twin  → eee40016/downlink/<node>  Setpoint      the limit for this interval (one entry of
                                                the schedule) and the trust index
edge  → eee40016/ack/<node>       Ack           what was actually drawn
edge  → eee40016/status/<node>    "online"      retained; "offline" is the edge's last will,
                                                so the twin knows whether the Pi is there
```

With the battery on the Pi there are two more topics per step, `breq/battery` and
`bresp/battery`, described under Gia's section above. Every program must act only on the
topics it subscribed to and skip anything else: the laptop's broker (amqtt) can hand a new
subscriber other nodes' retained status messages, and `src/mqtt_edge.py` ignores them.

The twin moves on only after the ack arrives. If it doesn't arrive within a wall-clock
timeout, the miss is logged and the run continues rather than stalling. The ack topic
bypasses the injector, as the plan specifies. Physical LAN latency never enters the
simulated delay; it is measured and logged (median 6.7 ms on this laptop).

Why the twin sends meter readings to the edge: the plant is the twin's power flow, so it is
the only thing that knows what a meter would read. The edge then publishes those readings
as telemetry, through the injector, the way a real meter does. The edge's measurement
pipeline is real; the physics behind it is simulated.

### Examples, generated from the code

`eee40016/sync`
```json
{"step": 36, "t_from": 1140.0, "t_to": 1145.0,
 "readings": {"LOAD1": 0.412, "LOAD2": 1.083},
 "type": "StepStart", "schema": 2}
```

`eee40016/uplink/edge`
```json
{"node": "edge", "seq": 36, "sent": 1145.0,
 "readings": {"LOAD1": 0.412, "LOAD2": 1.083},
 "ev": {"EV_LOAD17": {"connected": true, "delivered_kwh": 6.25, "wanted_kwh": 18.4}},
 "type": "Measurement", "schema": 2}
```

`eee40016/downlink/edge`, the fresh entry of the schedule issued at step 36
```json
{"node": "edge", "step": 36, "t_to": 1145.0,
 "limit_kw": 2.6, "trust": 0.874, "envelope_kw": 3.1, "fallback": false,
 "issued_step": 36, "entry": 0, "valid_from": 1145.0, "valid_until": 1150.0,
 "type": "Setpoint", "schema": 2}
```

and two steps later, when no newer schedule has got through: entry 2 of the same schedule,
planned with a larger margin for data ten minutes older
```json
{"node": "edge", "step": 38, "t_to": 1145.0,
 "limit_kw": 2.4, "trust": 0.874, "envelope_kw": 2.9, "fallback": false,
 "issued_step": 36, "entry": 2, "valid_from": 1155.0, "valid_until": 1160.0,
 "type": "Setpoint", "schema": 2}
```

`eee40016/ack/edge`
```json
{"node": "edge", "step": 36,
 "draws": {"EV_LOAD17": 2.6, "EV_LOAD30": 1.9}, "fallback": false,
 "type": "Ack", "schema": 2}
```

## Where this differs from the plan

- **Telemetry is batched per sample.** One uplink message carries every connection's
  reading rather than one message per meter, which matches a data concentrator. There are
  ten samples per control step, each with the reading at its own time, so 13 messages a
  step in all. The injector drops or delays whole samples.
- **PV readings ride in the same message,** as `PV_<connection>` keys, positive kW, the
  way a meter with a separate generation register reports them.
- **The uplink carries P, not V or transformer loading.** The twin solves the power flow
  from the P it believes, so it gets voltages and loading from the solution. Measured
  voltages would be useful for the plausibility test; adding a `v` field is easy if Hoang
  wants it.
- **The injector is co-located with the twin** in the reference implementation. MQTT is the
  physical transport, and the degradation happens in simulated time after receipt. That is
  what keeps LAN latency out of the results, as the plan requires. Hoang can move it into a
  separate process if that suits Hoang better; the interface doesn't change.

## Test that your part plugs in

Over a real broker and the real Pi, in one command from the laptop (it copies the files,
starts the Pi's program over SSH and compares):

```
py tools/pi_session.py --pi <user>@<Pi address> --team lomitha
```

or by hand, with the Pi running `run_pi_node.py --team lomitha`:

```
py tools/run_with_pi.py --broker <broker address> --compare --team lomitha
```

It runs one evening over MQTT, then the same evening in process, and should print
`EQUIVALENT`. If it doesn't, it lists the steps where the two disagree. Run it at a point
where schedules are actually used, too (`--latency 300 --loss 0.1`), so entries 1 and 2 get
exercised. Without the Pi, `py tests/test_mqtt_equivalence.py` makes the same comparison on
one machine for the stand-in.

## Timing

The integration session with the Raspberry Pi is on 12 October. The twin side and the Pi
package are ready and rehearsed. Bring your class in its `team/` file, passing your
acceptance tests (Hoang and Gia) or ready to run on the Pi (Lomitha).
