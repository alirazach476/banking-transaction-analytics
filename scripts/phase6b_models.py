"""Phase 6b: fraud-pattern model, unsupervised anomaly detection, demand forecasting, customer segmentation,
hyper-parameter search, and model persistence (models/*.joblib + models/model_registry.json).

All numbers are measured on the synthetic payment data and written to docs/PHASE6B_RESULTS.md/.json.
Run: PYTHONPATH=. python scripts/phase6b_models.py
"""
from __future__ import annotations
import json, warnings
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import loguniform, randint, uniform
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, silhouette_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from scripts.phase6_stats_ml import load

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
SEED = 42
registry: dict = {}


def save(name, obj, meta):
    MODELS.mkdir(exist_ok=True)
    path = MODELS / f"{name}.joblib"
    joblib.dump(obj, path)
    registry[name] = {"file": f"models/{path.name}", "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "seed": SEED, "synthetic_data_only": True, **meta}


def search(X, y, groups_time_sorted=True, n_iter=8):
    base = xgb.XGBClassifier(eval_metric="logloss", random_state=SEED, n_jobs=4, tree_method="hist")
    dist = {"n_estimators": randint(150, 500), "max_depth": randint(2, 7), "learning_rate": loguniform(0.02, 0.2),
            "subsample": uniform(0.6, 0.4), "colsample_bytree": uniform(0.6, 0.4), "min_child_weight": randint(1, 20)}
    rs = RandomizedSearchCV(base, dist, n_iter=n_iter, scoring="average_precision", cv=TimeSeriesSplit(3),
                            random_state=SEED, n_jobs=1, refit=True)
    rs.fit(X, y)
    return rs


def main():
    d = load().sort_values("ts").reset_index(drop=True)
    out = {}
    cut = d.ts.quantile(0.8)
    tr, te = (d.ts <= cut).to_numpy(), (d.ts > cut).to_numpy()

    # ---------- card-level behavioural features (point-in-time: only past events)
    # robust computation: sort by card then time, rolling per card, then restore order
    tmp = d[["card_id", "ts", "amount"]].copy()
    tmp["_i"] = np.arange(len(tmp))
    tmp = tmp.sort_values(["card_id", "ts"])
    r = tmp.set_index("ts").groupby("card_id")["amount"].rolling("60min")
    tmp["card_txn_60m"] = r.count().to_numpy()
    tmp["card_amt_60m"] = r.sum().to_numpy()
    tmp["card_prior_mean"] = tmp.groupby("card_id")["amount"].transform(lambda x: x.shift().expanding().mean())
    tmp = tmp.sort_values("_i")
    d["card_txn_60m"] = tmp["card_txn_60m"].to_numpy()
    d["card_amt_60m"] = tmp["card_amt_60m"].to_numpy()
    d["amt_vs_card_mean"] = (d.amount / tmp["card_prior_mean"].to_numpy()).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    d["foreign_merchant"] = (d.merchant_country != d.card_country).astype(float)

    # ---------- 1. fraud-pattern model (supervised) + isolation forest (unsupervised)
    fcols = ["log_amt", "intl", "cnp", "night", "hour", "card_txn_60m", "card_amt_60m", "amt_vs_card_mean", "foreign_merchant"]
    X, y = d[fcols], d.fraud.astype(int)
    rs = search(X[tr].iloc[-200000:], y[tr].iloc[-200000:]) if y[tr].sum() > 50 else None
    best = rs.best_estimator_
    p = best.predict_proba(X[te])[:, 1]
    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=SEED, n_jobs=4).fit(X[tr])
    a = -iso.score_samples(X[te])
    prec, rec, thr = precision_recall_curve(y[te], p)
    f1 = 2 * prec * rec / np.maximum(prec + rec, 1e-9)
    k = int(np.nanargmax(f1[:-1]))
    out["fraud"] = {"test_rows": int(te.sum()), "test_fraud_rate": float(y[te].mean()),
                    "best_params": {kk: (float(v) if isinstance(v, (float, np.floating)) else int(v)) for kk, v in rs.best_params_.items()},
                    "cv_pr_auc": float(rs.best_score_), "supervised_pr_auc": float(average_precision_score(y[te], p)),
                    "supervised_roc_auc": float(roc_auc_score(y[te], p)),
                    "best_f1": float(f1[k]), "precision_at_best_f1": float(prec[k]), "recall_at_best_f1": float(rec[k]),
                    "isolation_forest_pr_auc": float(average_precision_score(y[te], a)),
                    "isolation_forest_roc_auc": float(roc_auc_score(y[te], a)),
                    "random_baseline_pr_auc": float(y[te].mean())}
    save("fraud_xgb", {"model": best, "features": fcols, "threshold": float(thr[k])},
         {"task": "synthetic fraud-pattern detection", "features": fcols, "metrics": {"pr_auc": out["fraud"]["supervised_pr_auc"]}})
    save("anomaly_isoforest", {"model": iso, "features": fcols}, {"task": "unsupervised anomaly score", "features": fcols,
                                                                  "metrics": {"pr_auc": out["fraud"]["isolation_forest_pr_auc"]}})

    # ---------- 2. decline model with hyper-parameter search (replaces fixed params in phase6)
    dcols = ["log_amt", "intl", "cnp", "night", "hour"]
    DX = pd.concat([d[dcols], pd.get_dummies(d[["channel", "merchant_category", "card_status"]].apply(lambda s_: s_.str.title()), dtype=float)], axis=1)
    rs2 = search(DX[tr].iloc[-200000:], d.declined[tr].iloc[-200000:])
    pd_ = rs2.best_estimator_.predict_proba(DX[te])[:, 1]
    out["decline_tuned"] = {"best_params": {kk: (float(v) if isinstance(v, (float, np.floating)) else int(v)) for kk, v in rs2.best_params_.items()},
                            "cv_pr_auc": float(rs2.best_score_), "test_roc_auc": float(roc_auc_score(d.declined[te], pd_)),
                            "test_pr_auc": float(average_precision_score(d.declined[te], pd_))}
    save("decline_xgb", {"model": rs2.best_estimator_, "features": list(DX.columns)},
         {"task": "authorization decline probability", "features": list(DX.columns), "metrics": {"roc_auc": out["decline_tuned"]["test_roc_auc"]}})

    # ---------- 3. forecasting: daily payment volume, 90-day holdout
    daily = d.set_index("ts").resample("D").size()
    daily = daily[daily.index >= daily.index.min() + pd.Timedelta(days=7)]  # drop ramp-up edge
    h = 90
    train, test = daily.iloc[:-h], daily.iloc[-h:]
    naive = pd.Series(np.tile(train.iloc[-7:].to_numpy(), h // 7 + 1)[:h], index=test.index)
    hw = ExponentialSmoothing(train, trend="add", damped_trend=True, seasonal="add", seasonal_periods=7).fit()
    fc = hw.forecast(h)
    mape = lambda a_, b_: float(np.mean(np.abs((a_ - b_) / a_)) * 100)
    out["forecast"] = {"holdout_days": h, "seasonal_naive_mape_pct": mape(test, naive), "holt_winters_mape_pct": mape(test, fc),
                       "mean_daily_volume": float(daily.mean())}
    save("volume_holtwinters", hw, {"task": "daily payment volume forecast", "metrics": {"mape_pct": out["forecast"]["holt_winters_mape_pct"]}})

    # ---------- 4. customer segmentation
    c = d.groupby("customer_id").agg(n=("payment_id", "size"), mean_amt=("amount", "mean"), decline=("declined", "mean"),
                                     intl=("intl", "mean"), cnp=("cnp", "mean"), n_cat=("merchant_category", "nunique"))
    c = c[c.n >= 5]
    c["log_n"] = np.log1p(c.n); c["log_amt"] = np.log1p(c.mean_amt)
    cf = ["log_n", "log_amt", "decline", "intl", "cnp", "n_cat"]
    sc = StandardScaler().fit(c[cf]); Z = sc.transform(c[cf])
    sample = np.random.default_rng(SEED).choice(len(Z), min(5000, len(Z)), replace=False)
    scores = {}
    for kk in range(3, 8):
        lab = KMeans(kk, n_init=5, random_state=SEED).fit_predict(Z)
        scores[kk] = float(silhouette_score(Z[sample], lab[sample]))
    kbest = max(scores, key=scores.get)
    km = KMeans(kbest, n_init=10, random_state=SEED).fit(Z)
    c["segment"] = km.labels_
    prof = c.groupby("segment").agg(customers=("n", "size"), avg_payments=("n", "mean"), avg_amount=("mean_amt", "mean"),
                                    decline_rate=("decline", "mean"), intl_share=("intl", "mean"), cnp_share=("cnp", "mean"))
    out["segmentation"] = {"customers": int(len(c)), "silhouette_by_k": scores, "chosen_k": kbest,
                           "profiles": prof.round(3).reset_index().to_dict("records")}
    save("customer_segments_kmeans", {"scaler": sc, "model": km, "features": cf},
         {"task": "customer behavioural segmentation", "features": cf, "metrics": {"silhouette": scores[kbest]}})

    (MODELS / "model_registry.json").write_text(json.dumps(registry, indent=2))
    (ROOT / "docs" / "PHASE6B_RESULTS.json").write_text(json.dumps(out, indent=2))
    f, dt, fo, sg = out["fraud"], out["decline_tuned"], out["forecast"], out["segmentation"]
    L = ["# Phase 6b results (measured; synthetic data)", "",
         "## Fraud-pattern detection (time split, 80/20)",
         f"- Test rows {f['test_rows']:,}; fraud rate {f['test_fraud_rate']:.4%} (random-guess PR-AUC = that rate)",
         f"- XGBoost (RandomizedSearchCV, TimeSeriesSplit(3), 8 candidates): CV PR-AUC {f['cv_pr_auc']:.3f}; test PR-AUC {f['supervised_pr_auc']:.3f}, ROC-AUC {f['supervised_roc_auc']:.3f}",
         f"- Best-F1 operating point: F1 {f['best_f1']:.3f} (precision {f['precision_at_best_f1']:.3f}, recall {f['recall_at_best_f1']:.3f})",
         f"- Unsupervised IsolationForest: PR-AUC {f['isolation_forest_pr_auc']:.3f}, ROC-AUC {f['isolation_forest_roc_auc']:.3f}",
         "", "## Decline model, tuned",
         f"- CV PR-AUC {dt['cv_pr_auc']:.3f}; test ROC-AUC {dt['test_roc_auc']:.3f}, PR-AUC {dt['test_pr_auc']:.3f} (phase 6 fixed-parameter ROC-AUC was 0.635)",
         "", "## Daily volume forecast (90-day holdout)",
         f"- Holt-Winters (damped trend, weekly seasonality) MAPE {fo['holt_winters_mape_pct']:.2f}% vs seasonal-naive {fo['seasonal_naive_mape_pct']:.2f}%",
         "", f"## Customer segmentation (KMeans, {sg['customers']:,} customers with >=5 payments)",
         "- Silhouette by k: " + ", ".join(f"{k_}: {v:.3f}" for k_, v in sg["silhouette_by_k"].items()) + f"; chosen k={sg['chosen_k']}",
         "", "| segment | customers | avg payments | avg amount | decline rate | intl share | CNP share |", "|---|---|---|---|---|---|---|"]
    for r_ in sg["profiles"]:
        L.append(f"| {int(r_['segment'])} | {int(r_['customers'])} | {r_['avg_payments']:.1f} | {r_['avg_amount']:.1f} | {r_['decline_rate']:.3f} | {r_['intl_share']:.3f} | {r_['cnp_share']:.3f} |")
    L += ["", "## Persistence", "Models saved to `models/*.joblib` with `models/model_registry.json` (features, metrics, seed, timestamp). Load with `joblib.load`.",
          "", "## Caveats",
          "- Synthetic data: the fraud pattern is a generated card burst (6-12 foreign e-commerce payments in <20 min); scores here say nothing about real-world fraud. Features are point-in-time (past events only), so the first payments of a burst look normal, which caps recall.",
          "- Segments are descriptive clusters; no ground-truth segment labels exist to validate against.",
          "- Search budget is small (8 candidates, 200k-row subsample); no fairness/drift monitoring; no serving endpoint yet (Phase 8)."]
    (ROOT / "docs" / "PHASE6B_RESULTS.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
