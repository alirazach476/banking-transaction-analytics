const KEY = new URLSearchParams(location.search).get("key");

export async function api(path, body) {
  const r = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json", ...(KEY ? { "X-API-Key": KEY } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 429) throw new Error("Rate limit reached, retry in " + (r.headers.get("Retry-After") || "a few") + " s");
  if (!r.ok) throw new Error(path + " returned " + r.status);
  return r.json();
}

export const pct = (x) => (x * 100).toFixed(2) + "%";
