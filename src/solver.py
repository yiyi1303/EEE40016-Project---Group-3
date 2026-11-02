"""Network solver behind one interface, so the study does not depend on which engine runs.

Both backends are built from the same parsed feeder (`feeder_csv.load_feeder`), so the
network is defined once and the engine is an implementation detail. The twin calls
`set_loads`, `solve`, then reads voltages and loadings; it never touches OpenDSS or SINCAL
directly.

    OpenDSSSolver   free, no node limit, in-process. The published reference solution for
                    this feeder is itself an OpenDSS result, so V1 is an exact check.
    SincalSolver    PSS(R)SINCAL over COM. Works, but the Xplore licence on this machine
                    caps simulation at 50 nodes, so it cannot run this feeder.
                    See notes/BLOCKER_licence.md.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feeder_csv import load_feeder  # noqa: E402

PHASE_NODE = {"A": 1, "B": 2, "C": 3}


class SolveError(RuntimeError):
    pass


# --------------------------------------------------------------------------- OpenDSS

class OpenDSSSolver:
    """The feeder in OpenDSS, driven in process."""

    name = "OpenDSS"

    def __init__(self, feeder=None, transformer_kva=None, source_pu=None):
        import opendssdirect as dss
        self.dss = dss
        self.feeder = feeder or load_feeder()
        tx = self.feeder.transformer
        self.transformer_kva = transformer_kva if transformer_kva else tx.mva * 1000.0
        self.source_pu = source_pu if source_pu else self.feeder.source.pu
        self._built = False
        self._load_names = [l.name for l in self.feeder.loads]
        self.ev_names = []
        self.pv_names = []
        self.battery_bus = None

    # -- construction ----------------------------------------------------------

    def dss_script(self):
        """The circuit as OpenDSS commands. Returned rather than run, so it can be saved."""
        f, tx, src = self.feeder, self.feeder.transformer, self.feeder.source
        cmds = ["Clear",
                "New Circuit.EULV bus1=%s basekv=%g pu=%g phases=3 Isc3=%g Isc1=%g"
                % (tx.bus_hv, src.kv, self.source_pu, src.isc3_a, src.isc1_a)]

        for c in f.linecodes.values():
            cmds.append("New Linecode.%s nphases=%d R1=%g X1=%g R0=%g X0=%g C1=%g C0=%g units=km"
                        % (c.name, c.nphases, c.r1, c.x1, c.r0, c.x0, c.c1, c.c0))

        cmds.append(
            "New Transformer.%s phases=3 windings=2 XHL=%g %%loadloss=%g "
            "wdg=1 bus=%s conn=%s kv=%g kva=%g "
            "wdg=2 bus=%s conn=%s kv=%g kva=%g"
            % (tx.name, tx.xhl_percent, tx.r_percent,
               tx.bus_hv, tx.conn_hv.strip().lower(), tx.kv_hv, self.transformer_kva,
               tx.bus_lv, tx.conn_lv.strip().lower(), tx.kv_lv, self.transformer_kva))

        for ln in f.lines:
            cmds.append("New Line.%s bus1=%s bus2=%s phases=3 length=%g units=km linecode=%s"
                        % (ln.name, ln.bus1, ln.bus2, ln.length_km, ln.linecode))

        for ld in f.loads:
            cmds.append(
                "New Load.%s phases=1 bus1=%s.%d kV=%g kW=%g PF=%g model=1 conn=wye "
                "Vminpu=0.8 Vmaxpu=1.2"
                % (ld.name, ld.bus, PHASE_NODE[ld.phase], ld.kv, ld.base_kw, ld.pf))

        cmds += ["Set voltagebases=[%g, %g]" % (tx.kv_hv, tx.kv_lv),
                 "Calcvoltagebases",
                 "Set mode=snapshot",
                 "Set maxcontroliter=100"]
        return cmds

    def build(self):
        for c in self.dss_script():
            self.dss.Text.Command(c)
            err = self.dss.Error.Description()
            if err:
                raise SolveError("OpenDSS rejected %r: %s" % (c[:70], err))
        self._built = True
        return self

    def add_ev_loads(self, ev_connections, pf=1.0):
        """Add a charge point at each given connection, starting at zero kW.

        EV load is kept as a separate element from the house load so the two stay
        separable in results, and so the controller can set charging power without
        touching household demand. Unity power factor: AC charge points present an
        essentially unity-PF load, and AS/NZS 4777.2 governs inverters, not loads.
        """
        if not self._built:
            self.build()
        self.ev_names = []
        for ld in ev_connections:
            name = "EV_%s" % ld.name
            self.dss.Text.Command(
                "New Load.%s phases=1 bus1=%s.%d kV=%g kW=0 PF=%g model=1 conn=wye "
                "Vminpu=0.8 Vmaxpu=1.2"
                % (name, ld.bus, PHASE_NODE[ld.phase], ld.kv, pf))
            err = self.dss.Error.Description()
            if err:
                raise SolveError("could not add %s: %s" % (name, err))
            self.ev_names.append(name)
        self.dss.Text.Command("Calcvoltagebases")
        return self.ev_names

    def set_ev_power(self, kw, only=None):
        """Set charge points to the same kW. This is the equal-share rule, A8.

        `only` restricts the setting to a list of charge points; everything else is set
        to zero, which is how cars that have not arrived yet or are already full are
        represented.
        """
        d = self.dss
        chosen = None if only is None else set(only)
        for name in getattr(self, "ev_names", []):
            d.Loads.Name(name)
            d.Loads.kW(kw if (chosen is None or name in chosen) else 0.0)

    def set_ev_powers(self, kw_by_name):
        """Set charge points individually. Anything omitted is set to zero."""
        d = self.dss
        for name in getattr(self, "ev_names", []):
            d.Loads.Name(name)
            d.Loads.kW(kw_by_name.get(name, 0.0))

    def ev_power_total(self):
        d, total = self.dss, 0.0
        for name in getattr(self, "ev_names", []):
            d.Loads.Name(name)
            total += d.Loads.kW()
        return total

    # -- rooftop PV ------------------------------------------------------------

    def add_pv(self, connections):
        """Rooftop PV at each given connection, on the same phase as the house.

        Modelled as a negative load at unity power factor, which OpenDSS treats as
        generation. Kept separate from the house load so telemetry can report house demand
        and PV output as two readings, as a meter with a separate generation register does.
        """
        if not self._built:
            self.build()
        self.pv_names = []
        for ld in connections:
            name = "PV_%s" % ld.name
            self.dss.Text.Command(
                "New Load.%s phases=1 bus1=%s.%d kV=%g kW=0 PF=1 model=1 conn=wye "
                "Vminpu=0.8 Vmaxpu=1.2" % (name, ld.bus, PHASE_NODE[ld.phase], ld.kv))
            err = self.dss.Error.Description()
            if err:
                raise SolveError("could not add %s: %s" % (name, err))
            self.pv_names.append(name)
        self.dss.Text.Command("Calcvoltagebases")
        return self.pv_names

    # -- the battery -----------------------------------------------------------

    def add_battery(self, bus, kv_ll):
        """A three-phase four-quadrant battery at `bus`, as one element that charges and
        discharges: positive kW charges, negative discharges; negative kvar supplies vars."""
        if not self._built:
            self.build()
        self.dss.Text.Command(
            "New Load.BATTERY phases=3 bus1=%s kV=%g kW=0 kvar=0 model=1 conn=wye "
            "Vminpu=0.8 Vmaxpu=1.2" % (bus, kv_ll))
        err = self.dss.Error.Description()
        if err:
            raise SolveError("could not add the battery: %s" % err)
        self.battery_bus = str(bus)
        return "BATTERY"

    def set_battery(self, p_kw, q_kvar):
        self.dss.Loads.Name("BATTERY")
        self.dss.Loads.kW(p_kw)
        self.dss.Loads.kvar(q_kvar)

    def bus_voltage(self, bus):
        """Mean line-to-neutral voltage across the phases of one bus, in volts."""
        self.dss.Circuit.SetActiveBus(str(bus))
        mags = self.dss.Bus.VMagAngle()[0::2]
        mags = [m for m in mags if m > 0]
        return sum(mags) / len(mags) if mags else 0.0

    # -- driving ---------------------------------------------------------------

    def set_loads(self, kw_by_name):
        """Set active power per load in kW. Reactive power follows each load's power factor.

        Readings named PV_<connection> are PV output, reported as a positive number and
        applied as generation.
        """
        if not self._built:
            self.build()
        d = self.dss
        for name, kw in kw_by_name.items():
            d.Loads.Name(name)
            if d.Loads.Name().lower() != name.lower():
                raise SolveError("no load called %r in the circuit" % name)
            d.Loads.kW(-kw if name.startswith("PV_") else kw)

    def solve(self):
        if not self._built:
            self.build()
        self.dss.Solution.Solve()
        if not self.dss.Solution.Converged():
            raise SolveError("power flow did not converge")
        return True

    # -- results ---------------------------------------------------------------

    def node_voltages(self):
        """{(bus, phase_node): volts} for every energised node, line-to-neutral."""
        names = self.dss.Circuit.AllNodeNames()
        mags = self.dss.Circuit.AllBusVMag()
        out = {}
        for n, v in zip(names, mags):
            bus, _, node = n.partition(".")
            out[(bus.upper(), int(node))] = v
        return out

    def node_voltages_pu(self):
        names = self.dss.Circuit.AllNodeNames()
        pus = self.dss.Circuit.AllBusMagPu()
        out = {}
        for n, v in zip(names, pus):
            bus, _, node = n.partition(".")
            out[(bus.upper(), int(node))] = v
        return out

    def total_load_kw(self):
        p, _ = self.dss.Circuit.TotalPower()      # negative = drawn from the circuit
        return -p

    def transformer_loading_percent(self):
        """Apparent power through the transformer LV winding, as a percent of nameplate."""
        self.dss.Circuit.SetActiveElement("Transformer.%s" % self.feeder.transformer.name)
        powers = self.dss.CktElement.Powers()
        # terminal 2 (LV) occupies the second half of the per-terminal power list
        half = len(powers) // 2
        p = sum(powers[half::2])
        q = sum(powers[half + 1::2])
        return 100.0 * math.hypot(p, q) / self.transformer_kva

    def line_currents(self):
        """{line name: highest phase current in amps}."""
        d, out = self.dss, {}
        for name in d.Lines.AllNames():
            d.Circuit.SetActiveElement("Line.%s" % name)
            c = d.CktElement.CurrentsMagAng()
            half = len(c) // 2
            out[name] = max(c[0:half:2]) if half else 0.0
        return out

    def losses_kw(self):
        return self.dss.Circuit.Losses()[0] / 1000.0


# ---------------------------------------------------------------------------- SINCAL

class SincalSolver:
    """PSS(R)SINCAL over COM. Kept because the model builds and the sequence is proven.

    On this machine the Xplore licence permits 50 nodes for simulation, so solving the
    906-node feeder raises SolveError. Small models work.
    """

    name = "SINCAL"

    def __init__(self, project_files_dir):
        self.files = os.path.abspath(project_files_dir)
        self.db = os.path.join(self.files, "database.db")
        self.sim = None

    def build(self):
        import win32com.client as w
        # Do not call BatchMode: it segfaults the calling process.
        self.sim = w.gencache.EnsureDispatch("Sincal.Simulation")
        self.sim.Init("EN")
        self.sim.DataSource("SQLITE", self.db, "", "")
        return self

    def solve(self, method="LF_USYM"):
        """Run a load flow. LF_USYM is SINCAL's unbalanced (per-phase) load flow and is the
        one that matches OpenDSS here: the feeder's 55 loads are single-phase. Plain "LF" is
        the balanced load flow and writes a symmetrical answer to LFNodeResult instead."""
        if self.sim is None:
            self.build()
        self.method = method
        self.sim.Start(method)
        if self.sim.StatusID != 1101:
            raise SolveError("%s: %s" % (self.sim.StatusText, self.last_error() or "no detail"))
        return True

    def last_error(self):
        """The real reason lives in the log database, not in StatusText."""
        import sqlite3
        log = os.path.join(self.files, "LOG", "Log.001.db")
        if not os.path.exists(log):
            return None
        con = sqlite3.connect("file:%s?mode=ro" % log.replace("\\", "/"), uri=True)
        rows = con.execute("select Text from LogMsg where LogLevel >= 30 "
                           "order by LogMsg_ID").fetchall()
        con.close()
        return "; ".join(r[0] for r in rows) or None

    def node_voltages(self):
        """{(bus, phase_node): volts} line-to-earth, the same shape as OpenDSSSolver's."""
        return read_sincal_voltages(self.db)


