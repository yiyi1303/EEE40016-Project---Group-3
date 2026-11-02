"""Read the IEEE European LV Test Feeder CSV package and check it before import.

This is step one of the importer. It turns the published package into plain Python
objects with SI units, and refuses to hand anything on unless the data passes a set of
structural checks. Getting a unit or a bus reference wrong here would surface later as a
failed V1 with no obvious cause, so the checks are deliberately fussy.

Run:  py src/feeder_csv.py
Out:  notes/feeder_validation.md
"""
import csv
import os
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(HERE, "data", "feeder", "European_LV_CSV")
REPORT = os.path.join(HERE, "notes", "feeder_validation.md")


@dataclass
class LineCode:
    name: str
    nphases: int
    r1: float          # ohm/km, positive sequence
    x1: float
    r0: float          # ohm/km, zero sequence
    x0: float
    c1: float          # nF/km
    c0: float


@dataclass
class Line:
    name: str
    bus1: int
    bus2: int
    phases: str
    length_km: float
    linecode: str


@dataclass
class Load:
    name: str
    bus: int
    phase: str         # 'A', 'B' or 'C'
    kv: float          # phase to neutral
    base_kw: float
    pf: float
    shape: str


@dataclass
class Transformer:
    name: str
    bus_hv: str
    bus_lv: int
    kv_hv: float
    kv_lv: float
    mva: float
    conn_hv: str
    conn_lv: str
    xhl_percent: float
    r_percent: float


@dataclass
class Source:
    kv: float
    pu: float
    isc3_a: float
    isc1_a: float


@dataclass
class Feeder:
    source: Source
    transformer: Transformer
    linecodes: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)
    loads: list = field(default_factory=list)
    coords: dict = field(default_factory=dict)
    shapes: dict = field(default_factory=dict)

    @property
    def buses(self):
        b = {l.bus1 for l in self.lines} | {l.bus2 for l in self.lines}
        return b | {self.transformer.bus_lv}


# --------------------------------------------------------------------------- reading

