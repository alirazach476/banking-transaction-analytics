import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApi, useRange, useRangeApi } from "../lib/context.jsx";
import { compact, date, dowName, int, pct, usd } from "../lib/format.js";
import { ChartCard, ExportButton, MultiSelect, PageHeader, Segmented, Stat, saveText, toCsv, useUrlFilters } from "../ui/kit.jsx";
import EChart, { axis, baseGrid } from "../ui/EChart.jsx";
import { hbar, timeSeries } from "../ui/charts.js";

const KEYS = ["channel", "category", "status", "merchant"];

export default function Payments() {
  const nav = useNavigate();
  const { from, to } = useRange();
  const [f, setF, clear] = useUrlFilters(KEYS, ["channel", "category"]);
  const [heatMode, setHeatMode] = useState("payments");
  const opts = useApi("/v1/payments/filters");
  const extra = { channel: f.channel, category: f.category, status: f.status || undefined, merchant: f.merchant.trim() || undefined };
  const kp = useRangeApi("/v1/payments/kpis", extra);
  const tr = useRangeApi("/v1/payments/trend", extra);
  const ch = useRangeApi("/v1/payments/channels", extra);
  const am = useRangeApi("/v1/payments/amount-distribution", extra);
  const post = useRangeApi("/v1/payments/post-authorization", extra);
  const fl = useRangeApi("/v1/payments/failures", extra);
  const ct = useRangeApi("/v1/payments/categories", extra);
  const hm = useRangeApi("/v1/payments/heatmap", extra);
  const lc = useRangeApi("/v1/payments/lifecycle", extra);
  const k = kp.data;
  const active = KEYS.some((x) => (Array.isArray(f[x]) ? f[x].length : f[x]));
  const approvalRate = k ? k.approved / (k.approved + k.declined) : null;

  const funnel = useMemo(() => k && [
    { name: "Authorization attempts", value: k.payments }, { name: "Approved", value: k.approved }, { name: "Cleared", value: k.cleared }, { name: "Settled", value: k.settled }], [k]);

  const sankey = (t) => ({
    tooltip: { trigger: "item", valueFormatter: (v) => int(v) },
    series: [{ type: "sankey", left: 8, right: 150, top: 10, bottom: 10, nodeGap: 9, nodeWidth: 10, draggable: false, emphasis: { focus: "adjacency" }, nodeAlign: "left", layoutIterations: 64,
      lineStyle: { color: "gradient", opacity: .38, curveness: .5 }, label: { color: t.text, fontSize: 11.5, position: "right", distance: 6 }, labelLayout: { hideOverlap: true },
      data: [...new Set(lc.data.links.flatMap((l) => [l.source, l.target]))].map((n) => ({ name: n, itemStyle: { color: /Declined|Reversed|Chargeback|No response|Not cleared/.test(n) ? t.bad : /Refunded|Cleared, not/.test(n) ? t.warn : t.teal } })),
      links: lc.data.links }],
  });

  const funnelOpt = (t) => ({
    tooltip: { trigger: "item", formatter: (p) => `${p.name}<br/><b>${int(p.value)}</b> (${pct(p.value / funnel[0].value, 2)} of attempts)` },
    legend: { show: false },
    series: [{ type: "funnel", left: "4%", width: "92%", top: 8, bottom: 8, sort: "descending", gap: 4, minSize: "34%", label: { position: "inside", color: "#fff", fontSize: 12, fontWeight: 600, formatter: (p) => `${p.name}\n${compact(p.value)} · ${pct(p.value / funnel[0].value, 1)}` },
      itemStyle: { borderColor: t.surface, borderWidth: 1 }, data: funnel.map((d, i) => ({ ...d, itemStyle: { color: t.colors[[0, 2, 1, 5][i]] } })) }],
  });

  const channelOpt = (t) => ({
    grid: baseGrid, toolbox: { right: 4, top: 0, itemSize: 13, feature: { saveAsImage: { title: "Save as image", pixelRatio: 2, backgroundColor: t.surface } } },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } }, legend: { top: 0, left: 0, textStyle: { color: t.text2 } },
    xAxis: { type: "category", data: ch.data.map((r) => r.channel), ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, interval: 0, width: 80, overflow: "break" } }) },
    yAxis: [{ type: "value", ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => compact(v) } }) }, { type: "value", min: 0.9, max: 1, position: "right", ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, formatter: (v) => pct(v, 0) } }) }],
    series: [{ name: "Payments", type: "bar", data: ch.data.map((r) => r.payments), itemStyle: { color: t.colors[0], borderRadius: [4, 4, 0, 0] }, barMaxWidth: 36, tooltip: { valueFormatter: int } },
      { name: "Approval rate", type: "line", yAxisIndex: 1, data: ch.data.map((r) => r.approval_rate), itemStyle: { color: t.colors[3] }, lineStyle: { width: 2 }, symbolSize: 7, tooltip: { valueFormatter: (v) => pct(v, 2) } }],
  });

  const amountOpt = (t) => ({
    grid: baseGrid, tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    xAxis: { type: "category", data: am.data.rows.map((r) => r.label), name: "USD", nameLocation: "middle", nameGap: 28, nameTextStyle: { color: t.muted }, ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, interval: 0 } }) },
    yAxis: { type: "value", ...axis(t, { axisLabel: { color: t.muted, formatter: (v) => compact(v) } }) },
    series: [{ type: "bar", data: am.data.rows.map((r) => r.payments), itemStyle: { color: t.colors[1], borderRadius: [4, 4, 0, 0] }, barMaxWidth: 40, tooltip: { valueFormatter: int } }],
  });

  const treemapOpt = (t) => ({
    tooltip: { formatter: (p) => `<b>${p.name}</b><br/>Value: ${usd(p.value)}<br/>Payments: ${int(p.data.payments)}<br/>Approval rate: ${pct(p.data.approval_rate, 2)}` },
    series: [{ type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false }, left: 0, right: 0, top: 0, bottom: 0, itemStyle: { borderColor: t.surface, borderWidth: 2, gapWidth: 2, borderRadius: 4 },
      label: { color: "#fff", fontSize: 12, formatter: (p) => `${p.name}\n${usd(p.value)}` },
      data: ct.data.map((r, i) => ({ name: r.category, value: r.value, payments: r.payments, approval_rate: r.approval_rate, itemStyle: { color: t.colors[i % t.colors.length] } })) }],
  });

  const heatOpt = (t) => {
    const rows = hm.data.rows;
    const val = (r) => (heatMode === "payments" ? r.payments : r.decline_rate);
    const max = Math.max(...rows.map((r) => val(r) || 0), 1e-9);
    return {
      grid: { left: 8, right: 12, top: 10, bottom: 70, containLabel: true },
      tooltip: { formatter: (p) => `${dowName(p.value[1] + 1)} ${String(p.value[0]).padStart(2, "0")}:00<br/>${heatMode === "payments" ? int(p.value[2]) + " payments" : pct(p.value[2], 2) + " decline rate"}` },
      xAxis: { type: "category", data: Array.from({ length: 24 }, (_, h) => String(h).padStart(2, "0")), splitArea: { show: false }, ...axis(t, { splitLine: { show: false } }) },
      yAxis: { type: "category", data: [1, 2, 3, 4, 5, 6, 7].map(dowName), inverse: true, ...axis(t, { splitLine: { show: false } }) },
      visualMap: { min: 0, max, calculable: true, orient: "horizontal", left: "center", bottom: 4, itemWidth: 14, itemHeight: 160, textStyle: { color: t.muted }, formatter: (v) => (heatMode === "payments" ? compact(v) : pct(v, 1)), inRange: { color: [t.surface, t.colors[0], t.colors[1]] } },
      series: [{ type: "heatmap", data: rows.map((r) => [r.hour, r.dow - 1, val(r) || 0]), itemStyle: { borderColor: t.surface, borderWidth: 1, borderRadius: 3 } }],
    };
  };

  const post_rows = (post.data?.rows || []).map((r) => ({ ...r, reversal_rate: r.approved ? r.reversals / r.approved : null, refund_rate: r.settled ? r.refunds / r.settled : null, chargeback_rate: r.settled ? r.chargebacks / r.settled : null }));
  const reasonTrend = useMemo(() => {
    if (!fl.data) return { periods: [], reasons: [] };
    const periods = [...new Set(fl.data.trend.map((r) => r.period))].sort();
    const reasons = [...new Set(fl.data.trend.map((r) => r.reason))];
    return { periods, reasons, get: (p, r) => (fl.data.trend.find((x) => x.period === p && x.reason === r) || {}).declined || 0 };
  }, [fl.data]);
  const exportCategories = () => saveText(toCsv(ct.data, [{ key: "category", label: "Category" }, { key: "payments", label: "Payments" }, { key: "value", label: "Value USD" }, { key: "declined", label: "Declined" }, { key: "approval_rate", label: "Approval rate" }]), `payments-by-category-${from}_${to}.csv`);

  return (
    <>
      <PageHeader title="Payment intelligence" subtitle="Authorization, clearing, settlement and post-settlement outcomes for card payments. Lifecycle events in this dataset are generated, so every figure here is synthetic."
        domains={[{ kind: "synthetic", label: "Synthetic · card payments & lifecycle events" }]} actions={<ExportButton onClick={exportCategories} disabled={!ct.data}>Export categories (CSV)</ExportButton>} />
      <div className="filters" data-testid="payment-filters">
        <MultiSelect label="Channel" options={opts.data?.channels || []} value={f.channel} onChange={(v) => setF("channel", v)} testId="filter-channel" />
        <MultiSelect label="Merchant category" options={opts.data?.categories || []} value={f.category} onChange={(v) => setF("category", v)} testId="filter-category" />
        <label>Status
          <select className="field" value={f.status} onChange={(e) => setF("status", e.target.value)} data-testid="filter-status"><option value="">All</option><option value="approved">Approved</option><option value="declined">Declined</option></select>
        </label>
        <label>Merchant ID<input className="field" placeholder="MERCH-00000123" value={f.merchant} onChange={(e) => setF("merchant", e.target.value)} data-testid="filter-merchant" /></label>
        {active && <button className="btn sm" onClick={clear} style={{ alignSelf: "end" }}>Clear filters</button>}
        <span style={{ color: "var(--muted)", fontSize: 12, alignSelf: "end" }}>Transaction type and branch do not apply to card payments; use the <a className="link" onClick={() => nav("/explorer")}>Transaction Explorer</a> for core banking.</span>
      </div>

      <div className="grid g-kpi6">
        <Stat loading={kp.isPending} label="Payments" value={int(k?.payments)} note={`${date(from)} to ${date(to)}`} />
        <Stat loading={kp.isPending} label="Value (USD)" value={usd(k?.value)} />
        <Stat loading={kp.isPending} label="Approval rate" value={pct(approvalRate, 2)} />
        <Stat loading={kp.isPending} label="Declined" value={int(k?.declined)} note={k ? pct(k.declined / (k.approved + k.declined), 2) + " of authorizations" : ""} />
        <Stat loading={kp.isPending} label="Median response" value={k ? Math.round(k.median_response_ms) + " ms" : "–"} />
        <Stat loading={kp.isPending} label="Chargebacks" value={int(k?.charged_back)} note={k && k.settled ? pct(k.charged_back / k.settled, 2) + " of settled" : ""} />
      </div>

      <div className="grid g-21 mb">
        <ChartCard title="Payment lifecycle" subtitle="Where authorization attempts end up (click-through flow, synthetic events)" query={lc} isEmpty={(d) => !d.links.length} height={520} footer={lc.data?.note}>
          {lc.data && <EChart height={330} ariaLabel="Payment lifecycle Sankey" option={sankey} />}
          {lc.data && (
            <div className="table-wrap" style={{ marginTop: 8 }} data-testid="lifecycle-outcomes">
              <table className="dt" style={{ tableLayout: "auto" }}>
                <thead><tr><th>Outcome</th><th className="r">Payments</th><th className="r">Share of attempts</th></tr></thead>
                <tbody>{[["Declined", lc.data.totals.declined], ["No response", lc.data.totals.no_response], ["Reversed before clearing", lc.data.totals.reversed_before_clearing], ["Not cleared", lc.data.totals.not_cleared],
                  ["Cleared, not settled", lc.data.totals.cleared_not_settled], ["Settled and retained", lc.data.totals.retained], ["Settled, then refunded", lc.data.totals.refunded], ["Settled, then charged back", lc.data.totals.chargeback]].map(([n, v]) => (
                  <tr key={n}><td>{n}</td><td className="r">{int(v)}</td><td className="r">{pct(v / lc.data.totals.attempts, 2)}</td></tr>))}</tbody>
              </table>
            </div>
          )}
        </ChartCard>
        <ChartCard title="Authorization funnel" subtitle="Attempts to settlement, with conversion from attempts" query={kp} isEmpty={(d) => !d.payments} height={520}>
          {funnel && <EChart height={470} ariaLabel="Authorization funnel" option={funnelOpt} />}
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Approval vs decline trend" subtitle={`Per ${tr.data?.grain || "period"}`} query={tr} isEmpty={(d) => !d.rows.length} height={280}>
          {tr.data && <EChart height={280} ariaLabel="Approval vs decline" option={timeSeries(tr.data.rows.map((r) => ({ ...r })), "period", [{ key: "approved", name: "Approved", type: "bar", stack: "a", color: "teal", fmt: int }, { key: "declined", name: "Declined", type: "bar", stack: "a", color: "bad", fmt: int }, { key: "approval_rate", name: "Approval rate", axis: 1, color: "blue", fmt: (v) => pct(v, 2) }], { y2Fmt: (v) => pct(v, 0) })} />}
        </ChartCard>
        <ChartCard title="Volume by payment channel" subtitle="Payments (bars) and approval rate (line); click a bar to filter" query={ch} isEmpty={(d) => !d.length} height={280}>
          {ch.data && <EChart height={280} ariaLabel="Volume by channel" option={channelOpt} onClick={(e) => e.componentType === "series" && e.seriesType === "bar" && setF("channel", [e.name])} />}
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Transaction amount distribution" subtitle="Payments by USD amount band (payments with a USD rate)" query={am} isEmpty={(d) => !d.rows.some((r) => r.payments)} height={280}>
          {am.data && <EChart height={280} ariaLabel="Amount distribution" option={amountOpt} />}
        </ChartCard>
        <ChartCard title="Merchant category treemap" subtitle="Area = value (USD); hover for approval rate; click to filter" query={ct} isEmpty={(d) => !d.length} height={280}>
          {ct.data && <EChart height={280} ariaLabel="Merchant category treemap" option={treemapOpt} onClick={(e) => e.name && setF("category", [e.name])} />}
        </ChartCard>
      </div>

      <div className="grid g-3 mb">
        <ChartCard title="Reversal and refund trends" subtitle="Monthly rates" query={post} isEmpty={(d) => !d.rows.length || d.rows.every((r) => !r.settled)} height={250} footer="Reversal rate = reversals / approved; refund rate = refunds / settled.">
          {post.data && <EChart height={250} ariaLabel="Reversal and refund trends" option={timeSeries(post_rows, "period", [{ key: "reversal_rate", name: "Reversal rate", color: "warn", fmt: (v) => pct(v, 2) }, { key: "refund_rate", name: "Refund rate", color: "violet", fmt: (v) => pct(v, 2) }], { yFmt: (v) => pct(v, 1) })} />}
        </ChartCard>
        <ChartCard title="Chargeback trend" subtitle="Monthly chargebacks and rate" query={post} isEmpty={(d) => !d.rows.length || d.rows.every((r) => !r.settled)} height={250} footer={post.data?.note}>
          {post.data && <EChart height={250} ariaLabel="Chargeback trend" option={timeSeries(post_rows, "period", [{ key: "chargebacks", name: "Chargebacks", type: "bar", color: "bad", fmt: int }, { key: "chargeback_rate", name: "Chargeback rate", axis: 1, color: "blue", fmt: (v) => pct(v, 2) }], { y2Fmt: (v) => pct(v, 1) })} />}
        </ChartCard>
        <ChartCard title="Payment failure reasons" subtitle="Declined payments by reason" query={fl} isEmpty={(d) => !d.reasons.length} height={250}>
          {fl.data && <EChart height={250} ariaLabel="Failure reasons" option={hbar(fl.data.reasons, "reason", "declined", { fmt: int, colorFn: () => "bad", name: "Declined", extra: (r) => `Value: ${usd(r.value)}` })}
            onClick={(e) => nav(`/explorer?tab=payment-failures&filters=${encodeURIComponent(JSON.stringify([{ id: "decline_reason", op: "eq", value: e.name }]))}`)} />}
        </ChartCard>
      </div>

      <div className="grid g-2 mb">
        <ChartCard title="Failure reasons over time" subtitle="Top 5 reasons, monthly declines" query={fl} isEmpty={(d) => !d.trend.length} height={280}>
          {fl.data && <EChart height={280} ariaLabel="Failure reasons over time" option={timeSeries(reasonTrend.periods.map((p) => ({ period: p, ...Object.fromEntries(reasonTrend.reasons.map((r) => [r, reasonTrend.get(p, r)])) })), "period",
            reasonTrend.reasons.map((r) => ({ key: r, name: r.replace(/_/g, " "), type: "bar", stack: "r", fmt: int })), { yFmt: compact })} />}
        </ChartCard>
        <ChartCard title="Hourly transaction heatmap" subtitle="Day of week by hour of authorization" query={hm} isEmpty={(d) => !d.rows.length} height={280}
          actions={<Segmented value={heatMode} onChange={setHeatMode} label="Heatmap metric" options={[{ value: "payments", label: "Volume" }, { value: "decline", label: "Decline rate" }]} />} footer={hm.data?.note}>
          {hm.data && <EChart height={280} ariaLabel="Hourly heatmap" option={heatOpt} />}
        </ChartCard>
      </div>
    </>
  );
}
