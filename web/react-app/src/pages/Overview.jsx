import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useRange, useRangeApi } from "../lib/context.jsx";
import { compact, date, int, pct, usd } from "../lib/format.js";
import { Badge, Card, ChartCard, DomainBadge, ExportButton, KpiCard, Notice, saveText, toCsv } from "../ui/kit.jsx";
import EChart from "../ui/EChart.jsx";
import { bubble, donut, gauge, hbar, hourHeat, rose, timeSeries } from "../ui/charts.js";

const ratio = (a, b) => (a + b ? a / (a + b) : null);

export default function Overview() {
  const nav = useNavigate();
  const { from, to } = useRange();
  const ov = useRangeApi("/v1/overview");
  const ser = useRangeApi("/v1/overview/series");
  const br = useRangeApi("/v1/overview/breakdowns");
  const rk = useRangeApi("/v1/branches/ranking");
  const hm = useRangeApi("/v1/payments/heatmap");
  const heads = ov.data?.headline || [];
  const sec = ov.data?.secondary || [];
  const s = ser.data;
  const b = br.data;
  const byKey = (k) => [...heads, ...sec].find((x) => x.key === k);
  const sparks = useMemo(() => {
    if (!s) return {};
    const p = s.payments, c = s.core;
    return {
      payment_volume: p.map((r) => r.volume), payment_value_usd: p.map((r) => r.value), approval_rate: p.map((r) => ratio(r.approved, r.declined)),
      decline_rate: p.map((r) => (r.approved + r.declined ? r.declined / (r.approved + r.declined) : null)), avg_transaction_value: p.map((r) => (r.volume ? r.value / r.volume : null)),
      core_volume: c.map((r) => r.volume), core_value_usd: c.map((r) => r.value),
    };
  }, [s]);
  const exportKpis = () => saveText(toCsv([...heads, ...sec].map((k) => ({ ...k })), [{ key: "label", label: "KPI" }, { key: "domain", label: "Domain" }, { key: "value", label: "Value" }, { key: "prior", label: "Prior period" }, { key: "delta", label: "Change" }, { key: "delta_unit", label: "Change unit" }]), `nova-kpis-${from}_${to}.csv`);
  const grainWord = s?.grain || "period";
  const approval = byKey("approval_rate");
  const vol = byKey("payment_volume"), val = byKey("payment_value_usd");
  const branches = rk.data?.rows || [];

  return (
    <>
      <section className="hero" aria-label="Overview summary">
        <span className="orbit" aria-hidden="true" />
        <div style={{ position: "relative", zIndex: 1 }}>
          <span className="eyebrow"><i />NovaBank financial pulse</span>
          <h1>Executive <em>overview</em></h1>
          <p>Card payments and core banking, {date(from)} to {date(to)}. Values in USD; every figure is read from the project's database.</p>
          <div className="pills">
            <div className="pill"><span>Payments</span><b>{vol ? int(vol.value) : "…"}</b></div>
            <div className="pill"><span>Value</span><b>{val ? usd(val.value) : "…"}</b></div>
            <div className="pill"><span>Core txns</span><b>{byKey("core_volume") ? int(byKey("core_volume").value) : "…"}</b></div>
          </div>
          <div className="badges"><DomainBadge kind="synthetic" label="Synthetic · card payments" /><DomainBadge kind="synthetic" label="Synthetic · core banking" /></div>
        </div>
        <div className="gauge-box" aria-label="Approval rate gauge">
          {approval ? <EChart height={190} ariaLabel="Approval rate gauge" option={gauge(approval.value, { name: "Approval rate", min: 0.8, max: 1 })} /> : <div style={{ height: 190 }} />}
        </div>
      </section>
      <div className="actions" style={{ justifyContent: "flex-end", marginBottom: 12 }}><ExportButton onClick={exportKpis} disabled={!heads.length}>Export KPIs (CSV)</ExportButton></div>
      {ov.isError && <Notice warn>Could not load KPIs: {ov.error.message}</Notice>}
      <div className="grid g-kpi6" data-testid="kpis-headline">
        {ov.isPending ? Array.from({ length: 6 }).map((_, i) => <KpiCard key={i} loading />) : heads.map((k) => <KpiCard key={k.key} k={k} spark={sparks[k.key] || []} onClick={k.domain === "payments" ? () => nav("/payments") : () => nav("/fraud")} />)}
      </div>
      <div className="grid g-kpi4">{ov.isPending ? null : sec.map((k) => <KpiCard key={k.key} k={k} spark={sparks[k.key] || []} />)}</div>
      <p className="sub" style={{ color: "var(--muted)", fontSize: 12.5, margin: "-4px 0 16px" }}>
        Changes compare with the preceding period of equal length ({ov.data ? `${date(ov.data.range.prior_from)} to ${date(ov.data.range.prior_to)}` : "…"}). Rates change in percentage points. Anomaly rate counts alerts, not confirmed fraud.
      </p>

      <div className="grid g-21 mb">
        <ChartCard title="Transaction value (USD)" subtitle={`Card payments and core-banking completed value per ${grainWord}`} query={ser} isEmpty={(d) => !d.payments.length} footer="USD-converted with the dataset's synthetic FX table; payments without a rate are excluded from value." height={300}>
          <EChart height={300} ariaLabel="Transaction value over time" option={s && timeSeries(s.payments.map((r) => ({ ...r, core: (s.core.find((c) => c.period === r.period) || {}).value })), "period", [{ key: "value", name: "Card payments", area: true, fmt: (v) => usd(v) }, { key: "core", name: "Core banking (completed)", area: true, fmt: (v) => usd(v) }], { yFmt: (v) => usd(v) })} />
        </ChartCard>
        <ChartCard title="Transactions by channel" subtitle="Share of card payments (click a slice)" query={br} isEmpty={(d) => !d.channels.length} height={300}>
          <EChart height={300} ariaLabel="Payments by channel" onClick={(e) => e.name && nav(`/payments?channel=${encodeURIComponent(e.name.split("  ")[0])}`)} option={b && donut(b.channels, "channel", "payments", { fmt: int, totalLabel: "payments" })} />
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Approved vs declined" subtitle={`Authorizations per ${grainWord} with approval rate`} query={ser} isEmpty={(d) => !d.payments.length} height={300} footer="Approval rate = approved / (approved + declined).">
          <EChart height={300} ariaLabel="Approved versus declined" option={s && timeSeries(s.payments.map((r) => ({ ...r, rate: r.approved / (r.approved + r.declined) })), "period",
            [{ key: "approved", name: "Approved", type: "bar", stack: "a", color: "teal", fmt: int }, { key: "declined", name: "Declined", type: "bar", stack: "a", color: "bad", fmt: int }, { key: "rate", name: "Approval rate", axis: 1, color: "blue", fmt: (v) => pct(v, 2) }],
            { y2Fmt: (v) => pct(v, 0), yFmt: compact })} />
        </ChartCard>
        <ChartCard title="Merchant category mix" subtitle="Card-payment value (USD) by category; petal size = value" query={br} isEmpty={(d) => !d.categories.length} height={300} footer="Click a petal to open Payment Intelligence for that category.">
          <EChart height={300} ariaLabel="Merchant category value" onClick={(e) => e.name && nav(`/payments?category=${encodeURIComponent(b.categories.find((c) => c.category.startsWith(e.name.replace("…", "")))?.category || e.name)}`)}
            option={b && rose(b.categories, "category", "value", { fmt: (v) => usd(v), extra: (r) => `Approval rate ${pct(r.approval_rate, 2)} · ${int(r.payments)} payments` })} />
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Branch efficiency" subtitle="Each bubble is a branch: transactions (x), completed value (y), size = value, colour = failure rate" query={rk} isEmpty={(d) => !d.rows.length} height={320} footer="Teal: failure below 5%; amber: 5-5.8%; red: above 5.8%. Click a bubble to open the branch.">
          <EChart height={320} ariaLabel="Branch efficiency bubble chart" onClick={(e) => { const r = branches[e.dataIndex]; r && nav(`/branches/${r.branch_id}`); }}
            option={rk.data && bubble(branches, { x: "transactions", y: "value", size: "value", xName: "Transactions", yFmt: (v) => usd(v), colorFn: (r) => (r.failure_rate > 0.058 ? "bad" : r.failure_rate > 0.05 ? "warn" : "teal"),
              tip: (r) => `<b>${r.branch_name}</b><br/>${r.city}<br/>${int(r.transactions)} transactions · ${usd(r.value)}<br/>Failure rate ${pct(r.failure_rate, 2)}` })} />
        </ChartCard>
        <ChartCard title="When customers pay" subtitle="Card payments by weekday and hour of authorization" query={hm} isEmpty={(d) => !d.rows.length} height={320} footer={hm.data?.note}>
          <EChart height={320} ariaLabel="Payments by weekday and hour" option={hm.data && hourHeat(hm.data.rows, "payments", { fmt: int, name: "Payments" })} />
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Top branches by value" subtitle="Top 10 branches by completed value (core banking, USD)" query={br} isEmpty={(d) => !d.branches.length} height={310} footer="Click a bar to open the branch. Amber bars have a failure rate above 6%.">
          <EChart height={310} ariaLabel="Branch ranking" onClick={(e) => { const row = b.branches.find((x) => x.branch_name === e.name); row && nav(`/branches/${row.branch_id}`); }}
            option={b && hbar(b.branches, "branch_name", "value", { fmt: (v) => usd(v), name: "Completed value", colorFn: (r) => (r.failure_rate > 0.06 ? "warn" : "blue"), extra: (r) => `${r.city} · failure rate ${pct(r.failure_rate, 2)}` })} />
        </ChartCard>
        <ChartCard title="Customer segmentation" subtitle="Customers by activity segment (all time)" query={br} isEmpty={(d) => !d.segments.rows.length} height={310} footer={b?.segments.note}>
          <EChart height={310} ariaLabel="Customer segments" onClick={() => nav("/customers")} option={b && donut(b.segments.rows, "segment", "customers", { fmt: int, totalLabel: "customers" })} />
        </ChartCard>
      </div>

      <ChartCard title="Recent high-severity anomaly alerts" subtitle="Latest alerts in the selected range; alerts are not confirmed fraud" query={br} isEmpty={(d) => !d.alerts.length}
        actions={<button className="btn sm" onClick={() => nav("/fraud")}>Open investigation</button>} height={200}>
        <div className="table-wrap" style={{ maxHeight: 300 }}>
          <table className="dt auto">
            <thead><tr><th>Time</th><th>Customer</th><th className="r">Amount</th><th className="r">Score</th><th>Severity</th></tr></thead>
            <tbody>{(b?.alerts || []).map((a) => (
              <tr key={a.anomaly_id} style={{ cursor: "pointer" }} onClick={() => nav(`/fraud?anomaly=${a.anomaly_id}`)}>
                <td className="num">{a.transaction_timestamp.slice(0, 16).replace("T", " ")}</td>
                <td><span className="idchip">{a.customer_id}</span></td>
                <td className="r"><span className="dbar" style={{ "--p": `${Math.min(100, (a.amount / 20000) * 100)}%`, "--c": "var(--bad)" }}>{usd(a.amount, false)}</span></td>
                <td className="r">{a.ml_anomaly_score.toFixed(3)}</td>
                <td><Badge value={a.severity} /></td>
              </tr>))}</tbody>
          </table>
        </div>
      </ChartCard>
      <Card style={{ padding: 14, marginTop: 16 }}><small style={{ color: "var(--muted)" }}>Card payments and core-banking transactions are separate synthetic datasets that share customer and merchant IDs. External real-world aggregates (SBP, World Bank, BIS, ECB, FRED) are on the Global Financial Intelligence page and are never mixed with these records.</small></Card>
    </>
  );
}
