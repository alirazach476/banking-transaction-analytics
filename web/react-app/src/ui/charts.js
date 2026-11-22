// Option builders for ECharts. Each returns a function of the theme tokens so charts restyle with the theme.
import { axis, baseGrid } from "./EChart.jsx";
import { compact } from "../lib/format.js";

const withToolbox = (t) => ({ right: 4, top: 0, itemSize: 13, iconStyle: { borderColor: t.muted }, feature: { saveAsImage: { title: "Save as image", pixelRatio: 2, backgroundColor: t.surface } } });

// series: [{ key, name, type: 'line'|'bar', area?, axis?: 0|1, fmt?: fn, stack?: string, color?: string, smooth? }]
export function timeSeries(rows, xKey, series, { yFmt = compact, y2Fmt = compact, y2Name, yName, zoom = false, legend = series.length > 1 } = {}) {
  return (t) => ({
    grid: { ...baseGrid, top: legend ? 44 : 30 },
    toolbox: withToolbox(t),
    tooltip: { trigger: "axis", axisPointer: { type: "cross", lineStyle: { color: t.grid }, crossStyle: { color: t.grid } } },
    legend: legend ? { top: 0, left: 0, textStyle: { color: t.text2 } } : { show: false },
    xAxis: { type: "category", data: rows.map((r) => r[xKey]), boundaryGap: series.some((s) => s.type === "bar"), ...axis(t, { splitLine: { show: false } }) },
    yAxis: [{ type: "value", name: yName, nameTextStyle: { color: t.muted, fontSize: 11 }, ...axis(t, { axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => yFmt(v) } }) },
      ...(series.some((s) => s.axis === 1) ? [{ type: "value", name: y2Name, nameTextStyle: { color: t.muted, fontSize: 11 }, position: "right", ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => y2Fmt(v) } }) }] : [])],
    dataZoom: zoom ? [{ type: "inside" }, { type: "slider", height: 18, bottom: 0, borderColor: "transparent", textStyle: { color: t.muted } }] : undefined,
    series: series.map((s, i) => {
      const color = s.color ? t[s.color] || s.color : t.colors[i % t.colors.length];
      return {
        name: s.name, type: s.type || "line", yAxisIndex: s.axis || 0, stack: s.stack, smooth: s.smooth ?? false, showSymbol: rows.length < 40, symbolSize: 5, barMaxWidth: 26,
        data: rows.map((r) => r[s.key]), itemStyle: { color, borderRadius: s.type === "bar" ? [3, 3, 0, 0] : 0 }, lineStyle: { width: 2, color },
        areaStyle: s.area ? { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + "55" }, { offset: 1, color: color + "00" }] } } : undefined,
        tooltip: { valueFormatter: (v) => (s.fmt || yFmt)(v) },
      };
    }),
  });
}

export function donut(rows, nameKey, valueKey, { fmt = compact, onlyTop = 8, centerLabel } = {}) {
  return (t) => ({
    tooltip: { trigger: "item", valueFormatter: (v) => fmt(v) },
    legend: { orient: "vertical", right: 0, top: "middle", textStyle: { color: t.text2 }, formatter: (n) => (n.length > 22 ? n.slice(0, 21) + "…" : n) },
    series: [{ type: "pie", radius: ["52%", "78%"], center: ["34%", "50%"], avoidLabelOverlap: true, itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 4 }, label: { show: false },
      emphasis: { label: { show: !!centerLabel, fontSize: 14, fontWeight: 600, color: t.text } },
      data: rows.slice(0, onlyTop).map((r) => ({ name: r[nameKey], value: r[valueKey] })) }],
  });
}

// Horizontal bars (names top-down in the given order). colorFn(row) -> token key or css color.
export function hbar(rows, nameKey, valueKey, { fmt = compact, colorFn, name = "", extra } = {}) {
  const r = [...rows].reverse();
  return (t) => ({
    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
    toolbox: withToolbox(t),
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, formatter: (p) => { const row = r[p[0].dataIndex]; return `<b>${row[nameKey]}</b><br/>${name || valueKey}: ${fmt(row[valueKey])}${extra ? "<br/>" + extra(row) : ""}`; } },
    xAxis: { type: "value", ...axis(t, { axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => fmt(v) } }) },
    yAxis: { type: "category", data: r.map((x) => x[nameKey]), ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.text2, fontSize: 11, width: 130, overflow: "truncate" } }) },
    series: [{ type: "bar", data: r.map((x) => ({ value: x[valueKey], itemStyle: { color: colorFn ? (t[colorFn(x)] || colorFn(x)) : t.colors[0], borderRadius: [0, 4, 4, 0] } })), barMaxWidth: 18 }],
  });
}
