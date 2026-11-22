"""Generate the NovaBank project PDF report.

Facts come from the repository itself wherever possible: the commit history (git), calibration results, forecast results and the
documented test/benchmark results. Figures that were measured on the local database are stated as such. All transactional data is synthetic.

Run: python scripts/generate_project_pdf.py   ->   docs/NovaBank_Project_Report.pdf
"""

from __future__ import annotations

import io
import json
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "NovaBank_Project_Report.pdf"
REPO = "https://github.com/alirazach476/banking-transaction-analytics"
LIVE = "https://banking-transaction-analytics.vercel.app"

TEAL = colors.HexColor("#0d6e6e")
DEEP = colors.HexColor("#102a43")
BLUE = colors.HexColor("#3b6fe0")
MUTED = colors.HexColor("#5c6b7a")
LINE = colors.HexColor("#d5dde6")
SOFT = colors.HexColor("#e6f3f3")
PAPER = colors.HexColor("#f7f9fb")

# the built-in PDF fonts cover Latin-1 only: swap the few symbols the text uses
_SYMBOLS = {"→": "->", "≥": ">=", "≤": "<=", "−": "-", "×": "x", "≈": "~", "–": "-", "—": " - ", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "..."}


def clean(text: str) -> str:
    for k, v in _SYMBOLS.items():
        text = text.replace(k, v)
    return text


def P(text, style):
    return Paragraph(clean(str(text)), style)


