import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { compact } from "../lib/format.js";
import { Card, ChartCard, DomainBadge, EmptyState, ErrorState, Notice, PageHeader, Skeleton, Stat } from "../ui/kit.jsx";
import EChart from "../ui/EChart.jsx";
import { specProblems, toOption } from "../lib/spec.js";

// External, real, aggregate statistics (SBP, World Bank, BIS, ECB, FRED, Global Findex). Deliberately separate from the
// synthetic NovaBank transaction data: no joins, different granularity, different periods.
const full = (v, unit) => (typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) + (unit ? " " + unit : "") : v ?? "");

function DataTable({ c }) {
  return (
    <div className="table-wrap">
      <table className="dt auto">
        <thead><tr>{c.series.map((s) => <th key={s.key}>{s.name}</th>)}</tr></thead>
        <tbody>{c.data.map((r, i) => <tr key={i}>{c.series.map((s) => <td key={s.key} className={typeof r[s.key] === "number" ? "r" : ""}>{typeof r[s.key] === "number" ? full(r[s.key]) : r[s.key]}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

function SpecChart({ c }) {
  const problems = specProblems(c);
  const h = c.type === "barh" ? Math.max(220, c.data.length * 24 + 40) : 280;
  return (
    <div style={c.wide ? { gridColumn: "1 / -1" } : undefined} data-testid={"chart-" + c.id}>
      <ChartCard title={c.title + (c.unit && c.type !== "table" ? ` (${c.unit})` : "")} subtitle={c.subtitle} height={c.type === "table" ? 200 : h}
        query={{ isPending: false, data: c }} isEmpty={() => problems.length > 0} footer={[c.note, c.source && "Source: " + c.source].filter(Boolean).join(" · ")}>
        {c.type === "table" ? <DataTable c={c} /> : <EChart height={h} ariaLabel={c.title} option={(t) => toOption(c, t)} />}
      </ChartCard>
    </div>
  );
}

export default function GlobalIntel() {
  const q = useQuery({ queryKey: ["analysis.json"], staleTime: Infinity, queryFn: () => fetch(import.meta.env.BASE_URL + "analysis.json").then((r) => (r.ok ? r.json() : Promise.reject(new Error("analysis.json " + r.status)))) });
  const [sec, setSec] = useState("overview");
  if (q.isPending) return <><PageHeader title="Global financial intelligence" /><Skeleton h={300} /></>;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  const s = d.sections.find((x) => x.id === sec) || d.sections[0];
  const n = d.sections.reduce((a, x) => a + x.charts.length, 0);
  return (
    <>
      <PageHeader title="Global financial intelligence" subtitle={`${d.title}. ${n} charts and tables, generated ${d.generated}.`}
        domains={[{ kind: "real", label: "Real · external aggregates" }]} />
      <Notice>These are published aggregate statistics (State Bank of Pakistan, World Bank, BIS, ECB, FRED, Global Findex). They are not joined to the synthetic NovaBank transactions: periods, granularity and populations differ, so comparisons across the two are not meaningful.</Notice>
      <div className="seg" role="tablist" aria-label="Sections" style={{ flexWrap: "wrap", margin: "12px 0 16px" }}>
        {d.sections.map((x) => <button key={x.id} role="tab" aria-selected={x.id === s.id} className={x.id === s.id ? "on" : ""} onClick={() => setSec(x.id)}>{x.title}</button>)}
      </div>
      <Card style={{ padding: 16, marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}><h2 style={{ fontSize: 16, margin: 0 }}>{s.title}</h2>{s.id === "ml" && <DomainBadge kind="simulated" label="Simulated + real benchmark" />}</div>
        <p style={{ color: "var(--text-2)", margin: 0 }}>{s.id === "overview" ? "Headline figures from the real external datasets summarised in the other tabs (SBP, World Bank, BIS, ECB, FRED, Global Findex)." : s.intro}</p>
      </Card>
      {s.kpis.length > 0 && <div className="grid g-kpi4 mb">{s.kpis.map((k) => <Stat key={k.label} label={k.label} value={k.value} note={k.note} />)}</div>}
      {s.charts.length === 0 ? (s.kpis.length ? null : <EmptyState title="No charts in this section" />) : <div className="grid g-2" data-testid={"sec-" + s.id}>{s.charts.map((c) => <SpecChart key={c.id} c={c} />)}</div>}
    </>
  );
}
