"""BIS CPMI cashless-payments analysis (26 reporting countries, annual 2012-2024) joined with WDI population and exchange rates.

Pakistan is not a CPMI reporter, so this is cross-country context, not Pakistan data. The BIS table repeats totals under many dimension
combinations, so headline rows are selected (all device/terminal/function/speed/issuer = A or Z; issued-inside or at-terminal-inside) and
validated by checking that instruments add up to 'cashless payments, all'. Values are converted to USD with the WDI annual-average
exchange rate; per-capita uses WDI total population. Writes docs/BIS_CPMI_ANALYSIS.md/.json and docs/img/bis_*.png.
Run: python scripts/bis_cpmi_analysis.py
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
con = duckdb.connect(str(ROOT / "data" / "warehouse" / "novabank_data.duckdb"), read_only=True)
R: dict = {}

b = con.execute("""
select left(rep_ctyreporting_country,2) cty, rep_ctyreporting_country cname, left(instrument_typeinstrument_type,1) inst, left(measuremeasure,1) meas,
       try_cast(time_periodtime_period_or_range as int) yr, try_cast(obs_valueobservation_value as double) v, unit_measureunit_of_measure unit,
       left(directiondirection,1) dr, left(terminal_locterminal_location,1) tl, left(card_iss_loccards_issuance_location,1) il,
       left(dev_state_techdevice_state_technology,1) dt, left(terminal_typeterminal_type,1) tt, left(card_fctcard_function,1) cf,
       left(paymt_speedpayment_speed,1) ps, left(issuer_or_onusissuer_or_onus_payments,1) io
