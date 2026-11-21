"""Part A: Pakistan banking-system health from the SBP Quarterly Compendium (Sep-2026) + deposits/advances/investments series."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

con = connect()
PER = ["Sep-24", "Dec-24", "Mar-25", "Jun-25", "Sep-25", "Dec-25", "Mar-26", "Jun-26", "Sep-26"]
D: dict = {}

# ---- A1 financial soundness indicators (pages 6-9) ----
fsi: dict = {}
ind = None
df = sbp_lines(con, "QC-_Sep-26")
df = df[df.page.between(6, 9)]
for r in df.itertuples():
    t = r.raw_line.strip()
    if r.n_values == 0 and "|" not in t and not t.startswith(("^", "*", "#", "$", "&", "~", "Quarterly", "yCompendium", "Table", "Percent", "Indicators")) and len(t) < 70:
        ind = t
        continue
    if ind and r.n_values >= 3 and re.match(r"(Public|Local|Foreign|Commercial|Digital|Specialized|All)", r.label.replace(" ", ""), re.I):
        vals = [getattr(r, f"v{k}") for k in range(1, 10)][: r.n_values]
        fsi.setdefault(ind, {})[r.label] = vals
def allb(name):
    for k, v in fsi.items():
        if name.lower().replace(" ", "") in k.lower().replace(" ", ""):
            g = next((g for g in v if g.replace(" ", "").lower() == "allbanks"), None)
            if g:
                return v[g]
D["fsi_indicators_found"] = list(fsi)
keys = {"CAR": "RiskWeightedCAR", "Tier1": "Tier1Capital", "NPL ratio": "NPLstoTotal", "Provisions/NPLs": "ProvisionstoNPLs", "ROA after tax": "ReturnonAssets(AfterTax)",
        "ROE after tax": "ROE(Avg.Equity&Surplus)(AfterTax)", "Cost/income": "Cost/IncomeRatio", "Liquid assets/deposits": "LiquidAssets/TotalDeposits", "Advances/deposits": "Advances/Deposits",
        "Domestic loans to public sector / total loans": "PublicSectorDomesticLoanstoTotalLoans", "Corporate & SME loans / total loans": "Corporate&SMESectorDomesticLoanstoTotalLoans", "FX loans / total loans": "ForeignCurrencyLoanstoTotalLoans"}
A = {k: allb(v) for k, v in keys.items()}
D["all_banks_fsi"] = A
D["fsi_period_labels"] = PER
D["npl_ratio_by_group_sep26"] = {g: v[-1] for g, v in fsi.get("NPLstoTotal Loans", {}).items()}
D["car_by_group_sep26"] = {g: v[-1] for g, v in fsi.get("RiskWeightedCAR^", {}).items()}

# ---- A2 asset quality table 1.8 (page 16) ----
aq = sbp_lines(con, "QC-_Sep-26", 16)
rows = {}
for r in aq.itertuples():
    if r.row_no in (7, 8, 9, 10, 11, 15, 16, 17, 18, 19):
        rows.setdefault(r.label or r.raw_line[:20], []).append([getattr(r, f"v{k}") for k in range(1, 6)])
raw = {r.row_no: r.raw_line for r in aq.itertuples()}
def nums(s):
    out = []
    for x in re.findall(r"\(?-?[\d,]+\)?", s.split("|", 1)[1] if "|" in s else s):
        v = float(x.strip("()").replace(",", ""))
        out.append(-v if x.startswith("(") else v)
    return out
D["asset_quality_sep25_to_sep26"] = {"periods": ["Sep-25", "Dec-25", "Mar-26", "Jun-26", "Sep-26"], "gross_advances": nums(raw[7]), "npls": nums(raw[8]), "provisions": nums(raw[9]),
                                     "net_advances": nums(raw[10]), "net_npls": nums(raw[11]), "oaem": nums(raw[15]), "substandard": nums(raw[16]), "doubtful": nums(raw[17]), "loss": nums(raw[18])}
a = D["asset_quality_sep25_to_sep26"]
D["gross_npl_ratio_sep26_pct"] = round(a["npls"][-1] / a["gross_advances"][-1] * 100, 2)
D["loss_category_share_of_npls_sep26_pct"] = round(a["loss"][-1] / a["npls"][-1] * 100, 1)
D["gross_advances_growth_sep25_sep26_pct"] = round((a["gross_advances"][-1] / a["gross_advances"][0] - 1) * 100, 1)
D["npl_growth_sep25_sep26_pct"] = round((a["npls"][-1] / a["npls"][0] - 1) * 100, 1)
D["doubtful_npl_jump_jun26_sep26_pct"] = round((a["doubtful"][-1] / a["doubtful"][-2] - 1) * 100, 1)
D["earlier_implied_gross_loans_jun26_rs_m"] = round(a["net_advances"][3] + a["provisions"][3] - 0, 0)

# ---- chart ----
fig, axs = plt.subplots(1, 3, figsize=(12, 3.6))
for ax, k in zip(axs, ("CAR", "NPL ratio", "Advances/deposits")):
    if A[k]:
        ax.plot(PER[-len(A[k]):], A[k], marker="o", lw=2); ax.set_title(f"All banks: {k} (%)", fontsize=10); ax.tick_params(axis="x", rotation=60)
fig.tight_layout(); fig.savefig(IMG / "allin_banking_fsi.png"); plt.close(fig)


# ---- A3 sector / segment NPLs (page 17) ----
def last3(raw):
    n = [float(x.replace(",", "")) for x in re.findall(r"(?<![\w.])\d[\d,]*\.?\d*(?![\w])", raw)]
    return n[-3:] if len(n) >= 15 else None


pg = sbp_lines(con, "QC-_Sep-26", 17)
seg, sec = {}, {}
for r in pg.itertuples():
    name = re.match(r"([A-Za-z][A-Za-z&/ ,.\-]+?)(?=\s*[\d(])", r.raw_line)
    l3 = last3(r.raw_line)
    if name and l3:
        (seg if r.row_no <= 30 else sec)[name.group(1).strip()] = {"advances_m": l3[0], "npls_m": l3[1], "npl_ratio_pct": l3[2]}
D["segment_npl_sep26"] = seg
D["sector_npl_sep26"] = sec
big = sorted(((k, v) for k, v in sec.items() if v["advances_m"] > 2e5 and k not in ("Total", "Others")), key=lambda kv: -kv[1]["npl_ratio_pct"])
D["sector_highest_npl_ratio_sep26"] = [(k, v["npl_ratio_pct"], v["advances_m"]) for k, v in big[:6]]
D["sector_lowest_npl_ratio_sep26"] = [(k, v["npl_ratio_pct"], v["advances_m"]) for k, v in big[-4:]]

# ---- A4 stress test (page 22) ----
st = sbp_lines(con, "QC-_Sep-26", 22)
sc = []
for r in st.itertuples():
    m = re.match(r"^(C-\d+|IR-\d|ER-\d|EQ-\d)\b.*?(Hypothetical|Historical)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", r.raw_line.replace("|", " "))
    if m:
        sc.append({"id": m.group(1), "type": m.group(2), "below0": int(m.group(3)), "0_8": int(m.group(4)), "8_11.5": int(m.group(5)), "above11.5": int(m.group(6))})
D["stress_scenarios_parsed"] = len(sc)
D["stress_max_banks_below_8pct"] = max((x["below0"] + x["0_8"] for x in sc), default=None)
D["stress_scenarios_with_any_bank_below_8pct"] = [x["id"] for x in sc if x["below0"] + x["0_8"] > 0]
D["stress_banks_total"] = (sc[0]["below0"] + sc[0]["0_8"] + sc[0]["8_11.5"] + sc[0]["above11.5"]) if sc else None
D["stress_scenarios"] = sc
D["spike_note"] = "SBP's own all-banks advances/deposits ratio (FSI table) jumps 36.3% (Sep-24) -> 49.7% (Dec-24) -> 39.7% (Mar-25)."

# ---- markdown ----
al = A
npl = D["npl_ratio_by_group_sep26"]
car = D["car_by_group_sep26"]
hi = "; ".join(f"{k} {r}% (Rs {v/1e3:,.0f}bn)" for k, r, v in D["sector_highest_npl_ratio_sep26"][:5])
lo = "; ".join(f"{k} {r}%" for k, r, v in D["sector_lowest_npl_ratio_sep26"])
md = f"""## A. Banking-system health (SBP Quarterly Compendium Sep-2026 and deposit/advance series)

