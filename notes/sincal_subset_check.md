# SINCAL against OpenDSS on a reduced feeder

Both engines solve the same reduced feeder with the same kW per load. SINCAL runs its unbalanced load flow (`LF_USYM`); OpenDSS its snapshot solve. Pass criterion as V1: every node voltage within 0.5%.

Reduction (identical for both cases): 906 buses, 205 after merging plain cable segments, 46 kept. 9 of 55 loads sit on their own bus; 46 moved to the nearest kept bus upstream on their own phase. The kept part reaches 0.294 km of the feeder's 0.296 km, down to the load at bus 899.

| | benchmark | study |
| --- | --- | --- |
| load minute | 566 (09:26) | 1000 (16:40) |
| transformer | 800 kVA | 150 kVA |
| source | 1.05 pu | 1.00 pu |
| total load | 57.4 kW | 48.0 kW |
| SINCAL nodes (cap 50) | 47 | 47 |
| phase-nodes compared | 141 | 141 |
| lowest voltage, OpenDSS | 238.40 V at 899.2 | 233.88 V at 899.2 |
| lowest voltage, SINCAL | 238.63 V | 234.01 V |
| largest difference | 0.0992% at 899.2 | 0.0575% at 899.2 |
| mean difference | 0.0552% | 0.0509% |
| nodes in one engine only | 0 | 0 |
| result | **PASS** | **PASS** |

What this does not cover: the 906-bus feeder itself, which only the AVD's full licence can solve. `tools/make_avd_package.py` builds that run (avd_crosscheck.zip).
