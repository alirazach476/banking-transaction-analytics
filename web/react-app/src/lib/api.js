// API client for the analytics endpoints. The optional API key comes from ?key=... (kept for the session) and is sent as X-API-Key.
const stored = () => { try { return sessionStorage.getItem("nb_key"); } catch { return null; } };
const fromUrl = new URLSearchParams(typeof location !== "undefined" ? location.search : "").get("key");
if (fromUrl) { try { sessionStorage.setItem("nb_key", fromUrl); } catch { /* storage unavailable */ } }
export const apiKey = () => fromUrl || stored();

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export function qs(params = {}) {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => u.append(k, x)); else u.append(k, v);
  }
  const s = u.toString();
  return s ? "?" + s : "";
}

async function call(method, path, params, body) {
  const key = apiKey();
  const r = await fetch(path + (method === "GET" ? qs(params) : ""), {
    method,
    headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...(key ? { "X-API-Key": key } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 429) throw new ApiError("Rate limit reached, retry in " + (r.headers.get("Retry-After") || "a few") + " s", 429);
  if (r.status === 401) throw new ApiError("The API requires a key: open the app with ?key=YOUR_KEY", 401);
  if (!r.ok) {
    let detail = "";
    try { detail = (await r.json()).detail; } catch { /* not json */ }
    throw new ApiError(typeof detail === "string" && detail ? detail : `${path} returned ${r.status}`, r.status);
  }
  return r.json();
}

export const get = (path, params) => call("GET", path, params);
export const send = (method, path, body) => call(method, path, undefined, body);

// Download a server-side export (needs the key header, so a plain <a href> is not enough).
export async function download(path, params, filename) {
  const key = apiKey();
  const r = await fetch(path + qs(params), { headers: key ? { "X-API-Key": key } : {} });
  if (!r.ok) throw new ApiError("Export failed (" + r.status + ")", r.status);
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