def read_sincal_voltages(db):
    """Per-phase node voltages from a solved SINCAL database, in volts line-to-earth.

    Reads ULFNodeResult, which only the unbalanced load flow (LF_USYM) fills. U1..U3 are kV
    phase-to-earth. Raises if the database holds only a balanced result, because comparing
    a balanced answer against an unbalanced feeder would look like a model error.
    """
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % os.path.abspath(db).replace("\\", "/"),
                          uri=True)
    try:
        rows = con.execute("select n.Name, r.U1, r.U2, r.U3 from ULFNodeResult r "
                           "join Node n using (Node_ID)").fetchall()
        if not rows:
            n_bal = con.execute("select count(*) from LFNodeResult").fetchone()[0]
            raise SolveError("no unbalanced load-flow result in %s%s" % (
                db, " (only a balanced LF result: rerun as unbalanced, LF_USYM)"
                if n_bal else ""))
    finally:
        con.close()
    out = {}
    for name, *u in rows:
        for node, kv in zip((1, 2, 3), u):
            if kv and kv > 0:
                out[(str(name).upper(), node)] = kv * 1000.0
    return out


def get_solver(engine="opendss", **kw):
    if engine.lower() in ("opendss", "dss"):
        return OpenDSSSolver(**kw).build()
    if engine.lower() == "sincal":
        return SincalSolver(**kw).build()
    raise ValueError("unknown engine %r" % engine)
