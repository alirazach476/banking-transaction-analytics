import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useRange, useRangeApi, useApi } from "../lib/context.jsx";
import { send } from "../lib/api.js";
import { compact, dowName, int, num, pct, usd } from "../lib/format.js";
import { Badge, Card, ChartCard, Notice, PageHeader, Stat } from "../ui/kit.jsx";
import EChart, { axis, baseGrid } from "../ui/EChart.jsx";
import { donut, hbar, timeSeries } from "../ui/charts.js";
import ServerTable from "../ui/ServerTable.jsx";
import Scorer from "./Scorer.jsx";

const STATUSES = ["NEW", "INVESTIGATING", "CONFIRMED_FRAUD", "FALSE_POSITIVE", "CLOSED"];
const SEV = { High: "bad", Medium: "warn", Low: "info" };

function InvestigationPanel({ row, onSaved }) {
  const detail = useApi(`/v1/anomalies/${row.anomaly_id}`);
  const [status, setStatus] = useState(row.investigation_status);
  const [assignee, setAssignee] = useState(row.assignee || "");
  const [note, setNote] = useState(row.note || "");
  const [msg, setMsg] = useState("");
  const save = async () => {
    try { await send("PUT", `/v1/anomalies/${row.anomaly_id}/investigation`, { status, assignee: assignee || null, note: note || null }); setMsg("Saved"); onSaved(); } catch (e) { setMsg(e.message); }
  };
  const d = detail.data;
  return (
    <div className="grid g-2" data-testid="investigation-panel">
      <div>
        <div className="kv">
          <div><span>Transaction</span><b>{row.transaction_id}</b></div><div><span>Customer</span><b>{row.customer_id}</b></div>
          <div><span>Amount (USD)</span><b>{d?.amount_usd != null ? usd(d.amount_usd, false) : "–"}</b></div><div><span>Timestamp</span><b>{String(row.transaction_timestamp).replace("T", " ").slice(0, 19)}</b></div>
          <div><span>Detection method</span><b>{d?.detection_method || "…"}</b></div><div><span>ML score</span><b>{num(row.ml_anomaly_score, 4)}</b></div>
          <div><span>Rule score</span><b>{num(row.rule_based_score, 2)}</b></div><div><span>Severity</span><Badge value={row.severity} /></div>
        </div>
        <p style={{ margin: "10px 0 0", color: "var(--text-2)", fontSize: 12.5 }}><b>Why it was flagged:</b> {String(row.anomaly_reason).replace(/Potential anomaly: /g, "").split("; ").join(" · ")}</p>
        <p style={{ margin: "6px 0 0", color: "var(--muted)", fontSize: 12 }}>This is an alert from rules / an Isolation Forest model, not a confirmed fraud case.</p>
      </div>
      <div style={{ display: "grid", gap: 8, alignContent: "start" }}>
        <label style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>Investigation status
          <select className="field" style={{ width: "100%" }} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Investigation status">{STATUSES.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>Assignee<input className="field" style={{ width: "100%" }} value={assignee} maxLength={80} onChange={(e) => setAssignee(e.target.value)} aria-label="Assignee" /></label>
        <label style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>Note<input className="field" style={{ width: "100%" }} value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} aria-label="Note" /></label>
        <div className="actions"><button className="btn primary sm" onClick={save}>Save investigation</button><span style={{ color: "var(--muted)", fontSize: 12.5 }} role="status">{msg}</span></div>
      </div>
    </div>
  );
}

