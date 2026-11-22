import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Download, Inbox, Minus, RefreshCw } from "lucide-react";
import { deltaText, formatKpi } from "../lib/format.js";
import { PRESETS, useRange } from "../lib/context.jsx";

export const Card = ({ children, className = "", ...p }) => <div className={"card " + className} {...p}>{children}</div>;

export const Skeleton = ({ h = 16, w = "100%", style }) => <div className="skeleton" style={{ height: h, width: w, ...style }} />;
export const ErrorState = ({ error, onRetry }) => (
  <div className="state err" role="alert"><AlertTriangle size={22} /><div>{error?.message || "Something went wrong"}</div>{onRetry && <button className="btn sm" onClick={onRetry}><RefreshCw size={14} /> Retry</button>}</div>
);
export const EmptyState = ({ title = "No data for this selection", hint }) => (
  <div className="state"><Inbox size={22} /><div>{title}</div>{hint && <small>{hint}</small>}</div>
);

const DOMAINS = {
  synthetic: ["synthetic", "Synthetic data"], real: ["real", "Real external data"], simulated: ["simulated", "Simulated / demo"],
};
export const DomainBadge = ({ kind = "synthetic", label }) => <span className={"badge " + DOMAINS[kind][0]} title={DOMAINS[kind][1]}>{label || DOMAINS[kind][1]}</span>;
export const Badge = ({ value, kind }) => (value === null || value === undefined || value === "" ? <span className="badge neutral">–</span> : <span className={"badge " + (kind || value)}>{String(value).replace(/_/g, " ")}</span>);

export function PageHeader({ title, subtitle, domains = [], actions }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
        {domains.length > 0 && <div className="badges">{domains.map((d) => <DomainBadge key={d.label || d.kind} {...d} />)}</div>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

const INVERT = new Set(["decline_rate", "anomaly_rate", "chargeback_rate", "core_failure_rate"]); // an increase is bad

export function KpiCard({ k, loading, onClick }) {
  if (loading || !k) return <Card className="kpi"><Skeleton h={12} w="55%" /><Skeleton h={30} w="70%" style={{ margin: "10px 0" }} /><Skeleton h={12} w="40%" /></Card>;
  const d = k.delta;
  const bad = INVERT.has(k.key) ? d > 0 : d < 0;
  const cls = d === null || d === undefined || Math.abs(d) < 0.005 ? "flat" : bad ? "down" : "up";
  const Icon = cls === "flat" ? Minus : d > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <Card className="kpi" onClick={onClick} style={onClick ? { cursor: "pointer" } : undefined} data-testid={"kpi-" + k.key}>
      <div className="label"><span>{k.label}</span><span className={"badge " + (k.domain === "payments" || k.domain === "core" ? "synthetic" : "real")} style={{ fontSize: 10 }}>{k.domain === "core" ? "core banking" : k.domain}</span></div>
      <div className="value num" data-testid={"kpi-value-" + k.key}>{formatKpi(k)}</div>
      <div className="foot">
        <span className={"delta " + cls} title="Change vs the immediately preceding period of equal length"><Icon size={13} />{deltaText(d, k.delta_unit)}</span>
        <span>{k.note || "vs prior period"}</span>
      </div>
    </Card>
  );
}

// Chart container with loading / error / empty states. `query` is a TanStack Query result; `isEmpty(data)` decides emptiness.
export function ChartCard({ title, subtitle, query, isEmpty, footer, actions, height = 280, children, className = "" }) {
  const q = query;
  let body;
  if (q && q.isPending) body = <Skeleton h={height} style={{ opacity: .7 }} />;
  else if (q && q.isError) body = <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  else if (q && isEmpty && isEmpty(q.data)) body = <EmptyState />;
  else body = children;
  return (
    <Card className={"chart-card " + className} data-testid={"chart-" + (title || "").toLowerCase().replace(/[^a-z0-9]+/g, "-")}>
      <header>
        <div><h3>{title}</h3>{subtitle && <div className="sub">{subtitle}</div>}</div>
        {actions}
      </header>
      <div className="chart-body">{body}</div>
      {footer && <footer>{footer}</footer>}
    </Card>
  );
}

export function Segmented({ value, onChange, options, label }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => <button key={o.value} className={value === o.value ? "on" : ""} onClick={() => onChange(o.value)}>{o.label}</button>)}
    </div>
  );
}

