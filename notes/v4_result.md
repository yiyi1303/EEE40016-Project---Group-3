# V4 — envelope tightness

| | |
| --- | --- |
| Operating points | 40 |
| Constrained points judged | 29 |
| Unconstrained (envelope at the 7.2 kW ceiling) | 0 |
| Already in violation with no charging | 11 |
| Points with a violation at the envelope | 0 |
| Points where one more 0.1 kW step was still safe | 0 |
| Binding constraint within 1% of its limit | 8 of 29 |
| Worst headroom left | 2.44% |
| Wall clock | 5.3 s |

**PASS**

Safety and maximality are the pass conditions. Headroom above 1% is reported but is not a failure when the envelope is already maximal on the 0.1 kW actuation grid: the next step up would violate, so there is nothing to recover. Those cases are quantisation, not conservatism.

## Maximal but more than 1% from the limit

| Minute | Demand | Envelope kW | Headroom | Binding |
| ---: | ---: | ---: | ---: | --- |
| 1225 | x1.0 | 3.0 | 2.44% | cable |
| 1119 | x1.5 | 1.9 | 2.27% | cable |
| 1209 | x1.0 | 3.0 | 2.21% | cable |
| 1220 | x1.0 | 3.2 | 2.14% | cable |
| 1169 | x0.8 | 3.1 | 2.13% | cable |
| 1156 | x0.8 | 3.4 | 1.89% | cable |
| 1157 | x0.8 | 3.4 | 1.77% | cable |
| 1242 | x0.8 | 3.2 | 1.76% | cable |
| 965 | x0.8 | 3.4 | 1.72% | cable |
| 1295 | x1.5 | 2.7 | 1.68% | cable |
| 1057 | x1.0 | 3.2 | 1.65% | cable |
| 1057 | x1.0 | 3.2 | 1.65% | cable |
| 1067 | x0.8 | 3.4 | 1.64% | cable |
| 1246 | x1.0 | 3.0 | 1.64% | cable |
| 1222 | x1.5 | 2.5 | 1.31% | cable |

## Points

| Minute | Demand | Start load | Envelope kW | Binding | Headroom | Safe | Maximal |
| ---: | ---: | ---: | ---: | --- | ---: | --- | --- |
| 1191 | x3.0 | 0.5 pu | 0.0 | already in violation | 0.00% |  |  |
| 1191 | x3.0 | 0.9 pu | 0.0 | already in violation | 0.00% |  |  |
| 1057 | x1.0 | 0.9 pu | 3.2 | cable | 1.65% | ok | yes |
| 1203 | x4.0 | 0.9 pu | 0.0 | already in violation | 0.00% |  |  |
| 1055 | x0.8 | 0.5 pu | 3.4 | cable | 1.30% | ok | yes |
| 1115 | x1.0 | 0.2 pu | 2.8 | cable | 1.01% | ok | yes |
| 1235 | x4.0 | 0.9 pu | 0.3 | cable | 1.21% | ok | yes |
| 981 | x3.0 | 0.5 pu | 0.1 | cable | 0.62% | ok | yes |
| 1191 | x4.0 | 0.9 pu | 0.0 | already in violation | 0.00% |  |  |
| 1275 | x4.0 | 0.2 pu | 0.0 | already in violation | 0.00% |  |  |
| 1279 | x0.8 | 0.9 pu | 3.2 | cable | 0.84% | ok | yes |
| 992 | x0.8 | 0.2 pu | 2.4 | cable | 1.29% | ok | yes |
| 1057 | x1.0 | 0.9 pu | 3.2 | cable | 1.65% | ok | yes |
| 975 | x2.0 | 0.5 pu | 0.0 | already in violation | 0.00% |  |  |
| 1185 | x3.0 | 0.2 pu | 0.0 | already in violation | 0.00% |  |  |
| 1225 | x1.0 | 0.9 pu | 3.0 | cable | 2.44% | ok | yes |
| 1110 | x2.0 | 0.2 pu | 0.0 | already in violation | 0.00% |  |  |
| 1299 | x0.8 | 0.5 pu | 3.4 | cable | 0.69% | ok | yes |
| 1295 | x1.5 | 0.5 pu | 2.7 | cable | 1.68% | ok | yes |
| 1242 | x0.8 | 0.9 pu | 3.2 | cable | 1.76% | ok | yes |
| 1090 | x1.5 | 0.2 pu | 1.8 | cable | 0.24% | ok | yes |
| 1222 | x1.5 | 0.2 pu | 2.5 | cable | 1.31% | ok | yes |
| 995 | x3.0 | 0.2 pu | 0.0 | already in violation | 0.00% |  |  |
| 1165 | x0.8 | 0.5 pu | 3.3 | cable | 0.54% | ok | yes |
| 1157 | x0.8 | 0.2 pu | 3.4 | cable | 1.77% | ok | yes |
| 1310 | x0.8 | 0.2 pu | 2.9 | cable | 1.22% | ok | yes |
| 1067 | x0.8 | 0.5 pu | 3.4 | cable | 1.64% | ok | yes |
| 1152 | x4.0 | 0.5 pu | 0.0 | already in violation | 0.00% |  |  |
| 1174 | x0.8 | 0.9 pu | 3.2 | cable | 0.79% | ok | yes |
| 1282 | x1.0 | 0.9 pu | 3.0 | cable | 1.08% | ok | yes |
| 1098 | x1.5 | 0.2 pu | 2.1 | cable | 0.15% | ok | yes |
| 1119 | x1.5 | 0.2 pu | 1.9 | cable | 2.27% | ok | yes |
| 1169 | x0.8 | 0.2 pu | 3.1 | cable | 2.13% | ok | yes |
| 1086 | x4.0 | 0.2 pu | 0.0 | already in violation | 0.00% |  |  |
| 965 | x0.8 | 0.5 pu | 3.4 | cable | 1.72% | ok | yes |
| 1209 | x1.0 | 0.9 pu | 3.0 | cable | 2.21% | ok | yes |
| 1246 | x1.0 | 0.5 pu | 3.0 | cable | 1.64% | ok | yes |
| 1220 | x1.0 | 0.9 pu | 3.2 | cable | 2.14% | ok | yes |
| 1027 | x2.0 | 0.9 pu | 0.1 | cable | 0.02% | ok | yes |
| 1156 | x0.8 | 0.5 pu | 3.4 | cable | 1.89% | ok | yes |
