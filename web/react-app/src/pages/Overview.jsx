import React from "react";
import { useNavigate } from "react-router-dom";
import { useRange, useRangeApi } from "../lib/context.jsx";
import { compact, date, int, pct, usd } from "../lib/format.js";
import { Badge, Card, ChartCard, ExportButton, KpiCard, Notice, PageHeader, saveText, toCsv } from "../ui/kit.jsx";
import EChart from "../ui/EChart.jsx";
import { donut, hbar, timeSeries } from "../ui/charts.js";

export default function Overview() {
  const nav = useNavigate();
  const { from, to } = useRange();
  const ov = useRangeApi("/v1/overview");
  const ser = useRangeApi("/v1/overview/series");
  const br = useRangeApi("/v1/overview/breakdowns");
  const heads = ov.data?.headline || [];
  const sec = ov.data?.secondary || [];
  const s = ser.data;
  const b = br.data;
  const exportKpis = () => saveText(toCsv([...heads, ...sec].map((k) => ({ ...k, value: k.value, prior: k.prior, delta: k.delta })), [{ key: "label", label: "KPI" }, { key: "domain", label: "Domain" }, { key: "value", label: "Value" }, { key: "prior", label: "Prior period" }, { key: "delta", label: "Change" }, { key: "delta_unit", label: "Change unit" }]), `nova-kpis-${from}_${to}.csv`);
  const grainWord = s?.grain || "period";

  return (
    <>
      <PageHeader title="Executive overview" subtitle={`Card payments and core banking, ${date(from)} to ${date(to)}. Every figure comes from the project's database; values are in USD.`}
        domains={[{ kind: "synthetic", label: "Synthetic · card payments" }, { kind: "synthetic", label: "Synthetic · core banking" }]}
        actions={<ExportButton onClick={exportKpis} disabled={!heads.length}>Export KPIs (CSV)</ExportButton>} />
      {ov.isError && <Notice warn>Could not load KPIs: {ov.error.message}</Notice>}
      <div className="grid g-kpi6" data-testid="kpis-headline">
        {ov.isPending ? Array.from({ length: 6 }).map((_, i) => <KpiCard key={i} loading />) : heads.map((k) => <KpiCard key={k.key} k={k} onClick={k.domain === "payments" ? () => nav("/payments") : () => nav("/fraud")} />)}
      </div>
      <div className="grid g-kpi4">{sec.map((k) => <KpiCard key={k.key} k={k} />)}</div>
      <p className="sub" style={{ color: "var(--muted)", fontSize: 12.5, margin: "-4px 0 16px" }}>
        Changes compare with the preceding period of equal length ({ov.data ? `${date(ov.data.range.prior_from)} to ${date(ov.data.range.prior_to)}` : "…"}). Rates change in percentage points. Anomaly rate counts alerts, not confirmed fraud.
      </p>

      <div className="grid g-2 mb">
        <ChartCard title="Transaction volume" subtitle={`Card payments per ${grainWord}`} query={ser} isEmpty={(d) => !d.payments.length} footer="Payments domain (synthetic)." height={270}>
          <EChart height={270} ariaLabel="Payment volume over time" option={s && timeSeries(s.payments, "period", [{ key: "volume", name: "Payments", area: true, fmt: int }])} />
        </ChartCard>
        <ChartCard title="Transaction value (USD)" subtitle={`Card payments and core-banking completed value per ${grainWord}`} query={ser} isEmpty={(d) => !d.payments.length} footer="USD-converted with the dataset's synthetic FX table; payments without a rate are excluded from value." height={270}>
          <EChart height={270} ariaLabel="Transaction value over time" option={s && timeSeries(s.payments.map((r, i) => ({ ...r, core: (s.core.find((c) => c.period === r.period) || {}).value })), "period", [{ key: "value", name: "Card payments", area: true, fmt: (v) => usd(v) }, { key: "core", name: "Core banking (completed)", fmt: (v) => usd(v) }], { yFmt: (v) => usd(v) })} />
        </ChartCard>
      </div>

      <div className="grid g-21 mb">
        <ChartCard title="Approved vs declined" subtitle={`Authorizations per ${grainWord} with approval rate`} query={ser} isEmpty={(d) => !d.payments.length} height={290} footer="Approval rate = approved / (approved + declined).">
          <EChart height={290} ariaLabel="Approved versus declined" option={s && timeSeries(s.payments.map((r) => ({ ...r, rate: r.approved / (r.approved + r.declined) })), "period",
            [{ key: "approved", name: "Approved", type: "bar", stack: "a", color: "teal", fmt: int }, { key: "declined", name: "Declined", type: "bar", stack: "a", color: "bad", fmt: int }, { key: "rate", name: "Approval rate", axis: 1, color: "blue", fmt: (v) => pct(v, 2) }],
            { y2Fmt: (v) => pct(v, 0), yFmt: compact })} />
        </ChartCard>
        <ChartCard title="Transactions by channel" subtitle="Share of card payments (click a slice to drill down)" query={br} isEmpty={(d) => !d.channels.length} height={290}>
          <EChart height={290} ariaLabel="Payments by channel" onClick={(e) => e.name && nav(`/payments?channel=${encodeURIComponent(e.name)}`)} option={b && donut(b.channels, "channel", "payments", { fmt: int })} />
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Merchant category performance" subtitle="Card-payment value (USD) by merchant category; hover for approval rate" query={br} isEmpty={(d) => !d.categories.length} height={320} footer="Click a bar to open Payment Intelligence filtered to the category.">
          <EChart height={320} ariaLabel="Merchant category value" onClick={(e) => e.name && nav(`/payments?category=${encodeURIComponent(e.name)}`)}
            option={b && hbar(b.categories, "category", "value", { fmt: (v) => usd(v), name: "Value", extra: (r) => `Approval rate: ${pct(r.approval_rate, 2)}<br/>Payments: ${int(r.payments)}` })} />
        </ChartCard>
        <ChartCard title="Branch performance ranking" subtitle="Top 10 branches by completed value (core banking, USD)" query={br} isEmpty={(d) => !d.branches.length} height={320} footer="Click a bar to open the branch. Failure rate in the tooltip.">
          <EChart height={320} ariaLabel="Branch ranking" onClick={(e) => { const row = b.branches.find((x) => x.branch_name === e.name); row && nav(`/branches/${row.branch_id}`); }}
            option={b && hbar(b.branches, "branch_name", "value", { fmt: (v) => usd(v), name: "Completed value", colorFn: (r) => (r.failure_rate > 0.06 ? "warn" : "blue"), extra: (r) => `${r.city} · failure rate ${pct(r.failure_rate, 2)}` })} />
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Customer segmentation" subtitle="Customers by activity segment (all time)" query={br} isEmpty={(d) => !d.segments.rows.length} height={260} footer={b?.segments.note}>
          <EChart height={260} ariaLabel="Customer segments" onClick={() => nav("/customers")} option={b && donut(b.segments.rows, "segment", "customers", { fmt: int })} />
        </ChartCard>
        <ChartCard title="Recent high-severity anomaly alerts" subtitle="Latest alerts in the selected range; alerts are not confirmed fraud" query={br} isEmpty={(d) => !d.alerts.length}
          actions={<button className="btn sm" onClick={() => nav("/fraud")}>Open investigation</button>} height={260}>
          <div className="wrap" style={{ overflow: "auto", maxHeight: 260 }}>
            <table className="dt" style={{ tableLayout: "auto" }}>
              <thead><tr><th>Time</th><th>Customer</th><th className="r">Amount</th><th className="r">Score</th><th>Severity</th></tr></thead>
              <tbody>{(b?.alerts || []).map((a) => (
                <tr key={a.anomaly_id} style={{ cursor: "pointer" }} onClick={() => nav(`/fraud?anomaly=${a.anomaly_id}`)}>
                  <td className="num">{a.transaction_timestamp.slice(0, 16).replace("T", " ")}</td><td>{a.customer_id}</td><td className="r">{usd(a.amount, false)}</td><td className="r">{a.ml_anomaly_score.toFixed(3)}</td><td><Badge value={a.severity} /></td>
                </tr>))}</tbody>
            </table>
          </div>
        </ChartCard>
      </div>
      <Card style={{ padding: 14 }}><small style={{ color: "var(--muted)" }}>Data domains: card payments ({int(ov.data?.headline?.[0]?.value)} in range) and core-banking transactions are separate synthetic datasets; they share customer and merchant IDs. External real-world aggregates (SBP, World Bank, BIS, ECB, FRED) are on <a className="link" href="global">Global Financial Intelligence</a> and are never mixed with these records.</small></Card>
    </>
  );
}
