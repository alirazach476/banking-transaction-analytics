// Option builders for ECharts. Each returns a function of the theme tokens so charts restyle with the theme.
import { axis, baseGrid } from "./EChart.jsx";
import { compact } from "../lib/format.js";

const withToolbox = (t) => ({ right: 4, top: 0, itemSize: 13, iconStyle: { borderColor: t.muted }, feature: { saveAsImage: { title: "Save as image", pixelRatio: 2, backgroundColor: t.surface } } });
const hex = (c, a) => (/^#[0-9a-f]{6}$/i.test(c) ? c + a : c); // append alpha to #rrggbb tokens
const vgrad = (c, top = "ff", bottom = "66") => ({ type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: hex(c, top) }, { offset: 1, color: hex(c, bottom) }] });
const hgrad = (c, from = "55", to = "ff") => ({ type: "linear", x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: hex(c, from) }, { offset: 1, color: hex(c, to) }] });
export { hex, vgrad, hgrad };

// series: [{ key, name, type: 'line'|'bar', area?, axis?: 0|1, fmt?: fn, stack?: string, color?: string, smooth? }]
export function timeSeries(rows, xKey, series, { yFmt = compact, y2Fmt = compact, y2Name, yName, zoom = false, legend = series.length > 1 } = {}) {
  return (t) => ({
    grid: { ...baseGrid, top: legend ? 44 : 30 },
    toolbox: withToolbox(t),
    tooltip: { trigger: "axis", axisPointer: { type: "cross", lineStyle: { color: t.grid }, crossStyle: { color: t.grid } } },
    legend: legend ? { top: 0, left: 0, textStyle: { color: t.text2 } } : { show: false },
    xAxis: { type: "category", data: rows.map((r) => r[xKey]), boundaryGap: series.some((s) => s.type === "bar"), ...axis(t, { splitLine: { show: false } }) },
    yAxis: [{ type: "value", name: yName, nameTextStyle: { color: t.muted, fontSize: 11 }, ...axis(t, { axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => yFmt(v) }, splitLine: { lineStyle: { color: t.grid, type: "dashed" } } }) },
      ...(series.some((s) => s.axis === 1) ? [{ type: "value", name: y2Name, nameTextStyle: { color: t.muted, fontSize: 11 }, position: "right", ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => y2Fmt(v) } }) }] : [])],
    dataZoom: zoom ? [{ type: "inside" }, { type: "slider", height: 18, bottom: 0, borderColor: "transparent", textStyle: { color: t.muted } }] : undefined,
    series: series.map((s, i) => {
      const color = s.color ? t[s.color] || s.color : t.colors[i % t.colors.length];
      const isBar = s.type === "bar";
      return {
        name: s.name, type: s.type || "line", yAxisIndex: s.axis || 0, stack: s.stack, smooth: s.smooth ?? !isBar, showSymbol: rows.length < 30, symbol: "circle", symbolSize: 6, barMaxWidth: 26,
        data: rows.map((r) => r[s.key]),
        itemStyle: { color: isBar ? vgrad(color, "ff", "88") : color, borderRadius: isBar ? (s.stack ? 0 : [6, 6, 0, 0]) : 0, borderColor: t.surface, borderWidth: isBar ? 0 : 2 },
        lineStyle: { width: 2.6, color, shadowColor: hex(color, "66"), shadowBlur: s.area ? 10 : 0, shadowOffsetY: 4 },
        areaStyle: s.area ? { color: vgrad(color, "66", "00") } : undefined,
        emphasis: { focus: "series" },
        tooltip: { valueFormatter: (v) => (s.fmt || yFmt)(v) },
      };
    }),
  });
}

