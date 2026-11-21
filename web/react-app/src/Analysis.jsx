import React, { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// Okabe-Ito colour-blind-safe palette; readable on light and dark backgrounds
export const COLORS = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#B8A200"];
const BASE = "#7f9bb5";
const HILITE = "#D55E00";

export function compact(v) {
  if (typeof v !== "number" || !isFinite(v)) return v ?? "";
  const a = Math.abs(v);
  if (a >= 1e9) return (v / 1e9).toFixed(1).replace(/\.0$/, "") + "bn";
  if (a >= 1e6) return (v / 1e6).toFixed(1).replace(/\.0$/, "") + "m";
  if (a >= 1e3) return (v / 1e3).toFixed(1).replace(/\.0$/, "") + "k";
  return String(Math.round(v * 100) / 100);
}
const full = (v, unit) => (typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) + (unit || "") : v ?? "");

// Validates one chart spec; used by the unit test and to avoid rendering broken data
export function specProblems(c) {
  const p = [];
  if (!c.id || !c.title) p.push("missing id/title");
  if (!Array.isArray(c.data) || c.data.length === 0) p.push("no data");
  if (!["line", "step", "bar", "stacked", "barh", "table"].includes(c.type)) p.push("bad type " + c.type);
  if (Array.isArray(c.data) && c.data.length && c.type !== "table") {
    const xk = c.x || "x";
    if (!(xk in c.data[0])) p.push("x key missing: " + xk);
    for (const s of c.series || []) if (!c.data.some((r) => typeof r[s.key] === "number")) p.push("series has no numbers: " + s.key);
  }
  return p;
}

function Table({ c }) {
  return (
    <div className="wrap">
      <table>
        <thead><tr>{c.series.map((s) => <th key={s.key}>{s.name}</th>)}</tr></thead>
        <tbody>
          {c.data.map((r, i) => (
            <tr key={i}>
              {c.series.map((s) => (
                <td key={s.key} className={typeof r[s.key] === "number" ? "num" : ""}>{typeof r[s.key] === "number" ? full(r[s.key]) : r[s.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Plot({ c }) {
  const xk = c.x || "x";
  const tip = (v, n) => [full(v, c.unit), n];
  const grid = <CartesianGrid strokeOpacity={0.2} />;
  const tick = { fontSize: 11 };
  if (c.type === "barh") {
    const w = Math.min(190, Math.max(70, Math.max(...c.data.map((r) => String(r[xk]).length)) * 6.3));
    const h = Math.max(200, c.data.length * 24 + 40);
    return (
      <ResponsiveContainer width="100%" height={h}>
        <BarChart data={c.data} layout="vertical" margin={{ left: 4, right: 16 }}>
          {grid}
          <XAxis type="number" tick={tick} tickFormatter={compact} />
          <YAxis type="category" dataKey={xk} width={w} tick={tick} interval={0} />
          <Tooltip formatter={tip} />
          <Bar dataKey={c.series[0].key} name={c.series[0].name} isAnimationActive={false}>
            {c.data.map((r, i) => <Cell key={i} fill={r.highlight ? HILITE : BASE} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }
  if (c.type === "bar" || c.type === "stacked") {
    const stacked = c.type === "stacked";
    return (
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={c.data} margin={{ left: 0, right: 8 }}>
          {grid}
          <XAxis dataKey={xk} tick={tick} minTickGap={14} />
          <YAxis tick={tick} tickFormatter={compact} width={48} />
          <Tooltip formatter={tip} />
          {stacked && <Legend wrapperStyle={{ fontSize: 12 }} />}
          {c.series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} stackId={stacked ? "a" : undefined} fill={COLORS[i % COLORS.length]} isAnimationActive={false}>
              {!stacked && c.data.map((r, j) => <Cell key={j} fill={r[s.key] < 0 ? HILITE : COLORS[0]} />)}
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={c.data} margin={{ left: 0, right: 8 }}>
        {grid}
        <XAxis dataKey={xk} tick={tick} minTickGap={36} />
        <YAxis tick={tick} tickFormatter={compact} width={48} scale={c.log ? "log" : "auto"} domain={c.log ? [1, "auto"] : undefined} allowDataOverflow={!!c.log} />
        <Tooltip formatter={tip} />
        {c.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {c.series.map((s, i) => (
          <Line key={s.key} dataKey={s.key} name={s.name} type={c.type === "step" ? "stepAfter" : "linear"} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={c.data.length <= 14} isAnimationActive={false} connectNulls />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function ChartCard({ c }) {
  const problems = specProblems(c);
  return (
    <figure className={"panel chart" + (c.wide ? " wide" : "")} data-testid={"chart-" + c.id} aria-label={c.title}>
      <figcaption>
        <h3>{c.title}{c.unit && c.type !== "table" ? <span className="unit"> ({c.unit})</span> : null}</h3>
        {c.subtitle && <div className="sub">{c.subtitle}</div>}
      </figcaption>
      {problems.length ? <p className="err">Chart data problem: {problems.join("; ")}</p> : c.type === "table" ? <Table c={c} /> : <Plot c={c} />}
      {c.note && <p className="note">{c.note}</p>}
      {c.source && <p className="src">Source: {c.source}</p>}
    </figure>
  );
}

export default function Analysis() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    fetch("analysis.json").then((r) => (r.ok ? r.json() : Promise.reject(new Error("analysis.json " + r.status)))).then(setData).catch((e) => setErr(e.message));
  }, []);
  const nCharts = useMemo(() => (data ? data.sections.reduce((n, s) => n + s.charts.length, 0) : 0), [data]);
  if (err) return <p className="err">Could not load the analysis data: {err}</p>;
  if (!data) return <p className="sub">Loading analysis…</p>;
  return (
    <div data-testid="analysis">
      <p className="sub">{data.title}. {nCharts} charts and tables, generated {data.generated} from the files in the project's data warehouse. Real data only; the payments tab holds the synthetic data.</p>
      <nav className="pills" aria-label="Sections">
        {data.sections.map((s) => <a key={s.id} href={"#sec-" + s.id}>{s.title}</a>)}
      </nav>
      {data.sections.map((s) => (
        <section key={s.id} id={"sec-" + s.id} data-testid={"sec-" + s.id}>
          <h2 className="sec">{s.title}</h2>
          <p className="intro">{s.intro}</p>
          {s.kpis.length > 0 && (
            <div className="grid">
              {s.kpis.map((k) => (
                <div className="card" key={k.label}>
                  <div className="k">{k.label}</div>
                  <div className="v">{k.value}</div>
                  <div className="sub">{k.note}</div>
                </div>
              ))}
            </div>
          )}
          <div className="charts">{s.charts.map((c) => <ChartCard key={c.id} c={c} />)}</div>
        </section>
      ))}
    </div>
  );
}
