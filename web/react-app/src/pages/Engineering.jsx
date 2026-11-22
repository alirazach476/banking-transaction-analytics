import React from "react";
import { useApi } from "../lib/context.jsx";
import { date, int, pct } from "../lib/format.js";
import { Badge, Card, ChartCard, EmptyState, ErrorState, Notice, PageHeader, Skeleton, Stat } from "../ui/kit.jsx";
import EChart, { axis, baseGrid } from "../ui/EChart.jsx";
import ServerTable from "../ui/ServerTable.jsx";

const dt = (s) => (s ? String(s).replace("T", " ").slice(0, 16) : "–");
const dur = (s) => (s == null ? "–" : s >= 120 ? (s / 60).toFixed(1) + " min" : Number(s).toFixed(1) + " s");

function Table({ cols, rows, empty = "No rows" }) {
  if (!rows?.length) return <EmptyState title={empty} />;
  return (
    <div className="table-wrap"><table className="dt auto">
      <thead><tr>{cols.map((c) => <th key={c.k} style={{ textAlign: c.num ? "right" : "left" }}>{c.h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c.k} className={c.num ? "r" : ""}>{c.f ? c.f(r[c.k], r) : r[c.k] ?? "–"}</td>)}</tr>)}</tbody>
    </table></div>
  );
}
const status = (v) => <Badge value={v} />;

function Section({ title, sub, q, children, empty }) {
  return (
    <Card style={{ padding: 18, marginBottom: 16 }}>
      <h3 style={{ marginBottom: 2 }}>{title}</h3>{sub && <p style={{ color: "var(--muted)", margin: "0 0 10px", fontSize: 12 }}>{sub}</p>}
      {q.isPending ? <Skeleton h={120} /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : children(q.data)}
    </Card>
  );
}

