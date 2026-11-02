# First crossover result — preliminary

28 Sep 2026. Single seed, no PV, no battery, provisional cable ratings and session
distributions. Treat the shape as real and the numbers as indicative.

## The baseline had to be fixed first

The plan compares against "a fixed 7.2 kW limit". Run on this feeder, that limit violates
something on **44 of the 72 control steps** — cable current, unbalance, transformer
loading and overvoltage. Since a run with any violation does not count, controller B as
written could never produce a valid comparison and the research question could never be
answered.

7.2 kW is a charge point's nameplate, not a network's static limit. What a distributor
actually sets is the largest fixed limit that is safe under the worst conditions it
expects. So that is what the baseline has to be, and it has to be calculated rather than
assumed.

Calibrated by bisection over the whole evening, requiring zero violations at every step:

    largest always-safe fixed limit   2.3 kW
    energy delivered at that limit    174.4 kWh
    violating steps                   0

## The crossover

Controller A, trust-weighted, against that 2.3 kW static baseline. Every run below is
clean: zero violations at every step, so every run counts.

| Latency | Loss | Energy (kWh) | Mean trust | Mean limit (kW) | vs static |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 s | 0% | 227.4 | 1.000 | 3.31 | +30.4% |
| 5 s | 1% | 207.9 | 0.866 | 3.00 | +19.2% |
| 30 s | 5% | 195.0 | 0.762 | 2.82 | +11.8% |
| 60 s | 10% | 178.5 | 0.621 | 2.53 | +2.4% |
| 120 s | 20% | 147.2 | 0.380 | 2.10 | -15.6% |
| 300 s | 30% | 115.2 | 0.097 | 1.54 | -33.9% |

**The crossover lies between (60 s, 10%) and (120 s, 20%).**

On a clean link the live envelope delivers 30% more charging energy than the best static
limit, for the same zero violations. Past the crossover the caution costs more than the
flexibility earns, and a network would be better off with a static limit it can set and
forget.

This is the number the study exists to produce, and the SA Power Networks trial report is
the evidence that nobody has published one: their fallback timeout moved from 30 minutes
to four hours with no measured basis given.

## What has to happen before this is a result

- confirm the cable ratings against AS/NZS 3008.1.1, since cable current is the binding
  constraint about two-thirds of the time
- fit the charging sessions to VISTA, per D4
- more seeds, so the crossover has an uncertainty rather than a point
- refine the grid between (60 s, 10%) and (120 s, 20%) to locate the crossing properly
- add PV and the battery, which is what stages S3 and S4 are for
- swap the stand-in telemetry model for Hoang's injector
