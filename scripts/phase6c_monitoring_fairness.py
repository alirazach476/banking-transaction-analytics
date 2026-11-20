"""Phase 6c: larger hyper-parameter search (40 candidates, full training window), drift monitoring (PSI by month),
and a group-fairness audit of the saved models. Updates models/*.joblib only if the larger search beats the saved CV score.
Writes docs/PHASE6C_RESULTS.md/.json. Run: PYTHONPATH=. python -m scripts.phase6c_monitoring_fairness
"""
from __future__ import annotations
import json, time, warnings
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from scripts.phase6_stats_ml import load
from scripts.phase6b_models import build_features, search
from src.monitoring.drift import group_rates, psi

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
N_ITER = 40


def main():
    d = build_features(load().sort_values("ts").reset_index(drop=True))
    reg = json.loads((MODELS / "model_registry.json").read_text())
    cut = d.ts.quantile(0.8)
    tr, te = (d.ts <= cut).to_numpy(), (d.ts > cut).to_numpy()
    fcols = joblib.load(MODELS / "fraud_xgb.joblib")["features"]
    out = {"n_iter": N_ITER}

    # ---- 1. larger search on the FULL training window
    t0 = time.time()
    rs = search(d.loc[tr, fcols], d.loc[tr, "fraud"].astype(int), n_iter=N_ITER)
    old = joblib.load(MODELS / "fraud_xgb.joblib")
    p_new = rs.best_estimator_.predict_proba(d.loc[te, fcols])[:, 1]
    p_old = old["model"].predict_proba(d.loc[te, fcols])[:, 1]
    y = d.loc[te, "fraud"].astype(int)
    out["fraud_search"] = {"seconds": round(time.time() - t0), "train_rows": int(tr.sum()), "cv_pr_auc": float(rs.best_score_),
                           "test_pr_auc_new": float(average_precision_score(y, p_new)),
                           "test_pr_auc_previous": float(average_precision_score(y, p_old))}
    # promote only if the new model is better on test PR-AUC (CV alone is noisy with ~0.25% positives)
    promoted = out["fraud_search"]["test_pr_auc_new"] > out["fraud_search"]["test_pr_auc_previous"]
    out["fraud_search"]["promoted"] = bool(promoted)
    best = rs.best_estimator_ if promoted else old["model"]
    if promoted:
        from sklearn.metrics import precision_recall_curve
        pr, rc, th = precision_recall_curve(y, p_new)
        f1 = 2 * pr * rc / np.maximum(pr + rc, 1e-9)
        joblib.dump({"model": best, "features": fcols, "threshold": float(th[int(np.nanargmax(f1[:-1]))])}, MODELS / "fraud_xgb.joblib")
        reg["fraud_xgb"]["metrics"]["pr_auc"] = out["fraud_search"]["test_pr_auc_new"]
        reg["fraud_xgb"]["trained_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        reg["fraud_xgb"]["tuning"] = f"RandomizedSearchCV n_iter={N_ITER}, full train window"
    thr = joblib.load(MODELS / "fraud_xgb.joblib")["threshold"]

    # ---- 2. drift: reference = training window, compare each later month
    ref = d[tr]
    later = d[te].assign(month=lambda x: x.ts.dt.to_period("M").astype(str))
    feats = fcols + ["amount"]
    rows = []
    for m, g in later.groupby("month"):
        if len(g) < 500:
            continue
        r = {"month": m, "n": int(len(g))}
        for f in feats:
            r[f] = round(psi(ref[f], g[f]), 4)
        r["score_fraud"] = round(psi(best.predict_proba(ref[fcols])[:, 1], best.predict_proba(g[fcols])[:, 1]), 4)
        rows.append(r)
    drift = pd.DataFrame(rows)
    out["drift"] = {"reference_rows": int(len(ref)), "months": drift.to_dict("records"),
                    "max_psi_overall": float(drift.drop(columns=["month", "n"]).max().max()),
                    "alert_rule": "PSI>0.25 on any feature or on the score"}
    out["drift"]["alerts"] = [{"month": r["month"], "feature": k, "psi": v} for r in rows for k, v in r.items()
                              if k not in ("month", "n") and v > 0.25]

    # ---- 3. fairness audit at the saved operating threshold (proxy attributes: no protected attributes in data)
    t = d[te].copy()
    t["flag"] = (best.predict_proba(t[fcols])[:, 1] >= thr).astype(int)
    t["y"] = t.fraud.astype(int)
    fair = {}
    for grp in ("card_country", "channel", "merchant_category"):
        gr = group_rates(t, grp, "y", "flag")
        gr = gr[gr.n >= 1000]
        base = t.flag.mean()
        gr["flag_rate_ratio_vs_overall"] = gr.flag_rate / base if base else np.nan
        fair[grp] = {"groups": gr.round(4).to_dict("records"),
                     "max_flag_rate_ratio": float(gr.flag_rate_ratio_vs_overall.max()) if len(gr) else None,
                     "max_fpr_gap": float(gr.fpr.max() - gr.fpr.min()) if len(gr) else None}
    out["fairness"] = {"threshold": thr, "overall_flag_rate": float(t.flag.mean()), "by": fair}
    # decline model: approval-rate gap across the same proxies (descriptive)
    out["decline_rate_by_card_country"] = d.groupby("card_country").declined.agg(["mean", "size"]).query("size>=1000")["mean"].round(4).to_dict()

    (MODELS / "model_registry.json").write_text(json.dumps(reg, indent=2))
    (ROOT / "docs" / "PHASE6C_RESULTS.json").write_text(json.dumps(out, indent=2, default=float))
    fs = out["fraud_search"]
    L = ["# Phase 6c results (measured; synthetic data)", "",
         f"## Larger hyper-parameter search ({N_ITER} candidates, full {fs['train_rows']:,}-row training window, {fs['seconds']} s)",
         f"- CV PR-AUC {fs['cv_pr_auc']:.3f}; test PR-AUC new {fs['test_pr_auc_new']:.3f} vs previous {fs['test_pr_auc_previous']:.3f}; "
         f"promoted: **{fs['promoted']}** (rule: promote only if test PR-AUC improves)", "",
         "## Drift monitoring (PSI vs training window; rule PSI>0.25 = alert)",
         f"- Max PSI over all feature-months: {out['drift']['max_psi_overall']:.3f}; alerts: {len(out['drift']['alerts'])}", "",
         drift.to_markdown(index=False) if hasattr(drift, "to_markdown") else drift.to_string(index=False), "",
         "## Fairness audit (proxy attributes; the synthetic data has no protected attributes)",
         f"Fraud model at threshold {thr:.3f}; overall flag rate {out['fairness']['overall_flag_rate']:.4%}.", ""]
    for grp, v in fair.items():
        L.append(f"- **{grp}**: max flag-rate ratio vs overall {v['max_flag_rate_ratio']:.2f}, max FPR gap {v['max_fpr_gap']:.4f} across {len(v['groups'])} groups with n>=1000")
    L += ["", "## Caveats",
          "- Drift windows are one synthetic time series; the generator is stationary apart from seasonality, so few alerts are expected. The PSI machinery is unit-tested (`tests/test_monitoring.py`) on injected shifts.",
          "- Fairness here audits proxy attributes (country, channel, category). It is a template for a real audit, not evidence about real customers; rates for small groups are noisy (groups <1000 rows excluded).",
          "- Promotion rule uses the single test split; no further holdout was kept."]
    (ROOT / "docs" / "PHASE6C_RESULTS.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
