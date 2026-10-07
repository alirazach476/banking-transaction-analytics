"""
End-to-end NovaBank analytics pipeline.

Steps: generate -> DDL -> ingest -> validate -> dbt -> anomaly -> reconcile -> insights
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from config.settings import get_settings
from src.anomaly_detection.run_detection import run_detection
from src.ingestion.load_raw import main as ingest_main
from src.utils.db import get_engine, run_ddl
from src.utils.generate_insights import generate_insights
from src.utils.logging_utils import get_logger
from src.validation.reconciliation import run_reconciliation
from src.validation.run_validation import run_all_checks

logger = get_logger(__name__)


def _start_pipeline_run(engine, run_id: str, mode: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO audit.pipeline_runs
                    (run_id, pipeline_name, start_time, status, mode)
                VALUES (:id, 'novabank_pipeline', :ts, 'RUNNING', :mode)
                ON CONFLICT (run_id) DO NOTHING
                """
            ),
            {"id": run_id, "ts": datetime.now(timezone.utc), "mode": mode},
        )


def _finish_pipeline_run(engine, run_id: str, status: str, notes: str = "") -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE audit.pipeline_runs
                SET end_time = :ts, status = :st, notes = :notes
                WHERE run_id = :id
                """
            ),
            {
                "ts": datetime.now(timezone.utc),
                "st": status,
                "notes": notes,
                "id": run_id,
            },
        )


def _run_dbt(project_root: Path) -> bool:
    dbt_dir = project_root / "dbt"
    if not dbt_dir.exists():
        logger.warning("dbt project not found at %s — skipping dbt build", dbt_dir)
        return False

    cmd = [
        sys.executable,
        "-m",
        "dbt",
        "build",
        "--profiles-dir",
        ".",
    ]
    logger.info("Running dbt build in %s", dbt_dir)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(dbt_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            logger.info(result.stdout[-4000:])
        if result.returncode != 0:
            logger.warning("dbt build exited %s: %s", result.returncode, result.stderr[-2000:])
            return False
        return True
    except Exception as exc:
        logger.warning("dbt build failed: %s", exc)
        return False


def run_pipeline(
    skip_generate: bool = False,
    skip_dbt: bool = False,
    mode: str = "full",
) -> dict:
    settings = get_settings()
    run_id = str(uuid.uuid4())
    engine = get_engine()
    run_ddl(engine)
    _start_pipeline_run(engine, run_id, mode)
    summary: dict = {"run_id": run_id, "mode": mode, "steps": {}}

    try:
        if not skip_generate:
            logger.info("Step 1/8: Generating synthetic data...")
            from src.data_generation.generate_all import main as generate_main

            generate_main()
            summary["steps"]["generate"] = "SUCCESS"
        else:
            logger.info("Step 1/8: Skipping data generation")
            summary["steps"]["generate"] = "SKIPPED"

        logger.info("Step 2/8: Applying DDL...")
        run_ddl(engine)
        summary["steps"]["ddl"] = "SUCCESS"

        logger.info("Step 3/8: Ingesting source CSVs (mode=%s)...", mode)
        ingest_main(mode=mode)
        summary["steps"]["ingest"] = "SUCCESS"

        logger.info("Step 4/8: Running data quality validation...")
        dq = run_all_checks(engine=engine, run_id=run_id)
        summary["steps"]["validate"] = dq

        if not skip_dbt:
            logger.info("Step 5/8: Running dbt build...")
            dbt_ok = _run_dbt(settings.project_root)
            summary["steps"]["dbt"] = "SUCCESS" if dbt_ok else "SKIPPED_OR_FAILED"
        else:
            logger.info("Step 5/8: Skipping dbt build")
            summary["steps"]["dbt"] = "SKIPPED"

        logger.info("Step 6/8: Running anomaly detection...")
        anomaly = run_detection(mode=mode, run_id=run_id)
        summary["steps"]["anomaly"] = anomaly

        logger.info("Step 7/8: Running reconciliation...")
        recon = run_reconciliation(run_id=run_id)
        summary["steps"]["reconciliation"] = recon

        logger.info("Step 8/8: Generating business insights...")
        try:
            insights_path = generate_insights()
            summary["steps"]["insights"] = str(insights_path)
        except Exception as exc:
            logger.warning("Insights generation failed: %s", exc)
            summary["steps"]["insights"] = f"FAILED: {exc}"

        _finish_pipeline_run(engine, run_id, "SUCCESS")
        logger.info("Pipeline complete run_id=%s", run_id)
    except Exception as exc:
        _finish_pipeline_run(engine, run_id, "FAILED", notes=str(exc))
        logger.exception("Pipeline failed: %s", exc)
        raise

    return summary


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="NovaBank end-to-end pipeline")
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Skip synthetic data generation",
    )
    parser.add_argument(
        "--skip-dbt",
        action="store_true",
        help="Skip dbt build step",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default=get_settings().pipeline_mode,
        help="Ingestion mode: full or incremental",
    )
    args = parser.parse_args(argv)
    return run_pipeline(
        skip_generate=args.skip_generate,
        skip_dbt=args.skip_dbt,
        mode=args.mode,
    )


if __name__ == "__main__":
    main()
