# Amendments the build has forced on the research plan

Four changes, each found by running the method rather than by rereading it. Listed with
what to change and why, so they can go to the team and into the final report as recorded
decisions rather than as quiet edits.

## 1. The baseline is a calibrated static limit, not 7.2 kW

**Was:** "a fixed 7.2 kW limit", in the research question, in Table 9 as data item D9, and
as controller B.

**Change to:** "a static limit calibrated to be safe under the worst conditions in the
study window", which on this feeder is 2.3 kW.

**Why:** 7.2 kW run on this feeder violates something at 44 of the 72 control steps:
cable current, unbalance, transformer loading and overvoltage. Because a run with any
violation does not count, controller B as specified could never produce a valid
comparison, and the primary research question could never be answered at all.

7.2 kW is a charge point's nameplate. It is not a limit any network would impose on 22
simultaneous connections, and treating it as the baseline compares a careful scheme
against an unsafe one. The honest baseline is what a distributor actually does: pick the
largest fixed limit that stays safe, and set it.

**How it is obtained:** bisection over the whole evening on the 0.1 kW actuation grid,
requiring zero violations at every step. Reported with the results, and recalibrated for
every seed, since it depends on which cars arrive and when.

This makes the result stronger, not weaker. The live envelope now has to beat a
competently chosen static limit rather than an unsafe one.

## 2. V4's pass criterion cannot be met alongside a 0.1 kW actuation grid

**Was:** "Zero violations, and the binding quantity within 1% of its limit."

**Change to:** "Zero violations, and the envelope maximal on the actuation grid: one
further increment must produce a violation." Keep the 1% figure as a reported statistic.

**Why:** across 40 operating points, every envelope was maximal, and none could have been
raised. Even so, only 8 of 29 constrained points sat within 1% of the binding limit, worst
case 2.44%. The gap is the actuation increment, not conservatism. Table 9 specifies charge
points controllable in 0.1 kW steps, and on this feeder one step is often worth more than
1% of a constraint. The two clauses of the plan are in conflict; the tightness criterion
is the one to give way, because the increment is a property of real hardware.

## 3. Cable ratings are missing from the published data, and they decide the answer

**Was:** D1 states equipment ratings come from the IEEE test feeder package.

**Change to:** a new data item and assumption covering conductor current ratings, with
AS/NZS 3008.1.1 as the source and the installation method recorded.

**Why:** the package supplies R, X and C only. There is no ampacity in it anywhere. This
would be a footnote except that cable current turns out to be the binding constraint in 21
of 30 sampled operating points, so these ratings determine the headline number.

The conductor sizes themselves are established and not in doubt: the decimal line-code
names are legacy imperial copper in square inches, the whole numbers are nominal mm2 in
aluminium, and the published resistances confirm both readings to within a few percent.
It is the ampere values that need a source.

## 4. Assumption A17: the transformer is re-rated to 150 kVA

Already written into the plan. Repeated here because the build confirmed the reasoning:
at 800 kVA the evening peak reaches 21% of nameplate, and neither transformer loading nor
hot-spot temperature could ever bind. At 150 kVA both are live, and the rating is now
consistent with the 175 A head cables the feeder actually has, which an 800 kVA unit never
was.

## Consequences for the presentation and the report

The research question wording changes in the title slide, in slide 4, and in Section II of
the report. The phrase "a fixed 7.2 kW limit" appears in all three.

Nothing else in the method changes. The metric is still EV energy delivered, the
feasibility rule is still zero violations, and the deliverable is still the crossover
point.

## 5. The study case runs at 1.00 pu source voltage, not the published 1.05

**Was:** unstated. The importer took the source voltage from the published package, which
sets 1.05 pu, and used it for every case.

**Change to:** 1.05 pu for the benchmark case only, where it must not move because V1
compares against a reference solution solved at that voltage. 1.00 pu for the study case,
recorded as an assumption.

**Why:** measured, with no EV load at all and household demand only, the feeder reaches
**252.8 V against the 253 V limit**. Two tenths of a volt of headroom across the whole
evening.

That headroom is then spent by a mechanism that has nothing to do with how much charging
is allowed. Charge points are single-phase, so charging loads one phase harder than the
others, the neutral point shifts, and the line-to-neutral voltage on the lightly loaded
phases **rises**. On a feeder already at 252.8 V, the first few cars to arrive push it
over, whatever limit the controller has set.

The effect on the study was severe and would have been easy to miss. Calibrating the safe
static baseline gave 2.3 kW for seed 7 and 0.5 kW for seed 8, a factor of four apart, from
session sets that were almost identical — seed 8 actually had fewer cars charging at the
peak. The baseline was not measuring charging headroom at all. It was measuring which seed
happened to put a car on the wrong phase at 16:45. Every controller then inherited that,
and seed 8 produced no valid runs whatsoever.