export const Notice = ({ children, warn }) => <div className={"notice" + (warn ? " warn" : "")}>{children}</div>;

export function RangeControl() {
  const { from, to, setRange, preset } = useRange();
  const [custom, setCustom] = useState(false);
  return (
    <div className="actions" data-testid="range-control">
      <select className="field" aria-label="Date range" value={custom || preset === "custom" ? "custom" : preset} onChange={(e) => {
        if (e.target.value === "custom") setCustom(true);
        else { setCustom(false); const p = PRESETS.find((x) => x.id === e.target.value); setRange(p.from, p.to); }
      }}>
        {PRESETS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
        <option value="custom">Custom range…</option>
      </select>
      {(custom || preset === "custom") && (
        <>
          <input className="field" type="date" aria-label="From" value={from} min="2023-01-01" max={to} onChange={(e) => e.target.value && setRange(e.target.value, to)} />
          <input className="field" type="date" aria-label="To" value={to} min={from} max="2025-12-31" onChange={(e) => e.target.value && setRange(from, e.target.value)} />
        </>
      )}
    </div>
  );
}

export const ExportButton = ({ onClick, children = "Export", disabled }) => <button className="btn sm" onClick={onClick} disabled={disabled}><Download size={14} /> {children}</button>;

// Client-side CSV of data already on screen (small, aggregated tables); server-side exports are used for row-level tables
export function toCsv(rows, columns) {
  const esc = (v) => (v === null || v === undefined ? "" : /[",\n]/.test(String(v)) ? '"' + String(v).replace(/"/g, '""') + '"' : String(v));
  return [columns.map((c) => c.label).join(","), ...rows.map((r) => columns.map((c) => esc(r[c.key])).join(","))].join("\n");
}
export function saveText(text, filename, type = "text/csv") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
}

// Plain stat tile (no period comparison)
export function Stat({ label, value, note, loading }) {
  if (loading) return <Card className="kpi"><Skeleton h={12} w="55%" /><Skeleton h={28} w="70%" style={{ margin: "10px 0" }} /></Card>;
  return <Card className="kpi"><div className="label"><span>{label}</span></div><div className="value num">{value}</div>{note && <div className="foot"><span>{note}</span></div>}</Card>;
}

// Multi-select dropdown with checkboxes
export function MultiSelect({ label, options = [], value = [], onChange, testId }) {
  const [open, setOpen] = useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const h = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const toggle = (o) => onChange(value.includes(o) ? value.filter((x) => x !== o) : [...value, o]);
  return (
    <label style={{ position: "relative" }} ref={ref}>
      {label}
      <button type="button" className="field" style={{ textAlign: "left", minWidth: 150, cursor: "pointer" }} onClick={() => setOpen(!open)} data-testid={testId} aria-haspopup="listbox" aria-expanded={open}>
        {value.length === 0 ? "All" : value.length === 1 ? value[0] : `${value.length} selected`}
      </button>
      {open && (
        <div className="menu" style={{ left: 0, right: "auto", top: 58, minWidth: 220 }} role="listbox">
          <div className="colmenu">
            {options.map((o) => <label key={o} style={{ textTransform: "none", letterSpacing: 0, fontSize: 13, color: "var(--text)" }}><input type="checkbox" checked={value.includes(o)} onChange={() => toggle(o)} /> {o}</label>)}
            {value.length > 0 && <button type="button" className="btn sm" onClick={() => onChange([])}>Clear</button>}
          </div>
        </div>
      )}
    </label>
  );
}

// Filters kept in the URL (so a filtered view can be shared or reached by drill-down from another page)
export function useUrlFilters(keys, arrays = []) {
  const [sp, setSp] = useSearchParams();
  const get = (k) => (arrays.includes(k) ? sp.getAll(k) : sp.get(k) || "");
  const set = (k, v) => {
    const n = new URLSearchParams(sp);
    n.delete(k);
    (Array.isArray(v) ? v : v ? [v] : []).forEach((x) => n.append(k, x));
    setSp(n, { replace: true });
  };
  const values = Object.fromEntries(keys.map((k) => [k, get(k)]));
  const clear = () => { const n = new URLSearchParams(sp); keys.forEach((k) => n.delete(k)); setSp(n, { replace: true }); };
  return [values, set, clear];
}
