# Feeder package validation

Source: `data/feeder/European_LV_CSV`, read by `src/feeder_csv.py`.

## Facts

| Quantity | Value |
| --- | --- |
| buses | 906 |
| lines | 905 |
| loads | 55 |
| line codes defined | 10 |
| line codes used | 10 |
| total line length (km) | 1.4315 |
| shortest line (m) | 0.034 |
| longest line (m) | 11.977 |
| bus number range | 1..906 |
| islands | 1 |
| closed loops | 0 |
| loads per phase | A=21, B=19, C=15 |
| buses without coordinates | 0 |
| transformer | TR1, 800 kVA, 11/0.416 kV, Delta-Wye, XHL 4.0% |
| source | 11 kV at 1.05 pu, Isc3 3000 A |

## Checks

All structural checks passed. The package is safe to import:

- every referenced line code is defined
- bus numbers form one contiguous block
- every load sits on a bus that exists, and has a load profile
- the feeder is connected, radial, and has the right branch count
- the transformer LV terminal is on the feeder
- every load is single-phase, as the unbalanced model assumes

## Units after parsing

| Quantity | Unit |
| --- | --- |
| line length | km (converted from the package's metres) |
| line R, X | ohm/km |
| transformer rating | MVA |
| load base power | kW, scaled by its one-minute profile |
| load voltage | kV, phase to neutral |

