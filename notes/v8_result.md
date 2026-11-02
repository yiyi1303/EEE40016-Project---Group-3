# V8 — known-answer check

**Overall: PASS**

## Case 1 — no EVs at all

The full chain: telemetry, trust, envelope search, power flow, thermal model.
With no charging the feeder should never break a limit.

| | |
| --- | --- |
| Control steps | 72 |
| Violating steps | 0 |
| Peak hot spot | 56.1 C |

**PASS**

## Case 2 — every connection charging at 7.2 kW, no envelope

Predicted by hand arithmetic with no power flow: per-phase apparent power over 230 V at the head cable, against its 175 A rating. Then simulated through the full chain.

| | Predicted | Simulated |
| --- | --- | --- |
| First violating step | 7 | 7 |
| Time | 16:40 | 16:40 |
| Constraint | head cable, phase A at 196 A (112% of rating) | cable line12 at 113.2% of rating |
| Cars charging, phase A / B / C | 5 / 1 / 3 | |

Not judged: unbalance 2.11% at bus 682 at step 4 (16:25), earlier than the cable. The arithmetic models head-cable current only; with the VISTA sessions cars home before 16:00 are already charging when the window opens (amendment 28).

Allowed: the simulator up to 2 steps earlier than predicted, never later. The arithmetic ignores voltage drop, which only ever raises current.

Violating steps over the evening: 7 of 72. Types: {'unbalance': 7, 'cable': 1}

**PASS**