**Capital and asset quality are strong on the headline, with some weak spots.**
- Risk-weighted capital adequacy (all banks) is {al['CAR'][-1]}% (Sep-26) against {al['CAR'][0]}% two years earlier; Tier 1 is {al['Tier1'][-1]}%. By group: public sector {car['PublicSector Commercial Banks']}%, local private {car['Local Private Banks']}%, foreign {car['Foreign Banks']}%, digital {car['Digital Banks']}%, specialized {car['Specialized Banks']}%.
- **Gross NPL ratio {D['gross_npl_ratio_sep26_pct']}% (Sep-26)**, down from {al['NPL ratio'][0]}% in Sep-24: NPLs of Rs {a['npls'][-1]/1e3:,.0f}bn on gross advances of Rs {a['gross_advances'][-1]/1e6:.2f}tn. Advances grew {D['gross_advances_growth_sep25_sep26_pct']}% in the year while NPLs fell {abs(D['npl_growth_sep25_sep26_pct'])}%. By group: public sector {npl['PublicSector Commercial Banks']}%, local private {npl['Local Private Banks']}%, foreign {npl['Foreign Banks']}%, digital {npl['Digital Banks']}%, specialized {npl['SpecializedBanks']}%.
- Provisions cover {al['Provisions/NPLs'][-1]}% of NPLs, so net NPLs are negative (Rs {a['net_npls'][-1]/1e3:,.0f}bn). But **{D['loss_category_share_of_npls_sep26_pct']}% of NPLs are in the 'loss' category** (the longest-overdue category), and the 'doubtful' bucket jumped {D['doubtful_npl_jump_jun26_sep26_pct']}% in one quarter (Rs {a['doubtful'][-2]/1e3:.0f}bn to Rs {a['doubtful'][-1]/1e3:.0f}bn), an early deterioration signal. Net NPLs also moved from -Rs 120bn to -Rs 54bn over the year as provisions fell faster than NPLs.
- Profitability is high but easing: ROE after tax {al['ROE after tax'][0]}% to {al['ROE after tax'][-1]}%, ROA after tax {al['ROA after tax'][0]}% to {al['ROA after tax'][-1]}%, and the cost/income ratio rose from {al['Cost/income'][0]}% to {al['Cost/income'][-1]}%, consistent with falling interest rates compressing margins (a reading, not tested).
- ![](img/allin_banking_fsi.png)

