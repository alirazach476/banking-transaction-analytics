import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApi, useRange, useRangeApi } from "../lib/context.jsx";
import { compact, int, num, pct, usd } from "../lib/format.js";
import { Card, ChartCard, Notice, PageHeader, Stat } from "../ui/kit.jsx";
import EChart, { axis, baseGrid } from "../ui/EChart.jsx";
import { hbar, timeSeries } from "../ui/charts.js";
import ServerTable from "../ui/ServerTable.jsx";

const SEG_ORDER = ["Champions", "Loyal", "Potential loyalists", "Promising", "Need attention", "At risk", "Hibernating"];

export default function Customers() {
  const nav = useNavigate();
  const { from, to } = useRange();
  const [rate, setRate] = useState(0.015);
  const [life, setLife] = useState(36);
  const rfm = useRangeApi("/v1/customers/rfm");
  const tr = useRangeApi("/v1/customers/trends");
  const sp = useRangeApi("/v1/customers/spend-distribution");
  const co = useApi("/v1/customers/cohorts");
  const cl = useRangeApi("/v1/customers/clv", { revenue_rate: rate, lifetime_months: life });
  const top = useRangeApi("/v1/customers/top");
  const seg = (rfm.data?.segments || []).slice().sort((a, b) => SEG_ORDER.indexOf(a.segment) - SEG_ORDER.indexOf(b.segment));
  const n = (name) => seg.find((s) => s.segment === name)?.customers;

  const segOpt = (t) => ({
    grid: baseGrid, legend: { top: 0, left: 0, textStyle: { color: t.text2 } }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "category", data: seg.map((s) => s.segment), ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, interval: 0, width: 70, overflow: "break" } }) },
    yAxis: [{ type: "value", ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => compact(v) } }) }, { type: "value", position: "right", ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, formatter: (v) => usd(v) } }) }],
    series: [{ name: "Customers", type: "bar", data: seg.map((s) => s.customers), itemStyle: { color: t.colors[0], borderRadius: [4, 4, 0, 0] }, barMaxWidth: 34, tooltip: { valueFormatter: int } },
      { name: "Completed value (USD)", type: "line", yAxisIndex: 1, data: seg.map((s) => s.value), itemStyle: { color: t.colors[3] }, symbolSize: 7, tooltip: { valueFormatter: (v) => usd(v) } }],
  });
  const gridOpt = (t) => {
    const g = rfm.data.grid;
    return {
      grid: { left: 8, right: 12, top: 10, bottom: 56, containLabel: true },
      tooltip: { formatter: (p) => `Recency score ${p.value[1] + 1}, Frequency score ${p.value[0] + 1}<br/><b>${int(p.value[2])}</b> customers` },
      xAxis: { type: "category", data: [1, 2, 3, 4, 5], name: "Frequency score (5 = most)", nameLocation: "middle", nameGap: 26, nameTextStyle: { color: t.muted }, ...axis(t, { splitLine: { show: false } }) },
      yAxis: { type: "category", data: [1, 2, 3, 4, 5], name: "Recency score (5 = most recent)", nameTextStyle: { color: t.muted }, ...axis(t, { splitLine: { show: false } }) },
      visualMap: { min: 0, max: Math.max(...g.map((x) => x.customers), 1), show: false, inRange: { color: [t.surface, t.colors[0], t.colors[1]] } },
      series: [{ type: "heatmap", data: g.map((x) => [x.f - 1, x.r - 1, x.customers]), label: { show: true, color: "#fff", fontSize: 11, formatter: (p) => p.value[2] || "" }, itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 4 } }],
    };
  };
  const cohortOpt = (t) => {
    const rows = co.data.rows;
    const cohorts = [...new Set(rows.map((r) => r.cohort))].sort();
    const q = (c) => { const d = new Date(c); return `${d.getFullYear()} Q${Math.floor(d.getMonth() / 3) + 1}`; };
    return {
      grid: { left: 8, right: 12, top: 10, bottom: 50, containLabel: true },
      tooltip: { formatter: (p) => { const r = rows.find((x) => x.cohort === cohorts[p.value[1]] && x.offset_q === p.value[0]); return `Cohort ${q(cohorts[p.value[1]])} (${int(r.cohort_size)} customers)<br/>Quarter +${p.value[0]}: <b>${pct(r.retention, 1)}</b> active`; } },
      xAxis: { type: "category", data: Array.from({ length: 12 }, (_, i) => "+" + i), name: "Quarters since first completed transaction", nameLocation: "middle", nameGap: 26, nameTextStyle: { color: t.muted }, ...axis(t, { splitLine: { show: false } }) },
      yAxis: { type: "category", data: cohorts.map(q), inverse: true, ...axis(t, { splitLine: { show: false } }) },
      visualMap: { min: 0, max: 1, calculable: true, orient: "horizontal", left: "center", bottom: 0, itemWidth: 12, itemHeight: 140, textStyle: { color: t.muted }, formatter: (v) => pct(v, 0), inRange: { color: [t.surface, t.colors[2], t.colors[0]] } },
      series: [{ type: "heatmap", data: rows.map((r) => [r.offset_q, cohorts.indexOf(r.cohort), r.retention]), label: { show: true, color: "#fff", fontSize: 10, formatter: (p) => Math.round(p.value[2] * 100) }, itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 3 } }],
    };
  };
  const spendOpt = (t) => ({
    grid: baseGrid, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "category", data: sp.data.rows.map((r) => r.label), name: "Completed value per customer (USD)", nameLocation: "middle", nameGap: 28, nameTextStyle: { color: t.muted }, ...axis(t, { splitLine: { show: false } }) },
    yAxis: { type: "value", ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => compact(v) } }) },
    series: [{ type: "bar", data: sp.data.rows.map((r) => r.customers), itemStyle: { color: t.colors[1], borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40, tooltip: { valueFormatter: int } }],
  });
  const clvOpt = (t) => ({
    grid: baseGrid, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "category", data: cl.data.distribution.map((r) => (r.bin > 10 ? "2000+" : `${(r.bin - 1) * 200}-${r.bin * 200}`)), name: "Estimated CLV (USD)", nameLocation: "middle", nameGap: 28, nameTextStyle: { color: t.muted }, ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 10, interval: 0, rotate: 30 } }) },
    yAxis: { type: "value", ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => compact(v) } }) },
    series: [{ type: "bar", data: cl.data.distribution.map((r) => r.customers), itemStyle: { color: t.colors[2], borderRadius: [4, 4, 0, 0] }, barMaxWidth: 34, tooltip: { valueFormatter: int } }],
  });

  return (
    <>
      <PageHeader title="Customer analytics" subtitle="Segmentation, RFM, cohorts and lifetime-value estimates from completed core-banking transactions (USD)."
        domains={[{ kind: "synthetic", label: "Synthetic · core banking" }]} />
      <div className="grid g-kpi6">
        <Stat loading={rfm.isPending} label="Customers" value={int(rfm.data?.customers_total)} />
        <Stat loading={rfm.isPending} label="Active in range" value={int(rfm.data && rfm.data.customers_total - rfm.data.customers_without_completed_txn_in_range)} note="at least one completed transaction" />
        <Stat loading={rfm.isPending} label="Champions" value={int(n("Champions"))} note="best recency, frequency, value" />
        <Stat loading={rfm.isPending} label="At risk" value={int(n("At risk"))} note="valuable but not recent" />
        <Stat loading={rfm.isPending} label="Hibernating" value={int(n("Hibernating"))} />
        <Stat loading={cl.isPending} label="Median CLV (estimate)" value={usd(cl.data?.stats.median)} note={`rate ${pct(rate, 1)}, ${life} months`} />
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="RFM segments" subtitle={`Customers (bars) and completed value (line), as of ${to}`} query={rfm} isEmpty={(d) => !d.segments.length} height={300}
          footer={`${int(rfm.data?.customers_without_completed_txn_in_range)} customers had no completed transaction in the range and are not scored.`}>
          {rfm.data && <EChart height={300} ariaLabel="RFM segments" option={segOpt} />}
        </ChartCard>
        <ChartCard title="Recency x frequency" subtitle="Customer counts by RFM score (5 = best)" query={rfm} isEmpty={(d) => !d.grid.length} height={300}>
          {rfm.data && <EChart height={300} ariaLabel="RFM grid" option={gridOpt} />}
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Customer activity trend" subtitle={`Active and new customers per ${tr.data?.grain || "period"}`} query={tr} isEmpty={(d) => !d.rows.length} height={280}>
          {tr.data && <EChart height={280} ariaLabel="Customer trends" option={timeSeries(tr.data.rows, "period", [{ key: "active_customers", name: "Active customers", area: true, fmt: int }, { key: "new_customers", name: "New customers", fmt: int }])} />}
        </ChartCard>
        <ChartCard title="Customer spending distribution" subtitle="Customers by completed value in range" query={sp} isEmpty={(d) => !d.rows.some((r) => r.customers)} height={280} footer="USD, completed transactions only.">
          {sp.data && <EChart height={280} ariaLabel="Spend distribution" option={spendOpt} />}
        </ChartCard>
      </div>

      <div className="grid g-21 mb">
        <ChartCard title="Cohort retention" subtitle="Share of each quarterly cohort active in later quarters" query={co} isEmpty={(d) => !d.rows.length} height={400} footer={co.data?.note}>
          {co.data && <EChart height={400} ariaLabel="Cohort retention heatmap" option={cohortOpt} />}
        </ChartCard>
        <ChartCard title="Most valuable customers" subtitle="Completed value in range (click for detail)" query={top} isEmpty={(d) => !d.length} height={400}>
          {top.data && <EChart height={400} ariaLabel="Top customers" onClick={(e) => e.name && nav(`/customers/${e.name}`)} option={hbar(top.data, "customer_id", "value", { fmt: (v) => usd(v), name: "Completed value", extra: (r) => `${r.customer_type || ""} · ${r.region || ""} · ${r.transactions} transactions` })} />}
        </ChartCard>
      </div>

      <Card style={{ padding: 18, marginBottom: 16 }} data-testid="clv-card">
        <h3>Customer lifetime value (estimate)</h3>
        <Notice warn>{cl.data?.note || "CLV is an estimate built from the assumptions below, not observed revenue."}</Notice>
        <div className="filters" style={{ marginBottom: 12 }}>
          <label>Revenue rate (share of completed value)<input className="field" type="number" step="0.005" min="0" max="0.2" value={rate} onChange={(e) => setRate(Math.max(0, Math.min(0.2, +e.target.value || 0)))} aria-label="Revenue rate" /></label>
          <label>Expected lifetime (months)<input className="field" type="number" step="6" min="1" max="120" value={life} onChange={(e) => setLife(Math.max(1, Math.min(120, +e.target.value || 1)))} aria-label="Lifetime months" /></label>
          <span style={{ color: "var(--muted)", fontSize: 12.5, alignSelf: "end" }}>CLV = average monthly completed USD value x revenue rate x lifetime. Customers with fewer than 3 completed transactions are excluded.</span>
        </div>
        <div className="grid g-2">
          <ChartCard title="CLV distribution" subtitle={cl.data ? `${int(cl.data.stats.customers)} customers; mean ${usd(cl.data.stats.mean, false)}, total ${usd(cl.data.stats.total)}` : ""} query={cl} isEmpty={(d) => !d.distribution.length} height={260}>
            {cl.data && <EChart height={260} ariaLabel="CLV distribution" option={clvOpt} />}
          </ChartCard>
          <div className="table-wrap" style={{ maxHeight: 340 }}>
            <table className="dt" style={{ tableLayout: "auto" }}>
              <thead><tr><th>Customer</th><th>Type</th><th className="r">Txns</th><th className="r">Monthly value</th><th className="r">Est. CLV</th></tr></thead>
              <tbody>{(cl.data?.top || []).map((r) => <tr key={r.customer_id} style={{ cursor: "pointer" }} onClick={() => nav(`/customers/${r.customer_id}`)}><td className="link">{r.customer_id}</td><td>{r.customer_type}</td><td className="r">{int(r.transactions)}</td><td className="r">{usd(r.monthly_value, false)}</td><td className="r">{usd(r.clv, false)}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      </Card>

      <Card style={{ padding: 18, marginBottom: 16 }}>
        <h3>RFM methodology</h3>
        <p style={{ color: "var(--text-2)", margin: "6px 0 0", whiteSpace: "pre-line", fontSize: 13 }}>{rfm.data?.definition}</p>
      </Card>

      <Card style={{ padding: 18 }}>
        <h3 style={{ marginBottom: 10 }}>Customers</h3>
        <ServerTable dataset="customers" initialSort={{ id: "transaction_count", desc: true }} filterOptions={{ activity_segment: ["High Activity", "Medium Activity", "Low Activity", "Inactive"], customer_type: ["Retail", "Premium", "Business", "Student"] }} onRowClick={(r) => nav(`/customers/${r.customer_id}`)} />
      </Card>
    </>
  );
}
