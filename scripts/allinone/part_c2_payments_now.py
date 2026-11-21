"""Part C2: current Pakistani payments from SBP's quarterly Payment Systems Reviews (Q2 FY25 ... Q3 FY26 reports -> quarters Q2 FY24 ... Q3 FY26).

The PDFs (downloaded from sbp.org.pk into data/external_downloads/sbp_payments/) are text PDFs, read with pypdf in isolated mode (-I) because they are
downloaded, untrusted files. Annex tables A-1 (infrastructure), A-2 (cards), A-3 (PRISM), A-4 (retail payments by channel), A-15 (Raast), A-16 (cards by type)
are merged across reports (latest report wins for a quarter) and validated (components vs totals, revisions between reports).
Run:  python scripts/allinone/part_c2_payments_now.py   (PDFs are parsed with pypdf only; nothing in them is executed)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pypdf  # noqa: E402
from common import *  # noqa: E402,F403

DIR = ROOT / "data" / "external_downloads" / "sbp_payments"
D: dict = {}
NUM = re.compile(r"^-?\d[\d,]*\.?\d*$")


def quarter_key(q: str) -> tuple:
    m = re.match(r"Q(\d)-FY(\d\d)", q)
    return (int(m.group(2)), int(m.group(1)))


def parse_pdf(path: Path):
    r = pypdf.PdfReader(str(path))
    text = "\n".join((p.extract_text() or "") for p in r.pages)
    # split into annex tables
    parts = re.split(r"\n(?=A-\d+:)", text)
    tables = {}
    for part in parts:
        m = re.match(r"(A-\d+):", part)
        if not m:
            continue
        lines = part.splitlines()
        qline = next((l for l in lines if len(re.findall(r"Q\d-FY\d\d", l)) >= 4), None)
        if not qline:
            continue
        quarters = [re.sub(r"[RP]$", "", q) for q in re.findall(r"Q\d-FY\d\d[RP]?", qline)]
        rows, section = {}, ""
        for l in lines[lines.index(qline) + 1:]:
            if l.startswith(("P:", "R:", "*", "1 ", "2 ", "3 ", "4 ", "Based on", "Payment Systems")):
                if l.startswith("P:"):
                    break
                continue
            toks = l.split()
            nums = [t for t in toks if NUM.match(t.replace(",", "")) or NUM.match(t)]
            lab = [t for t in toks if not (NUM.match(t.replace(",", "")) or NUM.match(t))]
            if not lab:
                continue
            label = " ".join(re.sub(r"(?<=[A-Za-z/])\d+$", "", t) for t in lab)
            if not nums:
                section = label if label.endswith("Transactions") else section
                continue
            vals = [float(t.replace(",", "")) for t in nums]
            rows[(section + " | " if section and m.group(1) == "A-16" else "") + re.sub(r"(?<=[A-Za-z\)])\d$", "", label)] = vals
        tables[m.group(1)] = {"quarters": quarters, "rows": rows}
    return tables


reports = {}
for f in sorted(DIR.glob("PS-Review-*.pdf")):
    reports[f.stem.replace("PS-Review-", "")] = parse_pdf(f)
D["reports"] = list(reports)
order = sorted(reports, key=lambda k: quarter_key(re.sub(r"(Q\d)(FY\d\d)", r"\1-\2", k)))


CANON = {"ATM": "ATM/CDM", "ATM/CDM": "ATM/CDM", "POS": "POS (CP)", "POS (CP)": "POS (CP)", "Internet Banking": "Internet Banking Portal", "Internet Banking Portal": "Internet Banking Portal",
         "Mobile Phone Banking": "Mobile Banking Apps", "Mobile Banking Apps": "Mobile Banking Apps", "Call Centers/ IVR Banking": "Call Centers/ IVR Banking",
         "E-Commerce": "E-Commerce (CNP)", "E-Commerce (CNP)": "E-Commerce (CNP)", "E-Wallet": "E-Money Wallets", "E-Money Wallets": "E-Money Wallets",
         "BB Wallet": "Branchless/Digital Banking Apps", "Branchless/Digital Banking Apps": "Branchless/Digital Banking Apps", "Direct Debit": "Direct Debit",
         "BB Agent": "Banking Agents", "Banking Agents": "Banking Agents", "Bank Branch": "Bank Branches", "Bank Branches": "Bank Branches", "Total Transactions": "Total Transactions"}


def merge(table, per_q, canon=False):
    """per_q = number of values per quarter in each row. Returns {label: {quarter: tuple}} (latest report wins)."""
    out, src = {}, {}
    for rk in order:
        t = reports[rk].get(table)
        if not t:
            continue
        qs = t["quarters"]
        for lab, vals in t["rows"].items():
            if canon:
                lab = CANON.get(lab)
                if lab is None:
                    continue
            if len(vals) != per_q * len(qs):
                continue
            for i, q in enumerate(qs):
                out.setdefault(lab, {})[q] = tuple(vals[i * per_q:(i + 1) * per_q])
                src.setdefault((lab, q), []).append((rk, tuple(vals[i * per_q:(i + 1) * per_q])))
    return out, src


A4, A4src = merge("A-4", 2, canon=True)
A1, _ = merge("A-1", 1)
A2, _ = merge("A-2", 1)
A3, _ = merge("A-3", 2)
A15, _ = merge("A-15", 2)
A16, _ = merge("A-16", 2)
qs = sorted({q for v in A4.values() for q in v}, key=quarter_key)
D["quarters"] = qs
D["a4_channels"] = list(A4)

# ---- validation: components sum to total; revisions between reports ----
comp = [k for k in A4 if not k.startswith("Total")]
chk = {}
for q in qs:
    if "Total Transactions" in A4 and q in A4["Total Transactions"]:
        s_vol = sum(A4[k][q][0] for k in comp if q in A4[k])
        s_val = sum(A4[k][q][1] for k in comp if q in A4[k])
        t = A4["Total Transactions"][q]
        chk[q] = [round(s_vol - t[0], 1), round(s_val - t[1], 1)]
D["a4_sum_minus_total_vol_value"] = chk
D["a4_quarters_passing_sum_check"] = [q for q, (a, b) in chk.items() if abs(a) / max(1, A4["Total Transactions"][q][0]) < 0.005 and abs(b) / max(1, A4["Total Transactions"][q][1]) < 0.005]
qs = D["a4_quarters_passing_sum_check"]
D["quarters_used"] = qs
rev = []
for (lab, q), lst in A4src.items():
    if lab == "Total Transactions" and len(lst) >= 2:
        first, last = lst[0][1], lst[-1][1]
        rev.append((q, lst[0][0], lst[-1][0], round((last[0] / first[0] - 1) * 100, 2), round((last[1] / first[1] - 1) * 100, 2)))
D["total_revisions_vs_first_report"] = rev
D["max_abs_revision_volume_pct"] = max((abs(r[3]) for r in rev), default=0)

# ---- headline series ----
tot = {q: A4["Total Transactions"][q] for q in qs}
dig_labels = ["ATM/CDM", "POS (CP)", "Internet Banking Portal", "Mobile Banking Apps", "Call Centers/ IVR Banking", "E-Commerce (CNP)", "E-Money Wallets", "Branchless/Digital Banking Apps", "Direct Debit"]
otc_labels = ["Banking Agents", "Bank Branches"]
def lab_like(prefix):
    return next((k for k in A4 if k.replace(" ", "").lower().startswith(prefix.replace(" ", "").lower())), None)
LAB = {n: lab_like(n) for n in dig_labels + otc_labels}
D["label_map"] = LAB
dig = {q: sum(A4[LAB[n]][q][0] for n in dig_labels if LAB[n] and q in A4[LAB[n]]) for q in qs}
digv = {q: sum(A4[LAB[n]][q][1] for n in dig_labels if LAB[n] and q in A4[LAB[n]]) for q in qs}
D["digital_share_of_volume_pct"] = {q: round(dig[q] / tot[q][0] * 100, 1) for q in qs}
D["digital_share_of_value_pct"] = {q: round(digv[q] / tot[q][1] * 100, 1) for q in qs}
D["retail_volume_m"] = {q: tot[q][0] for q in qs}
D["retail_value_bn"] = {q: tot[q][1] for q in qs}
first_q, last_q = qs[0], qs[-1]
yoy_q = qs[-5] if len(qs) >= 5 else qs[0]
D["window"] = [first_q, last_q, yoy_q]
D["retail_volume_yoy_pct"] = round((tot[last_q][0] / tot[yoy_q][0] - 1) * 100, 1)
D["retail_value_yoy_pct"] = round((tot[last_q][1] / tot[yoy_q][1] - 1) * 100, 1)
ch = {}
for n in dig_labels + otc_labels:
    k = LAB[n]
    if k and last_q in A4[k] and yoy_q in A4[k]:
        ch[n] = {"vol_last": A4[k][last_q][0], "vol_yoy_pct": round((A4[k][last_q][0] / A4[k][yoy_q][0] - 1) * 100, 1), "val_last_bn": A4[k][last_q][1],
                 "val_yoy_pct": round((A4[k][last_q][1] / A4[k][yoy_q][1] - 1) * 100, 1), "share_of_volume_pct": round(A4[k][last_q][0] / tot[last_q][0] * 100, 1),
                 "avg_ticket_rs": round(A4[k][last_q][1] * 1e9 / (A4[k][last_q][0] * 1e6)) if A4[k][last_q][0] else None}
D["channels_latest"] = ch
atm_k = LAB["ATM/CDM"]
D["atm_volume_change_since_first_quarter_pct"] = round((A4[atm_k][last_q][0] / A4[atm_k][first_q][0] - 1) * 100, 1)
D["atm_share_of_retail_volume_latest_pct"] = round(A4[atm_k][last_q][0] / tot[last_q][0] * 100, 1)

# validation against SBP's own stated digital totals (latest report snapshot)
_txt = pypdf.PdfReader(str(DIR / "PS-Review-Q3FY26.pdf")).pages[8].extract_text()
_m = re.search(r"Digital Channels\S*\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)", _txt)
if _m:
    sv = [float(x.replace(",", "")) for x in _m.groups()]
    D["sbp_stated_digital_q2_q3_vol_val"] = sv
    D["my_digital_q2_q3_vol_val"] = [round(dig["Q2-FY26"], 1), round(digv["Q2-FY26"] / 1e3, 1), round(dig["Q3-FY26"], 1), round(digv["Q3-FY26"] / 1e3, 1)]
    D["digital_definition_matches_sbp"] = bool(abs(dig["Q3-FY26"] - sv[2]) < 1 and abs(digv["Q3-FY26"] / 1e3 - sv[3]) < 0.2)
# infrastructure
def row1(A, prefix):
    k = next((k for k in A if k.replace(" ", "").lower().startswith(prefix.replace(" ", "").lower())), None)
    return A[k] if k else {}
INF = {"POS machines": row1(A1, "POS Machines"), "ATMs": row1(A1, "ATMs"), "bank branches": row1(A1, "Commercial Banks/ MFBs Branches"), "BB agents": row1(A1, "Branchless Banking Agents"),
       "QR merchants": row1(A1, "QR enabled"), "POS merchants": row1(A1, "POS enabled"), "mobile banking users": row1(A1, "Mobile Phone Banking Users"),
       "BB mobile app users": row1(A1, "Branchless Banking Mobile App"), "internet banking users": row1(A1, "Internet Banking Users"), "payment cards": row1(A1, "Payment Cards"),
       "e-commerce merchants (banks)": row1(A1, "E-Commerce Merchants")}
D["infrastructure"] = {k: {q: v[0] for q, v in d.items()} for k, d in INF.items()}
iq = sorted({q for d in INF.values() for q in d}, key=quarter_key)
D["infra_growth_yoy_pct"] = {k: round((d[iq[-1]][0] / d[qs[-5]][0] - 1) * 100, 1) for k, d in INF.items() if iq[-1] in d and qs[-5] in d}
D["infra_growth_over_window_pct"] = {k: round((d[iq[-1]][0] / d[min(d, key=quarter_key)][0] - 1) * 100, 1) for k, d in INF.items() if iq[-1] in d}
D["infra_first_quarter_by_series"] = {k: min(d, key=quarter_key) for k, d in INF.items() if d}
D["infra_window"] = [iq[0], iq[-1]]
cards = {k: {q: v[0] for q, v in row1(A2, k).items()} for k in ("Credit Cards", "Debit Cards", "Pre-Paid Cards", "Social Welfare Cards", "Overall Cards")}
D["cards"] = cards
# Raast
R = {k: A15[k] for k in A15}
rt = next((k for k in R if k.lower().startswith("total raast")), None)
rq = sorted(R[rt], key=quarter_key) if rt else []
D["raast_quarters"] = rq
if rt:
    D["raast_total"] = {q: R[rt][q] for q in rq}
    p2p = next(k for k in R if k.startswith("P2P"))
    p2m = next(k for k in R if k.startswith("P2M"))
    D["raast_p2p_vol"] = {q: R[p2p][q][0] for q in rq if q in R[p2p]}
    D["raast_p2m_vol"] = {q: R[p2m][q][0] for q in rq if q in R[p2m]}
    D["raast_vol_growth_pct_first_last"] = round((R[rt][rq[-1]][0] / R[rt][rq[0]][0] - 1) * 100, 1)
    D["raast_value_growth_pct_first_last"] = round((R[rt][rq[-1]][1] / R[rt][rq[0]][1] - 1) * 100, 1)
    D["raast_share_of_digital_vol_latest_pct"] = round(R[rt][rq[-1]][0] / dig[last_q] * 100, 1) if rq[-1] == last_q else None
# PRISM
pt = next((k for k in A3 if k.lower().startswith("total")), None)
if pt:
    pq = sorted(A3[pt], key=quarter_key)
    D["prism_quarters"] = pq
    D["prism_total_thousand_trn"] = {q: A3[pt][q] for q in pq}
    D["prism_value_growth_over_window_pct"] = round((A3[pt][pq[-1]][1] / A3[pt][pq[0]][1] - 1) * 100, 1)
    D["prism_value_yoy_pct"] = round((A3[pt][pq[-1]][1] / A3[pt][pq[-5]][1] - 1) * 100, 1)
    gs = next(k for k in A3 if k.startswith("Government"))
    D["prism_govsec_share_of_value_latest_pct"] = round(A3[gs][pq[-1]][1] / A3[pt][pq[-1]][1] * 100, 1)
# card mix at POS (A-16)
pos_deb = next((k for k in A16 if k.startswith("POS Transactions | Debit")), None)
pos_cre = next((k for k in A16 if k.startswith("POS Transactions | Credit")), None)
if pos_deb and pos_cre:
    q16 = sorted(A16[pos_deb], key=quarter_key)
    D["pos_credit_share_of_pos_volume_pct"] = {q: round(A16[pos_cre][q][0] / (A16[pos_cre][q][0] + A16[pos_deb][q][0]) * 100, 1) for q in q16}
# population-based metrics (population 241.5m from the SBP review, census 2023)
POP = 241.5
last4 = qs[-4:]
card_pay = sum(A4[LAB["POS (CP)"]][q][0] + A4[LAB["E-Commerce (CNP)"]][q][0] for q in last4)
D["population_m_used"] = POP
D["card_payments_per_capita_last4q"] = round(card_pay / POP, 2)
cashw = sum(A4[atm_k][q][0] for q in last4)  # ATM/CDM transactions include cash withdrawals mostly (95%); used as cash-out proxy
cash_wd_atm = None
A5, _ = merge("A-5", 2)
cw = next((k for k in A5 if k.lower().startswith("cash withdrawals")), None)
if cw:
    cash_wd_atm = sum(A5[cw][q][0] for q in last4 if q in A5[cw])
branch_cw = 0
A14, _ = merge("A-14", 2)
for k in A14:
    if k.lower().startswith("cash withdrawal"):
        branch_cw += sum(A14[k][q][0] for q in last4 if q in A14[k])
agent_cw = 0
A13, _ = merge("A-13", 2)
for k in A13:
    if k.lower().startswith("cash withdrawals"):
        agent_cw += sum(A13[k][q][0] for q in last4 if q in A13[k])
if cash_wd_atm:
    D["cash_withdrawals_last4q_m"] = {"atm": round(cash_wd_atm, 1), "branch": round(branch_cw, 1), "agents": round(agent_cw, 1)}
    D["card_payments_per_cash_withdrawal_now"] = round(card_pay / (cash_wd_atm + branch_cw + agent_cw), 2)
D["digital_txns_per_capita_per_year"] = round(sum(dig[q] for q in last4) / POP, 1)
D["mobile_apps_and_wallets_share_of_digital_pct"] = round((A4[LAB["Mobile Banking Apps"]][last_q][0] + A4[LAB["Branchless/Digital Banking Apps"]][last_q][0] + A4[LAB["E-Money Wallets"]][last_q][0]) / dig[last_q] * 100, 1)

# ---- charts ----
fig, ax = plt.subplots(figsize=(8.5, 4))
x = list(range(len(qs)))
ax.bar(x, [dig[q] / 1e3 for q in qs], label="Digital channels", color="#1b9e77")
ax.bar(x, [(tot[q][0] - dig[q]) / 1e3 for q in qs], bottom=[dig[q] / 1e3 for q in qs], label="Over-the-counter", color="#999")
ax.set_xticks(x); ax.set_xticklabels(qs, rotation=45); ax.set_ylabel("Transactions (billion per quarter)"); ax.legend(frameon=False); ax.set_title("Pakistan retail payments by quarter (SBP)")
fig.tight_layout(); fig.savefig(IMG / "allin_pk_retail_now.png"); plt.close(fig)
if rq:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(rq, [R[rt][q][0] for q in rq], color="#7570b3"); ax.set_ylabel("Raast transactions (million)"); ax.set_title("Raast instant payments by quarter (SBP)")
    fig.tight_layout(); fig.savefig(IMG / "allin_raast.png"); plt.close(fig)


# ---- markdown ----
ch = D["channels_latest"]
inf, infw = D["infrastructure"], D["infra_growth_yoy_pct"]
g = lambda k, q: inf[k][q][0] if isinstance(inf[k][q], (list, tuple)) else inf[k][q]
# ---- ECB terminal density benchmark ----
_c = connect()
_pos = _c.execute("select time_period, obs_value from ecb.ptn where ref_area='U2' and freq='A' and title='Terminals provided by resident payment service providers (PSPs), POS terminals' and unit_measure='PN' order by time_period desc limit 1").fetchone()
_posm = _c.execute("select time_period, obs_value from ecb.ptn where ref_area='U2' and freq='A' and title='Terminals provided by resident payment service providers (PSPs), POS terminals, per million inhabitants' order by time_period desc limit 1").fetchone()
_atm = _c.execute("select time_period, obs_value from ecb.ptn where ref_area='U2' and freq='A' and title='Terminals provided by resident payment service providers (PSPs), ATMs' and unit_measure='PN' order by time_period desc limit 1").fetchone()
ea_pop_m = float(_pos[1]) / float(_posm[1])
D["ecb_terminals"] = {"year": _pos[0], "pos_terminals": float(_pos[1]), "pos_per_million": round(float(_posm[1])), "atms": float(_atm[1]), "implied_population_m": round(ea_pop_m, 1), "atms_per_million": round(float(_atm[1]) / ea_pop_m)}
pk_pos_pm = g("POS machines", last_q) / POP
pk_atm_pm = g("ATMs", last_q) / POP
D["pakistan_terminals_per_million"] = {"pos": round(pk_pos_pm), "atms": round(pk_atm_pm)}
D["pakistan_vs_euro_area_density_pct"] = {"pos": round(pk_pos_pm / float(_posm[1]) * 100, 1), "atms": round(pk_atm_pm / D["ecb_terminals"]["atms_per_million"] * 100, 1)}
rtq = D["raast_total"]
branch_val_share = round(ch["Bank Branches"]["val_last_bn"] / tot[last_q][1] * 100, 1)
ecb_note = ""
md = f"""## C2. Current Pakistani payments (SBP quarterly Payment Systems Reviews, {qs[0]} to {last_q})

