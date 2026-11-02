# V3 — bisection against an exhaustive sweep

| | |
| --- | --- |
| Operating points | 30 |
| Tolerance | 0.10 kW |
| Worst disagreement | 0.0500 kW |
| Points outside tolerance | 0 |
| Bisection solves | 244 (8.1 per point) |
| Exhaustive solves | 4389 (146.3 per point) |
| Saving | 18.0x fewer solves |
| Wall clock | 76.4 s for both methods |
| Points where feasibility was not monotonic | 0 |

**PASS**

The exhaustive sweep scans the whole 0 to 7.2 kW range rather than stopping at the first infeasible step, so it also tests assumption A9 directly: feasibility is monotonic in the limit, which is what the bisection relies on.

## Points

| Minute | Demand | Start load | Bisection kW | Exhaustive kW | Diff | Binding | Solves |
| ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 1081 | x4.0 | 1.0 pu | 0.00 | 0.00 | 0.000 | cable | 8 vs 147 |
| 1026 | x1.5 | 1.0 pu | 1.90 | 1.95 | 0.050 | hot_spot | 8 vs 146 |
| 1202 | x4.0 | 0.2 pu | 0.00 | 0.00 | 0.000 | cable | 8 vs 147 |
| 1270 | x0.6 | 0.6 pu | 3.60 | 3.65 | 0.050 | cable | 8 vs 146 |
| 1092 | x4.0 | 0.2 pu | 0.00 | 0.00 | 0.000 | unbalance | 8 vs 147 |
| 1058 | x2.5 | 1.0 pu | 1.70 | 1.75 | 0.050 | hot_spot | 9 vs 146 |
| 1241 | x2.5 | 0.6 pu | 1.10 | 1.15 | 0.050 | cable | 8 vs 146 |
| 1287 | x1.0 | 0.2 pu | 3.00 | 3.05 | 0.050 | cable | 8 vs 146 |
| 1285 | x1.0 | 1.0 pu | 3.00 | 3.00 | 0.000 | cable | 8 vs 146 |
| 1159 | x0.6 | 1.0 pu | 3.70 | 3.75 | 0.050 | hot_spot | 8 vs 146 |
| 992 | x1.0 | 1.0 pu | 2.00 | 2.00 | 0.000 | cable | 8 vs 146 |
| 981 | x1.5 | 0.2 pu | 2.20 | 2.20 | 0.000 | cable | 8 vs 146 |
| 1097 | x2.5 | 1.0 pu | 0.00 | 0.00 | 0.000 | cable | 8 vs 147 |
| 1158 | x2.5 | 0.6 pu | 0.70 | 0.75 | 0.050 | cable | 9 vs 146 |
| 1255 | x2.5 | 0.2 pu | 1.20 | 1.25 | 0.050 | cable | 8 vs 146 |
| 1147 | x0.6 | 0.2 pu | 3.70 | 3.70 | 0.000 | cable | 8 vs 146 |
| 1029 | x2.5 | 0.2 pu | 0.00 | 0.00 | 0.000 | unbalance | 8 vs 147 |
| 1092 | x2.5 | 1.0 pu | 0.00 | 0.00 | 0.000 | unbalance | 8 vs 147 |
| 1114 | x2.5 | 1.0 pu | 0.20 | 0.20 | 0.000 | cable | 8 vs 146 |
| 1157 | x4.0 | 0.6 pu | 0.00 | 0.00 | 0.000 | cable | 8 vs 147 |
| 1233 | x4.0 | 0.6 pu | 0.00 | 0.00 | 0.000 | cable | 8 vs 147 |
| 1259 | x1.0 | 0.6 pu | 3.10 | 3.10 | 0.000 | cable | 8 vs 146 |
| 1309 | x0.6 | 0.6 pu | 3.20 | 3.20 | 0.000 | cable | 8 vs 146 |
| 1270 | x1.0 | 1.0 pu | 3.30 | 3.30 | 0.000 | hot_spot | 8 vs 146 |
| 1127 | x4.0 | 1.0 pu | 0.00 | 0.00 | 0.000 | cable | 8 vs 147 |
| 1251 | x0.6 | 1.0 pu | 3.30 | 3.35 | 0.050 | hot_spot | 8 vs 146 |
| 1295 | x1.0 | 1.0 pu | 3.20 | 3.25 | 0.050 | hot_spot | 8 vs 146 |
| 1253 | x1.5 | 0.6 pu | 1.70 | 1.75 | 0.050 | cable | 9 vs 146 |
| 1023 | x0.6 | 0.6 pu | 3.50 | 3.50 | 0.000 | cable | 9 vs 146 |
| 1287 | x2.5 | 0.2 pu | 1.20 | 1.25 | 0.050 | cable | 8 vs 146 |
