import React from "react";
import { Link } from "react-router-dom";
import { useApi } from "../lib/context.jsx";
import { int, pct, usd } from "../lib/format.js";
import { Badge, Card, ChartCard, DomainBadge, ErrorState, Notice, PageHeader, Skeleton } from "../ui/kit.jsx";
import EChart from "../ui/EChart.jsx";
import { axis, baseGrid } from "../ui/EChart.jsx";
import { hbar, hex, vgrad } from "../ui/charts.js";

const fmt = (unit, v) => (v === null || v === undefined ? "–" : unit === "usd" ? usd(v, false).replace(/\.\d+$/, (m) => m) : pct(v, 1));
const money = (v) => (v === null || v === undefined ? "–" : "$" + Number(v).toFixed(2));
const val = (r, v) => (r.unit === "usd" ? money(v) : pct(v, 1));
const KIND = { matches: "success", off: "Medium", "far off": "High", "no real target": "neutral", "not generated": "neutral", "n/a": "neutral" };
const gapText = (g) => (g === null || g === undefined ? "–" : (g >= 0 ? "+" : "−") + Math.abs(g * 100).toFixed(0) + "%");

// grouped bars: real vs dashboard vs calibrated
function grouped(rows, unit) {
  return (t) => ({
    grid: { ...baseGrid, top: 40 }, legend: { top: 0, left: 0, textStyle: { color: t.text2 } },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v) => (v === null || v === undefined ? "–" : unit === "usd" ? money(v) : pct(v, 1)) },
    xAxis: { type: "category", data: rows.map((r) => r.short), ...axis(t, { splitLine: { show: false } }) },
    yAxis: { type: "value", ...axis(t, { axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => (unit === "usd" ? "$" + v : pct(v, 0)) }, splitLine: { lineStyle: { color: t.grid, type: "dashed" } } }) },
    series: [["Real (SBP)", "real", t.good], ["Dashboard (uncalibrated)", "dashboard", t.warn], ["Calibrated companion", "calibrated", t.blue]].map(([name, key, color]) => ({
      name, type: "bar", barMaxWidth: 30, data: rows.map((r) => r[key]), itemStyle: { color: vgrad(color, "ff", "88"), borderRadius: [6, 6, 0, 0] },
      label: { show: true, position: "top", color: t.text2, fontSize: 11, formatter: (p) => (p.value === null || p.value === undefined ? "" : unit === "usd" ? "$" + Number(p.value).toFixed(0) : pct(p.value, 0)) },
    })),
  });
}

