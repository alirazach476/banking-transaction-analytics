import React, { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, pct } from "./api.js";
import Analysis from "./Analysis.jsx";

function Tile({ k, v }) {
  return (
    <div className="card">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  );
}

function Scorer() {
  const [f, setF] = useState({ amount: 120, hour: 14, channel: "POS Chip", is_international: false, card_id: "", txn_ts: "" });
  const [out, setOut] = useState(null);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setOut(null);
    try {
      const base = { amount: +f.amount, channel: f.channel, is_international: f.is_international };
      const decline = await api("/score/decline", { ...base, hour: +f.hour });
      const fraud =
        f.card_id && f.txn_ts
          ? await api("/score/fraud/card", { ...base, card_id: f.card_id, authorization_ts: f.txn_ts })
          : await api("/score/fraud", { ...base, hour: +f.hour, foreign_merchant: f.is_international });
      setOut({ decline, fraud });
    } catch (x) {
      setErr(x.message);
    }
  }

  return (
    <div className="panel">
      <h2>Score a payment</h2>
      <form onSubmit={submit}>
        <label>Amount (USD)<input type="number" step="0.01" min="0.01" value={f.amount} onChange={set("amount")} required /></label>
        <label>Hour<input type="number" min="0" max="23" value={f.hour} onChange={set("hour")} /></label>
        <label>Channel
          <select value={f.channel} onChange={set("channel")}>
            {["POS Chip", "POS Contactless", "E-commerce", "Recurring"].map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="chk"><input type="checkbox" checked={f.is_international} onChange={set("is_international")} /> International</label>
        <label>Card ID (optional)<input placeholder="CARD-002863" value={f.card_id} onChange={set("card_id")} /></label>
        <label>Timestamp (with card)<input type="datetime-local" value={f.txn_ts} onChange={set("txn_ts")} /></label>
        <button type="submit">Score</button>
      </form>
      <p className="sub">
        With a card ID and timestamp, card features are computed on the server from that card's payment history;
        otherwise the form assumes a single payment on the card.
      </p>
      {err && <p className="err">{err}</p>}
      {out && (
        <p data-testid="score-out">
          Decline probability <b>{pct(out.decline.decline_probability)}</b> · Fraud probability{" "}
          <b>{pct(out.fraud.fraud_probability)}</b> ({out.fraud.flag ? "FLAGGED" : "not flagged"})
          {out.fraud.computed_features && (
            <> · card payments in last 60 min: {out.fraud.computed_features.card_txn_60m}, prior payments: {out.fraud.computed_features.prior_payments_on_card}</>
          )}
        </p>
      )}
    </div>
  );
}

function PaymentsTab() {
  const [s, setS] = useState(null);
  const [daily, setDaily] = useState([]);
  const [reasons, setReasons] = useState([]);
  const [queue, setQueue] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setS(await api("/kpis/summary"));
        setDaily((await api("/kpis/daily?limit=180")).reverse());
        setReasons(await api("/decline-reasons?limit=8"));
        setQueue(await api("/reconciliation/queue?limit=10"));
      } catch (x) {
        setErr(x.message + " (add ?key=... to the URL if the API requires a key)");
      }
    })();
  }, []);

  return (
    <>
      <h2 className="sec">NovaBank Payments</h2>
      <p className="sub">Synthetic data only. KPIs from dbt marts; scores from saved models.</p>
      {err && <p className="err">{err}</p>}
      {s && (
        <div className="grid">
          <Tile k="Payments" v={s.payments.toLocaleString()} />
          <Tile k="Approval rate" v={pct(s.approval_rate)} />
          <Tile k="Completion rate" v={pct(s.completion_rate)} />
          <Tile k="Settlement rate" v={pct(s.settlement_rate)} />
        </div>
      )}
      <div className="panel">
        <h2>Daily approval rate (last 180 days)</h2>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={daily}>
            <CartesianGrid strokeOpacity={0.2} />
            <XAxis dataKey="payment_date" minTickGap={40} />
            <YAxis domain={[0.8, 1]} tickFormatter={(v) => (v * 100).toFixed(0) + "%"} />
            <Tooltip formatter={(v) => pct(v)} />
            <Line dataKey="approval_rate" dot={false} stroke="#1f6feb" strokeWidth={2} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="panel">
        <h2>Top decline reasons</h2>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={reasons} layout="vertical" margin={{ left: 120 }}>
            <CartesianGrid strokeOpacity={0.2} />
            <XAxis type="number" />
            <YAxis type="category" dataKey="decline_reason" width={160} />
            <Tooltip />
            <Bar dataKey="declined_payments" fill="#1f6feb" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="panel">
        <h2>Open reconciliation exceptions</h2>
        <div className="wrap">
          <table>
            <thead><tr><th>Payment</th><th>Issue</th><th>At risk</th><th>Priority</th></tr></thead>
            <tbody>
              {queue.map((r) => (
                <tr key={r.payment_id + r.issue_type}>
                  <td>{r.payment_id}</td>
                  <td>{r.issue_type}</td>
                  <td>{r.amount_at_risk == null ? "" : r.amount_at_risk.toFixed(2) + " " + (r.currency || "")}</td>
                  <td>{r.priority}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <Scorer />
    </>
  );
}

export default function App() {
  const [tab, setTab] = useState(() => (window.location.hash.startsWith("#analysis") || window.location.hash.startsWith("#sec-") ? "analysis" : "payments"));
  const pick = (t) => () => {
    setTab(t);
    window.history.replaceState(null, "", t === "analysis" ? "#analysis" : "#payments");
  };
  return (
    <main>
      <h1>NovaBank</h1>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "payments"} className={tab === "payments" ? "on" : ""} onClick={pick("payments")}>Payments (synthetic)</button>
        <button role="tab" aria-selected={tab === "analysis"} className={tab === "analysis" ? "on" : ""} onClick={pick("analysis")}>Pakistan analysis (real data)</button>
      </div>
      {tab === "payments" ? <PaymentsTab /> : <Analysis />}
    </main>
  );
}
