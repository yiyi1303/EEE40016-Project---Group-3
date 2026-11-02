"""Validation item V9: results can be regenerated.

Plan wording: re-run three sweep points with the same seed a week later; log files
identical.

Two modes:

    py tests/v9_reproducibility.py --record     today: run three points, store their logs
                                                and fingerprints, and a fingerprint of the
                                                code and config that produced them
    py tests/v9_reproducibility.py --check      a week later: run the same three points and
                                                compare, step by step

If the logs differ, the check says whether the code or config changed in between, so a
real reproducibility failure can be told apart from an honest change to the model. A
code change means V9 has to be re-recorded, not that it failed.
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import sys
from dataclasses import asdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
from sweep import StudyRun                          # noqa: E402
import controllers                                  # noqa: E402

V9 = os.path.join(HERE, "results", "v9")
STATIC_KW = 2.1                                     # fixed, so calibration is not re-tested
POINTS = [("B", 5, 0.01, 0.0, "trust-weighted, good link"),
          ("C", 300, 0.20, 0.0, "binary fallback, poor link"),
          ("B", 60, 0.10, 5.0, "trust-weighted, moderate link, 5-minute stale hold")]


def code_fingerprint():
    h = hashlib.sha256()
    # everything that can change a result; plotting and summary scripts cannot, and are left
    # out so that tidying a figure does not make V9 report a model change
    # (timeout_sensitivity and refine_crossover are analysis drivers the three points never run)
    skip = ("plot_", "make_scenario_data", "inspect_sincal_schema", "build_sincal_model",
            "timeout_sensitivity", "refine_crossover")
    files = sorted(p for p in glob.glob(os.path.join(HERE, "src", "*.py"))
                   if not os.path.basename(p).startswith(skip)) + [
        os.path.join(HERE, "config", "study.json"),
        os.path.join(HERE, "config", "cable_ratings.json"),
        os.path.join(HERE, "data", "ambient.csv"),
        os.path.join(HERE, "data", "pv_profile.csv")]
    # only the session file the three points read: other session files come and go as other
    # scenarios and tests run, and must not make a real failure look like a model change
    from ev_sessions import path_for
    st = StudyRun()
    files.append(path_for(7, "_n%d" % len(st.ev_connections), **st.session_args))
    for p in files:
        h.update(os.path.relpath(p, HERE).replace("\\", "/").encode())
        with open(p, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def run_points():
    study = StudyRun()
    c = controllers.build(study.cfg, STATIC_KW)
    out = []
    for key, lat, loss, hold, label in POINTS:
        trace = []
        r = study.run(c[key], lat, loss, 7, trace, stale_hold_min=hold)
        d = asdict(r)
        d.pop("seconds")                            # wall clock is not a result
        log = {"point": label, "result": d, "trace": trace}
        text = json.dumps(log, sort_keys=True, separators=(",", ":"))
        out.append((label, hashlib.sha256(text.encode()).hexdigest(), log))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--record", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args()
    os.makedirs(V9, exist_ok=True)
    manifest_path = os.path.join(V9, "manifest.json")

    if a.record:
        pts = run_points()
        manifest = {"recorded": datetime.datetime.now().isoformat(timespec="seconds"),
                    "check_after": (datetime.date.today() + datetime.timedelta(days=7)).isoformat(),
                    "code_fingerprint": code_fingerprint(),
                    "points": [{"point": l, "log_sha256": h} for l, h, _ in pts]}
        for i, (_, _, log) in enumerate(pts):
            with open(os.path.join(V9, "log_%d.json" % i), "w", encoding="utf-8") as f:
                json.dump(log, f, sort_keys=True, indent=1)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print("recorded %d points, code fingerprint %s..." % (len(pts),
                                                              manifest["code_fingerprint"][:12]))
        for l, h, _ in pts:
            print("   %-52s %s..." % (l, h[:16]))
        print("check on or after %s with: py tests/v9_reproducibility.py --check"
              % manifest["check_after"])
        return 0

    manifest = json.load(open(manifest_path, encoding="utf-8"))
    same_code = code_fingerprint() == manifest["code_fingerprint"]
    pts = run_points()
    ok = True
    for i, ((l, h, log), rec) in enumerate(zip(pts, manifest["points"])):
        match = h == rec["log_sha256"]
        ok &= match
        print("%-52s %s" % (l, "identical" if match else "DIFFERS"))
        if not match:
            old = json.load(open(os.path.join(V9, "log_%d.json" % i), encoding="utf-8"))
            for a_, b_ in zip(old["trace"], log["trace"]):
                if a_ != b_:
                    print("   first difference at step %s" % a_["step"])
                    break
    days = (datetime.datetime.now() - datetime.datetime.fromisoformat(
        manifest["recorded"])).days
    print("\nrecorded %s, %d days ago; code and config %s"
          % (manifest["recorded"], days, "unchanged" if same_code else "HAVE CHANGED since"))
    if ok:
        print("V9 PASS" if days >= 7 else
              "logs identical, but the plan asks for a week's gap: re-check on or after %s"
              % manifest["check_after"])
    elif not same_code:
        print("V9 not assessable: the model changed after recording. Re-record with --record.")
    else:
        print("V9 FAIL: same code and config, different logs")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