At 1.00 pu the three baselines come out at 2.1, 2.6 and 2.1 kW, which is the kind of
spread the seeds should produce.

**Is this legitimate?** Yes, and it is what a distributor would do. A network sitting at
252.8 V at light load has a tap position problem, and tap changers exist for exactly this.
Choosing 1.00 pu models a feeder that has been tapped sensibly. It is recorded rather than
silently applied, and the benchmark case keeps the published value so V1 still means what
it claims.

**Worth keeping for the report:** the neutral-shift mechanism is a genuine result in its
own right. It is the reason an unbalanced three-phase model is necessary here and a
balanced positive-sequence one would have missed the effect entirely, which supports
criterion C5 in the option analysis.

## 6. The envelope is computed with a security margin, and the reason is counter-intuitive

**Was:** unstated. The envelope was applied exactly as computed.

**Change to:** the envelope is computed against limits tightened by a security factor, 0.95
in the current configuration, while violations are judged against the true limits. Add it
to the assumptions register alongside A9.

**Why:** validation item V4 establishes that the envelope is maximal — one further 0.1 kW
increment always violates something. That is the correct answer to "what is the most this
network can carry", and it is also the problem. A maximal envelope has zero headroom by
construction. The twin computes it from telemetry that has already aged, then applies it
to a network that has moved on, and the smallest drift tips it over.

**The counter-intuitive part, which belongs in the report:** without a margin, violations
appear at *low* latency, not high. Measured at seed 9, 15% loss:

| Latency | No margin | 5% margin | 10% margin |
| ---: | --- | --- | --- |
| 5 s | 181.6 kWh, violated | 169.8 kWh, clean | 160.0 kWh, clean |
| 15 s | 179.9 kWh, violated | 168.9 kWh, clean | 159.1 kWh, clean |
| 30 s | 173.2 kWh, violated | 164.3 kWh, clean | 154.2 kWh, clean |
| 45 s | 169.1 kWh, clean | 160.4 kWh, clean | 150.8 kWh, clean |
| 60 s | 162.8 kWh, clean | 154.8 kWh, clean | 146.9 kWh, clean |

When telemetry is good the trust score is high, so the controller runs close to the full
envelope, which is exactly where there is no headroom. When telemetry is poor the trust
weighting pulls the limit down towards the fallback and incidental headroom appears. A
live envelope scheme with no security margin is therefore at its most dangerous when its
data is at its best, which is the opposite of what anyone would assume.

5% was chosen because it removes every violation at a cost of about 6% of delivered
energy. 10% removes nothing further and costs twice as much.

**Where the margin is held:** on the constraints used to plan, not on the commanded power.
Holding it on the constraint means it lands on whichever constraint is actually binding —
cable current here, thermal or unbalance elsewhere — rather than assuming the binding one
in advance.

## 7. The trust metric must keep age and loss apart — a specification for the telemetry layer

**Was:** assumption A14 says the trust score is a function of measurement age, recent
loss rate and a plausibility test. It does not say how loss is measured.

**Change to:** add to A14, or to the telemetry node's interface specification, that loss
is estimated only over messages old enough to have settled. A message still plausibly in
flight is late, not lost, and lateness is already priced by the age term.

**Why:** the first stand-in telemetry model got this wrong, and the error was large enough
to bias every result. It counted a message as lost if it had not arrived by the end of the
control period it was sent in, and never revisited that verdict. It also never delivered a
message that arrived in a later period. Measured with **no packet loss configured at all**:

| Latency | Loss the twin measured (faulty) | Loss the twin measured (fixed) |
| ---: | ---: | ---: |
| 1 s | 10% | 0% |
| 60 s | 22% | 0% |
| 120 s | 38% | 0% |
| 300 s | 92% | 0% |
| 600 s | 100% | 1% |

Latency was being counted twice, once as age and again as phantom loss, so trust was too low
everywhere above zero latency and collapsed to nothing at long latencies. Controller A was
therefore systematically over-cautious and every crossover was biased low. It showed up as
a cliff: one second of latency cost 5 to 7 points of advantage, and then fifteen more
seconds cost almost nothing.

**How the fix works, in a form the telemetry node can implement:** the twin measures its own
delivery delays from the send timestamps on messages it has received, and takes the 95th
percentile. A message sent longer ago than that which still has not arrived is counted as
lost. Anything newer is still in flight and is left out of the loss estimate. This needs
only the sequence number and send timestamp the uplink topic already carries.

With the fix, configured loss of 20% is measured as 18% to 24% at every latency from 0 to
600 s, which is what a correct estimator should do.

