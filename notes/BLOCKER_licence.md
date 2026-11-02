# Blocker: the SINCAL licence caps simulation at 50 nodes

Found 28 Sep 2026 while running the first load flow.

## What happened

The engine loaded the model without a single data complaint:

    Loading table "Node" succeeded! Loaded records: 907
    Loading table "Element" succeeded! Loaded records: 962
    Loading table "Terminal" succeeded! Loaded records: 1868
    Loading table "Infeeder" succeeded! Loaded records: 1
    Loading table "TwoWindingTransformer" succeeded! Loaded records: 1
    Loading table "Load" succeeded! Loaded records: 55
    Loading table "Line" succeeded! Loaded records: 905

then refused to solve:

    There are 907 license-relevant nodes. Only 50 nodes are permitted for Simulation
    Simulation finished with errors

## Why

The installed licence is **PSS SINCAL Xplore**, the free evaluation licence
(`License/license_usr.bin`; the ReadMe describes it as usable on any PC for up to nine
months after release). It is node-limited. The IEEE European LV Test Feeder has 906 nodes
plus the 11 kV source bus.

Lab 1 has 10 nodes, which is why coursework runs fine and this does not.

## What this does and does not mean

The importer is fine. SINCAL parsed every table we wrote and objected to none of it, which
is a stronger check on the schema work than the structural tests were. The toolchain is
fine too: the same COM sequence solves a 10-node model in 0.05 s.

The only problem is model size against licence.

## Options

1. **Get a teaching licence from Swinburne.** The unit teaches SINCAL, so a lab or campus
   licence may exist with a higher node limit. Costs nothing to ask and changes nothing
   else. Ask the convener or the lab technician.
2. **Reduce the network below 50 nodes.** There is a published reduced equivalent of this
   exact feeder (IEEE DataPort, "A Reduced Electrically-Equivalent Model of the IEEE
   European Low Voltage Test Feeder"), which keeps the load nodes and renumbers them. With
   55 customer loads it will still exceed 50 nodes, so this probably does not rescue the
   Xplore limit on its own. Aggregating customers further would destroy the per-customer
   voltage detail the study measures.
3. **Solve with OpenDSS instead.** Free, no node limit, and the feeder is published
   natively for it. The reference solution used for V1 is itself an OpenDSS result, so V1
   would become an exact check rather than a cross-tool comparison. Against it: the
   submitted plan names SINCAL, though criterion C6 in that plan explicitly weighs licence
   availability, so a documented change is defensible.

## Recommended sequencing

Ask about the licence now, and in the meantime keep the solver behind a thin interface so
everything else — the constraint evaluation, the envelope bisection, the sweep runner —
can be built and validated without waiting on the answer. That work is the same either way.

## COM sequence that works (for the driver)

    sim = win32com.client.gencache.EnsureDispatch("Sincal.Simulation")
    sim.Init("EN")
    sim.DataSource("SQLITE", <path to database.db>, "", "")
    sim.Start("LF")
    sim.StatusID    # 1101 solved, 1102 finished with errors

Two traps found the hard way:

- `BatchMode(1)` segfaults the calling process. Do not call it.
- `Database(<files dir>)` loads but reports errors; `DataSource("SQLITE", <database.db>)`
  is the one that works.
- Messages land in `LOG/Log.001.db`, table `LogMsg`. Read it after every run; `StatusText`
  alone will not tell you why something failed.
