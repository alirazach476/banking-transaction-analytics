import React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useRange, useRangeApi } from "../lib/context.jsx";
import { compact, date, int, pct, usd } from "../lib/format.js";
import { Card, ChartCard, EmptyState, ErrorState, Notice, PageHeader, Skeleton, Stat } from "../ui/kit.jsx";
import EChart, { axis, baseGrid } from "../ui/EChart.jsx";
import { hbar, timeSeries } from "../ui/charts.js";
import BranchMap from "../ui/BranchMap.jsx";
import ServerTable from "../ui/ServerTable.jsx";

function BranchDetail({ id }) {
  const { from, to } = useRange();
  const q = useRangeApi(`/v1/branches/${id}`);
  if (q.isPending) return <><Skeleton h={34} w="30%" /><Skeleton h={300} style={{ marginTop: 14 }} /></>;
  if (q.isError) return q.error.status === 404 ? <EmptyState title={`Branch ${id} not found`} /> : <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const { profile: p, kpis: k, monthly } = q.data;
  return (
    <>
      <PageHeader title={p.branch_name} subtitle={`${p.branch_id} · ${p.city}, ${p.region} · ${p.branch_type} · ${p.branch_status} · opened ${date(p.opening_date)}`} domains={[{ kind: "synthetic", label: "Synthetic · core banking" }]} actions={<Link className="btn sm" to="/branches">All branches</Link>} />
      <div className="grid g-kpi6">
        <Stat label="Transactions" value={int(k.transactions)} note={`${date(from)} to ${date(to)}`} />
        <Stat label="Completed value (USD)" value={usd(k.value)} />
        <Stat label="Completion rate" value={pct(k.completed / (k.completed + k.failed), 2)} />
        <Stat label="Failure rate" value={pct(k.failed / k.transactions, 2)} />
        <Stat label="Active customers" value={int(k.customers)} />
      </div>
      <ChartCard title="Monthly transactions and completed value" height={300} query={{ isPending: false, data: monthly }} isEmpty={(d) => !d.length}>
        <EChart height={300} ariaLabel="Branch monthly" option={timeSeries(monthly, "period", [{ key: "transactions", name: "Transactions", type: "bar", fmt: int }, { key: "value", name: "Completed value", axis: 1, color: "teal", fmt: (v) => usd(v) }], { y2Fmt: (v) => usd(v) })} />
      </ChartCard>
      <Card style={{ padding: 18, marginTop: 16 }}><h3 style={{ marginBottom: 10 }}>Branch transactions</h3>
        <ServerTable dataset="transactions" testId="branch-transactions" initialSort={{ id: "ts", desc: true }} extraParams={{ filters: JSON.stringify([{ id: "branch_id", op: "eq", value: p.branch_id }]) }} filterOptions={{ status: ["Completed", "Failed", "Pending", "Reversed"] }} /></Card>
    </>
  );
}

export default function Branches() {
  const { id } = useParams();
  const nav = useNavigate();
  const rk = useRangeApi("/v1/branches/ranking");
  const mp = useRangeApi("/v1/branches/map");
  const rg = useRangeApi("/v1/branches/regions");
  if (id) return <BranchDetail id={id} />;
  const rows = rk.data?.rows || [];
  const regOpt = (t) => ({
    grid: baseGrid, legend: { top: 0, left: 0, textStyle: { color: t.text2 } }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "category", data: rg.data.rows.map((r) => r.region), ...axis(t, { splitLine: { show: false } }) },
    yAxis: [{ type: "value", ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => usd(v) } }) }, { type: "value", position: "right", min: 0, ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, formatter: (v) => pct(v, 1) } }) }],
    series: [{ name: "Completed value (USD)", type: "bar", data: rg.data.rows.map((r) => r.value), itemStyle: { color: t.colors[0], borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40, tooltip: { valueFormatter: (v) => usd(v) } },
      { name: "Failure rate", type: "line", yAxisIndex: 1, data: rg.data.rows.map((r) => r.failure_rate), itemStyle: { color: t.colors[3] }, symbolSize: 8, tooltip: { valueFormatter: (v) => pct(v, 2) } }],
  });
  const rateOpt = (t) => ({
    grid: { left: 8, right: 16, top: 30, bottom: 8, containLabel: true }, legend: { top: 0, left: 0, textStyle: { color: t.text2 } }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v) => pct(v, 2) },
    xAxis: { type: "value", min: 0.9, max: 1, ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => pct(v, 0) } }) },
    yAxis: { type: "category", data: rows.slice().sort((a, b) => a.completion_rate - b.completion_rate).slice(0, 10).map((r) => r.branch_name), ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.text2, fontSize: 11, width: 130, overflow: "truncate" } }) },
    series: [{ name: "Completion rate", type: "bar", data: rows.slice().sort((a, b) => a.completion_rate - b.completion_rate).slice(0, 10).map((r) => r.completion_rate), itemStyle: { color: t.colors[2], borderRadius: [0, 4, 4, 0] }, barMaxWidth: 16 }],
  });
  return (
    <>
      <PageHeader title="Branch & regional analytics" subtitle="Transaction volume, value and completion by branch and region (core banking, USD)." domains={[{ kind: "synthetic", label: "Synthetic · core banking" }]} />
      <div className="grid g-21 mb">
        <ChartCard title="Branch locations" subtitle="One marker per city (branches in the same city share a marker); click a marker for totals" query={mp} isEmpty={(d) => !d.markers.length} height={440} footer={mp.data?.note}>
          {mp.data && <BranchMap markers={mp.data.markers} height={440} />}
        </ChartCard>
        <ChartCard title="Regional performance" subtitle="Completed value and failure rate by region" query={rg} isEmpty={(d) => !d.rows.length} height={440} footer={rg.data?.note}>
          {rg.data && <EChart height={440} ariaLabel="Regional performance" option={regOpt} />}
        </ChartCard>
      </div>
      {mp.data?.unmapped_cities?.length > 0 && <Notice warn>No coordinates for: {mp.data.unmapped_cities.join(", ")} (not shown on the map).</Notice>}
      <div className="grid g-2 mb">
        <ChartCard title="Branch transaction value" subtitle="Top 15 branches by completed value (USD); click to open" query={rk} isEmpty={(d) => !d.rows.length} height={420}>
          {rk.data && <EChart height={420} ariaLabel="Branch value" onClick={(e) => { const r = rows.find((x) => x.branch_name === e.name); r && nav(`/branches/${r.branch_id}`); }}
            option={hbar(rows.slice(0, 15), "branch_name", "value", { fmt: (v) => usd(v), name: "Completed value", extra: (r) => `${int(r.transactions)} transactions · failure ${pct(r.failure_rate, 2)}` })} />}
        </ChartCard>
        <ChartCard title="Lowest completion rates" subtitle="10 branches with the lowest completed / (completed + failed)" query={rk} isEmpty={(d) => !d.rows.length} height={420} footer={rk.data?.note}>
          {rk.data && <EChart height={420} ariaLabel="Branch completion rates" option={rateOpt} />}
        </ChartCard>
      </div>
      <Card style={{ padding: 18 }}><h3 style={{ marginBottom: 10 }}>Branches</h3>
        <ServerTable dataset="branches" initialSort={{ id: "transaction_count", desc: true }} filterOptions={{ region: ["Northeast", "Southeast", "Midwest", "Southwest", "West"] }} onRowClick={(r) => nav(`/branches/${r.branch_id}`)} /></Card>
    </>
  );
}