**For the report:** this is a genuine methodological point, not just a bug. Any trust
metric built on message counting has to decide when a missing message becomes a lost one,
and getting it wrong makes a scheme look worse the higher its latency, for reasons that
have nothing to do with the data being stale.

All results produced before this fix are in `results/superseded/telemetry_bug/` and should
not be used.

## 8. The stale timeout is a primary parameter, and the crossover has to be reported with it

**Was:** not in the plan. The stand-in trust score used a 15-minute stale timeout, chosen
without measurement, and the crossover was reported as though it were a property of the
network alone.

**Change to:** report the crossover per timeout, or justify one timeout explicitly and show
the sensitivity alongside it. Add the timeout to the controller specification in the
assumptions register.

**Why:** measured at four settings, five seeds, same static baseline throughout. Median
latency at the crossing, in seconds:

| Packet loss | 5 min | 15 min | 30 min | 60 min |
| ---: | ---: | ---: | ---: | ---: |
| 10% | 101 | >600 | >600 | >600 |
| 20% | 43 | 345 | >600 | >600 |
| 30% | 10 | 90 | 350 | >600 |
| 40% | 0 | 0 | 0 | 0 |

Moving the timeout from 5 to 15 minutes moves the crossover by a factor of five or more. A
controller that gives up on its data quickly falls back to 1.4 kW, below the 2.1 kW static
limit, and loses to it within a minute or two of latency. One that keeps believing its
data stays ahead for ten minutes. The network is identical in every column.

**What this means for the answer:** the crossover is not purely a property of the telemetry.
It is a joint property of the telemetry and of how long the controller is willing to trust
it. That is itself a finding worth stating plainly, and it connects directly to the
evidence that motivated the study: SA Power Networks moved their fallback timeout from 30
minutes to four hours with no measured basis. This study measures what that choice is
worth.

At 40% loss no timeout helps, which is consistent with the loss term in the trust score
dominating there. Item 9, when the age-only runs finish, tests how much of that is the
formula.

**Rerun on the final model (2 Oct):** setpoint schedules on, main-case demand, controller B
against the static limit, the seven main-case seeds where the static limit binds. One
timeout now moves both ends together (the twin's trust timeout and the charge points'
fallback timeout, which since item 25 also sets the schedule length). Median latency where
B's advantage crosses zero (`results/timeout_sensitivity/`):

| loss | 5 min | 15 min | 30 min | 60 min |
| --- | --- | --- | --- | --- |
| 10% | 20 s | 90 s | 122 s | 149 s |
| 20% | never | 30 s | 44 s | 54 s |
| 30% and 40% | never | never | never | never |
| runs that broke a limit | 0 of 168 | 1 of 168 | 5 of 168 | 9 of 168 |

The timeout still matters, though less than before: no setting now keeps B ahead to 600 s.
Going from 15 minutes to 5 cuts the crossing at 10% loss from 90 s to 20 s and removes it
entirely at 20%. Going to 60 minutes stretches it to 149 s but multiplies the unsafe runs by
nine. A longer timeout buys reach by trusting old data, and the margin curves stop at
15 minutes, so the extra reach is paid for in safety. 15 minutes stays the reference, and the
crossover is reported with it.

## 9. The loss term in the trust score is doing safety work it was never designed for

**Question tested:** how much of the crossover's flat boundary near 30% loss is physics, and
how much is the `(1 - loss)` term in the trust formula? Same full grid run twice, 13 seeds,
1,950 runs each: trust with the loss term (w = 1) and trust from age alone (w = 0).

**First reading, which was wrong:** with age-only trust the median crossing is beyond 600 s
at every loss rate. That reading drops runs with violations, as the surface plots did, and
age-only produced eight times as many.

**Fair comparison:** a violating live run means live control was not a valid option there,
so it counts as a loss for live control. Measured as the share of seeds in which the live
envelope is both violation-free and ahead of its own static baseline:

| Loss | w = 1: live wins safely up to | w = 0: live wins safely up to |
| ---: | ---: | ---: |
| 10% | 450 s | 600 s or more |
| 20% | 240 s | 450 s |
| 30% | 60 s | 450 s |
| 35% | never | 450 s |
| 40% | never | 600 s or more |

Violations: **23 of 1,950 runs (1.2%) with w = 1; 187 of 1,950 (9.6%) with w = 0.**

**What this shows.** Even counting every violation against it, age-only trust wins safely in
most seeds at 40% loss. So the flat boundary in the w = 1 surface is mostly formula, not the
data going bad: at 30-second telemetry, losing 40% of messages barely ages the twin's picture.

But the loss term has been buying safety, through two separate mechanisms:

- **Low latency, one seed.** Every one of age-only's 70 violations at 45 s latency or less is
  seed 9, a hard case where running close to the envelope breaks even with the 5% margin.
  The same seed accounts for 15 of the 23 violations with w = 1. This is amendment 6 again:
  high trust means running at the envelope, where there is no headroom.