export function donut(rows, nameKey, valueKey, { fmt = compact, onlyTop = 8, total = true, totalLabel = "total" } = {}) {
  return (t) => {
    const data = rows.slice(0, onlyTop).map((r) => ({ name: r[nameKey], value: r[valueKey] }));
    const sum = data.reduce((a, d) => a + (d.value || 0), 0) || 1;
    return {
      tooltip: { trigger: "item", valueFormatter: (v) => fmt(v) },
      title: total ? { text: fmt(sum), subtext: totalLabel, left: "center", top: "33%", textAlign: "center", textStyle: { color: t.text, fontSize: 17, fontWeight: 800 }, subtextStyle: { color: t.muted, fontSize: 11 }, itemGap: 2 } : undefined,
      legend: { type: "scroll", orient: "horizontal", bottom: 0, left: "center", textStyle: { color: t.text2, fontSize: 11.5 }, itemGap: 12, formatter: (n) => { const d = data.find((x) => x.name === n); const label = n.length > 16 ? n.slice(0, 15) + "…" : n; return d ? `${label} ${((d.value / sum) * 100).toFixed(0)}%` : label; } },
      series: [{ type: "pie", radius: ["56%", "76%"], center: ["50%", "42%"], padAngle: 2, avoidLabelOverlap: true, itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 8 }, label: { show: false },
        emphasis: { scaleSize: 6, itemStyle: { shadowBlur: 18, shadowColor: "rgba(0,0,0,.35)" } },
        data }],
    };
  };
}

// Horizontal bars (names top-down in the given order). colorFn(row) -> token key or css color.
export function hbar(rows, nameKey, valueKey, { fmt = compact, colorFn, name = "", extra, labels = true } = {}) {
  const r = [...rows].reverse();
  return (t) => ({
    grid: { left: 8, right: labels ? 64 : 24, top: 8, bottom: 8, containLabel: true },
    toolbox: withToolbox(t),
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, formatter: (p) => { const row = r[p[0].dataIndex]; return `<b>${row[nameKey]}</b><br/>${name || valueKey}: ${fmt(row[valueKey])}${extra ? "<br/>" + extra(row) : ""}`; } },
    xAxis: { type: "value", ...axis(t, { axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => fmt(v) }, splitLine: { lineStyle: { color: t.grid, type: "dashed" } } }) },
    yAxis: { type: "category", data: r.map((x) => x[nameKey]), ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.text2, fontSize: 11, width: 130, overflow: "truncate" } }) },
    series: [{ type: "bar", showBackground: true, backgroundStyle: { color: hex(t.muted, "14"), borderRadius: [0, 6, 6, 0] },
      label: labels ? { show: true, position: "right", color: t.text2, fontSize: 11, fontWeight: 600, formatter: (p) => fmt(p.value) } : undefined,
      data: r.map((x) => { const c = colorFn ? (t[colorFn(x)] || colorFn(x)) : t.colors[0]; return { value: x[valueKey], itemStyle: { color: hgrad(c), borderRadius: [0, 6, 6, 0] } }; }), barMaxWidth: 16 }],
  });
}

// Semicircle gauge for a 0..1 ratio
export function gauge(value, { name = "", fmt = (v) => (v * 100).toFixed(1) + "%", min = 0, max = 1, valueColor = "good" } = {}) {
  return (t) => ({
    series: [{ type: "gauge", startAngle: 205, endAngle: -25, min, max, radius: "96%", center: ["50%", "58%"], splitNumber: 5,
      progress: { show: true, width: 16, roundCap: true, itemStyle: { color: { type: "linear", x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: t.teal }, { offset: 1, color: t.blue }] } } },
      axisLine: { roundCap: true, lineStyle: { width: 16, color: [[1, hex(t.muted, "30")]] } },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false }, pointer: { show: false }, anchor: { show: false },
      title: { offsetCenter: [0, "40%"], color: t.text, fontSize: 14, fontWeight: 600 },
      detail: { valueAnimation: true, offsetCenter: [0, "-4%"], fontSize: 32, fontWeight: 800, color: t[valueColor] || valueColor, formatter: (v) => fmt(v) },
      data: [{ value, name }] }],
  });
}

