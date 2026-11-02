"""Build a PSS(R)SINCAL project for the IEEE European LV Test Feeder.

906 nodes and 905 lines is too many to draw, so this writes rows straight into SINCAL's
SQLite database. A known-good project built by SINCAL itself is used as the template, so
all the defaults, settings and system tables come from SINCAL rather than from guesswork;
only the model tables are cleared and rewritten.

How SINCAL stores a model, as read out of the template (see notes/sincal_schema.md):

    Element                 one row per device. Element_ID is the key, Type names the kind.
    Line / Load / ...       the detail for that device, sharing the same Element_ID.
    Terminal                joins an Element_ID to a Node_ID with a TerminalNo.
    Node                    the buses.

Phase connection lives in Terminal.Flag_Terminal as a code, not a bitmask (SINCAL Database
Description, Terminal): 1=L1, 2=L2, 3=L3, 4=L12, 5=L23, 6=L31, 7=L123, 8=N. That is how the 55
single-phase loads attach to a three-phase feeder. An earlier version treated it as a bitmask
and wrote 4 for phase C, which SINCAL reads as a load between L1 and L2; the reduced-feeder
cross-check (tools/sincal_subset_check.py) caught it.

Run:  py src/build_sincal_model.py --case benchmark
      py src/build_sincal_model.py --case study
"""
import argparse
import json
import math
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feeder_csv import load_feeder, check  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EEE = os.path.dirname(HERE)
TEMPLATE_SIN = os.path.join(EEE, "Lab1.sin")
TEMPLATE_DIR = os.path.join(EEE, "Lab1_files")
CONFIG = os.path.join(HERE, "config", "study.json")
MODELS = os.path.join(HERE, "models")

PHASE_CODE = {"A": 1, "B": 2, "C": 3}     # Terminal.Flag_Terminal: L1, L2, L3
ALL_PHASES = 7                             # L123
DYN11 = 59                                 # TwoWindingTransformer.VecGrp (11 is DZ1)

# System tables that carry SINCAL's own settings. Everything else populated in the
# template is model or results, and gets cleared.
KEEP = {"CalcParameter", "EcoCurrency", "FeederParameter", "GlobalSetting",
        "GraphicAreaTile", "GraphicLayer", "GraphicObjectType", "NetworkGroup",
        "RelParameter", "Variant", "Version", "VoltageLevel"}


# --------------------------------------------------------------------- project scaffold