- **Long latency, systemic.** At 300 s and beyond, eleven different seeds violate under
  age-only trust. The 15-minute timeout lets 5- to 10-minute-old data keep a trust of 0.3 to
  0.7, and an envelope computed from a picture that old is wrong often enough to break
  limits. The loss term was masking this by pulling trust down for an unrelated reason.

**Recommendation for the telemetry node.** Do not rely on a loss penalty as a proxy for
staleness. Use age-only trust, which does not punish a link for losses that barely affect
freshness, and handle the real hazard directly with a security margin that grows with the
age of the data: small when the picture is fresh, large when it is minutes old. That targets
the actual cause of the long-latency violations instead of relying on a correlation.

**Correction to an earlier statement.** After amendment 6 the grid was reported with every
run clean. That was true of the grid run before the telemetry fix in amendment 7. With
correct telemetry, trust is higher everywhere and 23 runs (1.2%) violate even with w = 1,
15 of them seed 9. The 5% margin reduces violations; it does not eliminate them.

## 10. The envelope was planned with cars that were not charging

**A bug, found by chasing seed 9.** With perfect information (zero latency, trust 1.0, age
0), seed 9 still broke the unbalance limit. The twin planned a 2.3 kW envelope against an
unbalance limit tightened by 5%, and the real network exceeded the untightened limit at
that same 2.3 kW.

**Cause:** during the bisection, every trial limit was applied to all 22 charge points,
including cars that had not arrived yet and cars that were already full. Application then
charged only the cars really there, each capped at the energy it still wanted. So the twin
planned for one set of loads and the network got another.

For cable current, transformer loading and thermal, planning with extra phantom load is
just over-cautious. For unbalance it is not cautious at all: the phantom cars sit on
different phases from the real ones, so the twin planned for a phase distribution that
never happened.

**Fix:** the search now plans with exactly the draws application will produce: nothing for
cars not charging, and each charging car capped at what it still needs. The twin knows
this because the charge points report it (`status()` in the edge interface, which is why
that field is required).

**Effect:** it cut both ways. Seed 9 at zero latency went from 196.7 kWh with two unbalance
violations to 234.6 kWh with none. The phantom load had been suppressing the envelope and
costing about 19% of the energy, while also causing the violations. Every grid before this
fix understated live control. Those results are in `results/superseded/planner_bug/`.

## 11. The margin grows with the age of the data, sized from measured demand drift

**Was:** a flat 5% security margin at every age (amendment 6).

**Change to:** a margin read off a curve of data age. At each age it is the 95th-percentile
drift of per-phase household demand over that lag, measured from the feeder's own 1-minute
profiles over 15:00 to 22:00, as a fraction of one phase of the 175 A head cable (40.25 kW
at 230 V), the constraint that binds most often:

| Age | 1 min | 2 | 3 | 5 | 7 | 10 | 15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Margin | 6.8% | 8.5% | 10.7% | 12.7% | 14.5% | 16.0% | 17.1% |

**Why:** an old picture is wrong by roughly as much as demand drifts in that time, so that is
the headroom needed to absorb it. The flat 5% turns out to be about right for data a minute
old and too small for data five or ten minutes old, which is exactly where the long-latency
violations in amendment 9 occurred.

**Limits of the calibration:** it is sized on the head cable, the constraint that binds most
often, and applied to every constraint uniformly. Voltage unbalance responds to drift
differently. The comparison run will show whether that matters.

## 12. With the planner fixed, the crossover sits at the far corner of the S1 grid

Three variants, 13 seeds, 9 latencies (0 to 600 s) x 8 loss rates (5% to 40%), 936 runs
each, all with the planning fix from amendment 10.

**Mean advantage over each seed's own static limit, safe runs only**

| Loss | Latency | As planned (age and loss, flat 5%) | Age only, flat 5% |
| ---: | ---: | ---: | ---: |
| 5% | 0 s | +50.7% | +57.3% |
| 5% | 600 s | +23.9% | +27.7% |
| 20% | 0 s | +35.6% | +56.4% |
| 20% | 600 s | +11.3% | +23.9% |
| 40% | 0 s | +17.8% | +54.8% |
| 40% | 600 s | **-2.5%** | +21.0% |

Runs with any violation: 6 of 936 (0.6%) as planned; 45 of 936 (4.8%) age only, 40 of
them at 450 to 600 s.

**What this means for the research question.** With the formula in the plan, live
envelopes beat the best static limit everywhere in the planned S1 grid except its far
corner: 40% packet loss at around ten minutes of latency. The crossover the study was
designed to locate lies at, or beyond, the edge of the grid the plan specified. Locating it
properly needs the grid extended past 600 s and 40%, and SA Power Networks' timeout of 30
minutes to four hours is a good reason to go well past ten minutes.

