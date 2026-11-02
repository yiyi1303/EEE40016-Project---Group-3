# Importer — open items

The importer builds a structurally valid model and both cases pass `tests/check_model.py`.
These four things are either assumed or missing, and each needs settling before V1 can be
trusted. Listed worst first.

## 1. The package has no cable current ratings — blocks one of the four constraints

`LineCodes.csv` gives R1, X1, R0, X0 and C only. There is no ampacity anywhere in the
published package, so `Line.Ith` is written as 0 and SINCAL will not flag a single cable
overload. All 905 lines are in this state.

That matters because "cable current above rating" is one of the four constraints the study
enforces, and D1 in the data plan claims equipment ratings come from the feeder package.
They do not.

Two ways forward:

- **Derive ratings from the conductor size in the line code names.** The names encode it:
  `4c_70` is four-core 70 mm², `2c_16` is two-core 16 mm², `4c_.06` is 0.06 in² and so on.
  A current rating per size from AS/NZS 3008.1.1 would give defensible numbers, recorded as
  a new assumption.
- **Drop cable current** from the enforced set and say why, leaving voltage, transformer
  loading, hot-spot and unbalance.

Deriving them is the better option: on a feeder of 1.4 km total length with 16 mm² service
cable, current is plausibly the second binding constraint after voltage, and losing it would
weaken the result.

## 2. Transformer vector group is assumed

`Transformer.csv` says Delta primary, Wye secondary, and the header comment says the star
point is earthed. That is Dyn, but the clock number is not stated. The importer writes
`VecGrp=11` (Dyn11), which is the normal Australian and European distribution arrangement
and matches the 30 degree shift OpenDSS applies by default.

Check it in the SINCAL UI once the project opens. It changes phase angles, not magnitudes,
so V1 on voltage magnitudes would pass either way — which is exactly why it is worth
checking deliberately rather than assuming V1 covers it.

## 3. No diagram

Nothing is written to the `Graphic*` tables, so the project will solve but open with an
empty diagram. `Buscoords.csv` has coordinates for all 906 buses, so this is a
straightforward addition once the electrical model is confirmed.

Worth doing before anyone else has to look at the model, and worth skipping until V1 passes.

## 4. Grid short-circuit power is derived, not given

`Source.csv` gives Isc3 = 3000 A at 11 kV, which the importer converts to
Sk = sqrt(3) x 11 kV x 3000 A = 57.16 MVA, with R/X assumed 0.1. The package also lists
Isc1 = 5 A, which is unusually low for a single-phase fault and suggests a deliberately weak
earth path. The importer does not currently represent that.

Low priority: at 57 MVA behind an 800 kVA transformer the source is stiff enough that it has
little influence on LV voltages, which is what V1 measures.

## Confirmed along the way

- Minute 566 of the load profiles is 09:26, and the 55 loads sum to 57.36 kW there. That is
  the whole-day peak of the aggregate demand, which is consistent with the published
  snapshot being labelled "on peak".
- Load profile values are actual kW, not multipliers: `LoadShapes.csv` sets
  `useactual=TRUE` and `Loads.csv` sets `kW=1` on every load.
- `Load.P` in SINCAL is MW, so profile kW is divided by 1000 on the way in.
