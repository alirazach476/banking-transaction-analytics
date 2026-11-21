"""Run all parts of the all-in-one analysis in order, then merge. Needs the warehouse (read-only) and, for part_a, nothing else.
Part E reads part A's output; part H reads A-G; the merge reads all.   Run: python scripts/allinone/run_all.py"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for f in ("part_a_banking.py", "part_b_macro.py", "part_c_payments.py", "part_c2_payments_now.py", "part_d_crossborder.py", "part_e_global.py", "part_fg_wdi_findex.py", "part_h_quality.py", "build_all_in_one.py"):
    print("running", f, flush=True)
    p = subprocess.run([sys.executable, str(HERE / f)], capture_output=True, text=True)
    if p.returncode:
        print(p.stderr[-1500:])
        sys.exit(p.returncode)
print("done: docs/ALL_IN_ONE_ANALYSIS.md")