*This section replaces the FY2018-only limitation of Part C. Source: six SBP quarterly reviews (Q2 FY25 to Q3 FY26, downloaded from sbp.org.pk) merged into one quarterly series; the latest report wins for each quarter. The data covers payments through formal banking and payment channels only (cash outside the system is excluded); the latest quarters are provisional.*

**Scale and shift to digital.** In Q3 FY26 (Jan-Mar 2026) retail payments were {tot[last_q][0]:,.0f} million worth Rs {tot[last_q][1]/1e3:,.1f} trillion: volume {D['retail_volume_yoy_pct']:+.1f}% and value {D['retail_value_yoy_pct']:+.1f}% on a year earlier. Digital channels carried {D['digital_share_of_volume_pct'][last_q]}% of volume (against {D['digital_share_of_volume_pct'][qs[0]]}% in {qs[0]}) but only {D['digital_share_of_value_pct'][last_q]}% of value ({D['digital_share_of_value_pct'][qs[0]]}% in {qs[0]}); bank branches still carry {branch_val_share}% of value. Digital volume is {D['digital_txns_per_capita_per_year']} transactions per person per year (population 241.5 million).
- ![](img/allin_pk_retail_now.png)

**The volume is wallets and apps, not cards or ATMs** (Q3 FY26 shares of retail volume, year-on-year change in volume, average ticket):
| Channel | Volume (million) | Share | YoY volume | Avg ticket (Rs) |
|---|---|---|---|---|
| Branchless-banking wallet apps | {ch['Branchless/Digital Banking Apps']['vol_last']:,.0f} | {ch['Branchless/Digital Banking Apps']['share_of_volume_pct']}% | {ch['Branchless/Digital Banking Apps']['vol_yoy_pct']:+.0f}% | {ch['Branchless/Digital Banking Apps']['avg_ticket_rs']:,} |
| Bank/MFB mobile banking apps | {ch['Mobile Banking Apps']['vol_last']:,.0f} | {ch['Mobile Banking Apps']['share_of_volume_pct']}% | {ch['Mobile Banking Apps']['vol_yoy_pct']:+.0f}% | {ch['Mobile Banking Apps']['avg_ticket_rs']:,} |
| ATM/CDM | {ch['ATM/CDM']['vol_last']:,.0f} | {ch['ATM/CDM']['share_of_volume_pct']}% | {ch['ATM/CDM']['vol_yoy_pct']:+.0f}% | {ch['ATM/CDM']['avg_ticket_rs']:,} |
| Banking agents (OTC) | {ch['Banking Agents']['vol_last']:,.0f} | {ch['Banking Agents']['share_of_volume_pct']}% | {ch['Banking Agents']['vol_yoy_pct']:+.0f}% | {ch['Banking Agents']['avg_ticket_rs']:,} |
| POS (card present) | {ch['POS (CP)']['vol_last']:,.0f} | {ch['POS (CP)']['share_of_volume_pct']}% | {ch['POS (CP)']['vol_yoy_pct']:+.0f}% | {ch['POS (CP)']['avg_ticket_rs']:,} |
| Bank branches (OTC) | {ch['Bank Branches']['vol_last']:,.0f} | {ch['Bank Branches']['share_of_volume_pct']}% | {ch['Bank Branches']['vol_yoy_pct']:+.0f}% | {ch['Bank Branches']['avg_ticket_rs']:,} |
| Internet banking | {ch['Internet Banking Portal']['vol_last']:,.0f} | {ch['Internet Banking Portal']['share_of_volume_pct']}% | {ch['Internet Banking Portal']['vol_yoy_pct']:+.0f}% | {ch['Internet Banking Portal']['avg_ticket_rs']:,} |
| E-money wallets (EMIs) | {ch['E-Money Wallets']['vol_last']:,.0f} | {ch['E-Money Wallets']['share_of_volume_pct']}% | {ch['E-Money Wallets']['vol_yoy_pct']:+.0f}% | {ch['E-Money Wallets']['avg_ticket_rs']:,} |
| E-commerce (card not present) | {ch['E-Commerce (CNP)']['vol_last']:,.0f} | {ch['E-Commerce (CNP)']['share_of_volume_pct']}% | {ch['E-Commerce (CNP)']['vol_yoy_pct']:+.0f}% | {ch['E-Commerce (CNP)']['avg_ticket_rs']:,} |
Mobile apps and wallets together are {D['mobile_apps_and_wallets_share_of_digital_pct']}% of digital volume. ATM volume has stalled (+{ch['ATM/CDM']['vol_yoy_pct']:.0f}% in a year; ATMs are now {D['atm_share_of_retail_volume_latest_pct']}% of retail volume) while card-present POS grew {ch['POS (CP)']['vol_yoy_pct']:.0f}% and bank-branch volume fell {abs(ch['Bank Branches']['vol_yoy_pct']):.0f}%. Credit cards are a falling share of POS volume ({D['pos_credit_share_of_pos_volume_pct'][sorted(D['pos_credit_share_of_pos_volume_pct'], key=quarter_key)[0]]}% in {sorted(D['pos_credit_share_of_pos_volume_pct'], key=quarter_key)[0]} to {D['pos_credit_share_of_pos_volume_pct'][sorted(D['pos_credit_share_of_pos_volume_pct'], key=quarter_key)[-1]]}% in {sorted(D['pos_credit_share_of_pos_volume_pct'], key=quarter_key)[-1]}).

