"""PaySim fraud, balance-free models with account-history features, same time split as paysim_fraud_model.py (train steps 1-600, test 601-743).

Features use only information available BEFORE each transaction (cumulative counts per account by time order, no balances, no label information):
amount, log amount, type, hour, dest_prior_count, orig_prior_count, dest_seen_before, amount_is_round, amount_rank_within_step.
Compares with the earlier balance-free baseline (amount/type/hour only, PR-AUC 0.52). Appends a section to docs/PAYSIM_FRAUD_RESULTS.md.
Run: python scripts/paysim_fraud_behavioural.py
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
df = con.execute("""select step, _type t, amount, nameorig o, namedest d, isfraud y from external_paysim.paysim_transactions
                    where _type in ('TRANSFER','CASH_OUT') order by step""").df()
df["is_transfer"] = (df.t == "TRANSFER").astype(int)
df["hour"] = df.step % 24
df["log_amount"] = np.log1p(df.amount)
df["amount_is_round"] = (df.amount % 1000 == 0).astype(int)
df["dest_prior_count"] = df.groupby("d").cumcount()
df["orig_prior_count"] = df.groupby("o").cumcount()
df["dest_seen_before"] = (df.dest_prior_count > 0).astype(int)
df["amount_rank_in_step"] = df.groupby("step").amount.rank(pct=True)
# is this origin account a destination seen earlier (money received before it sends)?
first_dest_step = df.groupby("d").step.min()
df["orig_received_earlier"] = df.o.map(first_dest_step).lt(df.step).fillna(False).astype(int)
df = df.drop(columns=["o", "d"])
cut = 600
tr, te = df[df.step <= cut], df[df.step > cut]
base = ["amount", "is_transfer", "hour"]
beh = base + ["log_amount", "amount_is_round", "dest_prior_count", "orig_prior_count", "dest_seen_before", "amount_rank_in_step", "orig_received_earlier"]


def rep(name, s, y):
    p, r, th = precision_recall_curve(y, s)
    f1 = 2 * p * r / np.clip(p + r, 1e-9, None)
    i = int(np.nanargmax(f1[:-1]))
    return {"model": name, "pr_auc": round(float(average_precision_score(y, s)), 4), "roc_auc": round(float(roc_auc_score(y, s)), 4), "best_f1": round(float(f1[i]), 4),
            "precision": round(float(p[i]), 4), "recall": round(float(r[i]), 4)}


spw = min((len(tr) - tr.y.sum()) / tr.y.sum(), 100)
res, imp = [], {}
for name, cols in (("amount/type/hour only (earlier baseline)", base), ("with account-history features (no balances)", beh)):
    m = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, scale_pos_weight=spw, tree_method="hist", n_jobs=-1, random_state=7, eval_metric="aucpr")
    m.fit(tr[cols], tr.y)
    res.append(rep(name, m.predict_proba(te[cols])[:, 1], te.y))
    if cols is beh:
        imp = {c: round(float(v), 3) for c, v in sorted(zip(cols, m.feature_importances_), key=lambda z: -z[1])}
# fraud-rate sanity for the new features
fr = {"fraud_dest_seen_before_share": round(float(df[df.y == 1].dest_seen_before.mean()), 3), "legit_dest_seen_before_share": round(float(df[df.y == 0].dest_seen_before.mean()), 3),
      "fraud_orig_received_earlier_share": round(float(df[df.y == 1].orig_received_earlier.mean()), 3), "legit_orig_received_earlier_share": round(float(df[df.y == 0].orig_received_earlier.mean()), 3)}
out = {"results": res, "importance": imp, "feature_sanity": fr, "test_rows": int(len(te)), "test_fraud": int(te.y.sum())}
(ROOT / "docs" / "PAYSIM_FRAUD_BEHAVIOURAL.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
