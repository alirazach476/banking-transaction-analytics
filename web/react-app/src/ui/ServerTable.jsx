import React, { useEffect, useMemo, useState } from "react";
import { flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Columns3, Download, FileSpreadsheet, Search } from "lucide-react";
import { download } from "../lib/api.js";
import { useApi, useRange } from "../lib/context.jsx";
import { date, dateTime, int, num, pct, usdFull } from "../lib/format.js";
import { Badge, EmptyState, ErrorState, Skeleton, saveText, toCsv } from "./kit.jsx";

const STATUSY = /(^|_)(status|severity)$|^investigation_status$/;
const pretty = (id) => id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).replace(/ Usd\b/, " (USD)").replace(/ Id\b/, " ID").replace(/ Ms\b/, " (ms)").replace(/ Pct\b/, " %");

// Default cell rendering with conditional formatting (status badges, severity, scores, amounts, rates)
export function renderCell(id, kind, v) {
  if (v === null || v === undefined || v === "") return <span style={{ color: "var(--muted)" }}>–</span>;
  if (STATUSY.test(id)) return <Badge value={v} />;
  if (kind === "bool") return v ? <span className="badge success">Yes</span> : <span className="badge neutral">No</span>;
  if (kind === "ts") return <span className="num">{id.endsWith("_at") || id === "ts" || id.includes("time") ? dateTime(v) : date(v)}</span>;
  if (/score$/.test(id)) {
    const c = v >= 0.65 ? "var(--bad)" : v >= 0.55 ? "var(--warn)" : "var(--info)";
    return <span style={{ display: "inline-flex", alignItems: "center", gap: 6, justifyContent: "flex-end", width: "100%" }}><span className="num">{Number(v).toFixed(3)}</span><span style={{ width: 34, height: 5, borderRadius: 3, background: "var(--surface-3)" }}><i style={{ display: "block", height: 5, borderRadius: 3, width: `${Math.min(100, v * 100)}%`, background: c }} /></span></span>;
  }
  if (kind === "num") {
    if (/amount_usd|value_usd|^amount$/.test(id)) return <span style={{ fontWeight: v >= 10000 ? 700 : 400, color: v >= 10000 ? "var(--warn)" : undefined }}>{usdFull(v)}</span>;
    if (/approval_rate|completion_rate/.test(id)) return <span style={{ color: v < 0.9 ? "var(--warn)" : undefined }}>{pct(v, 2)}</span>;
    if (/failure_rate_pct/.test(id)) return <span style={{ color: v > 7 ? "var(--bad)" : v > 5.5 ? "var(--warn)" : undefined, fontWeight: v > 7 ? 700 : 400 }}>{num(v, 2)}%</span>;
    if (/failed|chargebacks|declined|failed_rows/.test(id) && v > 0) return <span style={{ color: "var(--bad)" }}>{int(v)}</span>;
    return Number.isInteger(v) ? int(v) : num(v, 3);
  }
  return String(v);
}

