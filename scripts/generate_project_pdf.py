"""Generate a professional NovaBank project PDF report."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    HRFlowable,
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

TEAL = colors.HexColor("#0d6e6e")
DEEP = colors.HexColor("#102a43")
MUTED = colors.HexColor("#5c6b7a")
LINE = colors.HexColor("#d5dde6")
SOFT = colors.HexColor("#e6f3f3")
PAPER = colors.HexColor("#f7f9fb")


def styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=26,
            leading=32,
            textColor=DEEP,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=DEEP,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=TEAL,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=DEEP,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=DEEP,
            leftIndent=8,
            spaceAfter=2,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#6a5420"),
            alignment=TA_LEFT,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(i, style), leftIndent=8, bulletColor=TEAL) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
        bulletFontSize=9,
    )


def kv_table(rows):
    data = [[Paragraph(f"<b>{k}</b>", ParagraphStyle("k", fontSize=9, textColor=DEEP)),
             Paragraph(str(v), ParagraphStyle("v", fontSize=9, textColor=DEEP))] for k, v in rows]
    t = Table(data, colWidths=[2.4 * inch, 4.2 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def data_table(headers, rows):
    hdr = [Paragraph(f"<b>{h}</b>", ParagraphStyle("th", fontSize=8, textColor=colors.white)) for h in headers]
    body = [
        [Paragraph(str(c), ParagraphStyle("td", fontSize=8, textColor=DEEP)) for c in row]
        for row in rows
    ]
    t = Table([hdr] + body, colWidths=[6.6 * inch / len(headers)] * len(headers))
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), DEEP),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(body) + 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), PAPER))
    t.setStyle(TableStyle(style_cmds))
    return t


def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 8 * mm, "NovaBank Analytics Pipeline | Synthetic data only")
    canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build():
    s = styles()
    story = []

    # Cover
    story.append(Spacer(1, 1.3 * inch))
    story.append(Paragraph("NovaBank", s["cover_title"]))
    story.append(Paragraph("Banking Transaction Analytics Pipeline", s["cover_title"]))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="60%", thickness=1.2, color=TEAL, spaceBefore=4, spaceAfter=12, hAlign="CENTER"))
    story.append(Paragraph("End-to-End Data Engineering + Analytics + Anomaly Monitoring", s["cover_sub"]))
    story.append(Paragraph("Portfolio Project Report", s["cover_sub"]))
    story.append(Spacer(1, 18))
    story.append(
        Paragraph(
            "This project uses synthetic banking data generated solely for demonstrating "
            "data engineering, analytics, and transaction-monitoring capabilities. "
            "It does not represent real customer or banking data.",
            s["disclaimer"],
        )
    )
    story.append(Spacer(1, 20))
    story.append(
        kv_table(
            [
                ("Author", "Ali Raza"),
                ("GitHub", "https://github.com/alirazach476/banking-transaction-analytics"),
                ("Live demo", "https://banking-transaction-analytics.vercel.app"),
                ("BI dashboard", "https://banking-transaction-analytics.vercel.app/dashboard"),
                ("Report date", datetime.now().strftime("%d %B %Y")),
                ("Stack", "Python, PostgreSQL, dbt, Airflow, scikit-learn, Docker, Vercel"),
            ]
        )
    )
    story.append(PageBreak())

    # 1 Overview
    story.append(Paragraph("1. Project Overview", s["h1"]))
    story.append(
        Paragraph(
            "NovaBank is a fictional retail bank requiring a centralized analytics platform for "
            "transaction monitoring, customer/account behavior, channel and branch performance, "
            "operational failures, and a Transaction Anomaly Detection Prototype. "
            "This portfolio delivers a runnable, tested, dockerized pipeline with dimensional "
            "modeling, reconciliation, and a live BI dashboard.",
            s["body"],
        )
    )
    story.append(Paragraph("Business goals", s["h2"]))
    story.append(
        bullets(
            [
                "Single source of truth for transaction analytics",
                "Reliable KPIs for finance, operations, and channel performance",
                "Controlled anomaly review queue (not production fraud decisioning)",
                "Interview-ready demonstration of DE / AE / analyst skills",
            ],
            s["bullet"],
        )
    )

    # 2 Architecture
    story.append(Paragraph("2. Architecture", s["h1"]))
    story.append(
        Paragraph(
            "Pipeline flow: Synthetic source systems → Ingestion → Raw layer → Data quality → "
            "PostgreSQL → dbt (staging / intermediate / warehouse / analytics) → "
            "Anomaly detection → BI dashboard / SQL analytics / Airflow orchestration.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Schemas:</b> raw, staging, intermediate, warehouse, analytics, audit, monitoring.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Fact grain:</b> One row in fact_transactions represents one financial transaction event.",
            s["body"],
        )
    )

    # 3 Dataset
    story.append(Paragraph("3. Dataset Statistics (Verified Demo Run)", s["h1"]))
    story.append(
        Paragraph(
            "Configurable volumes via .env. Figures below are from the verified end-to-end run.",
            s["body"],
        )
    )
    story.append(
        data_table(
            ["Entity", "Count / Value"],
            [
                ["Customers", "5,000"],
                ["Accounts", "7,500"],
                ["Transactions (fact)", "101,600"],
                ["Transfers", "15,000"],
                ["ATM transactions", "20,000"],
                ["Card transactions", "40,000"],
                ["Branches / Merchants / Cards", "50 / 1,000 / 10,000"],
                ["Total transaction value", "$81,172,698.21"],
                ["Average transaction", "$799.18"],
                ["Anomalies requiring review", "8,645"],
                ["Daily mart rows", "1,095"],
            ],
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Full portfolio targets (configurable): 100k customers, 150k accounts, 2M+ transactions.",
            s["body"],
        )
    )

    # 4 Warehouse
    story.append(Paragraph("4. Data Warehouse Design", s["h1"]))
    story.append(
        Paragraph(
            "Kimball star schema in PostgreSQL. Dimensions include dim_customer (SCD Type 2), "
            "dim_account, dim_branch, dim_merchant, dim_card, dim_channel, dim_transaction_type, "
            "and dim_date. Facts include fact_transactions, fact_transfers, fact_atm_transactions, "
            "and fact_card_transactions. Surrogate keys join facts to dimensions.",
            s["body"],
        )
    )
    story.append(Paragraph("dbt layers", s["h2"]))
    story.append(
        bullets(
            [
                "Staging: clean, cast, standardize statuses, deduplicate",
                "Intermediate: enriched metrics and anomaly features",
                "Warehouse: dimensions + incremental facts",
                "Analytics: business marts (daily/monthly, customer, branch, channel, failures, anomalies)",
            ],
            s["bullet"],
        )
    )

    # 5 Quality & recon
    story.append(Paragraph("5. Data Quality & Reconciliation", s["h1"]))
    story.append(
        Paragraph(
            "Source CSVs intentionally include a small rate of duplicates, missing values, "
            "inconsistent capitalization, and invalid foreign keys. Staging standardizes these. "
            "DQ results land in audit.data_quality_results. Reconciliation compares distinct "
            "source business keys to warehouse counts/sums (PASS on demo run). "
            "Balance reconciliation samples accounts for opening + credits − debits vs reported closing.",
            s["body"],
        )
    )

    # 6 Anomaly
    story.append(Paragraph("6. Transaction Anomaly Detection Prototype", s["h1"]))
    story.append(
        Paragraph(
            "IMPORTANT: This is an analytical prototype, not a production fraud decision engine. "
            "Outputs are labeled “Potential anomaly” / “Transaction requiring review.”",
            s["disclaimer"],
        )
    )
    story.append(
        bullets(
            [
                "Rule-based: high amount, high frequency, rapid window, night activity, multiple failures, sudden behavior change",
                "Statistical: per-customer z-score (configurable threshold, default 3.0)",
                "Machine learning: Isolation Forest (contamination 0.02)",
                "Persisted to monitoring.transaction_anomalies with severity Low/Medium/High/Critical",
            ],
            s["bullet"],
        )
    )
    story.append(Paragraph("Demo anomaly counts", s["h2"]))
    story.append(
        data_table(
            ["Severity", "Count"],
            [["Low", "5,041"], ["Medium", "1,573"], ["High", "2,031"], ["Total", "8,645"]],
        )
    )

    story.append(PageBreak())

    # 7 Insights
    story.append(Paragraph("7. Business Insights (from live SQL)", s["h1"]))
    story.append(
        Paragraph(
            "Generated from analytics marts / warehouse — synthetic data only.",
            s["body"],
        )
    )
    story.append(Paragraph("Channels", s["h2"]))
    story.append(
        data_table(
            ["Channel", "Transactions", "Notes"],
            [
                ["Mobile App", "31,713", "34.6% of top-channel volume"],
                ["ATM", "18,233", ""],
                ["POS", "14,799", ""],
                ["Internet Banking", "14,795", ""],
                ["Branch", "12,088", ""],
            ],
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Customer segments", s["h2"]))
    story.append(
        Paragraph(
            "Inactive: &gt;90 days since last txn (dataset as-of) or 0 txns; Low &lt;10; "
            "Medium 10–49; High 50–199; Premium ≥200.",
            s["body"],
        )
    )
    story.append(
        data_table(
            ["Segment", "Customers"],
            [
                ["Medium Activity", "2,471"],
                ["Inactive", "1,955"],
                ["High Activity", "388"],
                ["Low Activity", "186"],
            ],
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Top branches by completed value", s["h2"]))
    story.append(
        data_table(
            ["Branch", "Region", "Value", "Fail %"],
            [
                ["NovaBank Dallas #50", "Southwest", "$1,149,418", "5.00"],
                ["NovaBank Philadelphia #7", "Northeast", "$1,021,449", "5.48"],
                ["NovaBank Detroit #47", "Midwest", "$1,000,420", "4.96"],
                ["NovaBank Minneapolis #20", "Midwest", "$955,959", "4.63"],
                ["NovaBank Atlanta #22", "Southeast", "$894,079", "4.30"],
            ],
        )
    )

    # 8 BI
    story.append(Paragraph("8. BI Dashboard & Deployment", s["h1"]))
    story.append(
        Paragraph(
            "An interactive HTML BI dashboard is published on Vercel with executive KPIs, "
            "monthly trends, channel/region charts, customer segments, branch rankings, and "
            "anomaly review tables. Power BI Desktop specs and DAX measures are documented "
            "under dashboards/powerbi/ for native .pbix rebuilds.",
            s["body"],
        )
    )
    story.append(
        bullets(
            [
                "Live site: https://banking-transaction-analytics.vercel.app",
                "Dashboard: https://banking-transaction-analytics.vercel.app/dashboard",
                "GitHub: https://github.com/alirazach476/banking-transaction-analytics",
            ],
            s["bullet"],
        )
    )

    # 9 Testing
    story.append(Paragraph("9. Testing, Orchestration & Ops", s["h1"]))
    story.append(
        bullets(
            [
                "pytest: 17 tests covering generation, validation, anomaly logic (all passing in verified run)",
                "Airflow DAG banking_daily_pipeline for daily orchestration",
                "Docker Compose for Postgres (+ Airflow); embedded Postgres fallback for local Windows",
                "Makefile / python -m src.pipeline.run_pipeline for end-to-end execution",
                "Idempotent ingest via truncate/upsert + unique business keys; incremental watermarks supported",
            ],
            s["bullet"],
        )
    )

    # 10 Limitations
    story.append(Paragraph("10. Limitations & Future Work", s["h1"]))
    story.append(
        bullets(
            [
                "Demo-scale defaults; full 2M+ transaction volumes are configurable but heavier to run",
                "Anomaly prototype is not a production fraud engine and has no labeled precision/recall claim",
                "Native Power BI .pbix is specified, not auto-generated",
                "Future: cloud warehouse (Redshift/Synapse/BigQuery), streaming ingest, SCD2 expansion, CI orchestration",
            ],
            s["bullet"],
        )
    )

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.8, color=LINE, spaceBefore=4, spaceAfter=10))
    story.append(
        Paragraph(
            "End of report — NovaBank Banking Transaction Analytics Pipeline (synthetic data).",
            s["small"],
        )
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="NovaBank Banking Transaction Analytics Pipeline — Project Report",
        author="Ali Raza",
    )
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    print(f"Wrote {OUT}")
    return OUT


if __name__ == "__main__":
    build()