**Raast instant payments.** Raast processed {rtq[last_q][0]:,.0f} million transactions worth Rs {rtq[last_q][1]/1e3:,.1f} trillion in {last_q}, {D['raast_vol_growth_pct_first_last']/100 + 1:.1f}x the volume of {D['raast_quarters'][0]} ({rtq[D['raast_quarters'][0]][0]:,.0f} million); person-to-person transfers are {D['raast_p2p_vol'][last_q]:,.0f} million of that, and person-to-merchant payments rose from {D['raast_p2m_vol'].get('Q3-FY25', 0)} million a year earlier to {D['raast_p2m_vol'][last_q]} million. Raast is equal to {D['raast_share_of_digital_vol_latest_pct']}% of digital-channel volume (the two are counted on different bases, so treat this ratio as indicative).
- ![](img/allin_raast.png)

**Infrastructure (Mar 2026, change on Mar 2025).** POS machines {g('POS machines', last_q):,.0f} ({infw['POS machines']:+.0f}%); QR-enabled merchants {g('QR merchants', last_q):,.0f} ({infw['QR merchants']:+.0f}%); ATMs {g('ATMs', last_q):,.0f} ({infw['ATMs']:+.0f}%); bank/MFB branches {g('bank branches', last_q):,.0f} ({infw['bank branches']:+.0f}%); branchless-banking agents {g('BB agents', last_q):,.0f} ({infw['BB agents']:+.0f}%); payment cards {D['cards']['Overall Cards'][last_q]/1e6:.1f} million ({infw['payment cards']:+.0f}%: {D['cards']['Debit Cards'][last_q]/1e6:.1f} million debit, {D['cards']['Credit Cards'][last_q]/1e6:.2f} million credit); mobile-banking users {g('mobile banking users', last_q)/1e6:.1f} million ({infw['mobile banking users']:+.0f}%); branchless-banking app users {g('BB mobile app users', last_q)/1e6:.1f} million ({infw['BB mobile app users']:+.0f}%). Against June 2018 (Part C): ATMs 14,019 to {g('ATMs', last_q):,.0f}, POS machines 53,511 to {g('POS machines', last_q):,.0f} ({g('POS machines', last_q)/53511:.1f}x), cards 40.9 million to {D['cards']['Overall Cards'][last_q]/1e6:.1f} million.