**Lending mix.** Banks are liquid (liquid assets {al['Liquid assets/deposits'][-1]}% of deposits) and lend little: the all-banks advances-to-deposits ratio is {al['Advances/deposits'][-1]}% (Sep-26). Corporate and SME lending is {al['Corporate & SME loans / total loans'][-1]}% of loans, domestic public-sector loans {al['Domestic loans to public sector / total loans'][-1]}%, and FX loans rose from {al['FX loans / total loans'][0]}% to {al['FX loans / total loans'][-1]}%.

**Where the bad loans are (Sep-26).** Highest NPL ratios among large sectors: {hi}. Lowest: {lo}. Consumer lending has the lowest NPL ratio of the segments ({seg.get('Consumer sector', {}).get('npl_ratio_pct', 'n/a')}%; credit cards {seg.get('i.Credit cards', {}).get('npl_ratio_pct', 'n/a')}%) and SME and agriculture loans the highest ({seg.get('SMEsSector', {}).get('npl_ratio_pct', 'n/a')}% and {seg.get('Agriculture Sector', {}).get('npl_ratio_pct', 'n/a')}%).

**Stress tests (SBP, Sep-26).** {D['stress_scenarios_parsed']} scenarios were parsed. In the worst single scenario {D['stress_max_banks_below_8pct']} of {D['stress_banks_total']} banks fall below 8% CAR and none goes below 0%. The critical infection ratio (the NPL ratio at which capital is wiped out) is 61.3% against the current 5.6% (read from the SBP table text).

**The late-2024 advances spike is real in SBP's published data.** The weekly advances series jumps 30% between Sep and Dec 2024. SBP's own all-banks advances-to-deposits ratio in the compendium moves {al['Advances/deposits'][0]}% (Sep-24), {al['Advances/deposits'][1]}% (Dec-24), {al['Advances/deposits'][2]}% (Mar-25), so it is not an OCR error. The cause is not stated in these files; a temporary year-end surge is the most likely reading but I have not verified that.
"""
save("part_a", md, D)
print(md)
