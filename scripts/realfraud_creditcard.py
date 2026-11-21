"""Fraud models on REAL card transactions: the public "creditcard" dataset (ULB Machine Learning Group; Dal Pozzolo, Caelen, Johnson, Bontempi 2015).

284,807 European card transactions over two days in September 2013, 492 frauds; features V1-V28 are PCA components (anonymised by the owners), plus Time and Amount.
Downloaded from OpenML (dataset 1597, licence 'Public'; original database under the Database Contents License) into data/external_downloads/openml_creditcard/ (git-ignored).
The file is validated before use (row count, fraud count, time range). Evaluation is TIME-ORDERED: train on the first 70% of the time span, test on the rest;
with only a few hundred frauds in total, the test metrics carry wide uncertainty, so PR-AUC bootstrap intervals are reported.
Writes docs/REAL_FRAUD_CREDITCARD.json (+ .md).   Run: python scripts/realfraud_creditcard.py
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "external_downloads" / "openml_creditcard" / "creditcard.arff"
raw = SRC.read_bytes()
i = raw.find(b"@data")
df = pd.read_csv(io.BytesIO(raw[i + 5:].lstrip()), header=None, dtype=str, na_filter=False)
cols = ["Time"] + [f"V{k}" for k in range(1, 29)] + ["Amount", "Class"]
assert df.shape[1] == 31, df.shape
df.columns = cols
df["Class"] = df["Class"].str.strip("'").astype(int)
for c in cols[:-1]:
    df[c] = pd.to_numeric(df[c], errors="raise")
# validation against the dataset's published properties
checks = {"rows": len(df), "frauds": int(df.Class.sum()), "time_max": float(df.Time.max()), "amount_mean": round(float(df.Amount.mean()), 4), "missing_cells": int(df.isna().sum().sum())}
assert checks["rows"] == 284807 and checks["frauds"] == 492 and checks["missing_cells"] == 0, f"download incomplete or altered: {checks}"
df = df.sort_values("Time").reset_index(drop=True)
cut = df.Time.min() + 0.7 * (df.Time.max() - df.Time.min())
tr, te = df[df.Time <= cut], df[df.Time > cut]
feats = [c for c in cols if c not in ("Class",)]
R = {"dataset": "creditcard (ULB / OpenML 1597)", "validation": checks, "train_rows": int(len(tr)), "test_rows": int(len(te)), "train_fraud": int(tr.Class.sum()), "test_fraud": int(te.Class.sum()),
     "test_fraud_rate": round(float(te.Class.mean()), 5), "split": f"train Time <= {cut:.0f}s (first 70% of the span), test after"}


def best_f1(y, s):
    p, r, th = precision_recall_curve(y, s)
    f1 = 2 * p * r / np.clip(p + r, 1e-9, None)
    k = int(np.nanargmax(f1[:-1]))
    return round(float(f1[k]), 4), round(float(p[k]), 4), round(float(r[k]), 4)


def recall_at_fpr(y, s, fpr=0.01):
    neg = np.sort(s[y == 0])
    thr = neg[int(np.ceil((1 - fpr) * len(neg))) - 1]
    return round(float((s[y == 1] > thr).mean()), 4)


def rep(name, s, y, rng):
    f1, p, r = best_f1(y.values, s)
    boots = []
    idx = np.arange(len(y))
    for _ in range(1000):
        b = rng.choice(idx, len(idx))
        if y.values[b].sum() == 0:
            continue
        boots.append(average_precision_score(y.values[b], s[b]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"model": name, "pr_auc": round(float(average_precision_score(y, s)), 4), "pr_auc_95ci": [round(float(lo), 3), round(float(hi), 3)], "roc_auc": round(float(roc_auc_score(y, s)), 4),
            "best_f1": f1, "precision_at_best_f1": p, "recall_at_best_f1": r, "recall_at_1pct_fpr": recall_at_fpr(y.values, s)}


rng = np.random.default_rng(7)
res = []
sc = StandardScaler().fit(tr[feats])
lr = LogisticRegression(max_iter=2000, class_weight="balanced", C=0.1).fit(sc.transform(tr[feats]), tr.Class)
res.append(rep("Logistic regression (balanced)", lr.predict_proba(sc.transform(te[feats]))[:, 1], te.Class, rng))
iso = IsolationForest(n_estimators=300, contamination="auto", random_state=7, n_jobs=-1).fit(tr[feats])
res.append(rep("IsolationForest (unsupervised)", -iso.score_samples(te[feats]), te.Class, rng))
spw = float((len(tr) - tr.Class.sum()) / tr.Class.sum())
xgb = XGBClassifier(n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, scale_pos_weight=min(spw, 50), tree_method="hist", n_jobs=-1, random_state=7, eval_metric="aucpr")
xgb.fit(tr[feats], tr.Class)
res.append(rep("XGBoost", xgb.predict_proba(te[feats])[:, 1], te.Class, rng))
R["results"] = res
R["random_baseline_pr_auc"] = R["test_fraud_rate"]
R["top_features_xgboost"] = {c: round(float(v), 3) for c, v in sorted(zip(feats, xgb.feature_importances_), key=lambda z: -z[1])[:8]}
(ROOT / "docs" / "REAL_FRAUD_CREDITCARD.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
lines = ["# Fraud models on real card transactions (public 'creditcard' dataset)", "",
         "Real, anonymised European card transactions from two days in September 2013 (ULB Machine Learning Group; Dal Pozzolo, Caelen, Johnson and Bontempi, CIDM 2015): "
         f"{checks['rows']:,} transactions, {checks['frauds']} frauds (0.17%). Features V1-V28 are PCA components published by the owners; Time and Amount are raw. Downloaded from OpenML (dataset 1597, licence 'Public'). "
         "This is the project's only evidence about real card fraud; the other fraud results come from simulators or synthetic data.", "",
         f"Split by time: train on the first 70% of the span ({R['train_rows']:,} rows, {R['train_fraud']} frauds), test on the rest ({R['test_rows']:,} rows, {R['test_fraud']} frauds, rate {R['test_fraud_rate']:.4%}). "
         f"The random-guess PR-AUC equals the test fraud rate ({R['test_fraud_rate']:.4f}).", "",
         "| model | PR-AUC (95% bootstrap CI) | ROC-AUC | best F1 | precision | recall | recall at 1% false-positive rate |", "|---|---|---|---|---|---|---|"]
for r in res:
    lines.append(f"| {r['model']} | {r['pr_auc']} ({r['pr_auc_95ci'][0]}-{r['pr_auc_95ci'][1]}) | {r['roc_auc']} | {r['best_f1']} | {r['precision_at_best_f1']} | {r['recall_at_best_f1']} | {r['recall_at_1pct_fpr']} |")
lines += ["", "Most important XGBoost features: " + ", ".join(f"{k} {v}" for k, v in R["top_features_xgboost"].items()) + " (PCA components, so not interpretable as named variables).", "",
          "## Limits", f"- Only {R['test_fraud']} frauds in the test period, hence the wide bootstrap intervals; differences between models smaller than the intervals should not be read as real.",
          "- Two days of one European issuer in 2013 and anonymised features: performance here does not transfer to Pakistani card or wallet fraud, and the NovaBank API's fraud model (trained on synthetic data) is unaffected by this result.",
          "- The time split puts all test frauds after the training period, which is the realistic direction, but a two-day window has little concept drift to test."]
(ROOT / "docs" / "REAL_FRAUD_CREDITCARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
