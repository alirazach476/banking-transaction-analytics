"""Forecasting of real series: model correctness, backtest hygiene, labels, and consistency of the published results."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts import forecast_real_series as F

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "_parts" / "forecasts.json"


def test_naive_and_drift():
    y = np.log(np.array([10.0, 12.0, 14.0, 16.0]))
    assert np.allclose(F.f_naive(y, 3, 1), y[-1])
    d = F.f_drift(y, 2, 1)
    assert d[0] == pytest.approx(y[-1] + (y[-1] - y[0]) / 3)


def test_seasonal_naive_repeats_last_cycle_and_refuses_short_history():
    y = np.log(np.arange(1, 13, dtype=float))
    assert np.allclose(F.f_snaive(y, 5, 4), [y[-4], y[-3], y[-2], y[-1], y[-4]])
    with pytest.raises(ValueError):
        F.f_snaive(y[:5], 2, 4)


def test_backtest_uses_only_data_before_the_origin():
    rng = np.random.default_rng(0)
    y = 100 * 1.03 ** np.arange(40) * np.exp(rng.normal(0, 0.01, 40))
    a = F.rolling_scores(y, [30], [1], 1, ["drift", "naive"])
    y2 = y.copy()
    y2[31:] = 1e6  # anything after the scored point must not matter
    b = F.rolling_scores(y2, [30], [1], 1, ["drift", "naive"])
    assert a["drift"][1]["mape"] == pytest.approx(b["drift"][1]["mape"])
    y3 = y.copy()
    y3[30] = 1e6  # but the actual value at the origin's target does matter
    assert F.rolling_scores(y3, [30], [1], 1, ["naive"])["naive"][1]["mape"] != pytest.approx(a["naive"][1]["mape"])


def _series(kind, n=60, seed=1):
    rng = np.random.default_rng(seed)
    if kind == "trend":
        return 100 * 1.04 ** np.arange(n) * np.exp(rng.normal(0, 0.005, n))
    return 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))  # random walk


CFG = dict(id="t", title="t (u)", unit="u", freq="month", m=12, H=6, h_eval=[1, 3], test=12, source="test")


def labels(n):
    return [f"{2010 + i // 12}-{i % 12 + 1:02d}" for i in range(n)]


def test_a_clear_trend_is_forecast_better_than_naive():
    y = _series("trend")
    r = F.run_series(CFG, labels(len(y)), list(y))
    assert r["beats_naive"] and r["published"] != "naive"
    assert r["forecast"][0]["y"] > y[-1]  # trend continues
    assert all(f["lo"] <= f["y"] <= f["hi"] for f in r["forecast"])
    assert not r["selection_window_is_test_window"]  # 60 points: chosen on validation, scored on the last window


def test_a_random_walk_is_not_dressed_up_as_predictable():
    y = _series("walk", n=120, seed=3)
    r = F.run_series(dict(CFG, H=6), labels(len(y)), list(y))
    # whatever won on validation, a model that fails to beat naive on the test window is not published
    assert r["published"] == "naive" or r["beats_naive"]
    # naive forecast is flat
    if r["published"] == "naive":
        assert len({round(f["y"], 6) for f in r["forecast"]}) == 1


def test_band_widens_with_horizon_and_has_sensible_coverage():
    y = _series("walk", n=150, seed=5)
    r = F.run_series(dict(CFG, H=6), labels(len(y)), list(y))
    widths = [f["hi"] - f["lo"] for f in r["forecast"]]
    assert widths == sorted(widths) and widths[-1] > widths[0]
    assert r["band_one_step_coverage"] is None or 0.5 <= r["band_one_step_coverage"] <= 1.0


def test_short_series_is_flagged_as_optimistic():
    y = [100, 112, 125, 140, 152, 171, 190, 210, 236, 260]
    r = F.run_series(dict(CFG, freq="fq", m=1, H=4, h_eval=[1], test=3), [f"Q{(i % 4) + 1}-FY2{4 + i // 4}" for i in range(10)], y)
    assert r["selection_window_is_test_window"] is True


@pytest.mark.parametrize("last,freq,expect", [
    ("Q3-FY26", "fq", ["Q4-FY26", "Q1-FY27", "Q2-FY27"]),
    ("2026-11", "month", ["2026-12", "2027-01", "2027-02"]),
    ("2026-Q3", "calq", ["2026-Q4", "2027-Q1", "2027-Q2"]),
    ("2024", "year", ["2025", "2026", "2027"]),
])
def test_next_labels_roll_over_correctly(last, freq, expect):
    assert F.next_labels(last, freq, 3) == expect


@pytest.mark.skipif(not RESULTS.exists(), reason="run scripts/forecast_real_series.py first")
def test_published_results_are_internally_consistent():
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert {r["id"] for r in res} >= {"retail_volume", "raast", "remittances", "usdpkr", "bis_claims"}
    for r in res:
        assert r["history"] and r["forecast"]
        assert (r["published"] == r["chosen"]) if r["beats_naive"] else (r["published"] == "naive")
        assert all(f["lo"] <= f["y"] <= f["hi"] for f in r["forecast"])
        assert r["n_points"] == len(r["history"])
    spec = F.chart_specs(res)
    ids = [c["id"] for c in spec["charts"]]
    assert len(ids) == len(set(ids)) and all(c.get("source") for c in spec["charts"])
    for c in spec["charts"]:
        if c["type"] == "line":
            assert any(r["forecast"] is not None for r in c["data"]) and any(r["actual"] is not None for r in c["data"])


@pytest.mark.skipif(not (ROOT / "web/react-app/public/analysis.json").exists(), reason="analysis.json not built")
def test_forecast_section_is_in_the_dashboard_data():
    a = json.loads((ROOT / "web/react-app/public/analysis.json").read_text(encoding="utf-8"))
    sec = [s for s in a["sections"] if s["id"] == "forecast"]
    assert len(sec) == 1 and len(sec[0]["charts"]) == 6