export default function Engineering() {
  const sum = useApi("/v1/observability/summary");
  const pl = useApi("/v1/observability/pipelines");
  const ing = useApi("/v1/observability/ingestion");
  const dq = useApi("/v1/observability/data-quality");
  const rc = useApi("/v1/observability/reconciliation");
  const fr = useApi("/v1/observability/freshness");
  const dbt = useApi("/v1/observability/dbt");
  const af = useApi("/v1/observability/airflow");
  const er = useApi("/v1/observability/errors");
  const s = sum.data;
  const nOf = (arr, st) => arr?.filter((x) => String(x.status).toUpperCase() === st).reduce((a, x) => a + x.n, 0) || 0;
  const dqTot = s ? s.data_quality.reduce((a, x) => a + x.n, 0) : 0;
  const prTot = s ? s.pipeline_runs.reduce((a, x) => a + x.n, 0) : 0;
  const durOpt = (t) => ({
    grid: baseGrid, tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v) => dur(v) },
    xAxis: { type: "category", data: pl.data.history.map((r) => r.pipeline_name + " " + dt(r.start_time).slice(5)).reverse(), ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 10, rotate: 25, hideOverlap: true } }) },
    yAxis: { type: "value", ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => v + " s" } }) },
    series: [{ type: "bar", barMaxWidth: 28, data: pl.data.history.map((r) => ({ value: r.duration_s, itemStyle: { color: r.status === "SUCCESS" ? t.colors[2] : t.colors[3], borderRadius: [4, 4, 0, 0] } })).reverse() }],
  });
  return (
    <>
      <PageHeader title="Data engineering & monitoring" subtitle="Pipeline runs, ingestion, data quality, reconciliation, freshness and dbt results read from the project's own audit tables and files."
        domains={[{ kind: "real", label: "Real · pipeline metadata" }]} />
      <div className="grid g-kpi4 mb">
        <Stat label="Pipeline runs recorded" value={int(prTot)} note={`${int(nOf(s?.pipeline_runs, "SUCCESS"))} succeeded`} loading={sum.isPending} />
        <Stat label="Data-quality checks" value={int(dqTot)} note={`${int(nOf(s?.data_quality, "PASS"))} pass · ${int(dqTot - nOf(s?.data_quality, "PASS"))} not passing`} loading={sum.isPending} />
        <Stat label="Rows loaded (latest ingestion)" value={int(s?.ingestion.rows_loaded)} note={`${int(s?.ingestion.rows_rejected)} rejected from ${int(s?.ingestion.sources)} sources`} loading={sum.isPending} />
        <Stat label="Airflow" value={af.data ? (af.data.connected ? "Connected" : "Not connected") : "…"} note={af.data?.connected ? "live DAG runs below" : "definitions only"} loading={af.isPending} />
      </div>

      <div className="grid g-2 mb">
        <Section title="Pipelines" sub={pl.data?.note} q={pl}>{(d) => <Table rows={d.stats} cols={[{ k: "pipeline_name", h: "Pipeline" }, { k: "runs", h: "Runs", num: 1 }, { k: "success", h: "OK", num: 1 }, { k: "failed", h: "Failed", num: 1 }, { k: "avg_duration_s", h: "Avg duration", num: 1, f: dur }, { k: "rows_processed", h: "Rows", num: 1, f: int }, { k: "last_run", h: "Last run", f: dt }]} />}</Section>
        <ChartCard title="Recent run durations" subtitle="Green = success" query={pl} isEmpty={(d) => !d.history.length} height={230}>{pl.data && <EChart height={230} ariaLabel="Run durations" option={durOpt} />}</ChartCard>
      </div>

      <Section title="Source ingestion" sub="Latest load per source: rows read, loaded and rejected." q={ing}>{(d) => <Table rows={d} cols={[{ k: "source_name", h: "Source" }, { k: "source_system", h: "System" }, { k: "status", h: "Status", f: status }, { k: "rows_read", h: "Read", num: 1, f: int }, { k: "rows_loaded", h: "Loaded", num: 1, f: int }, { k: "rows_rejected", h: "Rejected", num: 1, f: int }, { k: "reject_rate", h: "Reject rate", num: 1, f: (v) => pct(v, 2) }, { k: "completed_at", h: "Completed", f: dt }]} />}</Section>

      <div className="grid g-2 mb">
        <Section title="Data freshness" sub={fr.data?.note} q={fr}>{(d) => <Table rows={d.items} cols={[{ k: "name", h: "Dataset" }, { k: "kind", h: "Kind", f: (v) => <Badge value={v} kind={v === "synthetic" ? "synthetic" : "neutral"} /> }, { k: "latest", h: "Latest", f: (v) => dt(v) }, { k: "age_days", h: "Age (days)", num: 1, f: (v) => (v == null ? "–" : Number(v).toFixed(1)) }]} />}</Section>
        <Section title="Data-quality checks" sub="Checks by table; failing checks are listed below." q={dq}>{(d) => (
          <>
            <Table rows={d.by_table} cols={[{ k: "table_name", h: "Table" }, { k: "status", h: "Status", f: status }, { k: "n", h: "Checks", num: 1, f: int }]} />
            {d.failing.length > 0 && <><h4 style={{ margin: "12px 0 6px" }}>Not passing</h4><Table rows={d.failing} cols={[{ k: "check_name", h: "Check" }, { k: "table_name", h: "Table" }, { k: "status", h: "Status", f: status }, { k: "failed_rows", h: "Failed rows", num: 1, f: int }, { k: "checked_at", h: "Checked", f: dt }]} /></>}
          </>)}</Section>
      </div>

      <Section title="Reconciliation" sub="Source-to-warehouse control totals, and the latest card-payment clearing reconciliation run." q={rc}>{(d) => (
        <>
          <Table rows={d.source_to_warehouse} cols={[{ k: "source_name", h: "Source" }, { k: "metric_name", h: "Metric" }, { k: "source_value", h: "Source", num: 1, f: (v) => int(v) }, { k: "warehouse_value", h: "Warehouse", num: 1, f: (v) => int(v) }, { k: "difference", h: "Difference", num: 1, f: (v) => int(v) }, { k: "status", h: "Status", f: status }]} />
          {d.payments_latest_run && (() => { const p = d.payments_latest_run; return (
            <div className="grid g-kpi6" style={{ marginTop: 14 }}>
              <Stat label="Cleared payments" value={int(p.cleared_payments)} note={`as of ${dt(p.as_of)} · SLA ${p.sla_days} days`} />
              <Stat label="Matched" value={int(p.matched)} note={pct(p.matched / p.cleared_payments, 1)} />
              <Stat label="Missing settlement" value={int(p.missing)} />
              <Stat label="Duplicate" value={int(p.duplicate)} />
              <Stat label="Amount mismatch" value={int(p.amount_mismatch)} />
              <Stat label="Late" value={int(p.late)} />
            </div>); })()}
          {d.payments_exception_queue?.length > 0 && <><h4 style={{ margin: "12px 0 6px" }}>Exception queue</h4><Table rows={d.payments_exception_queue} cols={[{ k: "issue_type", h: "Issue" }, { k: "status", h: "Status", f: status }, { k: "n", h: "Count", num: 1, f: int }, { k: "amount_at_risk", h: "Amount at risk", num: 1, f: (v) => int(v) }]} /></>}
        </>)}</Section>

      <div className="grid g-2 mb">
        <Section title="dbt" sub={dbt.data?.note} q={dbt}>{(d) => !d.available ? <EmptyState title="No dbt artifacts found" hint="Run dbt build to create target/run_results.json." /> : (
          <>
            <p style={{ margin: "0 0 8px", color: "var(--text-2)" }}>Last invocation: <b>dbt {d.last_invocation.command}</b> · {dt(d.last_invocation.generated_at)} · {dur(d.last_invocation.elapsed_s)} · dbt {d.last_invocation.dbt_version}
              {" · "}{Object.entries(d.last_invocation.counts).map(([k, v]) => `${v} ${k}`).join(", ")}</p>
            <p style={{ margin: "0 0 8px", color: "var(--muted)", fontSize: 12 }}>Project inventory: {Object.entries(d.inventory.nodes_by_type).map(([k, v]) => `${v} ${k}`).join(", ")}, {d.inventory.sources} sources.</p>
            <Table rows={d.last_invocation.results} cols={[{ k: "unique_id", h: "Node" }, { k: "status", h: "Status", f: status }, { k: "seconds", h: "Seconds", num: 1, f: (v) => Number(v).toFixed(2) }, { k: "failures", h: "Failures", num: 1 }]} />
          </>)}</Section>
        <Section title="Airflow" q={af}>{(d) => (
          <>
            {d.connected ? <Notice>Connected to Airflow.</Notice> : <Notice warn>Not connected: {d.reason} Live DAG run status is therefore not shown; the DAG definitions below are parsed from the project's airflow/dags files.</Notice>}
            <Table rows={d.definitions} cols={[{ k: "dag_id", h: "DAG" }, { k: "schedule", h: "Schedule" }, { k: "tasks", h: "Tasks", num: 1, f: (v) => (Array.isArray(v) ? v.length : v) }, { k: "file", h: "File" }]} />
            {d.runs?.length > 0 && <><h4 style={{ margin: "12px 0 6px" }}>Recent DAG runs</h4><Table rows={d.runs} cols={[{ k: "dag_id", h: "DAG" }, { k: "state", h: "State", f: status }, { k: "start_date", h: "Started", f: dt }, { k: "end_date", h: "Ended", f: dt }]} /></>}
          </>)}</Section>
      </div>

      <Section title="Error and warning log" sub={er.data?.note} q={er}>{(d) => <Table rows={d.entries} empty="No errors or warnings recorded" cols={[{ k: "time", h: "Time", f: dt }, { k: "source", h: "Source" }, { k: "level", h: "Level", f: status }, { k: "message", h: "Message" }]} />}</Section>

      <Card style={{ padding: 18 }}><h3 style={{ marginBottom: 10 }}>Pipeline run history</h3><ServerTable dataset="pipeline-runs" initialSort={{ id: "start_time", desc: true }} filterOptions={{ status: ["SUCCESS", "FAILED", "WARNING", "RUNNING"] }} /></Card>
      <Card style={{ padding: 18, marginTop: 16 }}><h3 style={{ marginBottom: 10 }}>Data-quality results</h3><ServerTable dataset="data-quality" initialSort={{ id: "checked_at", desc: true }} filterOptions={{ status: ["PASS", "FAIL", "WARN"] }} /></Card>
    </>
  );
}