// Nightingale rose: one coloured petal per category, radius = value
export function rose(rows, nameKey, valueKey, { fmt = compact, top = 8, extra } = {}) {
  return (t) => {
    const data = rows.slice(0, top);
    return {
      tooltip: { trigger: "item", formatter: (p) => `<b>${p.name}</b><br/>${fmt(p.value)} (${p.percent}%)${extra ? "<br/>" + extra(data[p.dataIndex]) : ""}` },
      legend: { show: false },
      series: [{ type: "pie", roseType: "radius", radius: ["16%", "74%"], center: ["50%", "52%"], padAngle: 1.5, itemStyle: { borderRadius: 8, borderColor: t.surface, borderWidth: 2 },
        label: { color: t.text2, fontSize: 11, formatter: (p) => `${p.name.length > 14 ? p.name.slice(0, 13) + "…" : p.name}\n${fmt(p.value)}` }, labelLine: { length: 8, length2: 8, lineStyle: { color: t.grid } },
        emphasis: { scaleSize: 6, itemStyle: { shadowBlur: 20, shadowColor: "rgba(0,0,0,.35)" } },
        data: data.map((r, i) => ({ name: r[nameKey], value: r[valueKey], itemStyle: { color: vgrad(t.colors[i % t.colors.length], "ff", "aa") } })) }],
    };
  };
}

// Bubble scatter: x, y numeric, size and colour by fields
export function bubble(rows, { x, y, size, nameKey, xFmt = compact, yFmt = compact, xName, yName, colorFn, tip }) {
  return (t) => {
    const sv = rows.map((r) => r[size] || 0);
    const hi = Math.max(...sv, 1), lo = Math.min(...sv, 0);
    return {
      grid: { left: 8, right: 20, top: 24, bottom: 28, containLabel: true },
      toolbox: withToolbox(t),
      tooltip: { trigger: "item", formatter: (p) => tip(rows[p.dataIndex]) },
      xAxis: { type: "value", name: xName, nameLocation: "middle", nameGap: 26, nameTextStyle: { color: t.muted }, scale: true, ...axis(t, { axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => xFmt(v) }, splitLine: { lineStyle: { color: t.grid, type: "dashed" } } }) },
      yAxis: { type: "value", name: yName, nameTextStyle: { color: t.muted, fontSize: 11 }, scale: true, ...axis(t, { axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => yFmt(v) }, splitLine: { lineStyle: { color: t.grid, type: "dashed" } } }) },
      series: [{ type: "scatter", data: rows.map((r) => ({ value: [r[x], r[y]], symbolSize: 14 + ((r[size] - lo) / (hi - lo || 1)) * 30, itemStyle: { color: hex(t[colorFn(r)] || colorFn(r), "cc"), borderColor: t[colorFn(r)] || colorFn(r), borderWidth: 1.5, shadowBlur: 14, shadowColor: hex(t[colorFn(r)] || colorFn(r), "66") } })),
        emphasis: { scale: 1.25 } }],
    };
  };
}

// Hour (x) by weekday (y) heat map; rows [{ dow 1..7, hour 0..23, <key> }]
export function hourHeat(rows, key, { fmt = compact, name = "" } = {}) {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return (t) => {
    const vals = rows.map((r) => r[key] || 0);
    return {
      grid: { left: 8, right: 16, top: 8, bottom: 46, containLabel: true },
      tooltip: { formatter: (p) => `${days[p.value[1]]} ${String(p.value[0]).padStart(2, "0")}:00<br/>${name}: <b>${fmt(p.value[2])}</b>` },
      xAxis: { type: "category", data: Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0")), splitArea: { show: false }, ...axis(t, { splitLine: { show: false } }) },
      yAxis: { type: "category", data: days, inverse: true, ...axis(t, { splitLine: { show: false }, axisLabel: { color: t.text2, fontSize: 11 } }) },
      visualMap: { min: Math.min(...vals), max: Math.max(...vals, 1), calculable: false, orient: "horizontal", left: "center", bottom: 0, itemWidth: 12, itemHeight: 120, textStyle: { color: t.muted, fontSize: 11 }, inRange: { color: [hex(t.blue, "22"), t.blue, t.violet, t.colors[4]] }, formatter: (v) => fmt(v) },
      series: [{ type: "heatmap", data: rows.map((r) => [r.hour, r.dow - 1, r[key] || 0]), itemStyle: { borderColor: t.surface, borderWidth: 2, borderRadius: 4 }, emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,.4)" } } }],
    };
  };
}