export default function Fraud() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [sp] = useSearchParams();
  const { from, to } = useRange();
  const [refresh, setRefresh] = useState(0);
  const sm = useRangeApi("/v1/anomalies/summary");
  const se = useRangeApi("/v1/anomalies/series");
  const ca = useRangeApi("/v1/anomalies/categories");
  const sd = useRangeApi("/v1/anomalies/score-distribution");
  const sc = useRangeApi("/v1/anomalies/scatter");
  const rc = useRangeApi("/v1/anomalies/risk/customers");
  const rm = useRangeApi("/v1/anomalies/risk/merchants");
  const hm = useRangeApi("/v1/anomalies/heatmap");
  const cp = useRangeApi("/v1/anomalies/comparison");
  const s = sm.data;
  const investigated = s ? s.investigation_status.filter((x) => x.status !== "NEW").reduce((a, b) => a + b.alerts, 0) : null;

  const sevColor = (t, sev) => t[SEV[sev]];
  const scoreOpt = (t) => ({
    grid: baseGrid, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } }, legend: { top: 0, left: 0, textStyle: { color: t.text2 } },
    xAxis: { type: "category", data: sd.data.rows.map((r) => r.score_from.toFixed(3)), name: "Isolation Forest score", nameLocation: "middle", nameGap: 28, nameTextStyle: { color: t.muted }, ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 10, interval: 3 } }) },
    yAxis: { type: "value", ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => compact(v) } }) },
    series: [{ name: "Other alerts", type: "bar", stack: "s", data: sd.data.rows.map((r) => r.alerts - r.high), itemStyle: { color: t.colors[0] }, tooltip: { valueFormatter: int } },
      { name: "High severity", type: "bar", stack: "s", data: sd.data.rows.map((r) => r.high), itemStyle: { color: t.bad }, tooltip: { valueFormatter: int } }],
  });
  const scatterOpt = (t) => ({
    grid: { ...baseGrid, top: 36 }, legend: { top: 0, left: 0, textStyle: { color: t.text2 } },
    tooltip: { trigger: "item", formatter: (p) => `${p.seriesName}<br/>Amount: ${usd(p.value[0], false)}<br/>ML score: ${p.value[1].toFixed(3)}` },
    xAxis: { type: "log", name: "Amount (USD, log scale)", nameLocation: "middle", nameGap: 28, nameTextStyle: { color: t.muted }, min: 1, ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => compact(v) } }) },
    yAxis: { type: "value", name: "ML anomaly score", min: 0.35, nameTextStyle: { color: t.muted }, ...axis(t) },
    series: ["High", "Medium", "Low"].map((sev) => ({ name: sev, type: "scatter", symbolSize: 6, itemStyle: { color: sevColor(t, sev), opacity: 0.65 }, data: sc.data.rows.filter((r) => r.severity === sev && r.amount_usd > 0).map((r) => [r.amount_usd, r.score]) })),
  });
  const heatOpt = (t) => {
    const rows = hm.data.rows;
    return {
      grid: { left: 8, right: 12, top: 10, bottom: 70, containLabel: true },
      tooltip: { formatter: (p) => `${dowName(p.value[1] + 1)} ${String(p.value[0]).padStart(2, "0")}:00<br/>${int(p.value[2])} alerts` },
      xAxis: { type: "category", data: Array.from({ length: 24 }, (_, h) => String(h).padStart(2, "0")), ...axis(t, { splitLine: { show: false } }) },
      yAxis: { type: "category", data: [1, 2, 3, 4, 5, 6, 7].map(dowName), inverse: true, ...axis(t, { splitLine: { show: false } }) },
      visualMap: { min: 0, max: Math.max(...rows.map((r) => r.alerts), 1), calculable: true, orient: "horizontal", left: "center", bottom: 4, itemWidth: 14, itemHeight: 160, textStyle: { color: t.muted }, inRange: { color: [t.surface, t.warn, t.bad] } },
      series: [{ type: "heatmap", data: rows.map((r) => [r.hour, r.dow - 1, r.alerts]), itemStyle: { borderColor: t.surface, borderWidth: 1, borderRadius: 3 } }],
    };
  };
  const cmpOpt = (t) => ({
    grid: baseGrid, legend: { top: 0, left: 0, textStyle: { color: t.text2 } }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v) => pct(v, 1) },
    xAxis: { type: "category", data: cp.data.detectors.map((d) => d.detector.replace(/ \(incl\.[^)]*\)/, "")), ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, interval: 0, width: 110, overflow: "break" } }) },
    yAxis: { type: "value", max: 1, ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => pct(v, 0) } }) },
    series: [{ name: "Recall", type: "bar", data: cp.data.detectors.map((d) => d.recall), itemStyle: { color: t.colors[2], borderRadius: [4, 4, 0, 0] }, barMaxWidth: 34 }, { name: "Precision", type: "bar", data: cp.data.detectors.map((d) => d.precision), itemStyle: { color: t.colors[1], borderRadius: [4, 4, 0, 0] }, barMaxWidth: 34 }],
  });

  return (
    <>
      <PageHeader title="Fraud & anomaly intelligence" subtitle="Alerts raised by statistical rules and an Isolation Forest model over core-banking transactions. An alert is a lead to investigate, not confirmed fraud."
        domains={[{ kind: "synthetic", label: "Synthetic · core-banking anomaly alerts" }]} />
      <Notice>Detection quality below is measured against the <b>synthetic injected-anomaly labels</b> planted by the data generator. The data has no confirmed-fraud outcomes, so real-world precision and recall are unknown.</Notice>
      <div className="grid g-kpi6">
        <Stat loading={sm.isPending} label="Alerts" value={int(s?.alerts)} note={`${from} to ${to}`} />
        <Stat loading={sm.isPending} label="Anomaly rate" value={pct(s?.rate, 2)} note="alerts / transactions" />
        <Stat loading={sm.isPending} label="High severity" value={int(s?.high)} note={s ? pct(s.high / s.alerts, 1) + " of alerts" : ""} />
        <Stat loading={sm.isPending} label="Medium / Low" value={s ? `${int(s.medium)} / ${int(s.low)}` : "–"} />
        <Stat loading={sm.isPending} label="Under investigation or closed" value={int(investigated)} note="status other than NEW" />
        <Stat loading={cp.isPending} label="Injected anomalies caught" value={pct(cp.data?.detectors.find((d) => d.detector === "Any detector")?.recall, 1)} note="recall vs synthetic labels" />
      </div>

      <div className="grid g-21 mb">
        <ChartCard title="Anomaly volume over time" subtitle={`Alerts per ${se.data?.grain || "period"} by severity`} query={se} isEmpty={(d) => !d.rows.length} height={290}>
          {se.data && <EChart height={290} ariaLabel="Anomaly volume" option={timeSeries(se.data.rows, "period", [{ key: "low", name: "Low", type: "bar", stack: "s", color: "info", fmt: int }, { key: "medium", name: "Medium", type: "bar", stack: "s", color: "warn", fmt: int }, { key: "high", name: "High", type: "bar", stack: "s", color: "bad", fmt: int }])} />}
        </ChartCard>
        <ChartCard title="Severity distribution" subtitle="Alerts by severity" query={sm} isEmpty={(d) => !d.alerts} height={290}>
          {s && <EChart height={290} ariaLabel="Severity distribution" option={(t) => ({ ...donut([{ n: "High", v: s.high }, { n: "Medium", v: s.medium }, { n: "Low", v: s.low }], "n", "v", { fmt: int })(t), color: [t.bad, t.warn, t.info] })} />}
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Anomaly categories" subtitle="Alerts by triggering rule (an alert can trigger several)" query={ca} isEmpty={(d) => !d.length} height={300}>
          {ca.data && <EChart height={300} ariaLabel="Anomaly categories" option={hbar(ca.data, "category", "alerts", { fmt: int, name: "Alerts" })} />}
        </ChartCard>
        <ChartCard title="Isolation Forest score distribution" subtitle="Alerts by ML anomaly score (high severity in red)" query={sd} isEmpty={(d) => !d.rows.length} height={300} footer="Higher score = more unusual. High severity requires the ML model to agree.">
          {sd.data && <EChart height={300} ariaLabel="ML score distribution" option={scoreOpt} />}
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Transaction amount vs anomaly score" subtitle="Sample of up to 2,500 alerts" query={sc} isEmpty={(d) => !d.rows.length} height={310} footer={sc.data?.note}>
          {sc.data && <EChart height={310} ariaLabel="Amount vs anomaly score" option={scatterOpt} />}
        </ChartCard>
        <ChartCard title="Rule-based vs machine-learning detection" subtitle="Recall and precision against the synthetic injected labels" query={cp} isEmpty={(d) => !d.detectors} height={310} footer={cp.data?.note}>
          {cp.data && <EChart height={310} ariaLabel="Detector comparison" option={cmpOpt} />}
        </ChartCard>
      </div>

      <div className="grid g-3 mb">
        <ChartCard title="Customer risk ranking" subtitle="Risk points: High 3, Medium 2, Low 1 (click for the customer)" query={rc} isEmpty={(d) => !d.rows.length} height={330}>
          {rc.data && <EChart height={330} ariaLabel="Customer risk" onClick={(e) => e.name && nav(`/customers/${e.name}`)} option={hbar(rc.data.rows, "customer_id", "risk_points", { fmt: int, name: "Risk points", colorFn: () => "warn", extra: (r) => `${r.alerts} alerts (${r.high} high) in ${r.transactions} transactions` })} />}
        </ChartCard>
        <ChartCard title="Merchant risk ranking" subtitle="Alert rate among core-banking transactions (merchants with 20+ transactions)" query={rm} isEmpty={(d) => !d.rows.length} height={330}>
          {rm.data && <EChart height={330} ariaLabel="Merchant risk" onClick={(e) => { const r = rm.data.rows.find((x) => (x.merchant_name || x.merchant_id) === e.name); r && nav(`/merchants/${r.merchant_id}`); }}
            option={hbar(rm.data.rows.map((r) => ({ ...r, label: r.merchant_name || r.merchant_id })), "label", "alert_rate", { fmt: (v) => pct(v, 1), name: "Alert rate", colorFn: () => "bad", extra: (r) => `${r.alerts} alerts / ${r.transactions} transactions` })} />}
        </ChartCard>
        <ChartCard title="Hourly anomaly heatmap" subtitle="Alerts by day of week and hour" query={hm} isEmpty={(d) => !d.rows.length} height={330} footer={hm.data?.note}>
          {hm.data && <EChart height={330} ariaLabel="Anomaly heatmap" option={heatOpt} />}
        </ChartCard>
      </div>

      <Card style={{ padding: 18, marginBottom: 16 }} id="investigation">
        <h3 style={{ marginBottom: 4 }}>High-risk transaction investigation</h3>
        <p style={{ margin: "0 0 12px", color: "var(--muted)", fontSize: 12.5 }}>Sorted by ML score. Expand a row to see why it was flagged and to record the investigation outcome (stored in monitoring.anomaly_investigations). Alerts only; nothing here is confirmed fraud.</p>
        <ServerTable dataset="anomalies" initialSort={{ id: "ml_anomaly_score", desc: true }} refreshKey={refresh} filterOptions={{ severity: ["High", "Medium", "Low"], investigation_status: STATUSES }}
          extraParams={sp.get("anomaly") ? { filters: JSON.stringify([{ id: "anomaly_id", op: "eq", value: Number(sp.get("anomaly")) }]) } : {}}
          renderDetail={(row) => <InvestigationPanel key={row.anomaly_id} row={row} onSaved={() => { setRefresh((x) => x + 1); qc.invalidateQueries({ queryKey: ["/v1/anomalies/summary"] }); }} />} />
      </Card>
      <div className="grid g-2 mb"><div><Scorer /></div>
        <Card style={{ padding: 18 }}><h3 style={{ marginBottom: 6 }}>About the scoring models</h3><p style={{ color: "var(--text-2)", margin: 0 }}>The form on the left calls the saved decline and fraud models (XGBoost trained on <b>synthetic</b> card payments). Probabilities are for demonstration; they were validated only on synthetic labels and must not be used for real customer decisions.</p></Card>
      </div>
    </>
  );
}
