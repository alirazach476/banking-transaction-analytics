"""Command-line entry point for the orchestration tasks (used by the Airflow DAGs via BashOperator so tasks run in the
project's own Python environment, independent of Airflow's pinned dependencies).

    python -m src.orchestration.cli generate --num-payments 20000
    python -m src.orchestration.cli load | reconcile | quality-gate | drift | ingest-external
    python -m src.orchestration.cli dbt --select models/payments
Prints one JSON line on success; exits 1 (with the error on stderr) on failure.
"""
from __future__ import annotations

import argparse
import json
import sys

from src.orchestration import tasks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NovaBank orchestration tasks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("--num-payments", type=int, default=100_000); g.add_argument("--seed", type=int)
    sub.add_parser("load"); sub.add_parser("reconcile"); sub.add_parser("quality-gate"); sub.add_parser("drift")
    e = sub.add_parser("ingest-external"); e.add_argument("--only", nargs="*")
    d = sub.add_parser("dbt"); d.add_argument("--select", required=True)
    a = ap.parse_args(argv)
    try:
        res = {
            "generate": lambda: tasks.generate_payments(a.num_payments, a.seed) if a.cmd == "generate" else None,
            "load": tasks.load_payments, "reconcile": tasks.run_reconciliation, "quality-gate": tasks.quality_gate,
            "drift": tasks.drift_check,
            "ingest-external": lambda: tasks.ingest_external(getattr(a, "only", None)),
            "dbt": lambda: tasks.run_dbt(getattr(a, "select", "")),
        }[a.cmd]()
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(res, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
