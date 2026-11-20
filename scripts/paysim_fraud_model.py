"""Fraud model on the PaySim dataset (public simulated mobile-money data, 6.36M rows) with a time-based split.

PaySim is itself a SIMULATION derived from a real mobile-money log, so results show method behaviour on that simulator, not real-world fraud.
Fraud only occurs in TRANSFER and CASH_OUT; the model is trained on those. Compares: (a) a one-line rule, (b) XGBoost with all features,
(c) XGBoost without balance-consistency features (to show how much of the signal is the simulator's balance artefact).
Writes docs/PAYSIM_FRAUD_RESULTS.md/.json.   Run: python scripts/paysim_fraud_model.py
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
con = duckdb.connect(str(ROOT / "data" / "warehouse" / "novabank_data.duckdb"), read_only=True)
df = con.execute("""select step, _type t, amount, oldbalanceorg ob_o, newbalanceorig nb_o, oldbalancedest ob_d, newbalancedest nb_d, isfraud y
                    from external_paysim.paysim_transactions where _type in ('TRANSFER','CASH_OUT')""").df()
df["is_transfer"] = (df.t == "TRANSFER").astype(int)
df["hour"] = df.step % 24
df["err_orig"] = df.ob_o - df.amount - df.nb_o        # 0 when the origin balance update is consistent
df["err_dest"] = df.ob_d + df.amount - df.nb_d
df["orig_emptied"] = ((df.nb_o == 0) & (df.ob_o > 0)).astype(int)
df["dest_zero_both"] = ((df.ob_d == 0) & (df.nb_d == 0)).astype(int)

cut = 600  # steps 1-600 train (hours), 601-743 test
tr, te = df[df.step <= cut], df[df.step > cut]
R = {"rows_modelled": int(len(df)), "train_rows": int(len(tr)), "test_rows": int(len(te)),
     "train_fraud": int(tr.y.sum()), "test_fraud": int(te.y.sum()), "test_fraud_rate": round(float(te.y.mean()), 5)}

full = ["amount", "ob_o", "nb_o", "ob_d", "nb_d", "is_transfer", "hour", "err_orig", "err_dest", "orig_emptied", "dest_zero_both"]
no_bal = ["amount", "is_transfer", "hour"]
no_err = ["amount", "ob_o", "nb_o", "ob_d", "nb_d", "is_transfer", "hour"]


def report(name, score, ytrue):
    p, r, th = precision_recall_curve(ytrue, score)
    f1 = 2 * p * r / np.clip(p + r, 1e-9, None)
    i = int(np.nanargmax(f1[:-1]))
    return {"model": name, "pr_auc": round(float(average_precision_score(ytrue, score)), 4),
            "roc_auc": round(float(roc_auc_score(ytrue, score)), 4), "best_f1": round(float(f1[i]), 4),
            "precision_at_best_f1": round(float(p[i]), 4), "recall_at_best_f1": round(float(r[i]), 4)}


res = [report("rule: origin emptied & amount>200k", ((te.orig_emptied == 1) & (te.amount > 200_000)).astype(float), te.y)]
spw = (len(tr) - tr.y.sum()) / tr.y.sum()
imp = {}
for name, cols in (("XGBoost all features", full), ("XGBoost without balance-error features", no_err), ("XGBoost amount/type/hour only", no_bal)):
    m = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8,
                      scale_pos_weight=min(spw, 100), tree_method="hist", n_jobs=-1, random_state=7, eval_metric="aucpr")
    m.fit(tr[cols], tr.y)
    res.append(report(name, m.predict_proba(te[cols])[:, 1], te.y))
    if name == "XGBoost all features":
        imp = {c: round(float(v), 3) for c, v in sorted(zip(cols, m.feature_importances_), key=lambda z: -z[1])}
R["results"] = res
R["feature_importance_all"] = imp
(ROOT / "docs" / "PAYSIM_FRAUD_RESULTS.json").write_text(json.dumps(R, indent=2), encoding="utf-8")
lines = ["# PaySim fraud model (time-based split)", "",
         "PaySim is a public **simulation** derived from a real mobile-money log. Fraud occurs only in TRANSFER/CASH_OUT, so only those "
         f"{R['rows_modelled']:,} rows are modelled. Train = steps 1-600 ({R['train_rows']:,} rows, {R['train_fraud']:,} fraud); "
         f"test = steps 601-743 ({R['test_rows']:,} rows, {R['test_fraud']:,} fraud, rate {R['test_fraud_rate']:.4%}).", "",
         "| model | PR-AUC | ROC-AUC | best F1 | precision | recall |", "|---|---|---|---|---|---|"]
for r in res:
    lines.append(f"| {r['model']} | {r['pr_auc']} | {r['roc_auc']} | {r['best_f1']} | {r['precision_at_best_f1']} | {r['recall_at_best_f1']} |")
lines += ["", "Feature importance (all-features model): " + ", ".join(f"{k} {v}" for k, v in imp.items()), ""]
(ROOT / "docs" / "PAYSIM_FRAUD_RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
