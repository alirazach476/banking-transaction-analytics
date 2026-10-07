"""Build canvas + HTML BI dashboard from exported warehouse JSON."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANVAS_DIR = Path.home() / ".cursor" / "projects" / "c-Users-DELL-Downloads-Bank-Anaylsis" / "canvases"


def main() -> None:
    d = json.loads((ROOT / "dashboards" / "data" / "bi_dashboard.json").read_text(encoding="utf-8"))
    k = d["kpis"]
    monthly = d["monthly"]
    channels = d["channels"]
    segments = d["segments"]
    branches = d["branches"][:10]
    txn_types = d["txn_types"]
    anomalies = d["anomalies"]
    anomaly_sample = d["anomaly_sample"][:12]
    regions = d["regions"]

    m_chart = monthly[-24:]
    m_cats = [m["month_label"] for m in m_chart]
    m_vals = [round(m["transaction_value"] / 1e6, 2) for m in m_chart]
    m_cnts = [int(m["transaction_count"]) for m in m_chart]
    m_fail = [m["failure_rate_pct"] for m in m_chart]

    ch_cats = [c["channel"] for c in channels]
    ch_cnt = [int(c["transaction_count"]) for c in channels]
    ch_val = [round(c["transaction_value"] / 1e6, 2) for c in channels]
    ch_fail = [c["failure_rate_pct"] for c in channels]

    seg_pie = [{"label": s["segment"], "value": s["customers"]} for s in segments]
    type_cats = [str(t["transaction_type"]) for t in txn_types if t.get("transaction_type")]
    type_cnt = [int(t["transaction_count"]) for t in txn_types if t.get("transaction_type")]
    reg_cats = [r["region"] for r in regions]
    reg_val = [round(r["transaction_value"] / 1e6, 2) for r in regions]

    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    anom_sev = sorted(anomalies, key=lambda x: order.get(x["severity"], 9))
    anom_pie = [{"label": a["severity"], "value": a["cnt"]} for a in anom_sev]

    branch_rows = [
        {
            "Branch": b["branch_name"],
            "Region": b["region"],
            "Txns": f"{int(b['transaction_count']):,}",
            "Value": f"${b['transaction_value']:,.0f}",
            "Fail %": f"{b['failure_rate_pct']:.2f}",
            "Customers": f"{int(b['active_customers']):,}",
        }
        for b in branches
    ]
    anom_rows = [
        {
            "Txn ID": a["transaction_id"],
            "Customer": a["customer_id"] or "—",
            "Amount": f"${float(a['amount'] or 0):,.0f}",
            "Severity": a["severity"],
            "Reason": (a["anomaly_reason"] or "")[:90],
        }
        for a in anomaly_sample
    ]

    payload = {
        "kpis": k,
        "m_cats": m_cats,
        "m_vals": m_vals,
        "m_cnts": m_cnts,
        "m_fail": m_fail,
        "ch_cats": ch_cats,
        "ch_cnt": ch_cnt,
        "ch_val": ch_val,
        "ch_fail": ch_fail,
        "seg_pie": seg_pie,
        "type_cats": type_cats,
        "type_cnt": type_cnt,
        "reg_cats": reg_cats,
        "reg_val": reg_val,
        "anom_pie": anom_pie,
        "branch_rows": branch_rows,
        "anom_rows": anom_rows,
    }

    # --- Canvas TSX ---
    canvas = f'''import {{
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  LineChart,
  PieChart,
  Pill,
  Row,
  Spacer,
  Stack,
  Stat,
  Table,
  Text,
}} from "cursor/canvas";

/**
 * NovaBank BI Dashboard — live warehouse extract (synthetic data).
 * Source: PostgreSQL analytics + warehouse + monitoring schemas.
 */

const KPIS = {json.dumps(payload["kpis"])} as const;
const M_CATS = {json.dumps(payload["m_cats"])} as string[];
const M_VALS = {json.dumps(payload["m_vals"])} as number[];
const M_CNTS = {json.dumps(payload["m_cnts"])} as number[];
const M_FAIL = {json.dumps(payload["m_fail"])} as number[];
const CH_CATS = {json.dumps(payload["ch_cats"])} as string[];
const CH_CNT = {json.dumps(payload["ch_cnt"])} as number[];
const CH_VAL = {json.dumps(payload["ch_val"])} as number[];
const CH_FAIL = {json.dumps(payload["ch_fail"])} as number[];
const SEG_PIE = {json.dumps(payload["seg_pie"])} as Array<{{ label: string; value: number }}>;
const TYPE_CATS = {json.dumps(payload["type_cats"])} as string[];
const TYPE_CNT = {json.dumps(payload["type_cnt"])} as number[];
const REG_CATS = {json.dumps(payload["reg_cats"])} as string[];
const REG_VAL = {json.dumps(payload["reg_val"])} as number[];
const ANOM_PIE = {json.dumps(payload["anom_pie"])} as Array<{{ label: string; value: number }}>;
const BRANCH_ROWS = {json.dumps(payload["branch_rows"])} as Array<Record<string, string>>;
const ANOM_ROWS = {json.dumps(payload["anom_rows"])} as Array<Record<string, string>>;

function money(n: number): string {{
  if (n >= 1_000_000) return `$${{(n / 1_000_000).toFixed(2)}}M`;
  if (n >= 1_000) return `$${{(n / 1_000).toFixed(1)}}K`;
  return `$${{n.toFixed(0)}}`;
}}

export default function NovaBankBiDashboard() {{
  const successPct = (KPIS.success_rate * 100).toFixed(1);
  const failPct = (KPIS.failure_rate * 100).toFixed(2);
  const anomRate = ((KPIS.anomaly_count / KPIS.transaction_count) * 100).toFixed(2);

  return (
    <Stack gap={20} style={{{{ padding: 20 }}}}>
      <Stack gap={6}>
        <Row gap={10} align="center">
          <H1>NovaBank</H1>
          <Pill tone="info">Executive BI</Pill>
          <Pill tone="neutral">Synthetic data</Pill>
        </Row>
        <Text tone="secondary">
          Banking Transaction Analytics — connected to PostgreSQL warehouse / analytics marts
          (2023–2025 demo extract). Not real customer or financial records.
        </Text>
      </Stack>

      <Callout tone="warning">
        Transaction Anomaly Detection Prototype only. Flags mean “potential anomaly /
        transaction requiring review,” not confirmed fraud.
      </Callout>

      <H2>Executive KPIs</H2>
      <Grid columns={4} gap={12}>
        <Stat label="Transaction value" value={{money(KPIS.total_value)}} tone="info" />
        <Stat label="Transaction count" value={{KPIS.transaction_count.toLocaleString()}} />
        <Stat label="Avg transaction" value={{money(KPIS.avg_value)}} />
        <Stat label="Success rate" value={{`${{successPct}}%`}} tone="success" />
        <Stat label="Active customers" value={{KPIS.active_customers.toLocaleString()}} />
        <Stat label="Active accounts" value={{KPIS.active_accounts.toLocaleString()}} />
        <Stat label="Failure rate" value={{`${{failPct}}%`}} tone="danger" />
        <Stat
          label="Anomalies (review)"
          value={{KPIS.anomaly_count.toLocaleString()}}
          tone="warning"
        />
      </Grid>
      <Text tone="secondary" size="small">
        Anomaly rate {{anomRate}}% of transactions · Source: warehouse.fact_transactions +
        monitoring.transaction_anomalies
      </Text>

      <Divider />

      <H2>Transaction trends</H2>
      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>Monthly transaction value (USD millions)</CardHeader>
          <CardBody>
            <LineChart
              categories={{M_CATS}}
              series={{[{{ name: "Txn value ($M)", data: M_VALS, tone: "info" }}]}}
              height={{220}}
              fill
              valueSuffix="M"
            />
            <Text tone="secondary" size="small">
              Source: analytics.mart_monthly_transactions · last 24 months · Y-axis: $M
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Monthly transaction count</CardHeader>
          <CardBody>
            <BarChart
              categories={{M_CATS}}
              series={{[{{ name: "Transactions", data: M_CNTS }}]}}
              height={{220}}
            />
            <Text tone="secondary" size="small">
              Source: analytics.mart_monthly_transactions · last 24 months · units: count
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Card>
        <CardHeader>Monthly failure rate (%)</CardHeader>
        <CardBody>
          <LineChart
            categories={{M_CATS}}
            series={{[{{ name: "Failure rate %", data: M_FAIL, tone: "danger" }}]}}
            height={{180}}
            valueSuffix="%"
          />
          <Text tone="secondary" size="small">
            Source: analytics.mart_monthly_transactions · failure_rate_pct
          </Text>
        </CardBody>
      </Card>

      <Divider />

      <H2>Channels & regions</H2>
      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>Transaction count by channel</CardHeader>
          <CardBody>
            <BarChart
              categories={{CH_CATS}}
              series={{[{{ name: "Transactions", data: CH_CNT }}]}}
              height={{220}}
              horizontal
            />
            <Text tone="secondary" size="small">
              Source: analytics.mart_channel_performance · X-axis: count
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Completed value by channel ($M)</CardHeader>
          <CardBody>
            <BarChart
              categories={{CH_CATS}}
              series={{[{{ name: "Completed value ($M)", data: CH_VAL, tone: "success" }}]}}
              height={{220}}
              horizontal
              valueSuffix="M"
            />
            <Text tone="secondary" size="small">
              Source: analytics.mart_channel_performance · total_completed_amount
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>Channel failure rate (%)</CardHeader>
          <CardBody>
            <BarChart
              categories={{CH_CATS}}
              series={{[{{ name: "Failure %", data: CH_FAIL, tone: "danger" }}]}}
              height={{200}}
              valueSuffix="%"
            />
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Transaction value by customer region ($M)</CardHeader>
          <CardBody>
            <BarChart
              categories={{REG_CATS}}
              series={{[{{ name: "Value ($M)", data: REG_VAL, tone: "info" }}]}}
              height={{200}}
              valueSuffix="M"
            />
            <Text tone="secondary" size="small">
              Source: fact_transactions × dim_customer.region
            </Text>
          </CardBody>
        </Card>
      </Grid>

      <Divider />

      <H2>Customers, types & anomalies</H2>
      <Grid columns={3} gap={16}>
        <Card>
          <CardHeader>Customer activity segments</CardHeader>
          <CardBody>
            <PieChart data={{SEG_PIE}} donut size={{180}} />
            <Text tone="secondary" size="small">
              Thresholds: Inactive &gt;90d / Low &lt;10 / Medium 10–49 / High 50–199 / Premium ≥200
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Anomalies by severity</CardHeader>
          <CardBody>
            <PieChart data={{ANOM_PIE}} donut size={{180}} />
            <Text tone="secondary" size="small">
              Source: monitoring.transaction_anomalies · prototype labels only
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>Transactions by type</CardHeader>
          <CardBody>
            <BarChart
              categories={{TYPE_CATS}}
              series={{[{{ name: "Count", data: TYPE_CNT }}]}}
              height={{180}}
              horizontal
            />
          </CardBody>
        </Card>
      </Grid>

      <H3>Top branches by completed value</H3>
      <Table
        columns={{[
          {{ key: "Branch", label: "Branch", sortable: true }},
          {{ key: "Region", label: "Region" }},
          {{ key: "Txns", label: "Txns", align: "right" }},
          {{ key: "Value", label: "Completed value", align: "right" }},
          {{ key: "Fail %", label: "Fail %", align: "right" }},
          {{ key: "Customers", label: "Customers", align: "right" }},
        ]}}
        rows={{BRANCH_ROWS}}
      />
      <Text tone="secondary" size="small">
        Source: analytics.mart_branch_performance · ranked by total_completed_amount
      </Text>

      <Spacer height={{8}} />
      <H3>High-severity anomalies requiring review</H3>
      <Table
        columns={{[
          {{ key: "Txn ID", label: "Transaction ID" }},
          {{ key: "Customer", label: "Customer" }},
          {{ key: "Amount", label: "Amount", align: "right" }},
          {{ key: "Severity", label: "Severity" }},
          {{ key: "Reason", label: "Reason" }},
        ]}}
        rows={{ANOM_ROWS}}
      />

      <Divider />
      <Text tone="secondary" size="small">
        NovaBank portfolio BI · Connected extract from live PostgreSQL · Refresh via
        python scripts/export_bi_dashboard_data.py && python scripts/build_bi_artifacts.py
      </Text>
    </Stack>
  );
}}
'''

    CANVAS_DIR.mkdir(parents=True, exist_ok=True)
    canvas_path = CANVAS_DIR / "novabank-bi-dashboard.canvas.tsx"
    canvas_path.write_text(canvas, encoding="utf-8")
    print(f"Canvas: {canvas_path}")

    # --- Attractive HTML dashboard (web/ + dashboards/) ---
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>NovaBank BI Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Instrument+Serif&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --ink: #0c1222;
    --paper: #f3f6f8;
    --panel: #ffffff;
    --muted: #5c6b7a;
    --line: #d7e0e8;
    --accent: #0d6e6e;
    --deep: #102a43;
    --good: #1f8a5b;
    --bad: #c23b3b;
    --warn-bg: #fff8e8;
    --warn-bd: #efd9a3;
    --warn-tx: #6a5420;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: "DM Sans", system-ui, sans-serif;
    color: var(--ink);
    background:
      radial-gradient(1000px 480px at 0% -5%, #d7ebe8 0%, transparent 55%),
      radial-gradient(800px 420px at 100% 0%, #e4ebf4 0%, transparent 50%),
      var(--paper);
  }}
  a {{ color: var(--accent); text-decoration: none; }}
  .shell {{ max-width: 1180px; margin: 0 auto; padding: 0 22px 48px; }}
  .topbar {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 18px 0; border-bottom: 1px solid var(--line); margin-bottom: 22px;
  }}
  .brand {{ font-family: "Instrument Serif", Georgia, serif; font-size: 26px; }}
  .topbar nav {{ display: flex; gap: 14px; align-items: center; font-size: 14px; font-weight: 500; }}
  .chip {{
    display: inline-flex; align-items: center; gap: 6px;
    background: #e6f3f3; color: var(--accent);
    border-radius: 999px; padding: 5px 10px; font-size: 12px; font-weight: 600;
  }}
  header h1 {{
    font-family: "Instrument Serif", Georgia, serif;
    font-weight: 400; font-size: clamp(1.9rem, 3.5vw, 2.5rem);
    margin: 0 0 8px; letter-spacing: -0.02em;
  }}
  header p {{ margin: 0; color: var(--muted); max-width: 62ch; font-size: 15px; }}
  .warn {{
    margin: 18px 0 20px; padding: 12px 14px; border-radius: 10px;
    background: var(--warn-bg); border: 1px solid var(--warn-bd); color: var(--warn-tx); font-size: 13px;
  }}
  .kpis {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px;
  }}
  .kpi {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
    padding: 16px 16px 14px; box-shadow: 0 1px 0 rgba(16,42,67,0.03);
  }}
  .kpi .label {{
    color: var(--muted); font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em;
  }}
  .kpi .value {{ font-size: 1.45rem; font-weight: 700; margin-top: 8px; letter-spacing: -0.02em; }}
  .kpi.accent .value {{ color: var(--accent); }}
  .kpi.good .value {{ color: var(--good); }}
  .kpi.bad .value {{ color: var(--bad); }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }}
  .card {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
    padding: 16px 16px 12px; box-shadow: 0 1px 0 rgba(16,42,67,0.03);
  }}
  .card h2 {{
    margin: 0 0 4px; font-size: 14px; font-weight: 650;
  }}
  .card .sub {{ color: var(--muted); font-size: 12px; margin-bottom: 10px; }}
  canvas {{ max-height: 260px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--line); }}
  th {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }}
  tbody tr:hover {{ background: #f7fafb; }}
  footer {{
    margin-top: 18px; color: var(--muted); font-size: 12px;
    display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;
  }}
  @media (max-width: 900px) {{
    .kpis, .grid2 {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="shell">
  <div class="topbar">
    <div class="brand">NovaBank</div>
    <nav>
      <a href="/">Home</a>
      <span class="chip">Synthetic extract</span>
    </nav>
  </div>
  <header>
    <h1>Transaction Analytics Dashboard</h1>
    <p>Warehouse-connected BI view of customer activity, channels, branches, and anomaly review queues. Demo data only — not real banking records.</p>
  </header>
  <div class="warn">Anomaly Detection Prototype: results are “transactions requiring review,” not confirmed fraud decisions.</div>
  <div class="kpis" id="kpis"></div>
  <div class="grid2">
    <div class="card"><h2>Monthly transaction value</h2><div class="sub">USD millions · last 24 months</div><canvas id="cValue"></canvas></div>
    <div class="card"><h2>Monthly transaction count</h2><div class="sub">Volume trend</div><canvas id="cCount"></canvas></div>
  </div>
  <div class="grid2">
    <div class="card"><h2>Channel volume</h2><div class="sub">Transaction count by channel</div><canvas id="cChannel"></canvas></div>
    <div class="card"><h2>Customer segments</h2><div class="sub">Activity thresholds from analytics mart</div><canvas id="cSeg"></canvas></div>
  </div>
  <div class="grid2">
    <div class="card"><h2>Regional value</h2><div class="sub">USD millions by customer region</div><canvas id="cRegion"></canvas></div>
    <div class="card"><h2>Anomalies by severity</h2><div class="sub">monitoring.transaction_anomalies</div><canvas id="cAnom"></canvas></div>
  </div>
  <div class="card" style="margin-bottom:14px">
    <h2>Top branches by completed value</h2>
    <div class="sub">analytics.mart_branch_performance</div>
    <table id="branchTable"><thead></thead><tbody></tbody></table>
  </div>
  <div class="card">
    <h2>High-severity anomalies requiring review</h2>
    <div class="sub">Prototype queue — not confirmed fraud</div>
    <table id="anomTable"><thead></thead><tbody></tbody></table>
  </div>
  <footer>
    <span>NovaBank portfolio BI · PostgreSQL warehouse extract</span>
    <span><a href="/">Project home</a></span>
  </footer>
</div>
<script>
const D = {json.dumps(payload)};
function money(n) {{
  if (n >= 1e6) return '$' + (n/1e6).toFixed(2) + 'M';
  if (n >= 1e3) return '$' + (n/1e3).toFixed(1) + 'K';
  return '$' + n.toFixed(0);
}}
const k = D.kpis;
const kpiMeta = [
  ['Transaction value', money(k.total_value), 'accent'],
  ['Transactions', k.transaction_count.toLocaleString(), ''],
  ['Avg transaction', money(k.avg_value), ''],
  ['Success rate', (k.success_rate*100).toFixed(1) + '%', 'good'],
  ['Customers', k.active_customers.toLocaleString(), ''],
  ['Accounts', k.active_accounts.toLocaleString(), ''],
  ['Failure rate', (k.failure_rate*100).toFixed(2) + '%', 'bad'],
  ['Anomalies', k.anomaly_count.toLocaleString(), ''],
];
document.getElementById('kpis').innerHTML = kpiMeta.map(([l,v,c]) =>
  `<div class="kpi ${{c}}"><div class="label">${{l}}</div><div class="value">${{v}}</div></div>`
).join('');

const tick = {{ color: '#5c6b7a', font: {{ size: 11, family: 'DM Sans' }} }};
const grid = {{ color: '#e6edf3' }};
Chart.defaults.font.family = 'DM Sans';
Chart.defaults.color = '#5c6b7a';

new Chart(document.getElementById('cValue'), {{
  type: 'line',
  data: {{ labels: D.m_cats, datasets: [{{
    label: 'Value $M', data: D.m_vals,
    borderColor: '#0d6e6e', backgroundColor: 'rgba(13,110,110,0.12)',
    fill: true, tension: 0.35, pointRadius: 0, borderWidth: 2.5
  }}] }},
  options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ ticks: tick, grid: {{ display: false }} }}, y: {{ ticks: tick, grid }} }} }}
}});
new Chart(document.getElementById('cCount'), {{
  type: 'bar',
  data: {{ labels: D.m_cats, datasets: [{{ label: 'Count', data: D.m_cnts, backgroundColor: '#102a43', borderRadius: 4 }}] }},
  options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ ticks: tick, grid: {{ display: false }} }}, y: {{ ticks: tick, grid }} }} }}
}});
new Chart(document.getElementById('cChannel'), {{
  type: 'bar',
  data: {{ labels: D.ch_cats, datasets: [{{ label: 'Txns', data: D.ch_cnt, backgroundColor: '#0d6e6e', borderRadius: 4 }}] }},
  options: {{ indexAxis: 'y', plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ ticks: tick, grid }}, y: {{ ticks: tick, grid: {{ display: false }} }} }} }}
}});
new Chart(document.getElementById('cSeg'), {{
  type: 'doughnut',
  data: {{ labels: D.seg_pie.map(x=>x.label), datasets: [{{ data: D.seg_pie.map(x=>x.value), backgroundColor: ['#0d6e6e','#8aa0b2','#102a43','#c4a35a'], borderWidth: 0 }}] }},
  options: {{ cutout: '62%', plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 10, padding: 14 }} }} }} }}
}});
new Chart(document.getElementById('cRegion'), {{
  type: 'bar',
  data: {{ labels: D.reg_cats, datasets: [{{ label: '$M', data: D.reg_val, backgroundColor: '#345995', borderRadius: 4 }}] }},
  options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ ticks: tick, grid: {{ display: false }} }}, y: {{ ticks: tick, grid }} }} }}
}});
new Chart(document.getElementById('cAnom'), {{
  type: 'doughnut',
  data: {{ labels: D.anom_pie.map(x=>x.label), datasets: [{{ data: D.anom_pie.map(x=>x.value), backgroundColor: ['#c23b3b','#c4a35a','#8aa0b2'], borderWidth: 0 }}] }},
  options: {{ cutout: '62%', plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 10, padding: 14 }} }} }} }}
}});

function fillTable(id, rows) {{
  if (!rows.length) return;
  const keys = Object.keys(rows[0]);
  document.querySelector('#' + id + ' thead').innerHTML = '<tr>' + keys.map(k => `<th>${{k}}</th>`).join('') + '</tr>';
  document.querySelector('#' + id + ' tbody').innerHTML = rows.map(r => '<tr>' + keys.map(k => `<td>${{r[k]}}</td>`).join('') + '</tr>').join('');
}}
fillTable('branchTable', D.branch_rows);
fillTable('anomTable', D.anom_rows);
</script>
</body>
</html>
"""
    html_path = ROOT / "dashboards" / "novabank_bi_dashboard.html"
    html_path.write_text(html, encoding="utf-8")
    web_dash = ROOT / "web" / "dashboard.html"
    web_dash.write_text(html, encoding="utf-8")
    print(f"HTML: {html_path}")
    print(f"Web:  {web_dash}")

    (ROOT / "dashboards" / "powerbi" / "OPEN_HTML_DASHBOARD.md").write_text(
        """# NovaBank Live BI Dashboard

1. **Deployed site** — Vercel (`web/`) landing + `/dashboard`
2. **Local HTML** — `dashboards/novabank_bi_dashboard.html` or `web/dashboard.html`
3. **Cursor Canvas** — `novabank-bi-dashboard.canvas.tsx`

```powershell
python scripts/export_bi_dashboard_data.py
python scripts/build_bi_artifacts.py
```
""",
        encoding="utf-8",
    )
    print("Done")


if __name__ == "__main__":
    main()
