import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { get } from "./api.js";

/* ---------------- theme ---------------- */
const ThemeCtx = createContext({ theme: "dark", setTheme: () => {} });
export const useTheme = () => useContext(ThemeCtx);

export function ThemeProvider({ children }) {
  const initial = () => {
    try { const s = localStorage.getItem("nb_theme"); if (s === "light" || s === "dark") return s; } catch { /* ignore */ }
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  };
  const [theme, setThemeState] = useState(initial);
  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); }, [theme]);
  const setTheme = useCallback((t) => { setThemeState(t); try { localStorage.setItem("nb_theme", t); } catch { /* ignore */ } }, []);
  return <ThemeCtx.Provider value={{ theme, setTheme }}>{children}</ThemeCtx.Provider>;
}

/* ---------------- global date range (lives in the URL so views are shareable) ---------------- */
export const DATA_MIN = "2023-01-01";
export const DATA_MAX = "2025-12-31";
// Default view: the latest full calendar year, so period-over-period comparison (vs 2024) has data
export const DEFAULT_FROM = "2025-01-01";
export const DEFAULT_TO = "2025-12-31";
export const PRESETS = [
  { id: "all", label: "All data (2023-2025)", from: "2023-01-01", to: "2025-12-31" },
  { id: "y2025", label: "2025", from: "2025-01-01", to: "2025-12-31" },
  { id: "y2024", label: "2024", from: "2024-01-01", to: "2024-12-31" },
  { id: "y2023", label: "2023", from: "2023-01-01", to: "2023-12-31" },
  { id: "h2_2025", label: "Last 6 months of data", from: "2025-07-01", to: "2025-12-31" },
  { id: "q4_2025", label: "Last quarter of data", from: "2025-10-01", to: "2025-12-31" },
  { id: "d30", label: "Last 30 days of data", from: "2025-12-02", to: "2025-12-31" },
];
const RangeCtx = createContext(null);
export const useRange = () => useContext(RangeCtx);

export function RangeProvider({ children }) {
  const [sp, setSp] = useSearchParams();
  const from = sp.get("from") || DEFAULT_FROM;
  const to = sp.get("to") || DEFAULT_TO;
  const setRange = useCallback((f, t) => {
    const n = new URLSearchParams(sp);
    if (f === DEFAULT_FROM && t === DEFAULT_TO) { n.delete("from"); n.delete("to"); } else { n.set("from", f); n.set("to", t); }
    setSp(n, { replace: true });
  }, [sp, setSp]);
  const value = useMemo(() => ({ from, to, setRange, params: { from, to }, preset: PRESETS.find((p) => p.from === from && p.to === to)?.id || "custom" }), [from, to, setRange]);
  return <RangeCtx.Provider value={value}>{children}</RangeCtx.Provider>;
}

/* ---------------- data fetching: cached and de-duplicated by TanStack Query ---------------- */
export function useApi(path, params, options = {}) {
  return useQuery({
    queryKey: [path, params || {}],
    queryFn: () => get(path, params),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
    retry: (n, e) => n < 1 && (!e.status || e.status >= 500),
    ...options,
  });
}

// Range-aware convenience: always includes the global from/to
export function useRangeApi(path, extra = {}, options = {}) {
  const { params } = useRange();
  return useApi(path, { ...params, ...extra }, options);
}
