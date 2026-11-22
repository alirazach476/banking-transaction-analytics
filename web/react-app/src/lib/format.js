export function compact(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const a = Math.abs(v);
  const f = (x, s) => (x.toFixed(digits).replace(/\.0+$/, "") + s);
  if (a >= 1e9) return f(v / 1e9, "B");
  if (a >= 1e6) return f(v / 1e6, "M");
  if (a >= 1e3) return f(v / 1e3, "K");
  return Math.round(v * 100) / 100 === Math.round(v) ? String(Math.round(v)) : v.toFixed(2);
}
export const int = (v) => (v === null || v === undefined ? "–" : Math.round(v).toLocaleString("en-US"));
export const usd = (v, c = true) => (v === null || v === undefined ? "–" : "$" + (c ? compact(v) : Math.round(v).toLocaleString("en-US")));
export const usdFull = (v) => (v === null || v === undefined ? "–" : v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }));
export const pct = (r, d = 1) => (r === null || r === undefined ? "–" : (r * 100).toFixed(d) + "%");
export const num = (v, d = 2) => (v === null || v === undefined ? "–" : Number(v).toLocaleString("en-US", { maximumFractionDigits: d }));
export const date = (s) => (s ? String(s).slice(0, 10) : "–");
export const dateTime = (s) => (s ? String(s).replace("T", " ").slice(0, 16) : "–");
export function deltaText(d, unit) {
  if (d === null || d === undefined || Number.isNaN(d)) return "n/a";
  const sign = d > 0 ? "+" : d < 0 ? "−" : "";
  return sign + Math.abs(d).toFixed(Math.abs(d) < 10 ? 2 : 1) + (unit === "pp" ? " pp" : "%");
}
export const dowName = (i) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i - 1];
export function formatKpi(k) {
  if (k.value === null || k.value === undefined) return "–";
  return k.unit === "usd" ? usd(k.value) : k.unit === "ratio" ? pct(k.value, 2) : int(k.value);
}
