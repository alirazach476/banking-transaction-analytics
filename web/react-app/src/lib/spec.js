import { compact } from "./format.js";
import { axis, baseGrid } from "./chartkit.js";

const full = (v, unit) => (typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) + (unit ? " " + unit : "") : v ?? "");

export function specProblems(c) {
  const p = [];
  if (!c.id || !c.title) p.push("missing id/title");
  if (!Array.isArray(c.data) || !c.data.length) p.push("no data");
  if (!["line", "step", "bar", "stacked", "barh", "table"].includes(c.type)) p.push("bad type " + c.type);
  return p;
}

// Converts one analysis.json chart spec into an ECharts option
export function toOption(c, t) {
  const xk = c.x || "x";
  const names = c.data.map((r) => r[xk]);
  const tip = { valueFormatter: (v) => full(v, c.unit) };
  const yAxis = { type: c.log ? "log" : "value", ...axis(t, { axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => compact(v) } }) };
  if (c.type === "barh") {
    const data = c.data.slice().reverse();
    return {
      grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...tip },
      xAxis: { type: "value", ...axis(t, { axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => compact(v) } }) },
      yAxis: { type: "category", data: data.map((r) => r[xk]), ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.text2, fontSize: 11, width: 150, overflow: "truncate" } }) },
      series: [{ name: c.series[0].name, type: "bar", barMaxWidth: 16, data: data.map((r) => ({ value: r[c.series[0].key], itemStyle: { color: r.highlight ? t.colors[3] : t.colors[0], borderRadius: [0, 4, 4, 0] } })) }],
    };
  }
  const isBar = c.type === "bar" || c.type === "stacked";
  return {
    grid: baseGrid, color: t.colors, legend: c.series.length > 1 ? { top: 0, left: 0, type: "scroll", textStyle: { color: t.text2 } } : undefined,
    tooltip: { trigger: "axis", axisPointer: { type: isBar ? "shadow" : "line" }, ...tip },
    xAxis: { type: "category", data: names, boundaryGap: isBar, ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, hideOverlap: true } }) },
    yAxis,
    series: c.series.map((s, i) => ({
      name: s.name, type: isBar ? "bar" : "line", step: c.type === "step" ? "end" : undefined, stack: c.type === "stacked" ? "a" : undefined,
      connectNulls: true, showSymbol: c.data.length <= 14, symbolSize: 6, smooth: false, lineStyle: { width: s.faint ? 1.2 : 2.2, type: s.dash ? "dashed" : "solid", opacity: s.faint ? 0.55 : 1, color: t.colors[s.colorIdx ?? (s.dash ? 1 : i) % 8] }, itemStyle: { color: t.colors[s.colorIdx ?? (s.dash ? 1 : i) % 8] }, barMaxWidth: 30,
      data: c.data.map((r) => (isBar && !c.type.startsWith("stack") && r[s.key] < 0 ? { value: r[s.key], itemStyle: { color: t.colors[3] } } : r[s.key])),
    })),
  };
}

