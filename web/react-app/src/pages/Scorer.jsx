import React, { useState } from "react";
import { api, pct } from "../api.js";

// Preserved from the original UI: decline and fraud probability from the saved models (trained on synthetic data).
export default function Scorer() {
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
    <div className="card" style={{ padding: 18 }}>
      <h3 style={{ marginBottom: 10 }}>Score a payment</h3>
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

