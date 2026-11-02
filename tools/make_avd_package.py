"""Bundle the full-feeder SINCAL projects for the uni AVD into one zip.

    py tools/make_avd_package.py

Rebuilds both cases with the current importer first, so the package never carries a stale
model. Out: avd_crosscheck.zip in the project folder, holding

    EULV_benchmark.sin + _files   800 kVA, 1.05 pu, minute 566 (V1's published snapshot)
    EULV_study.sin + _files       150 kVA, 1.00 pu, evening peak minute
    avd_solve.py                  repoints and solves both with the unbalanced load flow
    README.txt                    the steps, including the by-hand route with no Python
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from build_sincal_model import build, MODELS            # noqa: E402
from feeder_csv import load_feeder                      # noqa: E402
from sincal_subset_check import evening_peak_minute     # noqa: E402

OUT = os.path.join(HERE, "avd_crosscheck.zip")

README = """SINCAL cross-check on the uni AVD  (EEE40016, digital twin node)
=================================================================

Why: the laptop's SINCAL is the free Xplore licence, capped at 50 nodes. The feeder has
907. OpenDSS does the study; this checks that SINCAL, with the full licence, gets the same
voltages on the full feeder. A 47-node cut already agrees to within 0.1% on the laptop
(notes/sincal_subset_check.md).

1. Copy this whole folder (unzipped) somewhere on the AVD, e.g. Documents\\avd_crosscheck.

2a. With Python on the AVD:
        py -m pip install pywin32
        py avd_solve.py
    It repoints both projects, runs the UNBALANCED load flow on each and reports.

2b. Without Python, by hand, for EULV_benchmark.sin and then EULV_study.sin:
      - open the .sin in PSS SINCAL. If it complains it cannot find the database, the
        path in EULV_*_files\\database.ini is the laptop's: set the FILE= line to the
        database.db inside that same _files folder, save, reopen
      - run the load flow with the UNBALANCED method (Calculate menu, the load flow entry
        marked unbalanced). The ordinary load flow gives a balanced answer that will not
        compare: the feeder's 55 houses are single-phase
      - check the message window shows no "partially isolated" warnings
      - save and close

3. Copy EULV_benchmark_files and EULV_study_files back to the laptop (the whole folders).

4. On the laptop, from the project folder:
        py tools/avd_compare.py <path>\\EULV_benchmark_files\\database.db
        py tools/avd_compare.py <path>\\EULV_study_files\\database.db
   Pass: every node within 0.5% of OpenDSS (and, for the benchmark, of the published IEEE
   solution). Results go to notes/avd_crosscheck_benchmark.md and _study.md.

Cases:
{cases}
"""


def main():
    f = load_feeder()
    peak = evening_peak_minute(f)
    cases = [("benchmark", 566), ("study", peak)]
    rows = []
    for case, minute in cases:
        r = build(case, minute)
        rows.append("    %-10s %4d kVA  %.2f pu  minute %d  %.1f kW of house load  %d nodes"
                    % (case, r["transformer_kva"], r["source_pu"], minute,
                       r["total_load_kw"], r["counts"]["Node"]))
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for case, _ in cases:
            name = "EULV_" + case
            z.write(os.path.join(MODELS, name + ".sin"), "avd_crosscheck/%s.sin" % name)
            files = os.path.join(MODELS, name + "_files")
            for root, _, fns in os.walk(files):
                for fn in fns:
                    p = os.path.join(root, fn)
                    z.write(p, "avd_crosscheck/" + os.path.relpath(p, MODELS).replace("\\", "/"))
        z.write(os.path.join(HERE, "tools", "avd_solve.py"), "avd_crosscheck/avd_solve.py")
        z.writestr("avd_crosscheck/README.txt", README.format(cases="\n".join(rows)))
    print("\n".join(rows))
    print("wrote %s (%.1f MB)" % (OUT, os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    main()