def styles():
    base = getSampleStyleSheet()
    mk = lambda name, parent, **kw: ParagraphStyle(name, parent=base[parent], **kw)
    return {
        "cover_title": mk("cover_title", "Title", fontName="Times-Bold", fontSize=28, leading=34, textColor=DEEP, alignment=TA_CENTER, spaceAfter=6),
        "cover_sub": mk("cover_sub", "Normal", fontName="Helvetica", fontSize=12, leading=16, textColor=MUTED, alignment=TA_CENTER, spaceAfter=5),
        "h1": mk("h1", "Heading1", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=DEEP, spaceBefore=14, spaceAfter=8),
        "h2": mk("h2", "Heading2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=TEAL, spaceBefore=10, spaceAfter=5),
        "body": mk("body", "Normal", fontName="Helvetica", fontSize=9.5, leading=13, textColor=DEEP, alignment=TA_JUSTIFY, spaceAfter=6),
        "bullet": mk("bullet", "Normal", fontName="Helvetica", fontSize=9.5, leading=13, textColor=DEEP, leftIndent=8, spaceAfter=2),
        "small": mk("small", "Normal", fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED, alignment=TA_CENTER),
        "caption": mk("caption", "Normal", fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=MUTED, alignment=TA_CENTER, spaceAfter=8),
        "note": mk("note", "Normal", fontName="Helvetica-Oblique", fontSize=8.5, leading=11.5, textColor=colors.HexColor("#6a5420"), alignment=TA_LEFT, spaceBefore=3, spaceAfter=8),
        "td": ParagraphStyle("td", fontName="Helvetica", fontSize=8, leading=10.5, textColor=DEEP),
        "tdb": ParagraphStyle("tdb", fontName="Helvetica-Bold", fontSize=8, leading=10.5, textColor=DEEP),
        "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white),
        "mono": ParagraphStyle("mono", fontName="Courier", fontSize=7.8, leading=10, textColor=DEEP),
    }


S = styles()


def bullets(items):
    return ListFlowable([ListItem(P(i, S["bullet"]), leftIndent=8, bulletColor=TEAL) for i in items], bulletType="bullet", start="•", leftIndent=12, bulletFontSize=9)


def kv_table(rows):
    data = [[P(f"<b>{k}</b>", ParagraphStyle("k", fontSize=9, textColor=DEEP)), P(v, ParagraphStyle("v", fontSize=9, textColor=DEEP))] for k, v in rows]
    t = Table(data, colWidths=[1.9 * inch, 4.7 * inch])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def data_table(headers, rows, widths=None, mono_first=False):
    hdr = [P(h, S["th"]) for h in headers]
    body = [[P(c, S["mono"] if (mono_first and j == 0) else S["td"]) for j, c in enumerate(row)] for row in rows]
    widths = widths or [6.6 * inch / len(headers)] * len(headers)
    t = Table([hdr] + body, colWidths=widths, repeatRows=1)
    cmds = [("BACKGROUND", (0, 0), (-1, 0), DEEP), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    cmds += [("BACKGROUND", (0, i), (-1, i), PAPER) for i in range(2, len(body) + 1, 2)]
    t.setStyle(TableStyle(cmds))
    return t


def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 8 * mm, "NovaBank Analytics Platform | transactional data is synthetic; real data is labelled")
    canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


# ------------------------------------------------------------------ repository facts
def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def commits() -> list[tuple[str, str, str]]:
    out = git("log", "--reverse", "--format=%h|%ad|%s", "--date=short")
    rows = []
    for line in out.splitlines():
        h, d, s = line.split("|", 2)
        rows.append((h, d, s if len(s) <= 118 else s[:115] + "..."))
    return rows


def load(rel: str):
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def shot(name: str, crop_h: int | None = None, quality: int = 78):
    """A UI screenshot cropped to its top part, as a JPEG, scaled to the text width."""
    p = ROOT / "docs" / "ui" / name
    if not p.exists():
        return None
    im = PILImage.open(p).convert("RGB")
    if crop_h:
        im = im.crop((0, 0, im.width, min(crop_h, im.height)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    w = 6.6 * inch
    return Image(buf, width=w, height=w * im.height / im.width)


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


# ------------------------------------------------------------------ report
def build():
    story = []
    log = commits()
    head = git("rev-parse", "--short", "HEAD") or "n/a"
    remote = git("rev-parse", "--short", "origin/main") or head
    cal = load("docs/_parts/calibration_results.json")
    fc = load("docs/_parts/forecasts.json")
    bm = load("config/pakistan_calibration.json")

    # ---- cover
    story.append(Spacer(1, 0.9 * inch))
    logo = ROOT / "docs" / "ui" / "logo-mark.png"
    if logo.exists():
        story.append(Image(str(logo), width=1.15 * inch, height=1.15 * inch, hAlign="CENTER"))
        story.append(Spacer(1, 10))
    story.append(P("NovaBank", S["cover_title"]))
    story.append(P("Banking Analytics Platform", S["cover_title"]))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="60%", thickness=1.2, color=TEAL, spaceBefore=4, spaceAfter=12, hAlign="CENTER"))
    story.append(P("Data engineering, real-data analysis, machine learning and a hosted analytics dashboard", S["cover_sub"]))
    story.append(P("Project Report (updated)", S["cover_sub"]))
    story.append(Spacer(1, 14))
    story.append(P("All transactional data in this project (customers, accounts, core-banking transactions, card payments) is synthetic and was generated for demonstration. "
                   "Pages and tables that use real published statistics (SBP, BIS, World Bank, ECB, FRED) say so and are never mixed with the synthetic records.", S["note"]))
    story.append(Spacer(1, 14))
    story.append(kv_table([
        ("Author", "Ali Raza"),
        ("Repository", f"{REPO}"),
        ("Live app", f"{LIVE} (read-only snapshot)"),
        ("API docs", f"{LIVE}/docs"),
        ("Report date", datetime.now().strftime("%d %B %Y")),
        ("Commits", f"{len(log)} (first {log[0][1]}, latest {log[-1][1]}); local HEAD {head}, origin/main {remote}" if log else "n/a"),
        ("Stack", "Python, PostgreSQL, dbt, Airflow, FastAPI, DuckDB, XGBoost, React, ECharts, MapLibre, Playwright, GitHub Actions, Vercel"),
    ]))
    story.append(PageBreak())

    # ---- 1 summary
    story.append(P("1. Summary", S["h1"]))
    story.append(P("NovaBank is a fictional retail bank used to demonstrate an end-to-end analytics platform: synthetic source systems, ingestion, a PostgreSQL warehouse modelled with dbt, "
                   "a card-payment lifecycle with reconciliation, anomaly detection and ML, an analysis of real Pakistani banking and payments statistics, and an analytics web application "
                   "that is deployed publicly. The platform keeps three kinds of data apart and labels each one: <b>synthetic</b> transactions, <b>real</b> published aggregates, and "
                   "<b>simulated</b> model results.", S["body"]))
    story.append(P("At a glance (verified on the local build)", S["h2"]))
    story.append(data_table(["Area", "Result"], [
        ["Core-banking data (synthetic)", "5,000 customers, 7,500 accounts, 50 branches, 101,600 transactions (2023-2025)"],
        ["Card payments (synthetic)", "493,199 payment attempts, 1,918,653 lifecycle events, 454,881 settlements in the 500k-attempt run; 2023-2025"],
        ["Warehouse / dbt", "full dbt build: 157 pass, 1 warning, 0 errors (staging, intermediate, warehouse, analytics, payment and external models, snapshot)"],
        ["Reconciliation", "settlement exceptions injected by the generator are recovered with at least 99% recall and 100% precision (generator ground truth)"],
        ["Anomaly alerts", "8,645 alerts (2,031 high severity); alerts are leads, not confirmed fraud"],
        ["Real data analysed", "SBP, BIS, World Bank (WDI, IDS, remittance prices, Global Findex), ECB, FRED; 63 charts and tables in the dashboard"],
        ["Analytics app", "11 pages, light and dark themes, server-side tables with CSV/Excel export, MapLibre map, ECharts"],
        ["Tests", "128 pytest, 6 vitest, 24 Playwright end-to-end; GitHub Actions: all 4 jobs pass"],
        ["Hosted", f"{LIVE}: the same app and API on Vercel over a bundled read-only DuckDB snapshot"],
    ], widths=[1.8 * inch, 4.8 * inch]))
    story.append(P("What this report does not claim: no result here shows that models would work on real Pakistani transactions, and no synthetic number should be read as a real-world measurement. "
                   "Section 12 lists the limits.", S["note"]))

    # ---- 2 architecture
    story.append(P("2. Architecture", S["h1"]))
    story.append(P("Flow: synthetic source systems -> ingestion -> raw -> data-quality checks -> PostgreSQL -> dbt (staging, intermediate, warehouse, analytics) -> anomaly detection and ML -> "
                   "FastAPI (<font face='Courier'>/v1</font>) -> React app. A second, separate track loads real public data (SBP, BIS, World Bank, ECB, FRED) into a DuckDB warehouse that is read-only "
                   "for analysis.", S["body"]))
    story.append(data_table(["Layer", "Technology", "Notes"], [
        ["Generation", "Python, NumPy", "vectorised, chunked, seeded; 7 labelled data-defect types; ledger-consistent balances"],
        ["Storage", "PostgreSQL 16 (embedded for local use), DuckDB, Parquet", "schemas raw, staging, intermediate, warehouse, analytics, audit, monitoring, payments, external_*"],
        ["Transformation", "dbt 1.9", "SCD2 customer and merchant dimensions, incremental facts, tests, source freshness"],
        ["Orchestration", "Airflow DAGs (tested in a container), project CLI", "payments pipeline and external-data DAGs; quality gate; drift check"],
        ["API", "FastAPI", "/v1 analytics routers (SQL aggregation, bound parameters, TTL cache, optional API key), model scoring API, rate limiting"],
        ["UI", "React 18, Vite, TanStack Query/Table, ECharts, MapLibre", "design system with dark and light themes; code-split pages"],
        ["Quality", "pytest, vitest, Playwright, GitHub Actions", "4 CI jobs: unit tests, tests with Postgres, frontend build and tests, API image"],
        ["Hosting", "Vercel (static + Python function), DuckDB snapshot", "see section 11"],
    ], widths=[1.2 * inch, 2.1 * inch, 3.3 * inch]))

    # ---- 3 data
    story.append(P("3. Synthetic data and the warehouse", S["h1"]))
    story.append(P("Two synthetic domains share customer and merchant identifiers. <b>Core banking</b> holds account transactions across channels; <b>card payments</b> hold the full authorization-to-settlement "
                   "lifecycle. Value metrics in the app are converted to USD with the dataset's own synthetic FX table (last rate on or before the date); amounts whose currency has no rate stay in "
                   "volume counts but are left out of value.", S["body"]))
    story.append(data_table(["Entity", "Count / value"], [
        ["Customers / accounts / branches / merchants / cards", "5,000 / 7,500 / 50 / 1,000 / 10,000"],
        ["Core-banking transactions", "101,600; completed value US$ 72.79 million (USD-converted); average US$ 808.90"],
        ["Card payment attempts", "493,199 (2023-01-01 to 2025-12-31)"],
        ["Lifecycle events / settlements", "1,918,653 / 454,881 (500k-attempt run)"],
        ["Injected settlement exceptions (ground truth)", "9,563"],
        ["Scale tests", "core-banking generator: 2.0M transactions and 100K customers in about 4.3 minutes; payments: 1M in 228 s, 2M in 457 s"],
    ], widths=[2.8 * inch, 3.8 * inch]))
    story.append(P("Correction to an earlier version of this report: it showed a total value of $81.2 million and branch values that summed amounts in mixed currencies without conversion. "
                   "The figures here are USD-converted.", S["note"]))
    story.append(P("Warehouse and dbt", S["h2"]))
    story.append(bullets([
        "Kimball star schema: dim_customer (SCD Type 2), dim_account, dim_branch, dim_merchant, dim_card, dim_channel, dim_transaction_type, dim_date; fact_transactions, fact_transfers, fact_atm_transactions, fact_card_transactions.",
        "dbt layers: staging (clean, cast, standardise, deduplicate), intermediate (payment outcomes, anomaly features), warehouse (dimensions, incremental facts), analytics (daily and monthly, customer, branch, channel, failures, payment KPIs, decline reasons, settlement daily).",
        "Quality: source defects are injected on purpose and standardised in staging; results land in audit.data_quality_results; reconciliation compares source and warehouse counts and sums.",
        "Latest observed control totals: 17 data-quality checks recorded, 16 pass and 1 foreign-key check fails with 101 rows (visible on the Engineering page).",
    ]))

    # ---- 4 payments
    story.append(P("4. Payment lifecycle and reconciliation", S["h1"]))
    story.append(P("Each payment can pass through authorization request and response, clearing, settlement, reversal, refund and chargeback. KPI definitions are explicit: approval rate = authorized / "
                   "(authorized + declined); decline rate is its complement; chargeback rate = chargebacks / settled payments (disputes arrive 10-90 days later, so recent periods are understated).", S["body"]))
    story.append(data_table(["Latest payments reconciliation run", "Count"], [
        ["Cleared payments", "448,557"], ["Matched to a settlement", "439,582"], ["Missing settlement", "1,882"], ["Duplicate settlement", "1,398"],
        ["Amount mismatch", "1,370"], ["Currency mismatch", "680"], ["Late (beyond the 3-day SLA)", "3,645"], ["Unmatched settlements", "6,808"],
    ], widths=[4.0 * inch, 2.6 * inch]))
    story.append(P("The open exception queue holds 15,783 items. The exception types mirror the issues injected by the generator, which is why recall and precision can be measured.", S["body"]))

    # ---- 5 anomalies
    story.append(P("5. Anomaly detection and investigation", S["h1"]))
    story.append(P("Methods: rule-based (high amount, frequency, rapid window, night activity, repeated failures, sudden behaviour change), per-customer z-score (threshold 3.0) and an Isolation Forest "
                   "(contamination 0.02). Alerts are stored with a severity and a plain-language reason. They are labelled \"potential anomaly\", never \"fraud\": the data has no confirmed-fraud labels.", S["note"]))
    story.append(data_table(["Severity", "Alerts"], [["High", "2,031"], ["Medium", "1,573"], ["Low", "5,041"], ["Total", "8,645"]], widths=[3.3 * inch, 3.3 * inch]))
    story.append(P("Against the labels planted by the generator (usable only for evaluation), the rules recover 36% of injected anomalies and the Isolation Forest 13%; precision is low in both cases "
                   "because many alerts are legitimate unusual transactions. The app lets an analyst record an outcome per alert (new, investigating, confirmed fraud, false positive, closed); "
                   "that status is stored separately in monitoring.anomaly_investigations.", S["body"]))

    # ---- 6 ML
    story.append(P("6. Statistics and machine learning (synthetic and public data)", S["h1"]))
    story.append(data_table(["Experiment", "Data", "Result"], [
        ["Logit recovery of the generator's true decline coefficients", "synthetic payments, n = 394,398", "all 6 coefficients recovered; every 95% interval covers the truth"],
        ["XGBoost decline model, time-ordered split", "synthetic payments", "ROC-AUC 0.635 (0.606 without forced expired/blocked-card declines), PR-AUC 0.167"],
        ["Fraud model on synthetic payments", "synthetic payments", "PR-AUC about 0.26: modest, as expected from weak synthetic signal"],
        ["Behavioural fraud model, time split, no leakage", "PaySim simulator", "PR-AUC 0.80 (simulated data)"],
        ["XGBoost on public card transactions", "real European card data (2013), 132 test frauds", "PR-AUC 0.79 (95% interval 0.72-0.85); does not transfer to Pakistan"],
    ], widths=[2.6 * inch, 1.7 * inch, 2.3 * inch]))
    story.append(P("The synthetic-data results show that the pipeline is sound (the logit recovers known truth), not that real-world declines behave this way. Population stability (PSI) drift monitoring "
                   "and a fairness audit are in the repository (docs/PHASE6C_RESULTS.md).", S["body"]))

    # ---- 7 real data
    story.append(P("7. Real-data analysis: SBP, BIS, World Bank, ECB, FRED", S["h1"]))
    story.append(P("The warehouse holds the real files that were downloaded (SBP quarterly compendia and payment-systems reviews, BIS CPMI and locational statistics, World Bank WDI, IDS, remittance prices and "
                   "Global Findex, ECB payment statistics, FRED). The analysis covers eight parts: banking health, macro economy, payment systems, cross-border finance, global context, a 1,498-indicator "
                   "WDI screen, financial inclusion, and data quality. Selected findings (values as of the latest data in the files):", S["body"]))
    story.append(data_table(["Topic", "Finding"], [
        ["Monetary policy", "SBP policy rate 12.0% (Oct 2026); real rate 6.95% (Dec-2025 rate less 2025 inflation), third highest of 38 countries"],
        ["Banks", "capital adequacy 18.6%; gross NPL ratio 5.57% (8.4% two years earlier); 83.3% of NPLs are in the 'loss' category; advances are 36.1% of deposits"],
        ["Payments", "3,697 million retail payments in Q3 FY26 (+50.2% on a year earlier): 92.4% digital by volume but 40.4% by value; wallet apps are 58.5% of volume"],
        ["Raast", "742 million instant payments worth Rs 23.3 trillion in Q3 FY26, 6.9 times the volume of Q2 FY24"],
        ["Inclusion", "27.3% of adults have an account (rank 148 of 153); 11.9% of women, the lowest of all 153 economies"],
        ["External finance", "external debt US$ 135.1bn (34% of GNI); scheduled service of US$ 24.8bn in 2026; remittances US$ 41.6bn (+8.6%)"],
        ["Reliability", "13 of 16 cross-source checks pass; exchange rates from four sources agree; SBP tables are OCR extractions and were not checked cell by cell"],
    ], widths=[1.4 * inch, 5.2 * inch]))
    story.append(P("Limits that matter: BIS publishes no Pakistan payment statistics (cross-country charts use other countries), a part of BIS cross-border claims is confidential, one World Bank file is not public, "
                   "and this data is aggregate only (no individual transactions), so it cannot train a real Pakistani fraud or customer model.", S["note"]))

    # ---- 8 calibration + forecasts
    story.append(P("8. Calibration, forecasts and real-vs-synthetic comparison", S["h1"]))
    story.append(P("Calibration. The card-payment generator can optionally be calibrated to real SBP aggregates (Q3 FY26). With no calibration its output is byte-identical to the original, so the "
                   "validated baseline remains reproducible. The calibrated companion dataset matches the real targets largely by construction; that shows the calibration works, not that the data is realistic.", S["body"]))
    if cal:
        r, b, c = cal["real"], cal["baseline_generated"], cal["calibrated_generated"]
        story.append(data_table(["Property", "Real (SBP)", "Original synthetic", "Calibrated"], [
            ["Card-not-present share of card payments", pct(r["cnp_share"]), pct(b["cnp_share"]), pct(c["cnp_share"])],
            ["Annual growth of card payment volume", f"+{r['annual_volume_growth'] * 100:.1f}%", f"+{b['annual_volume_growth'] * 100:.1f}%", f"+{c['annual_volume_growth'] * 100:.1f}%"],
            ["Average POS ticket (USD)", f"${r['avg_ticket_usd']['pos']:.2f}", f"${b['avg_ticket_usd']['pos']:.2f}", f"${c['avg_ticket_usd']['pos']:.2f}"],
            ["Average e-commerce ticket (USD)", f"${r['avg_ticket_usd']['e_commerce']:.2f}", f"${b['avg_ticket_usd']['e_commerce']:.2f}", f"${c['avg_ticket_usd']['e_commerce']:.2f}"],
            ["Card decline rate (not calibrated: no real target)", "unknown", pct(b["decline_rate"]), pct(c["decline_rate"])],
        ], widths=[2.8 * inch, 1.1 * inch, 1.4 * inch, 1.3 * inch]))
        story.append(P("The decline rate falls when amounts shrink because the decline model depends on amount and channel: a side effect, not a calibrated value. "
                       f"Not calibrated at all: {'; '.join(x.split(' (')[0].lower() for x in (bm or {}).get('not_calibrated', [])[:5])}.", S["body"]))
    story.append(P("Forecasts of real series", S["h2"]))
    story.append(P("Each series is forecast with a rolling-origin backtest against a naive benchmark. A model that does not beat naive on the scoring window is not published; the forecast falls back to naive (flat). "
                   "MASE below 1 means the model's one-step errors beat a naive forecast.", S["body"]))
    if fc:
        rows = [[x["title"].split(" (")[0], f"{x['n_points']}", {"fq": "quarterly", "calq": "quarterly", "year": "annual", "month": "monthly"}.get(x["freq"], x["freq"]), x["published"].replace("_", " "), f"{x['mase_chosen']:.2f} ({x['mase_naive']:.2f})", "yes" if x["beats_naive"] else "no"] for x in fc]
        story.append(data_table(["Series", "Points", "Freq.", "Published model", "MASE (naive)", "Beats naive"], rows, widths=[2.3 * inch, 0.6 * inch, 0.7 * inch, 1.3 * inch, 1.0 * inch, 0.7 * inch]))
    story.append(P("Ten quarters (retail volume, Raast) is very little data: those two forecasts show direction and rough size, not precision, and SBP revises earlier quarters. "
                   "The US dollar-rupee rate behaves like a random walk, so the honest forecast is flat.", S["note"]))

    # ---- 9 UI
    story.append(P("9. The analytics application", S["h1"]))
    story.append(P("Eleven pages share one design system (dark and light themes, collapsible sidebar, breadcrumbs, global search, notification centre, date range kept in the URL). Every page carries a "
                   "badge for the kind of data it shows.", S["body"]))
    story.append(data_table(["Page", "What it shows"], [
        ["Executive overview", "hero banner with approval-rate gauge; six headline KPIs with prior-period change and sparklines; value, channel, category, branch and time-of-day views; recent high-severity alerts"],
        ["Payment intelligence", "lifecycle Sankey from recorded events only, funnel, trends, amount distribution, refunds/reversals/chargebacks, decline reasons, category treemap, hourly heat map; filters"],
        ["Fraud and anomaly", "alert volume and severity, score distribution, rule-versus-ML comparison, customer and merchant risk, investigation table with saved outcomes, scoring form"],
        ["Customers / merchants / branches", "RFM segmentation, cohort retention, estimated lifetime value with adjustable assumptions, merchant risk ranking, MapLibre branch map (city centroids, labelled as such), detail pages"],
        ["Transaction explorer", "nine server-side tables: search, multi-column sort, column filters, column visibility, resizable columns, row selection, expandable rows, CSV and Excel export of every matching row"],
        ["Global financial intelligence", "63 charts and tables from SBP, World Bank, BIS, ECB, FRED, Findex, including the backtested forecasts"],
        ["Real vs synthetic", "scorecard of real SBP payment metrics against the dashboard data and the calibrated companion; what was and was not calibrated"],
        ["Engineering and monitoring", "pipeline runs, ingestion, data quality, reconciliation, freshness, dbt results, Airflow (live only when connected), error log"],
        ["Settings", "theme, session, data domains, definition of every headline metric"],
    ], widths=[1.6 * inch, 5.0 * inch]))
    for name, h, cap in [("overview-dark.png", 1500, "Executive overview (dark theme)"), ("overview-light.png", 1500, "Executive overview (light theme)"),
                         ("fraud-dark.png", 1700, "Fraud and anomaly intelligence"), ("branches-dark.png", 1000, "Branch and regional analytics with the branch map"),
                         ("benchmarks-dark.png", 1250, "Real vs synthetic benchmarks")]:
        im = shot(name, h)
        if im:
            story.append(KeepTogether([Spacer(1, 6), im, P(cap, S["caption"])]))

    # ---- 10 api / data engineering
    story.append(P("10. API and data engineering", S["h1"]))
    story.append(bullets([
        "Analytics routers under /v1 use SQL aggregation with bound parameters, an in-process TTL cache, server-side pagination and an optional X-API-Key; the table endpoints whitelist datasets and columns and reject injection attempts.",
        "Notable fixes found by testing: a 50,000-row CSV export took 68 s because the stream yielded one row at a time (now 2 s); two queries used Postgres-only syntax; RFM quintiles and the score histogram were made deterministic.",
        "Observability reads real metadata only: audit tables, reconciliation results, dbt run_results.json (last invocation) and, when configured, the Airflow REST API; otherwise the page says Airflow is not connected.",
        "Benchmarks (measured, documented in docs/): Postgres partitioned plus indexed lifecycle table against heap; DuckDB on Parquet; PySpark against DuckDB on 1.92M events; API load test.",
    ]))

    # ---- 11 deployment
    story.append(P("11. Deployment", S["h1"]))
    story.append(P(f"The app and its API are live at {LIVE}. Vercel cannot run PostgreSQL, so the hosted copy runs the same FastAPI routers as a Python function over a bundled, read-only DuckDB snapshot "
                   "(about 28 MB) and serves the built React app statically. Payment scoring (needs trained models) and saving investigation outcomes are switched off in the hosted demo and the pages say so.", S["body"]))
    story.append(bullets([
        "Parity check: every GET endpoint was called on the PostgreSQL-backed and the DuckDB-backed servers; 50 of 51 are identical, the 51st differs only by the new demo flag. Rows that tie in an ORDER BY may be ordered differently.",
        "The API test suite passes on PostgreSQL and on DuckDB (independent SQL checks still run on PostgreSQL); the 24 end-to-end tests pass against the local PostgreSQL app, the local DuckDB app, a Vercel preview and the production URL.",
        "Rebuild: build the UI, run scripts/build_demo_db.py, scripts/build_vercel_bundle.py, then vercel deploy --prod (docs/DEPLOYMENT.md). The snapshot does not update by itself.",
    ]))

    # ---- 12 testing + limits
    story.append(P("12. Testing, continuous integration and limitations", S["h1"]))
    story.append(data_table(["Suite", "Count", "What it checks"], [
        ["pytest", "128", "generators, reconciliation, KPIs, anomaly logic, API (dashboard numbers against independent SQL), DuckDB adapter, calibration, forecasts"],
        ["vitest", "6", "every dashboard chart spec is valid, converts to a chart, names its source; number formatting"],
        ["Playwright", "24", "all 11 routes load without console errors, KPIs equal the API, date filter, theme, tables (sort, filter, page, export), map, error state, phone layout, search, benchmarks and forecasts"],
        ["GitHub Actions", "4 jobs", "python tests, python tests with Postgres, frontend build and tests, API image build and health check; all pass on the latest commit"],
    ], widths=[1.2 * inch, 0.8 * inch, 4.6 * inch]))
    story.append(P("Limitations", S["h2"]))
    story.append(bullets([
        "All transactional data is synthetic. Model results on it (decline ROC-AUC 0.635, fraud PR-AUC about 0.26) show the pipeline works, not real-world performance.",
        "Anomaly alerts are not confirmed fraud; evaluation uses the generator's planted labels only.",
        "Real data is aggregate (no individual transactions); SBP tables are OCR extractions; BIS has no Pakistan payment statistics; some BIS and World Bank data is not public.",
        "The calibrated dataset matches its targets by construction; metrics with no real target (decline rate, fraud, merchant mix) are not calibrated.",
        "Forecasts on ten quarters are indicative only; the hosted app is a fixed snapshot with no user accounts (a single optional API key).",
        "CLV is an estimate from adjustable assumptions, not observed revenue; the branch map plots city centroids, not branch addresses.",
    ]))

    # ---- 13 history
    story.append(PageBreak())
    story.append(P("13. Repository history (synced with GitHub)", S["h1"]))
    story.append(P(f"{len(log)} commits on main, from {log[0][1]} to {log[-1][1]}; local HEAD {head}, origin/main {remote}. Commits are authored with the GitHub noreply address. "
                   f"Repository: {REPO}", S["body"]))
    story.append(data_table(["Commit", "Date", "Message"], [list(c) for c in log], widths=[0.7 * inch, 0.8 * inch, 5.1 * inch], mono_first=True))

    # ---- 14 run it
    story.append(P("14. Run it", S["h1"]))
    for line in ["pip install -r requirements.txt", "python scripts/start_embedded_postgres.py        # or docker compose up", "python -m src.pipeline.run_pipeline",
                 "uvicorn src.api.main:app                    # app at http://127.0.0.1:8792/app/", "cd web/react-app && npm install && npm run build && npx playwright test",
                 "pytest", "python scripts/generate_project_pdf.py     # this report"]:
        story.append(P(line, S["mono"]))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.8, color=LINE, spaceBefore=4, spaceAfter=10))
    story.append(P("End of report - NovaBank Banking Analytics Platform (synthetic transactional data).", S["small"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title="NovaBank Banking Analytics Platform - Project Report", author="Ali Raza")
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} KB)")
    return OUT


if __name__ == "__main__":
    build()