export default function Benchmarks() {
  const q = useApi("/v1/benchmarks");
  if (q.isPending) return <><PageHeader title="Real vs synthetic benchmarks" /><Skeleton h={320} /></>;
  if (q.isError) return <><PageHeader title="Real vs synthetic benchmarks" /><ErrorState error={q.error} onRetry={() => q.refetch()} /></>;
  const d = q.data;
  const by = Object.fromEntries(d.scorecard.map((r) => [r.key, r]));
  const tickets = ["avg_ticket_usd.pos", "avg_ticket_usd.e_commerce", "avg_ticket_usd.wallet"].map((k, i) => ({ ...by[k], short: ["POS", "E-commerce", "Mobile wallet"][i] }));
  const shares = ["cnp_share", "annual_volume_growth"].map((k, i) => ({ ...by[k], short: ["Card-not-present share", "Annual volume growth"][i] }));
  return (
    <>
      <PageHeader title="Real vs synthetic benchmarks" subtitle="Real Pakistani payment aggregates (SBP) next to the dashboard's synthetic card payments and a calibrated companion dataset."
        domains={[{ kind: "real", label: "Real · SBP aggregates" }, { kind: "synthetic", label: "Synthetic · card payments" }]} />
      <Notice>{d.note}</Notice>

      <Card style={{ padding: 18, marginBottom: 16 }} data-testid="scorecard">
        <h3 style={{ marginBottom: 4 }}>Scorecard</h3>
        <p style={{ color: "var(--muted)", margin: "0 0 12px", fontSize: 12 }}>Real period: {d.real.period}. Rupee tickets converted at {d.real.usd_pkr?.toFixed(2)} PKR per USD. Gap = (synthetic − real) / real.</p>
        <div className="table-wrap">
          <table className="dt auto">
            <thead><tr><th>Metric</th><th className="r">Real</th><th className="r">Dashboard data</th><th className="r">Gap</th><th>Status</th><th className="r">Calibrated companion</th><th className="r">Gap</th><th>Status</th></tr></thead>
            <tbody>{d.scorecard.map((r) => (
              <tr key={r.key}>
                <td><b>{r.label}</b><div style={{ color: "var(--muted)", fontSize: 11.5, marginTop: 2 }}>{r.how}</div></td>
                <td className="r"><b style={{ color: "var(--good)" }}>{r.real === null ? "–" : val(r, r.real)}</b></td>
                <td className="r">{val(r, r.dashboard)}</td><td className="r">{gapText(r.gap_dashboard)}</td><td><Badge value={r.status_dashboard} kind={KIND[r.status_dashboard]} /></td>
                <td className="r">{val(r, r.calibrated)}</td><td className="r">{gapText(r.gap_calibrated)}</td><td><Badge value={r.status_calibrated} kind={KIND[r.status_calibrated]} /></td>
              </tr>))}</tbody>
          </table>
        </div>
      </Card>

      <div className="grid g-2 mb">
        <ChartCard title="Average ticket by channel (USD)" subtitle="Real SBP average ticket vs synthetic" query={q} height={300} footer="Real Pakistani card and wallet payments are small (about $13-20); the original synthetic tickets are about $160.">
          <EChart height={300} ariaLabel="Average ticket comparison" option={grouped(tickets, "usd")} />
        </ChartCard>
        <ChartCard title="Channel mix and growth" subtitle="Card-not-present share and annual volume growth" query={q} height={300} footer="Calibrated values match the real targets by construction.">
          <EChart height={300} ariaLabel="Mix and growth comparison" option={grouped(shares, "ratio")} />
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Real Pakistani retail payments by channel" subtitle="Share of volume, Q3 FY26 (SBP, all instruments, not just cards)" query={q} isEmpty={(x) => !x.real_channels.length} height={340}
          footer="Wallet apps carry 58.5% of volume; card-present POS 3.9% and card e-commerce 0.4%. This is why wallets are not calibrated as a card channel: most of that volume is person-to-person transfers.">
          <EChart height={340} ariaLabel="Real channel mix" option={hbar(d.real_channels, "channel", "share_pct", { fmt: (v) => v.toFixed(1) + "%", colorFn: (r) => (/POS|E-Commerce/.test(r.channel) ? "good" : "blue"), name: "Share of volume", extra: (r) => `${r.volume_m.toFixed(0)} million transactions · YoY ${r.yoy_pct > 0 ? "+" : ""}${r.yoy_pct}% · avg ticket Rs ${int(r.avg_ticket_rs)}` })} />
        </ChartCard>
        <Card style={{ padding: 18 }}>
          <h3>What was calibrated</h3>
          <ul style={{ margin: "8px 0 14px", paddingLeft: 18, color: "var(--text-2)", lineHeight: 1.6 }}>
            <li>Card-not-present share of card payments (from SBP POS and e-commerce volumes)</li>
            <li>Annual growth of card payment volume (volume-weighted year-on-year growth of POS and e-commerce)</li>
            <li>Average ticket size per channel, in USD</li>
          </ul>
          <h3>What was not</h3>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18, color: "var(--text-2)", lineHeight: 1.6 }} data-testid="not-calibrated">{d.not_calibrated.map((x) => <li key={x}>{x}</li>)}</ul>
        </Card>
      </div>

      <Card style={{ padding: 18, marginBottom: 16 }}>
        <h3>Assumptions</h3>
        <ul style={{ margin: "8px 0 0", paddingLeft: 18, color: "var(--text-2)", lineHeight: 1.6 }}>{d.assumptions.map((x) => <li key={x}>{x}</li>)}</ul>
      </Card>
      <Card style={{ padding: 18 }}>
        <h3>Use the calibration</h3>
        <p style={{ color: "var(--text-2)", margin: "8px 0" }}>The calibration is optional and off by default, so the validated baseline stays reproducible. To generate calibrated payments: <code>PAYMENT_CALIBRATION=config/pakistan_calibration.json</code> before running the payment generator. Rebuilding the whole dashboard on calibrated data also changes metrics that were not calibrated (the decline rate fell from 4.8% to 3.0% in the companion), so downstream tables and documented numbers need a fresh dbt run. Forecasts of real Pakistani series are on the <Link className="link" to="/global">Global Financial Intelligence</Link> page, tab "Forecasts (real series)".</p>
      </Card>
    </>
  );
}