**The trade-off between the trust formulas is now clear.** The loss penalty buys safety at
long latency and costs a lot of energy at high loss: at 40% loss and zero latency, age-only
trust delivers +54.8% against +17.8%. Age-only trust with a flat margin trusts stale data
too much. The age-scaled margin (amendment 11) is meant to sit between them; its first run
is being repeated because of item 13.

## 13. A margin of exactly zero is never safe, even with perfect data

The first age-scaled run had six violations at zero latency, all seed 8, one step each.
Traced: at step 66 the data was 0 minutes old, the margin was therefore 0, the twin planned
5.2 kW as feasible against the true limits, applied exactly 5.2 kW, and the head cable came
out at a hair over 100% of its rating.

The cause is numerical. OpenDSS converges to a tolerance (1e-4), so identical loads solved
from different starting states give slightly different answers. Measured: line2 current
spread by 0.010 A across five starting states, 0.006% of the 175 A rating. An envelope with
no margin sits inside that band. Planning and application solve from different starting
points, so the application can land just over the limit.

Fix: the age-scaled curve now starts at 1%, not 0. That is far above the numerical noise and
of the order of Class 1 revenue-meter accuracy, which is the real uncertainty in any
connection-point reading. The flat 5% variants were never affected. The general point for
the report: an envelope computed as exactly maximal by an iterative solver cannot be applied
with zero headroom, however good the data.

## 14. Withdrawn: "one seed in thirteen never pays"

Reported earlier from the pre-fix grids: seed 8, whose static baseline is 2.6 kW, never beat
it at any telemetry quality. With the planning fix, seed 8 is +40.2% at zero latency and 5%
loss. The finding was an artefact of the planning bug and should not appear in any report.

## 15. Telemetry samples now carry the reading at their own time

**Was:** each 5-minute window published ten 30-second samples, all stamped with the
end-of-window reading.

**Change:** each sample carries the one-minute profile value at its own send time, as Section
V-C of the plan specifies.

**Why it matters:** with every sample in a window identical, a sample delayed by 30 s or two
minutes carried exactly the same values as a fresh one. Below about five minutes, latency
therefore changed only the twin's trust, never the accuracy of what it believed. That
understated staleness along the primary axis of the study. It also made the 2-minute
stale-data hold in V3 meaningless, since a value frozen for two minutes inside a window that
only changes every five is not frozen at all. All results before this change are superseded.

## 16. Do no harm: the envelope search when the network is already in breach

With rooftop PV the feeder reaches 252.6 V at 16:00 with no charging at all, inside the 5%
planning margin of the 253 V limit. The search would then return zero kW, which is exactly
wrong: charging pulls the voltage down. The rule now is that a trial passes if every
constraint is either within its limit or no worse than it was with no charging. Charging may
not deepen a breach it did not cause. The exhaustive check used by V3 applies the same rule.

## 17. Controller labels and controller C now follow Table 2

**Was:** in the code, A was the trust-weighted envelope and B the fixed limit, the reverse of
Table 2. Controller C dropped to a 1.4 kW fallback when trust fell below 0.5.

**Now:** A is the static limit, B the trust-weighted envelope, C the binary fallback, as
Table 2 has them. C uses the full envelope until the communication timeout expires and then
reverts to the static limit, which is Table 2's definition. The timeout is the same 15-minute
stale timeout the trust score uses, so B and C draw the line between usable and unusable data
in the same place and differ only in how they respond.

Figures and tables produced before this change use the old labels and must not be put next
to the report.

## 18. Latency and loss now apply to the downlink as well

Table 8 says V1 and V2 apply to both uplink and downlink. Only the uplink was degraded. The
setpoint now travels down a link with the same latency and loss. The charge points act on
the newest setpoint that has reached them by the middle of the control step, which keeps the
model's 5-minute quasi-static resolution, and fall back to 1.4 kW when the newest setpoint is
older than their 15-minute fallback timeout.

## 19. The base case is now the one Table 7 describes

| Element | Now in the model | Provenance |
| --- | --- | --- |
| Rooftop PV, 60% of connections | 33 systems, 6.6 kW DC on 5 kW inverters, north-facing at 20 degrees | Ineichen-Perez clear sky via pvlib, Melbourne, 18 Nov 2026; cloud transient 16:40 to 16:55 at 25% of clear sky |
| Ambient temperature (D5) | one-minute profile for the thermal model | Bureau of Meteorology, Melbourne (Olympic Park), 30 Sep 2026, half-hourly observations |
| Battery at the electrical midpoint | bus 686, 100 kWh, 50 kVA, AS/NZS 4777.2 volt-var and volt-watt | stand-in for Gia's model, set points provisional |
| Stale-data hold (V3) | frozen values with current timestamps for 2, 5 or 8 minutes | as Table 8 defines it |

