import React, { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useRange, useRangeApi } from "../lib/context.jsx";
import { date, int, pct, usd } from "../lib/format.js";
import { Card, ChartCard, EmptyState, ErrorState, PageHeader, Segmented, Skeleton, Stat } from "../ui/kit.jsx";
import EChart, { axis, baseGrid } from "../ui/EChart.jsx";
import { hbar, timeSeries } from "../ui/charts.js";
import ServerTable from "../ui/ServerTable.jsx";

function MerchantDetail({ id }) {
  const { from, to } = useRange();
  const q = useRangeApi(`/v1/merchants/${id}`);
  if (q.isPending) return <><Skeleton h={34} w="30%" /><Skeleton h={300} style={{ marginTop: 14 }} /></>;
  if (q.isError) return q.error.status === 404 ? <EmptyState title={`Merchant ${id} not found`} /> : <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const { profile: p, kpis: k, monthly, decline_reasons: dr } = q.data;
  return (
    <>
      <PageHeader title={p.merchant_name} subtitle={`${p.merchant_id} · ${p.merchant_category} · ${p.city || "unknown city"}, ${p.region || "unknown region"} · ${p.merchant_status}`} domains={[{ kind: "synthetic", label: "Synthetic · card payments" }]} actions={<Link className="btn sm" to="/merchants">All merchants</Link>} />
      <div className="grid g-kpi6">
        <Stat label="Payments" value={int(k.payments)} note={`${date(from)} to ${date(to)}`} />
        <Stat label="Value (USD)" value={usd(k.value)} />
        <Stat label="Approval rate" value={pct(k.approved / (k.approved + k.declined), 2)} />
        <Stat label="Declined" value={int(k.declined)} />
        <Stat label="Chargebacks" value={int(k.chargebacks)} note={k.settled ? pct(k.chargebacks / k.settled, 2) + " of settled" : ""} />
      </div>
      <div className="grid g-21 mb">
        <ChartCard title="Monthly payments and value" height={290} query={{ isPending: false, data: monthly }} isEmpty={(d) => !d.length}>
          <EChart height={290} ariaLabel="Merchant monthly" option={timeSeries(monthly, "period", [{ key: "payments", name: "Payments", type: "bar", fmt: int }, { key: "value", name: "Value (USD)", axis: 1, color: "teal", fmt: (v) => usd(v) }], { y2Fmt: (v) => usd(v) })} />
        </ChartCard>
        <ChartCard title="Decline reasons" height={290} query={{ isPending: false, data: dr }} isEmpty={(d) => !d.length}>
          <EChart height={290} ariaLabel="Decline reasons" option={hbar(dr, "reason", "declined", { fmt: int, colorFn: () => "bad", name: "Declined" })} />
        </ChartCard>
      </div>
      <Card style={{ padding: 18 }}><h3 style={{ marginBottom: 10 }}>Payments</h3>
        <ServerTable dataset="payments" testId="merchant-payments" initialSort={{ id: "payment_date", desc: true }} extraParams={{ filters: JSON.stringify([{ id: "merchant_id", op: "eq", value: p.merchant_id }]) }} /></Card>
    </>
  );
}

export default function Merchants() {
  const { id } = useParams();
  const nav = useNavigate();
  const [sort, setSort] = useState("risk");
  const rk = useRangeApi("/v1/merchants/ranking", { sort, limit: 15 });
  const ct = useRangeApi("/v1/payments/categories");
  if (id) return <MerchantDetail id={id} />;
  const rows = rk.data?.rows || [];
  const nameOf = (r) => r.merchant_name || r.merchant_id;
  const metric = { risk: ["risk_index", "Risk index", (v) => v.toFixed(2)], value: ["value", "Value (USD)", (v) => usd(v)], payments: ["payments", "Payments", int], decline_rate: ["decline_rate", "Decline rate", (v) => pct(v, 2)], chargeback_rate: ["chargeback_rate", "Chargeback rate", (v) => pct(v, 2)] }[sort];
  const catOpt = (t) => ({
    grid: baseGrid, legend: { top: 0, left: 0, textStyle: { color: t.text2 } }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "category", data: ct.data.map((r) => r.category), ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, interval: 0, rotate: 30 } }) },
    yAxis: [{ type: "value", ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => usd(v) } }) }, { type: "value", position: "right", min: 0.9, max: 1, ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, formatter: (v) => pct(v, 0) } }) }],
    series: [{ name: "Value (USD)", type: "bar", data: ct.data.map((r) => r.value), itemStyle: { color: t.colors[0], borderRadius: [4, 4, 0, 0] }, barMaxWidth: 34, tooltip: { valueFormatter: (v) => usd(v) } },
      { name: "Approval rate", type: "line", yAxisIndex: 1, data: ct.data.map((r) => r.approval_rate), itemStyle: { color: t.colors[3] }, symbolSize: 7, tooltip: { valueFormatter: (v) => pct(v, 2) } }],
  });
  return (
    <>
      <PageHeader title="Merchant analytics" subtitle="Merchant ranking, category performance and relative risk from card payments." domains={[{ kind: "synthetic", label: "Synthetic · card payments" }]} />
      <div className="grid g-2 mb">
        <ChartCard title="Merchant category performance" subtitle="Card-payment value and approval rate" query={ct} isEmpty={(d) => !d.length} height={330}>
          {ct.data && <EChart height={330} ariaLabel="Category performance" option={catOpt} onClick={(e) => e.name && nav(`/payments?category=${encodeURIComponent(e.name)}`)} />}
        </ChartCard>
        <ChartCard title="Merchant ranking" subtitle={`Top 15 by ${metric[1].toLowerCase()} (merchants with 200+ payments in range)`} query={rk} isEmpty={(d) => !d.rows.length} height={330}
          actions={<Segmented value={sort} onChange={setSort} label="Rank by" options={[{ value: "risk", label: "Risk" }, { value: "value", label: "Value" }, { value: "payments", label: "Volume" }, { value: "decline_rate", label: "Declines" }]} />}
          footer={sort === "risk" ? rk.data?.definition : "Click a bar to open the merchant."}>
          {rk.data && <EChart height={330} ariaLabel="Merchant ranking" onClick={(e) => { const r = rows.find((x) => nameOf(x) === e.name); r && nav(`/merchants/${r.merchant_id}`); }}
            option={hbar(rows.map((r) => ({ ...r, label: nameOf(r) })), "label", metric[0], { fmt: metric[2], name: metric[1], colorFn: () => (sort === "risk" ? "bad" : "blue"), extra: (r) => `${r.merchant_category || ""} · ${int(r.payments)} payments · decline ${pct(r.decline_rate, 2)} · chargeback ${pct(r.chargeback_rate, 2)}` })} />}
        </ChartCard>
      </div>
      <Card style={{ padding: 18 }}><h3 style={{ marginBottom: 10 }}>Merchants</h3>
        <ServerTable dataset="merchants" initialSort={{ id: "value_usd", desc: true }} onRowClick={(r) => nav(`/merchants/${r.merchant_id}`)} filterOptions={{ merchant_category: ["Retail", "Grocery", "Restaurant", "Fuel", "Healthcare", "Entertainment", "Travel", "Utilities", "Technology", "Education", "Other"] }} /></Card>
    </>
  );
}