def new_project(name):
    """Copy the template project to models/<name>.sin and return the database path."""
    os.makedirs(MODELS, exist_ok=True)
    sin = os.path.join(MODELS, name + ".sin")
    files = os.path.join(MODELS, name + "_files")
    if os.path.exists(files):
        shutil.rmtree(files)
    shutil.copyfile(TEMPLATE_SIN, sin)
    shutil.copytree(TEMPLATE_DIR, files)

    db = os.path.join(files, "database.db")
    # the ini carries an absolute path to the database; point it at our copy
    ini = os.path.join(files, "database.ini")
    with open(ini, encoding="utf-8") as f:
        text = f.read()
    out = []
    for line in text.splitlines():
        out.append("FILE=" + db if line.upper().startswith("FILE=") else line)
    with open(ini, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    # results from the template model are meaningless here
    for sub in ("DBG", "LOG"):
        d = os.path.join(files, sub)
        for fn in os.listdir(d) if os.path.isdir(d) else []:
            if not fn.lower().endswith(".db"):
                os.remove(os.path.join(d, fn))
    return sin, db


def clear_model(con):
    """Empty every model and result table, leaving SINCAL's own settings alone."""
    tables = [r[0] for r in con.execute(
        "select name from sqlite_master where type='table'")]
    cleared = 0
    for t in tables:
        if t in KEEP:
            continue
        n = con.execute("select count(*) from [%s]" % t).fetchone()[0]
        if n:
            con.execute("delete from [%s]" % t)
            cleared += n
    return cleared


# ------------------------------------------------------------------------- row writers

class Builder:
    def __init__(self, con):
        self.con = con
        self.eid = 0
        self.tid = 0
        self.nid = 0
        self.node_of = {}      # feeder bus label -> Node_ID

    def _insert(self, table, values):
        cols = ", ".join("[%s]" % k for k in values)
        marks = ", ".join("?" * len(values))
        self.con.execute("insert into [%s] (%s) values (%s)" % (table, cols, marks),
                         list(values.values()))

    def voltage_levels(self, levels):
        """Rewrite the template's voltage levels in place, keeping every other column."""
        existing = [r[0] for r in self.con.execute(
            "select VoltLevel_ID from VoltageLevel order by VoltLevel_ID")]
        if len(existing) < len(levels):
            raise RuntimeError("template has %d voltage levels, need %d"
                               % (len(existing), len(levels)))
        for vid, (name, un) in zip(existing, levels):
            self.con.execute(
                "update VoltageLevel set Name=?, ShortName=?, Un=?, f=? where VoltLevel_ID=?",
                (name, name, un, 50.0, vid))
        # drop any spare levels the template had
        for vid in existing[len(levels):]:
            self.con.execute("delete from VoltageLevel where VoltLevel_ID=?", (vid,))
        return {name: vid for (name, _), vid in zip(levels, existing)}

    def node(self, label, volt_level_id, un_kv, busbar=False):
        self.nid += 1
        self._insert("Node", {
            "Node_ID": self.nid, "Variant_ID": 1, "Flag_Variant": 1, "Flag_Private": 0,
            "Name": str(label), "ShortName": str(label)[:20],
            "VoltLevel_ID": volt_level_id, "Group_ID": 1,
            "Flag_Type": 2 if busbar else 1, "Flag_Pos": 2,
            "Un": un_kv, "Flag_Phase": ALL_PHASES, "tkr": 1.0, "Flag_VERP": 1,
            "Report_No": 1,
        })
        self.node_of[str(label)] = self.nid
        return self.nid

    def element(self, type_name, name, volt_level_id, zero_sequence=False):
        """One Element row. Flag_Input is a bitmask of the data pages the element has filled
        in: 1 basic, 2 load flow, 4 zero-phase sequence. SINCAL ignores an element's r0/x0 or
        Z0/Z1 unless the 4 bit is set, and quietly uses the global zero-sequence mode
        instead; every SINCAL sample with zero-sequence data on a line carries 7."""
        self.eid += 1
        self._insert("Element", {
            "Element_ID": self.eid, "Variant_ID": 1, "Flag_Variant": 1,
            "Type": type_name, "Flag_Input": 7 if zero_sequence else 3, "Flag_Calc": 0,
            "Flag_Private": 0,
            "Flag_State": 1, "Name": name, "ShortName": name[:20],
            "VoltLevel_ID": volt_level_id, "Group_ID": 1,
            "fCe": 1.0, "fAkt": 1.0, "Metered": 0, "Report_No": 1,
        })
        return self.eid

    def terminal(self, element_id, node_id, no, phases=ALL_PHASES):
        self.tid += 1
        self._insert("Terminal", {
            "Terminal_ID": self.tid, "Variant_ID": 1, "Flag_Variant": 1,
            "Element_ID": element_id, "Node_ID": node_id, "TerminalNo": no,
            "Flag_State": 1, "Flag_Switch": 0, "Flag_Terminal": phases,
            "Flag_Obs": 0, "Flag_Cur": 0, "Report_No": 1,
        })
        return self.tid

    # -- devices ---------------------------------------------------------------

    def infeeder(self, node_id, volt_level_id, un_kv, sk_mva, r_over_x, u_percent):
        eid = self.element("Infeeder", "GRID", volt_level_id)
        self._insert("Infeeder", {
            "Element_ID": eid, "Variant_ID": 1, "Flag_Variant": 1,
            "Flag_Typ": 2, "Sk2": sk_mva, "R_X": r_over_x, "cact": 1.0,
            "Sk2max": sk_mva, "R_Xmax": r_over_x, "cmax": 1.1,
            "Sk2min": sk_mva, "R_Xmin": r_over_x, "cmin": 1.0,
            "Flag_Z0_Input": 1, "Flag_Lf": 3,          # 3 = slack: holds voltage and angle
            "u": u_percent, "u1": u_percent, "u2": u_percent, "u3": u_percent,
            "delta1": -30.0, "delta2": -150.0, "delta3": 90.0,
            "cosphi": 1.0, "fP": 1.0, "fQ": 1.0, "fS": 1.0, "fI": 1.0,
            "ull": 90.0, "uul": 110.0, "Flag_Har": 1, "qr": 1.0, "Flag_ZUP": 3,
        })
        self.terminal(eid, node_id, 1)
        return eid

    def transformer(self, name, node_hv, node_lv, volt_level_id, tx, sn_mva):
        eid = self.element("TwoWindingTransformer", name, volt_level_id, zero_sequence=True)
        self._insert("TwoWindingTransformer", {
            "Element_ID": eid, "Variant_ID": 1, "Flag_Variant": 1,
            "Un1": tx.kv_hv, "Un2": tx.kv_lv, "Sn": sn_mva,
            # uk is the short-circuit impedance magnitude; the package gives reactance (XHL)
            # and resistance separately, as OpenDSS takes them
            "uk": math.hypot(tx.xhl_percent, tx.r_percent), "Flag_ur": 1, "ur": tx.r_percent,
            "VecGrp": DYN11,                  # delta HV, earthed star LV
            # zero sequence seen from the earthed star equals the leakage impedance, which is
            # how OpenDSS treats a Dyn unit
            "Flag_Z0_Input": 1, "Z0_Z1": 1.0,
            "R0_X0": tx.r_percent / tx.xhl_percent if tx.xhl_percent else 0.0,
            "Flag_Lf": 1, "Flag_ConNode": 1, "Flag_roh": 1,
            "Flag_Ph": 8, "ull": 90.0, "uul": 110.0, "Flag_CompNode": 2,
            "Flag_Har": 1, "qr": 1.0, "tctrl_dyn": 300.0, "cosphiG": 0.9,
            "Flag_ZUP": 3, "Flag_Damage": 1, "c": 1.1, "UGmax": 100.0, "Flag_Side": 1,
        })
        self.terminal(eid, node_hv, 1)
        self.terminal(eid, node_lv, 2)
        # No neutral-point record: the N in DYN11 earths the LV star solidly, which is how
        # OpenDSS grounds a wye winding by default (checked: adding RE = XE = 0 changes nothing)
        return eid

    def line(self, ln, code, volt_level_id, un_kv):
        eid = self.element("Line", ln.name, volt_level_id, zero_sequence=True)
        self._insert("Line", {
            "Element_ID": eid, "Variant_ID": 1, "Flag_Variant": 1,
            "Flag_LineTyp": 1,                 # cable (2 would be overhead line)
            "Un": un_kv, "l": ln.length_km, "ParSys": 1.0,
            "r": code.r1, "x": code.x1, "c": code.c1,
            # Flag_Z0_Input 2: r0 and x0 in ohm/km. 1 would read the ratio fields r0/r1 and
            # x0/x1 instead, which are left at 0, giving every cable zero Z0
            "Flag_Cond": 1, "Flag_Z0_Input": 2, "r0": code.r0, "x0": code.x0, "c0": code.c0,
            "fn": 50.0, "Flag_Vart": 1, "Ith": 0.0,   # see notes: package carries no ratings
            "fr": 1.0, "Flag_Har": 1, "qr": 1.0, "Flag_ESB": 1, "Flag_ZUP": 3,
            "fIk": 1.0, "Flag_Lf": 1,
        })
        self.terminal(eid, self.node_of[str(ln.bus1)], 1)
        self.terminal(eid, self.node_of[str(ln.bus2)], 2)
        return eid

    def load(self, ld, volt_level_id, p_kw, pf):
        eid = self.element("Load", ld.name, volt_level_id)
        q_kvar = p_kw * math.tan(math.acos(pf))
        self._insert("Load", {
            "Element_ID": eid, "Variant_ID": 1, "Flag_Variant": 1,
            "Flag_Typified": 1, "Flag_Load": 1, "Flag_LoadType": 2,
            "Flag_Lf": 1,                       # P and Q given directly
            "P": p_kw / 1000.0, "Q": q_kvar / 1000.0,   # SINCAL works in MW / Mvar
            "u": 100.0, "Flag_Voltage": 1, "cosphi": pf,
            "fP": 1.0, "fQ": 1.0, "fS": 1.0, "fI": 1.0,
            "fEapcon": 1.0, "fErpcon": 1.0, "fE": 1.0, "fEap": 1.0, "fErp": 1.0,
            "Flag_Z0_Input": 1, "Flag_Measure": 1,
            "cos_phi_imax": 0.95, "cos_phi_imin": 0.75,
            "Flag_Har": 1, "qr": 1.0, "Flag_I": 1, "Flag_LP": 3, "CustCnt": 1,
            "Flag_Z0": 1,
        })
        # L1, L2 or L3 alone is "1-phase between Lx and ground" (SINCAL Input Data manual),
        # the same as OpenDSS's bus.n to node 0
        self.terminal(eid, self.node_of[str(ld.bus)], 1, PHASE_CODE[ld.phase])
        return eid


# ------------------------------------------------------------------------------- build

_PROFILES = {}


def _profile(path):
    """Every minute of one load profile, read from disk once per process.

    Re-reading the file on every call cost three quarters of a sweep's run time once
    telemetry was sampled every minute: 23,000 file reads per simulated evening. Parsing is
    unchanged, so the numbers are identical.
    """
    if path not in _PROFILES:
        with open(path, encoding="utf-8-sig") as f:
            rows = [r.strip() for r in f if r.strip()]
        if rows and not rows[0][0].isdigit() and rows[0][0] not in "-.":
            rows = rows[1:]                    # skip a header if the file has one
        _PROFILES[path] = [float(r.split(",")[-1]) for r in rows]
    return _PROFILES[path]


def profile_kw(project_dir, shape_file, minute):
    """Read one minute out of a load profile. Files are one value per line, kW."""
    path = os.path.join(project_dir, "data", "feeder", "European_LV_CSV",
                        "Load Profiles", shape_file)
    values = _profile(path)
    if not 1 <= minute <= len(values):
        raise ValueError("minute %d outside profile %s (%d points)"
                         % (minute, shape_file, len(values)))
    return values[minute - 1]


def build(case_name, minute, feeder=None, name=None, load_kw=None):
    """Write the case into a fresh SINCAL project.

    feeder and load_kw let a caller hand in a reduced feeder and its loads (the cross-check
    in tools/sincal_subset_check.py does this to stay under the Xplore 50-node cap). By
    default the full package is used with the load profiles at the given minute.
    """
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    case = cfg["cases"][case_name]

    if feeder is None:
        feeder = load_feeder()
        problems, _ = check(feeder)
        if problems:
            raise SystemExit("feeder package failed validation; run src/feeder_csv.py")

    sn_mva = case["transformer_kva"] / 1000.0
    source_pu = case.get("source_pu", feeder.source.pu)
    name = name or "EULV_" + case_name
    sin, db = new_project(name)

    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys=OFF")
    cleared = clear_model(con)

    b = Builder(con)
    hv_name = "%g kV" % feeder.transformer.kv_hv
    lv_name = "%g kV" % feeder.transformer.kv_lv
    lv = {}
    lv = b.voltage_levels([(hv_name, feeder.transformer.kv_hv),
                           (lv_name, feeder.transformer.kv_lv)])

    # HV source bus, then every LV bus in the package
    src_node = b.node(feeder.transformer.bus_hv, lv[hv_name], feeder.transformer.kv_hv,
                      busbar=True)
    for bus in sorted(feeder.buses):
        b.node(bus, lv[lv_name], feeder.transformer.kv_lv,
               busbar=(bus == feeder.transformer.bus_lv))

    # grid infeed. Sk from the package's three-phase fault current at 11 kV
    sk_mva = math.sqrt(3) * feeder.source.kv * feeder.source.isc3_a / 1000.0
    b.infeeder(src_node, lv[hv_name], feeder.source.kv, sk_mva, 0.1, source_pu * 100.0)

    b.transformer(feeder.transformer.name, src_node,
                  b.node_of[str(feeder.transformer.bus_lv)], lv[hv_name],
                  feeder.transformer, sn_mva)

    for ln in feeder.lines:
        b.line(ln, feeder.linecodes[ln.linecode], lv[lv_name], feeder.transformer.kv_lv)

    total_kw = 0.0
    for ld in feeder.loads:
        kw = load_kw[ld.name] if load_kw else profile_kw(HERE, feeder.shapes[ld.shape], minute)
        total_kw += kw
        b.load(ld, lv[lv_name], kw, ld.pf)

    con.commit()

    counts = {t: con.execute("select count(*) from [%s]" % t).fetchone()[0]
              for t in ("Node", "Element", "Terminal", "Line", "Load",
                        "TwoWindingTransformer", "Infeeder")}
    con.close()

    return {"project": sin, "database": db, "case": case_name,
            "transformer_kva": case["transformer_kva"], "source_pu": source_pu,
            "minute": minute,
            "total_load_kw": round(total_kw, 2), "rows_cleared": cleared,
            "counts": counts, "sk_mva": round(sk_mva, 2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", default="benchmark", choices=("benchmark", "study"))
    ap.add_argument("--minute", type=int, default=566,
                    help="minute of the load profiles to set (566 is the published on-peak "
                         "snapshot used for V1)")
    a = ap.parse_args()

    r = build(a.case, a.minute)
    print("case              %s" % r["case"])
    print("transformer       %d kVA" % r["transformer_kva"])
    print("source            %.2f pu" % r["source_pu"])
    print("load minute       %d  (total %.2f kW)" % (r["minute"], r["total_load_kw"]))
    print("grid Sk           %.2f MVA" % r["sk_mva"])
    print("template rows cleared %d" % r["rows_cleared"])
    for k, v in r["counts"].items():
        print("  %-24s %d" % (k, v))
    print("\nproject  %s" % r["project"])


if __name__ == "__main__":
    main()
