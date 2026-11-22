"""Forecast REAL Pakistani series with an honest backtest.

Series (all real, from the dashboard's analysis data): SBP retail payment volume and Raast (quarterly, only 10 points),
personal remittances (annual, 25 points), USD/PKR (monthly, 141 points), foreign banks' cross-border claims (quarterly, 106 points).

Method (per series):
  * candidate models on the log scale: naive, drift, damped Holt (ETS), ARIMA(1,1,0) with drift (long series only),
    seasonal naive (monthly/quarterly series with enough history)
  * rolling-origin backtest: re-fit on data up to each origin, forecast ahead, compare with what actually happened
  * long series: the model is CHOSEN on an earlier validation window and SCORED on the last window (never the same window);
    short series (< 15 points) have no room for that, so choice and score share the window and the result is flagged optimistic
  * score = MASE (error relative to a naive one-step forecast; < 1 beats naive) and MAPE
  * forecast = chosen model refit on all data; the 80% band uses the one-step backtest error spread, widened by sqrt(horizon)
A model that does not beat naive is reported as such: for a random-walk series like an exchange rate the honest answer is "flat".

Output: docs/_parts/forecasts.json and a `forecast` section merged into web/react-app/public/analysis.json.
Run: PYTHONPATH=. python scripts/forecast_real_series.py
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
Z80 = 1.2816


# ------------------------------------------------------------------ models (log scale in, log scale out)
def f_naive(y, h, m):
    return np.repeat(y[-1], h)


def f_drift(y, h, m):
    slope = (y[-1] - y[0]) / (len(y) - 1)
    return y[-1] + slope * np.arange(1, h + 1)


def f_snaive(y, h, m):
    if m < 2 or len(y) < 2 * m:
        raise ValueError("not enough history")
    return np.array([y[-m + (i % m)] for i in range(h)])


def f_ets(y, h, m):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(y, trend="add", damped_trend=True, initialization_method="estimated").fit()
        out = np.asarray(fit.forecast(h))
    if not np.all(np.isfinite(out)):
        raise ValueError("ets failed")
    return out


def f_arima(y, h, m):
    from statsmodels.tsa.arima.model import ARIMA
    if len(y) < 30:
        raise ValueError("series too short for ARIMA")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = np.asarray(ARIMA(y, order=(1, 1, 0), trend="t").fit().forecast(h))
    if not np.all(np.isfinite(out)):
        raise ValueError("arima failed")
    return out


MODELS = {"naive": f_naive, "drift": f_drift, "damped_ets": f_ets, "arima_110_drift": f_arima, "seasonal_naive": f_snaive}


def predict(name, ly, h, m):
    """Forecast on the original scale; falls back to NaN if the model cannot be fitted."""
    try:
        return np.exp(MODELS[name](ly, h, m))
    except Exception:
        return np.full(h, np.nan)


# ------------------------------------------------------------------ backtest
def rolling_scores(y, origins, h_list, m, models):
    """For each model and horizon: MASE and MAPE over the origins. Errors use only data available at each origin."""
    ly = np.log(y)
    scale = np.mean(np.abs(np.diff(y)))  # in-sample one-step naive MAE (non-seasonal MASE scale)
    res = {}
    for name in models:
        res[name] = {}
        for h in h_list:
            errs, pcts, logerr = [], [], []
            for o in origins:
                if o + h > len(y):
                    continue
                fc = predict(name, ly[:o], h, m)[h - 1]
                if not np.isfinite(fc):
                    continue
                a = y[o + h - 1]
                errs.append(abs(a - fc))
                pcts.append(abs(a - fc) / abs(a))
                logerr.append(np.log(a) - np.log(fc))
            if errs:
                res[name][h] = {"mase": float(np.mean(errs) / scale), "mape": float(np.mean(pcts) * 100), "n": len(errs), "log_err": [float(x) for x in logerr]}
    return res


def avg_mase(r, h_list):
    v = [r[h]["mase"] for h in h_list if h in r]
    return float(np.mean(v)) if v else np.inf


SERIES = [
    dict(id="retail_volume", title="SBP retail payment volume (million transactions per quarter)", unit="million", freq="fq", m=1, H=4, h_eval=[1], test=3,
         source="SBP Payment Systems Reviews (merged quarterly series, Q2 FY24 to Q3 FY26)", note="Only 10 quarters and SBP revises earlier quarters, so treat this as direction and rough size, not a precise forecast."),
    dict(id="raast", title="Raast instant payments (million per quarter)", unit="million", freq="fq", m=1, H=4, h_eval=[1], test=3,
         source="SBP Payment Systems Reviews (Raast table, Q2 FY24 to Q3 FY26)", note="Only 10 quarters and growth is fast (6.9x in 9 quarters); a damped trend may understate it."),
    dict(id="remittances", title="Personal remittances received (US$ million per year)", unit="US$ million", freq="year", m=1, H=3, h_eval=[1, 2], test=6,
         source="World Bank WDI, Pakistan, 2000-2024"),
    dict(id="usdpkr", title="USD/PKR monthly average (rupees per dollar)", unit="PKR per USD", freq="month", m=12, H=12, h_eval=[1, 6, 12], test=24,
         source="BIS exchange rates, monthly average, 2015-2026"),
    dict(id="bis_claims", title="Foreign banks' cross-border claims on Pakistan (US$ billion)", unit="US$ bn", freq="calq", m=4, H=4, h_eval=[1, 4], test=20,
         source="BIS locational banking statistics, quarterly, 2000-2026"),
]


def load_inputs() -> dict[str, tuple[list[str], list[float]]]:
    c2 = json.loads((ROOT / "docs/_parts/part_c2.json").read_text(encoding="utf-8"))
    a = json.loads((ROOT / "web/react-app/public/analysis.json").read_text(encoding="utf-8"))
    ch = {c["id"]: c for s in a["sections"] for c in s["charts"]}
    out = {}
    q = c2["quarters_used"]  # Q2-FY24 .. Q3-FY26 (10 quarters that pass the reconciliation check)
    out["retail_volume"] = (q, [float(c2["retail_volume_m"][k]) for k in q])
    def col(cid, key):
        c = ch[cid]
        xk = c.get("x", "x")
        rows = [r for r in c["data"] if r.get(key) is not None]
        return [str(r[xk]) for r in rows], [float(r[key]) for r in rows]
    out["raast"] = col("raast", "v")
    out["remittances"] = col("remittances", "usd_m")
    out["usdpkr"] = col("usdpkr", "usdpkr")
    out["bis_claims"] = col("lbs", "claims_usd_bn")
    return out


def next_labels(last: str, freq: str, h: int) -> list[str]:
    out = []
    cur = last
    for _ in range(h):
        if freq == "year":
            cur = str(int(cur) + 1)
        elif freq == "month":
            y, mth = int(cur[:4]), int(cur[5:7])
            y, mth = (y + 1, 1) if mth == 12 else (y, mth + 1)
            cur = f"{y}-{mth:02d}"
        elif freq == "calq":
            y, qn = int(cur[:4]), int(cur[-1])
            y, qn = (y + 1, 1) if qn == 4 else (y, qn + 1)
            cur = f"{y}-Q{qn}"
        else:  # fiscal quarter "Q3-FY26"
            qn, fy = int(cur[1]), int(cur[-2:])
            qn, fy = (1, fy + 1) if qn == 4 else (qn + 1, fy)
            cur = f"Q{qn}-FY{fy:02d}"
        out.append(cur)
    return out


def run_series(cfg: dict, labels: list[str], values: list[float]) -> dict:
    y = np.array(values, dtype=float)
    n, m, H, T = len(y), cfg["m"], cfg["H"], cfg["test"]
    h_list = cfg["h_eval"]
    models = [k for k in MODELS if k != "seasonal_naive" or (m > 1 and n >= 3 * m)]
    min_train = max(6, n - T - (T if n >= 40 else 0) - 1) if n < 40 else 20
    test_origins = list(range(n - T, n))
    val_origins = list(range(n - 2 * T, n - T)) if n >= 40 else []
    leak = not val_origins
    sel_origins = val_origins if val_origins else test_origins
    sel = rolling_scores(y, sel_origins, h_list, m, models)
    test = rolling_scores(y, test_origins, h_list, m, models)
    chosen = min(models, key=lambda k: avg_mase(sel[k], h_list))
    # naive must be among the candidates, so "chosen" can honestly be naive
    c_score, n_score = avg_mase(test[chosen], h_list), avg_mase(test["naive"], h_list)
    beats = bool(c_score < 0.95 * n_score) and chosen != "naive"
    published = chosen if beats else "naive"  # a model that cannot beat naive on the scoring window is not published
    # one-step backtest errors (log) of the PUBLISHED model give the band width
    e1 = np.array(test[published].get(1, {}).get("log_err", []) + (sel[published].get(1, {}).get("log_err", []) if not leak else []))
    sigma = float(np.std(e1, ddof=1)) if len(e1) > 2 else float(np.std(np.diff(np.log(y))))
    fc = predict(published, np.log(y), H, m)
    hh = np.arange(1, H + 1)
    lo, hi = fc * np.exp(-Z80 * sigma * np.sqrt(hh)), fc * np.exp(Z80 * sigma * np.sqrt(hh))
    # empirical coverage of the 80% band on the test origins (one step): how often the actual fell inside
    cov = None
    if len(e1) >= 3:
        cov = float(np.mean(np.abs(e1) <= Z80 * sigma))
    return {
        "id": cfg["id"], "title": cfg["title"], "unit": cfg["unit"], "freq": cfg["freq"], "source": cfg["source"], "note": cfg.get("note", ""),
        "n_points": n, "first": labels[0], "last": labels[-1], "test_origins": len(test_origins), "selection_window_is_test_window": leak,
        "chosen": chosen, "published": published, "mase_chosen": c_score, "mase_naive": n_score,
        "mape_chosen": float(np.mean([test[chosen][h]["mape"] for h in h_list if h in test[chosen]])),
        "mape_naive": float(np.mean([test["naive"][h]["mape"] for h in h_list if h in test["naive"]])),
        "beats_naive": beats,
        "band_sigma_log": sigma, "band_one_step_coverage": cov,
        "scores_all_models": {k: {"mase": avg_mase(test[k], h_list)} for k in models},
        "history": [{"x": labels[i], "y": float(y[i])} for i in range(n)],
        "forecast": [{"x": x, "y": float(f), "lo": float(l), "hi": float(u)} for x, f, l, u in zip(next_labels(labels[-1], cfg["freq"], H), fc, lo, hi)],
    }


# ------------------------------------------------------------------ dashboard chart specs
def chart_specs(results: list[dict]) -> dict:
    charts = []
    for r in results:
        hist, fc = r["history"], r["forecast"]
        data = []
        for i, p in enumerate(hist):
            data.append({"x": p["x"], "actual": p["y"], "forecast": p["y"] if i == len(hist) - 1 else None, "lo": p["y"] if i == len(hist) - 1 else None, "hi": p["y"] if i == len(hist) - 1 else None})
        data += [{"x": p["x"], "actual": None, "forecast": p["y"], "lo": p["lo"], "hi": p["hi"]} for p in fc]
        verdict = ("beats the naive benchmark" if r["beats_naive"] else "did NOT beat the naive benchmark, so the published forecast is the naive (flat) one")
        charts.append({
            "id": "fc_" + r["id"], "title": r["title"].split(" (")[0], "type": "line", "x": "x", "wide": False, "unit": r["unit"],
            "subtitle": f"Forecast with 80% band: {r['published'].replace('_', ' ')} model; the best candidate ({r['chosen'].replace('_', ' ')}) {verdict} (backtest MASE {r['mase_chosen']:.2f} vs naive {r['mase_naive']:.2f})",
            "series": [{"key": "actual", "name": "Actual"}, {"key": "forecast", "name": "Forecast", "dash": True}, {"key": "lo", "name": "Lower 80%", "dash": True, "faint": True}, {"key": "hi", "name": "Upper 80%", "dash": True, "faint": True}],
            "data": data, "source": r["source"],
            "note": (r["note"] + " " if r["note"] else "") + ("Model choice and backtest use the same window (series too short to split), so the score is optimistic." if r["selection_window_is_test_window"] else "Model chosen on an earlier validation window and scored on the last window."),
        })
    rows = [{"series": r["title"].split(" (")[0], "points": r["n_points"], "model": r["published"].replace("_", " "), "mase": round(r["mase_chosen"], 2), "naive_mase": round(r["mase_naive"], 2),
             "mape": round(r["mape_chosen"], 1), "beats": "yes" if r["beats_naive"] else "no", "cov": (f"{r['band_one_step_coverage'] * 100:.0f}%" if r["band_one_step_coverage"] is not None else "n/a")} for r in results]
    charts.append({"id": "fc_scores", "title": "Forecast backtest scorecard", "type": "table", "x": "series", "wide": True,
                   "series": [{"key": "series", "name": "Series"}, {"key": "points", "name": "Points"}, {"key": "model", "name": "Published model"}, {"key": "mase", "name": "MASE (chosen)"}, {"key": "naive_mase", "name": "MASE (naive)"},
                              {"key": "mape", "name": "MAPE %"}, {"key": "beats", "name": "Beats naive?"}, {"key": "cov", "name": "80% band hit rate"}],
                   "data": rows, "source": "Computed by scripts/forecast_real_series.py (rolling-origin backtest)",
                   "note": "MASE below 1 means the model's one-step errors are smaller than a naive 'same as last period' forecast. The hit rate is how often the actual landed inside the 80% band in the backtest; it should be near 80%."})
    return {"id": "forecast", "title": "Forecasts (real series)",
            "intro": "Forecasts of real Pakistani series with a rolling-origin backtest against a naive benchmark. Bands are 80% ranges from the backtest errors. Short series (10 quarters) carry a lot of uncertainty and are shown for direction, not precision; a model that cannot beat naive is reported as flat.",
            "kpis": [], "charts": charts}


def main() -> None:
    inputs = load_inputs()
    results = [run_series(cfg, *inputs[cfg["id"]]) for cfg in SERIES]
    (ROOT / "docs/_parts/forecasts.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    p = ROOT / "web/react-app/public/analysis.json"
    a = json.loads(p.read_text(encoding="utf-8"))
    a["sections"] = [s for s in a["sections"] if s["id"] != "forecast"] + [chart_specs(results)]
    p.write_text(json.dumps(a, separators=(",", ":")), encoding="utf-8")
    for r in results:
        print(f"{r['id']:14s} n={r['n_points']:3d} pub={r['published']:15s} MASE {r['mase_chosen']:.2f} (naive {r['mase_naive']:.2f}) MAPE {r['mape_chosen']:.1f}% beats_naive={r['beats_naive']} "
              f"cov={r['band_one_step_coverage']}  next={r['forecast'][0]['y']:.2f}")


if __name__ == "__main__":
    main()