The ambient record is early spring standing in for the late-spring day of Table 7, because no
November observation exists yet. The PV size and orientation are not in the plan; they are
the commonest Australian residential arrangement.

## 20. V8 now predicts import-driven overload only

With PV, the hand arithmetic predicted a head-cable overload at 16:05 with no cars charging,
from reverse flow. It was wrong: under export the voltage rises to about 250 V, so dividing
by 230 V overstates the current by about 6%. Hand arithmetic cannot know the voltage rise, so
V8 now predicts only phases importing power, where the 230 V assumption can only make the
simulator early. Case 1 separately confirms that PV export alone breaks nothing. With PV the
first EV overload moved from 17:25 to 17:50, and prediction and simulation still agree on the
step exactly.

## 21. Voltage unbalance needs its own margin, three times what it had

Once telemetry samples carried their own readings (item 15), controller B broke the
unbalance limit in most seeds even at 5 s latency. Traced: data half a minute old, envelope
planned against 1.9%, network at 2.00%.

Measured, 95th-percentile drift of the worst-bus unbalance with PV and EVs charging:
**0.33 percentage points in one minute**, 0.53 in five, 0.75 in fifteen. The flat 5% margin
gave 0.10, about a third of a single minute's drift. Unbalance is far more sensitive to stale
data than cable current, because one house on one phase moving a few kW shifts it.

Unbalance now has its own margin curve, measured the same way as the cable curve (item 11).
Both curves are read at the age of the *values*: a sample half a minute old carries the
previous minute's reading, so it counts as a one-minute lag. The default margin mode is now
"age".

Margins sized at the 95th percentile leave a small tail of exceedances by design. The
residual violations in the final runs are that tail, and they count against controller B.

## 22. A setpoint covers only the cars connected when it was issued

**Found:** one lost downlink message (1% loss) at 19:00, in the same five minutes as two
cars plugging in. The charge points held the previous setpoint, 7.0 kW computed for 10 cars,
applied it to 12, and the head cable reached 106%.

**Rule now in the edge stand-in, and a requirement for Lomitha's controller:** a setpoint
applies only to cars that were connected when it was computed. A car that plugs in later
charges at the fallback until a setpoint issued after its arrival reaches it.

**For the report:** losing a downlink message is more dangerous than losing an uplink one
when the fleet is growing, because the edge keeps acting on a decision made for a smaller
fleet. Holding the last setpoint on its own is not safe.

**Correction (2 Oct):** an earlier version of this item said holding the last setpoint is the
CSIP-AUS behaviour. It is not. IEEE 2030.5 controls carry an interval and expire at its end,
after which the device reverts to its DefaultDERControl. Item 25 brings the model into line.

## 23. Two faults that did not change the physics but did change the results

**Random seeds differed between processes.** Python randomises string hashing per process,
and the downlink was seeded with hash(("down", ...)). Every run had a different random
stream for the downlink, so no result could be regenerated. Found by V9's same-day
self-check; fixed with a SHA-256 seed. Runs made before the fix are in
`results/superseded/unstable_seed/` and are not used.

**Three quarters of the run time was re-reading files.** Each load profile was read from disk
on every call, 23,000 reads per simulated evening once telemetry was sampled every minute.
Profiles are now read once per process. The V9 baseline recorded before the change still
matched exactly afterwards, so the results are identical; an evening went from about 30 s to
about 10 s. An earlier guess, that checking cable currents was the bottleneck, was tested
first and was wrong: the vectorised call was identical but slower, so it was not adopted.

## 24. The margin must cover the setpoint's age when applied, not just the data's age

**Resolved by item 25.**

**Anomaly in the final S1 run:** controller B was less safe at 0 s latency than at 5 s once
loss reached 10%: 6 of 13 seeds safe at 0 s against 11 of 13 at 5 s.

**Traced:** at 0 s latency, 10% loss, all 7 of 7 violating steps were the charge points acting
on an older setpoint after the newer one was lost on the downlink. At 0 s the newest
measurement arrives in time, so the data is 0 minutes old and the margin sits at its 1%
floor. When the next setpoint is then lost, the charge points hold that tight setpoint for
another five minutes while demand drifts. At 5 s latency the data is half a minute old, the
margin is 6.8%, and a held setpoint still has headroom.

**Not fixed in this build, recorded as a design result.** The margin is sized for the age of
the data when the setpoint is computed. It should be sized for the age the setpoint may reach
when applied: data age plus however long the downlink might leave it in force. Two practical
remedies, either of which belongs in the report's recommendations: size the margin for data
age plus one control period whenever the downlink is lossy, or have the twin re-send a
setpoint until it is acknowledged.