export default function ServerTable({ dataset, extraParams = {}, filterOptions = {}, renderDetail, onRowClick, initialSort, pageSize = 25, title, testId, refreshKey = 0 }) {
  const cat = useApi("/v1/tables");
  const spec = cat.data?.find((d) => d.name === dataset);
  const { from, to } = useRange();
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(pageSize);
  const [sorting, setSorting] = useState(initialSort ? [initialSort] : []);
  const [colFilters, setColFilters] = useState({});
  const [search, setSearch] = useState("");
  const [dq, setDq] = useState("");
  const [vis, setVis] = useState(null);
  const [sizing, setSizing] = useState({});
  const [selection, setSelection] = useState({});
  const [open, setOpen] = useState(null);
  const [colMenu, setColMenu] = useState(false);
  useEffect(() => { const t = setTimeout(() => { setDq(search.trim()); setPage(0); }, 300); return () => clearTimeout(t); }, [search]);
  useEffect(() => { setPage(0); setSelection({}); setOpen(null); }, [dataset, from, to, JSON.stringify(extraParams)]);

  const visibility = vis || Object.fromEntries((spec?.hidden || []).map((h) => [h, false]));
  const filtersJson = useMemo(() => {
    const out = [];
    for (const [id, f] of Object.entries(colFilters)) {
      const k = spec?.columns.find((c) => c.id === id)?.kind;
      if (f.value !== undefined && f.value !== "" && f.value !== null && !(Array.isArray(f.value) && !f.value.length)) out.push({ id, op: f.op, value: f.value });
      else if (k === "num" && (f.min !== undefined || f.max !== undefined)) {
        const lo = f.min === "" || f.min === undefined ? null : Number(f.min), hi = f.max === "" || f.max === undefined ? null : Number(f.max);
        if (lo !== null && hi !== null) out.push({ id, op: "between", value: [lo, hi] }); else if (lo !== null) out.push({ id, op: "gte", value: lo }); else if (hi !== null) out.push({ id, op: "lte", value: hi });
      } else if (k === "ts" && (f.from || f.to)) {
        if (f.from && f.to) out.push({ id, op: "between", value: [f.from, f.to + "T23:59:59"] }); else if (f.from) out.push({ id, op: "gte", value: f.from }); else out.push({ id, op: "lte", value: f.to + "T23:59:59" });
      }
    }
    return out;
  }, [colFilters, spec]);
  const sortStr = sorting.length ? sorting.map((s) => `${s.id}:${s.desc ? "desc" : "asc"}`).join(",") : undefined;
  const params = { page, size, sort: sortStr, filters: filtersJson.length ? JSON.stringify(filtersJson) : undefined, q: dq || undefined, from, to, ...extraParams };
  const q = useApi(`/v1/tables/${dataset}`, { ...params, _r: refreshKey }, { enabled: !!spec });
  const rows = q.data?.rows || [];

  const columns = useMemo(() => {
    if (!spec) return [];
    const sel = { id: "_sel", size: 36, enableResizing: false, header: () => <input type="checkbox" aria-label="Select all rows on this page" checked={rows.length > 0 && rows.every((r) => selection[r[spec.id]])}
      onChange={(e) => setSelection(e.target.checked ? Object.fromEntries(rows.map((r) => [r[spec.id], true])) : {})} />,
      cell: ({ row }) => <input type="checkbox" aria-label="Select row" checked={!!selection[row.original[spec.id]]} onChange={(e) => setSelection({ ...selection, [row.original[spec.id]]: e.target.checked })} onClick={(e) => e.stopPropagation()} /> };
    const exp = { id: "_exp", size: 34, enableResizing: false, header: () => null, cell: ({ row }) => <button className="icon-btn" style={{ width: 24, height: 24, border: 0, background: "none" }} aria-label="Expand row"
      onClick={(e) => { e.stopPropagation(); setOpen(open === row.original[spec.id] ? null : row.original[spec.id]); }}>{open === row.original[spec.id] ? <ChevronDown size={15} /> : <ChevronRight size={15} />}</button> };
    return [sel, exp, ...spec.columns.map((c) => ({ id: c.id, accessorKey: c.id, header: pretty(c.id), size: c.kind === "ts" ? 160 : c.kind === "num" ? 120 : c.id.endsWith("_id") ? 150 : 150, meta: { kind: c.kind },
      cell: ({ getValue }) => renderCell(c.id, c.kind, getValue()) }))];
  }, [spec, rows, selection, open]);

  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel(), columnResizeMode: "onChange", state: { columnVisibility: { ...visibility, _sel: true, _exp: true }, columnSizing: sizing }, onColumnSizingChange: setSizing, manualSorting: true, manualPagination: true, manualFiltering: true,
    getRowId: (r) => String(r[spec?.id]) });

  const toggleSort = (id, multi) => setSorting((cur) => {
    const ex = cur.find((s) => s.id === id);
    const next = !ex ? { id, desc: false } : !ex.desc ? { id, desc: true } : null;
    const rest = multi ? cur.filter((s) => s.id !== id) : [];
    setPage(0);
    return next ? [...rest, next] : rest;
  });
  const setF = (id, patch) => { setColFilters((c) => ({ ...c, [id]: { ...(c[id] || {}), ...patch } })); setPage(0); };
  const nSel = Object.values(selection).filter(Boolean).length;
  const total = q.data?.total ?? 0;
  const pages = q.data?.pages ?? 0;
  const exportParams = { ...params, page: undefined, size: undefined, _r: undefined };
  const exportSel = () => {
    const cols = (spec?.columns || []).map((c) => ({ key: c.id, label: c.id }));
    saveText(toCsv(rows.filter((r) => selection[r[spec.id]]), cols), `${dataset}-selected.csv`);
  };
  const visibleCols = table.getVisibleLeafColumns().filter((c) => !c.id.startsWith("_"));

  if (cat.isError) return <ErrorState error={cat.error} onRetry={() => cat.refetch()} />;
  if (!spec) return <Skeleton h={260} />;
  return (
    <div data-testid={testId || "table-" + dataset}>
      <div className="tbar">
        {title && <b style={{ marginRight: 8 }}>{title}</b>}
        <div className="search" style={{ width: 260 }}><Search size={15} /><input aria-label={`Search ${dataset}`} placeholder="Search…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ height: 34 }} /></div>
        <span className="spacer" />
        {nSel > 0 && <><span className="badge neutral">{nSel} selected</span><button className="btn sm" onClick={exportSel}><Download size={14} /> Export selected</button></>}
        <div style={{ position: "relative" }}>
          <button className="btn sm" onClick={() => setColMenu(!colMenu)} aria-label="Columns"><Columns3 size={14} /> Columns</button>
          {colMenu && <div className="menu" style={{ minWidth: 220 }}><div className="colmenu">{spec.columns.map((c) => (
            <label key={c.id}><input type="checkbox" checked={visibility[c.id] !== false} onChange={(e) => setVis({ ...visibility, [c.id]: e.target.checked })} /> {pretty(c.id)}</label>))}</div></div>}
        </div>
        <button className="btn sm" onClick={() => download(`/v1/tables/${dataset}/export`, { ...exportParams, fmt: "csv" }, `${dataset}.csv`)} aria-label="Export CSV"><Download size={14} /> CSV</button>
        <button className="btn sm" onClick={() => download(`/v1/tables/${dataset}/export`, { ...exportParams, fmt: "xlsx" }, `${dataset}.xlsx`)} aria-label="Export Excel"><FileSpreadsheet size={14} /> Excel</button>
      </div>
      <div className="table-wrap" style={{ opacity: q.isFetching && q.data ? 0.65 : 1, transition: "opacity .15s" }}>
        <table className="dt" style={{ width: Math.max(table.getTotalSize(), 600) }}>
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>{hg.headers.map((h) => {
                const kind = h.column.columnDef.meta?.kind;
                const s = sorting.find((x) => x.id === h.column.id);
                return (
                  <th key={h.id} style={{ width: h.getSize() }} className={kind === "num" ? "r" : ""} aria-sort={s ? (s.desc ? "descending" : "ascending") : "none"}>
                    <div className="th-in" onClick={(e) => kind && toggleSort(h.column.id, e.shiftKey)} title={kind ? "Click to sort; Shift+click to add a sort column" : undefined} style={{ justifyContent: kind === "num" ? "flex-end" : "flex-start" }}>
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {s && (s.desc ? <ArrowDown size={13} /> : <ArrowUp size={13} />)}
                      {s && sorting.length > 1 && <small>{sorting.indexOf(s) + 1}</small>}
                    </div>
                    {h.column.getCanResize() && <div className={"resizer" + (h.column.getIsResizing() ? " on" : "")} onMouseDown={h.getResizeHandler()} onTouchStart={h.getResizeHandler()} />}
                  </th>);
              })}</tr>))}
            <tr>{table.getVisibleLeafColumns().map((c) => {
              const kind = c.columnDef.meta?.kind;
              const f = colFilters[c.id] || {};
              const th = { position: "sticky", top: 36, background: "var(--surface-2)", padding: "4px 6px", zIndex: 2 };
              if (c.id.startsWith("_") || !kind) return <th key={c.id} style={th} />;
              const opts = filterOptions[c.id];
              return (
                <th key={c.id} style={th}>
                  {opts ? <select className="field" style={{ height: 28, width: "100%" }} aria-label={`Filter ${c.id}`} value={f.value || ""} onChange={(e) => setF(c.id, { op: "eq", value: e.target.value })}><option value="">All</option>{opts.map((o) => <option key={o}>{o}</option>)}</select>
                    : kind === "text" ? <input className="field" style={{ height: 28, width: "100%" }} placeholder="contains…" aria-label={`Filter ${c.id}`} value={f.value || ""} onChange={(e) => setF(c.id, { op: "contains", value: e.target.value })} />
                    : kind === "num" ? <div style={{ display: "flex", gap: 4 }}><input className="field" style={{ height: 28, width: "50%", padding: "0 6px" }} placeholder="min" type="number" aria-label={`${c.id} minimum`} value={f.min ?? ""} onChange={(e) => setF(c.id, { min: e.target.value })} /><input className="field" style={{ height: 28, width: "50%", padding: "0 6px" }} placeholder="max" type="number" aria-label={`${c.id} maximum`} value={f.max ?? ""} onChange={(e) => setF(c.id, { max: e.target.value })} /></div>
                    : kind === "ts" ? <div style={{ display: "flex", gap: 4 }}><input className="field" style={{ height: 28, width: "50%", padding: "0 4px" }} type="date" aria-label={`${c.id} from`} value={f.from || ""} onChange={(e) => setF(c.id, { from: e.target.value })} /><input className="field" style={{ height: 28, width: "50%", padding: "0 4px" }} type="date" aria-label={`${c.id} to`} value={f.to || ""} onChange={(e) => setF(c.id, { to: e.target.value })} /></div>
                    : null}
                </th>);
            })}</tr>
          </thead>
          <tbody>
            {q.isPending && Array.from({ length: 8 }).map((_, i) => <tr key={i}>{table.getVisibleLeafColumns().map((c) => <td key={c.id}><Skeleton h={14} /></td>)}</tr>)}
            {rows.length > 0 && table.getRowModel().rows.map((row) => (
              <React.Fragment key={row.id}>
                <tr className={selection[row.original[spec.id]] ? "selected" : ""} style={onRowClick ? { cursor: "pointer" } : undefined} onClick={() => onRowClick && onRowClick(row.original)}>
                  {row.getVisibleCells().map((cell) => <td key={cell.id} className={cell.column.columnDef.meta?.kind === "num" ? "r" : ""} title={typeof cell.getValue() === "string" ? cell.getValue() : undefined}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}
                </tr>
                {open === row.original[spec.id] && (
                  <tr className="detail"><td colSpan={table.getVisibleLeafColumns().length}>
                    {renderDetail ? renderDetail(row.original) : <div className="kv">{spec.columns.map((c) => <div key={c.id}><span>{pretty(c.id)}</span><b style={{ fontWeight: 500, wordBreak: "break-word" }}>{renderCell(c.id, c.kind, row.original[c.id])}</b></div>)}</div>}
                  </td></tr>
                )}
              </React.Fragment>))}
          </tbody>
        </table>
        {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
        {q.data && rows.length === 0 && <EmptyState title="No rows match these filters" hint="Clear a filter or widen the date range." />}
      </div>
      <div className="pager">
        <span data-testid="table-count">{total ? `${int(page * size + 1)}–${int(Math.min(total, (page + 1) * size))} of ${int(total)}` : "0 rows"} · {visibleCols.length} columns</span>
        <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
          Rows
          <select className="field" style={{ height: 30 }} aria-label="Rows per page" value={size} onChange={(e) => { setSize(+e.target.value); setPage(0); }}>{[10, 25, 50, 100, 200].map((n) => <option key={n}>{n}</option>)}</select>
          <button className="icon-btn" aria-label="First page" disabled={page === 0} onClick={() => setPage(0)}><ChevronsLeft size={15} /></button>
          <button className="icon-btn" aria-label="Previous page" disabled={page === 0} onClick={() => setPage(page - 1)}><ChevronLeft size={15} /></button>
          <span className="num">Page {pages ? page + 1 : 0} / {pages}</span>
          <button className="icon-btn" aria-label="Next page" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}><ChevronRight size={15} /></button>
          <button className="icon-btn" aria-label="Last page" disabled={page + 1 >= pages} onClick={() => setPage(pages - 1)}><ChevronsRight size={15} /></button>
        </span>
      </div>
    </div>
  );
}