def _rows(path):
    """Yield dict rows, skipping the '#' comment lines the package puts above headers."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    for row in csv.DictReader(lines):
        yield {(k or "").strip(): (v or "").strip() for k, v in row.items()}


def _read_source(path):
    vals = {}
    with open(path, encoding="utf-8-sig") as f:
        for ln in f:
            ln = ln.strip()
            if "=" in ln and not ln.startswith("#"):
                k, v = ln.split("=", 1)
                vals[k.strip().lower()] = v.strip()

    def num(s):
        return float("".join(c for c in s if c.isdigit() or c in ".-"))

    return Source(kv=num(vals["voltage"]), pu=num(vals["pu"]),
                  isc3_a=num(vals["isc3"]), isc1_a=num(vals["isc1"]))


TO_KM = {"m": 1e-3, "km": 1.0, "ft": 3.048e-4, "mi": 1.609344}


def load_feeder(csv_dir=CSV_DIR):
    src = _read_source(os.path.join(csv_dir, "Source.csv"))

    t = next(_rows(os.path.join(csv_dir, "Transformer.csv")))
    tx = Transformer(name=t["Name"], bus_hv=t["bus1"], bus_lv=int(t["bus2"]),
                     kv_hv=float(t["kV_pri"]), kv_lv=float(t["kV_sec"]),
                     mva=float(t["MVA"]), conn_hv=t["Conn_pri"], conn_lv=t["Conn_sec"],
                     xhl_percent=float(t["%XHL"]), r_percent=float(t["% resistance"]))

    codes = {}
    for r in _rows(os.path.join(csv_dir, "LineCodes.csv")):
        if r["Units"].lower() != "km":
            raise ValueError("line code %s is in %s, expected ohm/km" % (r["Name"], r["Units"]))
        codes[r["Name"]] = LineCode(r["Name"], int(r["nphases"]), float(r["R1"]), float(r["X1"]),
                                    float(r["R0"]), float(r["X0"]), float(r["C1"]), float(r["C0"]))

    lines = []
    for r in _rows(os.path.join(csv_dir, "Lines.csv")):
        u = r["Units"].lower()
        if u not in TO_KM:
            raise ValueError("line %s has unknown length unit %r" % (r["Name"], r["Units"]))
        lines.append(Line(r["Name"], int(r["Bus1"]), int(r["Bus2"]), r["Phases"],
                          float(r["Length"]) * TO_KM[u], r["LineCode"]))

    loads = []
    for r in _rows(os.path.join(csv_dir, "Loads.csv")):
        if int(r["Model"]) != 1:
            raise ValueError("%s is model %s; only constant PQ (model 1) is handled"
                             % (r["Name"], r["Model"]))
        loads.append(Load(r["Name"], int(r["Bus"]), r["phases"], float(r["kV"]),
                          float(r["kW"]), float(r["PF"]), r["Yearly"]))

    coords = {int(r["Busname"]): (float(r["x"]), float(r["y"]))
              for r in _rows(os.path.join(csv_dir, "Buscoords.csv"))}

    shapes = {r["Name"]: r["File"] for r in _rows(os.path.join(csv_dir, "LoadShapes.csv"))}

    return Feeder(src, tx, codes, lines, loads, coords, shapes)


# ------------------------------------------------------------------------ validation

def check(f):
    """Return (list of problems, dict of facts). Empty problem list means safe to import."""
    problems, facts = [], {}
    buses = f.buses

    facts["buses"] = len(buses)
    facts["lines"] = len(f.lines)
    facts["loads"] = len(f.loads)
    facts["line codes defined"] = len(f.linecodes)
    facts["line codes used"] = len({l.linecode for l in f.lines})
    facts["total line length (km)"] = round(sum(l.length_km for l in f.lines), 4)
    facts["shortest line (m)"] = round(min(l.length_km for l in f.lines) * 1000, 3)
    facts["longest line (m)"] = round(max(l.length_km for l in f.lines) * 1000, 3)

    # every line code referenced must exist
    missing = {l.linecode for l in f.lines} - set(f.linecodes)
    if missing:
        problems.append("line codes referenced but not defined: %s" % ", ".join(sorted(missing)))

    # bus numbering should be a contiguous block, which keeps the id mapping trivial
    lo, hi = min(buses), max(buses)
    if hi - lo + 1 != len(buses):
        problems.append("bus numbers are not contiguous: %d..%d but only %d distinct"
                        % (lo, hi, len(buses)))
    facts["bus number range"] = "%d..%d" % (lo, hi)

    # loads must sit on buses that exist
    orphan = [l.name for l in f.loads if l.bus not in buses]
    if orphan:
        problems.append("loads on buses that do not exist: %s" % ", ".join(orphan[:10]))

    # the feeder should be a connected radial tree: n nodes, n-1 branches, no islands
    parent = {b: b for b in buses}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    loops = 0
    for l in f.lines:
        a, b = find(l.bus1), find(l.bus2)
        if a == b:
            loops += 1
        else:
            parent[a] = b
    islands = len({find(b) for b in buses})
    facts["islands"] = islands
    facts["closed loops"] = loops
    if islands != 1:
        problems.append("feeder is not connected: %d separate islands" % islands)
    if loops:
        problems.append("feeder is not radial: %d closed loop(s)" % loops)
    if len(f.lines) != len(buses) - 1:
        problems.append("expected %d lines for a radial tree of %d buses, found %d"
                        % (len(buses) - 1, len(buses), len(f.lines)))

    # the transformer's LV terminal must be the head of the feeder
    if f.transformer.bus_lv not in buses:
        problems.append("transformer LV bus %s is not on the feeder" % f.transformer.bus_lv)

    # phase split, and the single-phase load assumption the twin relies on
    by_phase = {}
    for l in f.loads:
        by_phase[l.phase] = by_phase.get(l.phase, 0) + 1
    facts["loads per phase"] = ", ".join("%s=%d" % kv for kv in sorted(by_phase.items()))
    odd = [l.name for l in f.loads if len(l.phase) != 1]
    if odd:
        problems.append("loads that are not single-phase: %s" % ", ".join(odd[:10]))

    # every load needs a profile
    noshape = [l.name for l in f.loads if l.shape not in f.shapes]
    if noshape:
        problems.append("loads with no matching load shape: %s" % ", ".join(noshape[:10]))

    # coordinates, needed only for the diagram
    nocoord = [b for b in buses if b not in f.coords]
    facts["buses without coordinates"] = len(nocoord)

    # sanity on the nameplate we are about to re-rate
    facts["transformer"] = "%s, %.0f kVA, %g/%g kV, %s-%s, XHL %.1f%%" % (
        f.transformer.name, f.transformer.mva * 1000, f.transformer.kv_hv,
        f.transformer.kv_lv, f.transformer.conn_hv, f.transformer.conn_lv,
        f.transformer.xhl_percent)
    facts["source"] = "%g kV at %.2f pu, Isc3 %.0f A" % (f.source.kv, f.source.pu, f.source.isc3_a)

    return problems, facts


def main():
    f = load_feeder()
    problems, facts = check(f)

    out = ["# Feeder package validation", "",
           "Source: `data/feeder/European_LV_CSV`, read by `src/feeder_csv.py`.", "",
           "## Facts", "", "| Quantity | Value |", "| --- | --- |"]
    out += ["| %s | %s |" % (k, v) for k, v in facts.items()]
    out += ["", "## Checks", ""]
    if problems:
        out += ["**%d problem(s) found.** Do not import until these are resolved." % len(problems), ""]
        out += ["- %s" % p for p in problems]
    else:
        out += ["All structural checks passed. The package is safe to import:", "",
                "- every referenced line code is defined",
                "- bus numbers form one contiguous block",
                "- every load sits on a bus that exists, and has a load profile",
                "- the feeder is connected, radial, and has the right branch count",
                "- the transformer LV terminal is on the feeder",
                "- every load is single-phase, as the unbalanced model assumes"]
    out += ["", "## Units after parsing", "",
            "| Quantity | Unit |", "| --- | --- |",
            "| line length | km (converted from the package's metres) |",
            "| line R, X | ohm/km |",
            "| transformer rating | MVA |",
            "| load base power | kW, scaled by its one-minute profile |",
            "| load voltage | kV, phase to neutral |", ""]

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")

    for k, v in facts.items():
        print("%-28s %s" % (k, v))
    print()
    if problems:
        print("FAILED %d check(s):" % len(problems))
        for p in problems:
            print("  -", p)
    else:
        print("all structural checks passed")
    print("wrote", REPORT)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())


def electrical_midpoint(f):
    """The bus halfway, by series impedance, from the transformer to the furthest point.

    Table 7 puts the battery at the feeder's electrical midpoint. Electrical distance is
    the positive-sequence impedance magnitude summed along the radial path; the bus picked
    is the first on the path to the electrically furthest bus where that sum passes half
    the total. Returns (bus, distance to it in ohms, total in ohms).
    """
    import math
    from collections import defaultdict, deque
    adj = defaultdict(list)
    for ln in f.lines:
        c = f.linecodes[ln.linecode]
        z = math.hypot(c.r1, c.x1) * ln.length_km
        adj[ln.bus1].append((ln.bus2, z))
        adj[ln.bus2].append((ln.bus1, z))
    root = f.transformer.bus_lv
    dist, parent = {root: 0.0}, {root: None}
    q = deque([root])
    while q:
        u = q.popleft()
        for v, z in adj[u]:
            if v not in dist:
                dist[v], parent[v] = dist[u] + z, u
                q.append(v)
    far = max(dist, key=dist.get)
    path = []
    b = far
    while b is not None:
        path.append(b)
        b = parent[b]
    path.reverse()
    half = dist[far] / 2.0
    mid = next(b for b in path if dist[b] >= half)
    return mid, dist[mid], dist[far]