**Terminal density against the euro area (ECB, {D['ecb_terminals']['year']}).** Pakistan has {D['pakistan_terminals_per_million']['pos']:,} POS terminals per million inhabitants against {D['ecb_terminals']['pos_per_million']:,} in the euro area (about {D['pakistan_vs_euro_area_density_pct']['pos']}% of the euro-area density), and {D['pakistan_terminals_per_million']['atms']} ATMs per million against {D['ecb_terminals']['atms_per_million']} ({D['pakistan_vs_euro_area_density_pct']['atms']}%). Euro-area ATM numbers are falling (253,000 in 2024, {D['ecb_terminals']['atms']:,.0f} in {D['ecb_terminals']['year']}) while POS terminals rose to {D['ecb_terminals']['pos_terminals']/1e6:.1f} million; Pakistan's ATMs are still growing (+8% a year).

**Large-value payments.** PRISM+ settled Rs {D['prism_total_thousand_trn'][last_q][1]:.1f} trillion in {last_q} ({D['prism_value_yoy_pct']:+.1f}% on a year earlier); government securities are {D['prism_govsec_share_of_value_latest_pct']}% of the value.

**Cards and cash, now against 2018.** Card payments (card-present POS plus card e-commerce) are {D['card_payments_per_capita_last4q']} per person per year (last four quarters) against 0.29 in FY2018, and {D['card_payments_per_cash_withdrawal_now']} card payments per cash withdrawal (ATM, branch and agent withdrawals) against 0.14 in FY2018: about the level of Saudi Arabia in 2018 (0.49) but still well below Indonesia (0.99) and India (1.1) in 2018. For comparison, the BIS 2023 figure for India is 9.5 card and e-money payments per person and for Indonesia 34.6 (Part C and the BIS report). The FY2018 and current figures are not strictly comparable (SBP's current review adds microfinance banks, branchless banking and e-money institutions, and its channel definitions changed), so read the change as direction and rough size.

**Reliability.** The channel rows add up to SBP's published total in {len(D['a4_quarters_passing_sum_check'])} of {len(D['a4_sum_minus_total_vol_value'])} quarters (the first quarter, {D['a4_sum_minus_total_vol_value'] and sorted(D['a4_sum_minus_total_vol_value'])[0]}, is excluded because the older report layout lacks the POS and e-commerce rows), and my digital-channel totals equal the totals SBP states for Q2 and Q3 FY26 (Q3: {D['my_digital_q2_q3_vol_val'][2]:,.1f} million and Rs {D['my_digital_q2_q3_vol_val'][3]} trillion against SBP's {D['sbp_stated_digital_q2_q3_vol_val'][2]:,.1f} million and Rs {D['sbp_stated_digital_q2_q3_vol_val'][3]} trillion). SBP revises earlier quarters: Q1 FY26 retail volume was revised by {[r for r in D['total_revisions_vs_first_report'] if r[0] == 'Q1-FY26'][0][3]:+.1f}% (value {[r for r in D['total_revisions_vs_first_report'] if r[0] == 'Q1-FY26'][0][4]:+.1f}%) between the Q1 FY26 and Q3 FY26 reports, and Q3 FY25 by {[r for r in D['total_revisions_vs_first_report'] if r[0] == 'Q3-FY25'][0][3]:+.1f}%; the latest published values are used throughout. The step-ups in some series between Q4 FY25 and Q1 FY26 (for example credit cards 2.2 to 3.1 million, branchless-banking volume) occur in the same quarter as those revisions and are not explained in the reports, so growth across that quarter should be treated with caution.
"""
save("part_c2", md, D)
print(md)
