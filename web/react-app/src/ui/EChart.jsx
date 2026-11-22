import React, { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, FunnelChart, GaugeChart, HeatmapChart, LineChart, PieChart, SankeyChart, ScatterChart, TreemapChart } from "echarts/charts";
import { AriaComponent, DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, ToolboxComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useTheme } from "../lib/context.jsx";
import { axis, baseGrid } from "../lib/chartkit.js";

echarts.use([BarChart, FunnelChart, GaugeChart, HeatmapChart, LineChart, PieChart, SankeyChart, ScatterChart, TreemapChart, AriaComponent, DataZoomComponent, GridComponent, LegendComponent,
  MarkLineComponent, TitleComponent, ToolboxComponent, TooltipComponent, VisualMapComponent, CanvasRenderer]);

// Design tokens read from CSS so charts follow the active theme
export function tokens() {
  const s = getComputedStyle(document.documentElement);
  const g = (n) => s.getPropertyValue(n).trim();
  return {
    text: g("--text"), text2: g("--text-2"), muted: g("--muted"), grid: g("--chart-grid"), surface: g("--surface"), border: g("--border"),
    good: g("--good"), bad: g("--bad"), warn: g("--warn"), info: g("--info"), blue: g("--blue"), violet: g("--violet"), teal: g("--teal"),
    colors: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => g(`--c${i}`)),
  };
}
export { axis, baseGrid };

export default function EChart({ option, height = 280, onClick, ariaLabel }) {
  const el = useRef(null);
  const chart = useRef(null);
  const { theme } = useTheme();
  useEffect(() => {
    chart.current = echarts.init(el.current, null, { renderer: "canvas" });
    const ro = new ResizeObserver(() => chart.current && chart.current.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); chart.current && chart.current.dispose(); chart.current = null; };
  }, []);
  useEffect(() => {
    if (!chart.current) return;
    const t = tokens();
    const o = typeof option === "function" ? option(t) : option;
    chart.current.setOption({
      backgroundColor: "transparent", color: t.colors, textStyle: { fontFamily: "Inter Variable, Inter, system-ui, sans-serif" },
      animationDuration: 350, aria: { enabled: true },
      tooltip: { backgroundColor: t.surface, borderColor: t.border, textStyle: { color: t.text, fontSize: 12 }, extraCssText: "box-shadow:0 8px 24px rgba(0,0,0,.25);border-radius:10px;" },
      legend: { textStyle: { color: t.text2, fontSize: 12 }, icon: "roundRect", itemWidth: 10, itemHeight: 10, type: "scroll" },
      ...o,
    }, true);
  }, [option, theme]);
  useEffect(() => {
    if (!chart.current || !onClick) return undefined;
    chart.current.off("click");
    chart.current.on("click", onClick);
    return () => chart.current && chart.current.off("click");
  }, [onClick, option]);
  return <div ref={el} className="echart" style={{ height }} role="img" aria-label={ariaLabel} />;
}