## 25. Setpoints are schedules, each entry planned for the age it will have when applied

**The defect behind item 24, which turned out to run along the whole latency axis.** A
setpoint computed at step j and still in force at step j + k is judged against the network
5k minutes after its data, but its margin was read at the data's age. An offline replay of
the downlink (13 seeds x 72 steps) shows how often that happens: 33% of steps at 120 s
latency with no loss at all, 79% at 300 s and 90% at 600 s. The 0 s, 10% loss anomaly of
item 24 was only the low-latency end of it.

**Chosen by a design panel** (three independent designs with safety, standards and validity
lenses, then a judge that checked the code; record in the session scratchpad `judge.txt`):

- Each downlink message is one schedule of H 5-minute entries, an IEEE 2030.5 DERControlList.
  H comes from the edge timeout, H = floor((timeout - 2.5) / 5) + 1 = 3 at 15 minutes, so the
  schedule runs out exactly when the edge would have fallen back anyway. Fallback incidence is
  unchanged in every cell and there is no hidden second timeout.
- Entry 0 is the setpoint computed before, byte for byte. Entry k is planned from the same
  believed state with the margin curves read at lag value_lag(age) + 5k, the transformer
  pre-heated through the k intervals in between, and the ambient for its own interval. It is
  capped at entry 0's envelope.
- The controller laws and their inputs are untouched (`schedule_age_basis: "data"`): B and C
  get the same envelopes, so any change in the comparison comes from the twin's defect alone.
  Trust at application age is a labelled sensitivity variant.
- One message, one loss draw, one delay draw, the same random stream and draw order. "10%
  downlink loss" means what it meant before; only the content of each message changed.
- Cars that arrived after the schedule was issued still draw 1.4 kW (item 22); 0 kW is a
  sensitivity variant and Lomitha's call (`uncovered_kw`).
- Rejected: re-sending until acknowledged (it erases the downlink loss variable and does
  nothing at long latency, where holds come from delay); a margin of data age plus one period
  whenever the link is lossy (pays the larger margin on the 90% of steps that arrive fresh,
  and needs the twin to know the loss rate); a single entry that expires after 5 minutes (a
  hidden 5-minute timeout); derating at the edge (the edge has no network model).

**Validated before any result was used:**

- `tests/golden_runs.py`: with the schedule off, 18 recorded runs (results and full per-step
  traces) are bit-identical to the code before the change; with it on, the 12 runs that have
  no held setpoints are bit-identical too.
- `tests/test_setpoint_schedule.py`, 10 of 10: entry shares match the design table over 42
  cells x 13 seeds; margins match; entries computed eagerly at issue time, as a real twin
  would, agree with the lazily computed ones on 143 of 143 held entries; snapshots are never
  mutated; the edge's validity guard never fires.
- `tests/test_mqtt_equivalence.py` EQUIVALENT at 60 s/10%, 300 s/10% and 0 s/40%;
  `tests/test_node_acceptance.py` 4 of 4.

**Paired S1 results (2 Oct), the same sessions with the schedule off and on:**

- Violating steps on held setpoints, B: 39 → 8 (main case), 67 → 13 (stress case), 139 → 28
  (heavy stand-in sessions). C: 199 → 86, 315 → 117, 826 → 226.
- The hard criteria passed everywhere: fallback incidence and every hold-free run identical.
- The 80% criterion passed for B in the stress case only (77%, 82%, 78%) and failed for C
  (56%, 65%, 71%). A held step stays riskier per step than a fresh one in all three cases.
  The remainder is almost all voltage unbalance on C.
- B's 0 s anomaly is gone in the main and stand-in cases; the stress case is one seed short at
  10% loss. B's energy cost on good links stayed under 5%.
- Sensitivity: `uncovered_kw = 0` changed almost nothing and its trigger was not met, so
  1.4 kW stays. Trust at application age cost B 15% of its energy for two fewer violating
  steps, so the data basis stays.

Reported as measured. The fix was not tuned until it passed.

## 26. Three silent faults in the SINCAL importer, found by a reduced-feeder cross-check

The Xplore licence here cannot solve the 906-bus feeder, so the importer had only ever been
checked structurally: SINCAL loaded every table without complaint. A 47-node cut of the
feeder that fits the licence (`tools/sincal_subset_check.py`: plain cable segments merged,
which is exact because the package's cables have no shunt capacitance; loads beyond the cut
moved upstream on their own phase) showed SINCAL and OpenDSS 5.8% apart. SINCAL was seeing
6 kW of the feeder's 57 kW. Causes, read out of SINCAL's own database description:

1. **Phase codes are not a bitmask.** `Terminal.Flag_Terminal` is 1 = L1, 2 = L2, 3 = L3,
   4 = L1-L2. Phase C loads had been written as 4, a phase-to-phase load.
2. **Vector group 11 is DZ1, not Dyn11.** Dyn11 is 59. With a zigzag and no neutral, nothing
   on the LV side was earthed.
3. **Zero-sequence data was never switched on.** SINCAL ignores an element's r0/x0 unless
   bit 4 of `Element.Flag_Input` is set (7, as in every SINCAL sample), and line
   `Flag_Z0_Input = 1` reads ratio fields that were left at 0. With no zero-sequence path
   every single-phase load was "partially isolated (zero system)" and dropped, with only a
   log warning.

Smaller corrections at the same time: cables written as cable, not overhead line; transformer
uk is the impedance magnitude (4.02%, not the 4% reactance); the study case's source is
1.00 pu, not the benchmark's 1.05; and the cross-check must use SINCAL's unbalanced load flow,
`Start("LF_USYM")`, which writes `ULFNodeResult`. The plain load flow is balanced.

**After the fixes:** every node within 0.10% (benchmark) and 0.06% (study) of OpenDSS on the
reduced feeder, against V1's 0.5%. The full-feeder check still needs the AVD;
`avd_crosscheck.zip` carries it, and `tools/avd_compare.py` reads the result back here. None
of this touches the study's results, which are OpenDSS throughout.

## 27. Charging sessions from VISTA (D4), and what they do to congestion

D4 is now fitted to VISTA 2024-25 (`src/vista_sessions.py`): plug-in at each driver's last
arrival home, energy from that day's driving at 0.17 kWh/km and 90% charger efficiency,
weighted. Median arrival 17:35, median energy 4.7 kWh, mean 7.2.

**Finding:** with every EV plugging in every evening and wanting only that day's driving, the
feeder is barely congested. Seed 7's static limit calibrates to the 7.2 kW ceiling, so live
control has nothing to gain. The study's premise and the 150 kVA re-rating were sized from the
stand-in sessions, which were much heavier.

**Evidence on what a realistic evening looks like** (research summary in the session
scratchpad, `evidence_synth.txt`): metered Melbourne trial data (Jemena-led, ARENA 2023) show
EVs charging on about a third of days (34%; 29-41% across the Melbourne networks) at about
18 kWh per charging day. Daily energy matches VISTA; what differs is that it comes in fewer,
bigger sessions. The planning method used by Australian distributors (University of
Melbourne for ENA/C4NET) assumes 70% of EVs charge on a design day.

**Decided 2 October 2026:**

- **Main case, S1:** 40% penetration (22 EVs). Each car plugs in on an evening with
  probability 0.34 and wants everything driven since its last plug-in, built up from VISTA
  daily driving over a 21-day warm-up (about 21 kWh a session).
- **Stress case, S2:** the distributor design day. Probability 0.70, two days of driving per
  session.
- **The transformer stays at 150 kVA.** Shrinking it again to manufacture congestion would
  not be defensible. With realistic demand the transformer rarely binds; cable current and
  unbalance are what matter on this feeder.

Every evening is a fresh draw per seed: which cars plug in, and with how much energy.
`config/study.json` holds the choice (`cases.study.plugin_model`); the stress case is run
with `--plugin-model s2`. The every-evening model stays only for the validation checks that
were recorded on it (golden runs, V8, the schedule tests).

Simplification to state: each day's driving is drawn afresh from the VISTA person-days, so a
heavy driver is not heavy every day. That narrows the spread of session sizes, not their
mean.

## 28. V8 judges the limit its hand prediction covers

**Found 3 Oct, when V8 was rerun on the final code:** V8 failed, the simulator breaking a
limit three steps before the predicted time. The prediction was still right. V8 predicts,
by hand arithmetic with no power flow, when the head cable first overloads with every house
charging at 7.2 kW: 16:40, phase A at 196 A against 175 A (112% of rating). The simulator's
first head-cable overload is also at 16:40, at 113.2% of rating.

What tripped first was voltage unbalance, at 16:25. The arithmetic does not model
unbalance. With the VISTA sessions (item 27), cars that got home before 16:00 are already
charging when the window opens; with the earlier stand-in sessions no car arrived before
16:06 and the cable happened to break first, so judging "the first violation of any kind"
never mattered.

**Change:** V8 now compares the prediction with the simulator's first head-cable overload,
and reports any earlier violation of a limit outside the arithmetic without judging it.
Result: same step, PASS (`notes/v8_result.md`). V1, V3 and V4 were rerun on the final code at
the same time and pass unchanged, and the MQTT path is still equivalent at 60 s and 10% loss.