from bis.ws_cpmi_cashless""").df()
R["raw_rows"] = int(len(b))
h = b[b.cf.isin(["A", "Z"]) & ((b.dt == "A") | ((b.inst == "M") & (b.dt == "O"))) & (b.tt == "A") & (b.ps == "A") & (b.io == "A") & b.dr.isin(["A", "Z", "D"])
      & ((b.il == "I") | (b.tl == "I") | ((b.il == "A") & (b.tl == "A")) | ((b.il == "Z") & (b.tl == "Z")))].dropna(subset=["v", "yr"])
# one value per country-year-instrument-measure: the largest consistent headline row
H = h.groupby(["cty", "cname", "inst", "meas", "yr"], as_index=False).agg(v=("v", "max"), unit=("unit", "first"), n_candidates=("v", "size"))
R["headline_rows"] = int(len(H))

# validation: F+B+C+D+E vs A (cashless payments, all), number of payments
N = H[H.meas == "N"].pivot_table(index=["cty", "yr"], columns="inst", values="v")
parts = [c for c in ("F", "B", "C", "D", "E") if c in N]
chk = N.dropna(subset=["A"] + parts[:1]).copy()
chk["sum_parts"] = chk[parts].sum(axis=1, min_count=1)
chk["ratio"] = chk.sum_parts / chk.A
R["validation_sum_of_instruments_over_total"] = {"n": int(chk.ratio.notna().sum()), "median": round(float(chk.ratio.median()), 3),
                                                 "share_within_5pct": round(float(((chk.ratio - 1).abs() <= .05).mean()), 3)}

# ---- WDI joins ----
cmap = con.execute("select country_code iso3, table_name from (select country_code, '' table_name from worldbank.d0037712_dr0095335_csv_file_wdicountry limit 0)").df() if False else None
cc = con.execute("select * from worldbank.d0037712_dr0095335_csv_file_wdicountry").df()
col2 = next(c for c in cc.columns if "2_alpha" in c or "2alpha" in c)
iso = cc[["country_code", col2]].rename(columns={col2: "cty", "country_code": "iso3"})
yrs = ", ".join(f"_{y}" for y in range(2012, 2025))
w = con.execute(f"select country_code iso3, indicator_code ic, {yrs} from worldbank.d0037712_dr0095335_csv_file_wdicsv where indicator_code in ('SP.POP.TOTL','PA.NUS.FCRF')").df()
w = w.melt(id_vars=["iso3", "ic"], var_name="yr", value_name="x")
w["yr"] = w.yr.str[1:].astype(int)
w["x"] = pd.to_numeric(w.x, errors="coerce")
w = w.merge(iso, on="iso3").pivot_table(index=["cty", "yr"], columns="ic", values="x").reset_index().rename(columns={"SP.POP.TOTL": "pop", "PA.NUS.FCRF": "fx"})
V = H[H.meas == "V"].merge(w, on=["cty", "yr"], how="left")
V["usd_m"] = V.v / V.fx
Nn = H[H.meas == "N"].merge(w[["cty", "yr", "pop"]], on=["cty", "yr"], how="left")
Nn["per_capita"] = Nn.v * 1e6 / Nn["pop"]
R["wdi_join_missing_fx_rows"] = int(V.fx.isna().sum())

# ---- results ----
yr = 2023
card = Nn[(Nn.inst == "F") & (Nn.yr == yr)].dropna(subset=["per_capita"]).sort_values("per_capita", ascending=False)
R["card_payments_per_capita_2023"] = {r.cname[4:]: round(r.per_capita, 1) for r in card.itertuples()}
tick = V[(V.inst == "F") & (V.yr == yr)][["cty", "cname", "usd_m"]].merge(Nn[(Nn.inst == "F") & (Nn.yr == yr)][["cty", "v"]], on="cty")
tick["avg_ticket_usd"] = tick.usd_m / tick.v
R["avg_card_ticket_usd_2023"] = {r.cname[4:]: round(r.avg_ticket_usd, 1) for r in tick.dropna().sort_values("avg_ticket_usd").itertuples()}
R["avg_card_ticket_usd_median"] = round(float(tick.avg_ticket_usd.median()), 1)

def cagr(inst, a=2015, z=2023):
    d = Nn[(Nn.inst == inst) & Nn.yr.isin([a, z])].pivot_table(index="cname", columns="yr", values="v").dropna()
    return ((d[z] / d[a]) ** (1 / (z - a)) - 1) * 100
for inst, nm in (("F", "card_emoney"), ("B", "credit_transfers"), ("D", "cheques"), ("M", "cash_withdrawals")):
    s = cagr(inst)
    R[f"cagr_2015_2023_{nm}"] = {"countries": int(len(s)), "median_pct": round(float(s.median()), 1), "share_declining": round(float((s < 0).mean()), 2),
                                 "fastest": [s.idxmax()[4:], round(float(s.max()), 1)], "slowest": [s.idxmin()[4:], round(float(s.min()), 1)]}
ind = Nn[(Nn.cty == "IN")].pivot_table(index="yr", columns="inst", values="v")
R["india_number_millions"] = {k: {int(y): round(float(v), 0) for y, v in ind[k].dropna().items() if y in (2015, 2019, 2023, 2024)} for k in ind.columns}
# cash vs card
cm = Nn[Nn.inst.isin(["F", "M"]) & (Nn.yr == yr)].pivot_table(index="cname", columns="inst", values="v").dropna()
cm["card_per_withdrawal"] = cm.F / cm.M
R["card_payments_per_cash_withdrawal_2023_median"] = round(float(cm.card_per_withdrawal.median()), 1)
R["card_payments_per_cash_withdrawal_2023"] = {i[4:]: round(float(r), 1) for i, r in cm.card_per_withdrawal.sort_values().items()}
# instrument mix 2023 (number)
mix = Nn[(Nn.yr == yr) & Nn.inst.isin(["F", "B", "C", "D", "E"])].pivot_table(index="cname", columns="inst", values="v")
mix = mix.div(mix.sum(axis=1), axis=0) * 100
R["instrument_mix_2023_median_pct"] = {k: round(float(mix[k].median()), 1) for k in mix.columns}

# ---- charts ----
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(figsize=(8, 5.5))
c2 = card.sort_values("per_capita")
ax.barh([n[4:] for n in c2.cname], c2.per_capita, color=["#1b9e77" if n.startswith("IN") else "#999" for n in c2.cname])
ax.set_title("Card and e-money payments per capita, 2023 (BIS CPMI + WDI population)"); fig.tight_layout(); fig.savefig(ROOT / "docs/img/bis_card_per_capita.png"); plt.close(fig)
fig, ax = plt.subplots(figsize=(8, 4))
for inst, l in (("F", "Card and e-money"), ("B", "Credit transfers"), ("D", "Cheques"), ("M", "Cash withdrawals")):
    s = Nn[Nn.inst == inst].groupby("yr").v.median()
    ax.plot(s.index, s / s.loc[2015] * 100, marker="o", ms=3, label=l)
ax.axhline(100, color="grey", lw=.7); ax.legend(frameon=False); ax.set_ylabel("Median country, 2015 = 100 (number of transactions)")
ax.set_title("Payment instruments over time (BIS CPMI)"); fig.tight_layout(); fig.savefig(ROOT / "docs/img/bis_instruments.png"); plt.close(fig)

R["series"] = {
    "instrument_index_2015_100": [{"year": int(y), **{nm: round(float(Nn[(Nn.inst == k) & (Nn.yr == y)].v.median() / Nn[(Nn.inst == k) & (Nn.yr == 2015)].v.median() * 100), 1) for k, nm in (("F", "Card and e-money"), ("B", "Credit transfers"), ("D", "Cheques"), ("M", "Cash withdrawals"))}} for y in range(2012, 2025)
                                if all(len(Nn[(Nn.inst == k) & (Nn.yr == y)]) for k in "FBDM")],
    "card_per_capita_2023": [{"country": r.cname[4:], "per_capita": round(float(r.per_capita), 1), "is_india": r.cty == "IN"} for r in card.sort_values("per_capita").itertuples()],
}
(ROOT / "docs" / "BIS_CPMI_ANALYSIS.json").write_text(json.dumps(R, indent=2, default=str), encoding="utf-8")
print(json.dumps(R, indent=1, default=str)[:7500])
