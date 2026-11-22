"""Smoke test of the project report generator: it builds, has the expected sections, and its facts come from the repository."""
from __future__ import annotations

import pytest

pytest.importorskip("reportlab")
pypdf = pytest.importorskip("pypdf")


def test_report_builds_with_repository_facts(tmp_path, monkeypatch):
    from scripts import generate_project_pdf as g

    monkeypatch.setattr(g, "OUT", tmp_path / "report.pdf")
    out = g.build()
    r = pypdf.PdfReader(str(out))
    text = " ".join(" ".join(p.extract_text().split()) for p in r.pages)
    assert len(r.pages) >= 8
    for heading in ("1. Summary", "7. Real-data analysis", "8. Calibration, forecasts", "11. Deployment", "13. Repository history"):
        assert heading in text
    log = g.commits()
    if log:  # inside a git checkout the history table lists every commit, newest last
        assert log[-1][0] in text and len(log) >= 50
    cal = g.load("docs/_parts/calibration_results.json")
    if cal:  # numbers in the calibration table are the measured ones, not typed in
        assert f"{cal['real']['avg_ticket_usd']['pos']:.2f}" in text
