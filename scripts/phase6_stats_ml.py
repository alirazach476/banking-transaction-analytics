"""Phase 6: statistics + ML on the synthetic payment data, validated against known ground truth.

1. Logit (statsmodels) on the decline outcome -> do 95% CIs recover the generator's true coefficients
   (src/payments/constants.py DECLINE_LOGIT)? Restricted to USD payments on non-expired/non-blocked cards
   (forced declines and FX conversion are outside the logit) and to rows without injected defects.
2. Chi-square / Mann-Whitney tests.
3. Gradient boosting (XGBoost) with a time-based split: ROC-AUC, PR-AUC, calibration; SHAP importance.
Writes docs/PHASE6_RESULTS.md and docs/PHASE6_RESULTS.json (all numbers measured, nothing hardcoded).
Run: PYTHONPATH=. python scripts/phase6_stats_ml.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.calibration import calibration_curve
import xgboost as xgb
import shap

from src.payments.constants import CARD_NOT_PRESENT_CHANNELS, DECLINE_LOGIT

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "source" / "payments"
SEED = 42


def load() -> pd.DataFrame:
    tx = pd.read_csv(SRC / "payment_transactions.csv", dtype=str, keep_default_na=False)
    ev = pd.read_csv(SRC / "payment_lifecycle_events.csv", dtype=str, keep_default_na=False)
    tx = tx[tx.dq_defect == ""].drop_duplicates("payment_id")
    resp = ev[(ev.event_type == "AUTH_RESPONSE") & (ev.dq_defect == "") & ev.event_status.isin(["APPROVED", "DECLINED"])]
    resp = resp.drop_duplicates("payment_id")[["payment_id", "event_status", "reason_code", "response_ms"]]
    d = tx.merge(resp, on="payment_id")
    d["amount"] = pd.to_numeric(d.amount, errors="coerce")
    d["ts"] = pd.to_datetime(d.authorization_ts, errors="coerce")
    d = d.dropna(subset=["amount", "ts"])
    d["declined"] = (d.event_status == "DECLINED").astype(int)
    d["response_ms"] = pd.to_numeric(d.response_ms, errors="coerce")
    d["intl"] = (d.is_international.str.lower() == "true").astype(float)
    d["cnp"] = d.channel.isin(CARD_NOT_PRESENT_CHANNELS).astype(float)
    d["night"] = (d.ts.dt.hour < 5).astype(float)
    d["fraud"] = (d.synthetic_fraud_pattern.str.lower() == "true").astype(float)
    d["hour"] = d.ts.dt.hour
    d["log_amt"] = np.log10(d.amount + 1)
    return d


def main():
    d = load()
    out = {"n_payments_used": int(len(d)), "overall_decline_rate": float(d.declined.mean())}

    # ---- 1. logit vs ground truth
    g = d[(d.currency == "USD") & ~d.card_status.str.title().isin(["Expired", "Blocked"])].copy()
    g["log10_amount_centered"] = g.log_amt - 1.7
    X = sm.add_constant(g[["intl", "cnp", "log10_amount_centered", "night", "fraud"]])
    m = sm.Logit(g.declined, X).fit(disp=0)
    truth = {"const": DECLINE_LOGIT["intercept"], "intl": DECLINE_LOGIT["international"],
             "cnp": DECLINE_LOGIT["card_not_present"], "log10_amount_centered": DECLINE_LOGIT["log10_amount_centered"],
             "night": DECLINE_LOGIT["night"], "fraud": DECLINE_LOGIT["fraud_pattern"]}
    ci = m.conf_int()
    rows = []
    for k in m.params.index:
        lo, hi = ci.loc[k]
        rows.append({"term": k, "true": truth[k], "estimate": float(m.params[k]), "ci_low": float(lo),
                     "ci_high": float(hi), "ci_covers_truth": bool(lo <= truth[k] <= hi)})
    out["logit"] = {"n": int(len(g)), "rows": rows}

    # ---- 2. tests
    ct = pd.crosstab(d.channel, d.declined)
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    out["chi2_channel_vs_decline"] = {"chi2": float(chi2), "dof": int(dof), "p": float(p)}
    a = d.loc[d.declined == 0, "response_ms"].dropna(); b = d.loc[d.declined == 1, "response_ms"].dropna()
    mw = stats.mannwhitneyu(a, b)
    out["mannwhitney_response_ms_approved_vs_declined"] = {"median_approved": float(a.median()),
                                                          "median_declined": float(b.median()), "p": float(mw.pvalue)}
    # note: with n this large, p-values are tiny for any effect; report effect sizes too
    out["decline_rate_by_flag"] = {c: d.groupby(c).declined.mean().round(4).to_dict() for c in ["intl", "cnp", "night", "fraud"]}

    # ---- 3. ML, time-based split
    d = d.sort_values("ts")
    cut = d.ts.quantile(0.8)
    feats_num = ["log_amt", "intl", "cnp", "night", "hour"]
    F = pd.concat([d[feats_num], pd.get_dummies(d[["channel", "merchant_category", "card_status"]].apply(lambda s: s.str.title()),
                                                 dtype=float)], axis=1)
    tr, te = d.ts <= cut, d.ts > cut
    mdl = xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.08, subsample=0.8, colsample_bytree=0.8,
                            eval_metric="logloss", random_state=SEED, n_jobs=4)
    mdl.fit(F[tr], d.declined[tr])
    pr = mdl.predict_proba(F[te])[:, 1]
    y = d.declined[te]
    frac, mean_p = calibration_curve(y, pr, n_bins=10, strategy="quantile")
    out["xgboost"] = {"train_rows": int(tr.sum()), "test_rows": int(te.sum()), "test_base_rate": float(y.mean()),
                      "roc_auc": float(roc_auc_score(y, pr)), "pr_auc": float(average_precision_score(y, pr)),
                      "brier": float(brier_score_loss(y, pr)),
                      "calibration": [{"mean_pred": float(a), "observed": float(b)} for a, b in zip(mean_p, frac)]}
    # leakage guard: card_status Expired/Blocked force declines by construction -> report AUC without those rows
    keep = te & ~d.card_status.str.title().isin(["Expired", "Blocked"])
    out["xgboost"]["roc_auc_excluding_forced_declines"] = float(
        roc_auc_score(d.declined[keep], mdl.predict_proba(F[keep])[:, 1]))
    sv = shap.TreeExplainer(mdl).shap_values(F[te].sample(min(20000, int(te.sum())), random_state=SEED))
    imp = pd.Series(np.abs(sv).mean(axis=0), index=F.columns).sort_values(ascending=False).head(10)
    out["shap_top10_mean_abs"] = {k: round(float(v), 4) for k, v in imp.items()}

    (ROOT / "docs" / "PHASE6_RESULTS.json").write_text(json.dumps(out, indent=2))
    L = ["# Phase 6 results (measured; synthetic data)", "",
         f"Payments used (no injected defects, with an authorization response): **{out['n_payments_used']:,}**; "
         f"overall decline rate **{out['overall_decline_rate']:.4f}**.", "",
         f"## 1. Logit recovery of true coefficients (n={out['logit']['n']:,}, USD, non-expired/blocked cards)", "",
         "| term | true | estimate | 95% CI | CI covers truth |", "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['term']} | {r['true']} | {r['estimate']:.3f} | [{r['ci_low']:.3f}, {r['ci_high']:.3f}] | {'yes' if r['ci_covers_truth'] else '**no**'} |")
    c = out["chi2_channel_vs_decline"]; w = out["mannwhitney_response_ms_approved_vs_declined"]
    x = out["xgboost"]
    L += ["", "## 2. Tests",
          f"- Channel vs decline chi-square: chi2={c['chi2']:.1f}, dof={c['dof']}, p={c['p']:.3g}",
          f"- Response time approved vs declined (Mann-Whitney): medians {w['median_approved']:.0f} vs {w['median_declined']:.0f} ms, p={w['p']:.3g}",
          "- With hundreds of thousands of rows nearly any difference is 'significant'; read the effect sizes (decline rate by flag in the JSON).",
          "", "## 3. XGBoost (time split: train on first 80% of time, test on last 20%)",
          f"- train/test rows: {x['train_rows']:,} / {x['test_rows']:,}; test base decline rate {x['test_base_rate']:.4f}",
          f"- ROC-AUC {x['roc_auc']:.3f}; excluding forced (expired/blocked-card) declines {x['roc_auc_excluding_forced_declines']:.3f}; PR-AUC {x['pr_auc']:.3f}; Brier {x['brier']:.4f}",
          "", "SHAP top features (mean |SHAP|, log-odds): " + ", ".join(f"{k} {v}" for k, v in out["shap_top10_mean_abs"].items()),
          "", "## Caveats",
          "- Labels and features come from a synthetic generator with a known logit; high recovery shows the pipeline is sound, not that real-world declines behave this way.",
          "- Expired/Blocked cards are deterministic declines (a leak-like feature); the AUC excluding them is the honest signal.",
          "- No hyper-parameter search or fairness analysis was done."]
    (ROOT / "docs" / "PHASE6_RESULTS.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
