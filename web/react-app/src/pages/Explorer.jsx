import React from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useApi } from "../lib/context.jsx";
import { Card, ErrorState, Notice, PageHeader, Skeleton } from "../ui/kit.jsx";
import ServerTable from "../ui/ServerTable.jsx";

const TABS = [
  ["transactions", "Transactions"], ["payments", "Card payments"], ["payment-failures", "Payment failures"], ["customers", "Customers"], ["merchants", "Merchants"],
  ["branches", "Branches"], ["anomalies", "Anomalies"], ["pipeline-runs", "Pipeline runs"], ["data-quality", "Data quality"],
];
const OPTIONS = {
  transactions: { status: ["Completed", "Failed", "Pending", "Reversed"], anomaly_severity: ["Low", "Medium", "High"], channel: ["ATM", "Branch", "Mobile", "Online", "POS"], injected_anomaly_label: ["true", "false"] },
  payments: { authorized: ["true", "false"], declined: ["true", "false"], charged_back: ["true", "false"] },
  anomalies: { severity: ["Low", "Medium", "High"], investigation_status: ["NEW", "INVESTIGATING", "CONFIRMED_FRAUD", "FALSE_POSITIVE", "CLOSED"] },
  "pipeline-runs": { status: ["SUCCESS", "FAILED", "WARNING", "RUNNING"] },
  "data-quality": { status: ["PASS", "FAIL", "WARN"] },
};
const LINKS = { customers: (r) => `/customers/${r.customer_id}`, merchants: (r) => `/merchants/${r.merchant_id}`, branches: (r) => `/branches/${r.branch_id}` };

export default function Explorer() {
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const cat = useApi("/v1/tables");
  const tab = TABS.some((t) => t[0] === sp.get("tab")) ? sp.get("tab") : "transactions";
  const go = (k) => setSp((p) => { const n = new URLSearchParams(p); n.set("tab", k); return n; });
  const spec = cat.data?.find((d) => d.name === tab);
  return (
    <>
      <PageHeader title="Transaction explorer" subtitle="Search, sort, filter and export row-level data. Sorting, filtering and paging run in the database; exports include every matching row."
        domains={[{ kind: "synthetic", label: "Synthetic · row-level data" }]} />
      <div className="seg" role="tablist" aria-label="Datasets" style={{ flexWrap: "wrap", marginBottom: 14 }}>
        {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => go(k)}>{l}</button>)}
      </div>
      {cat.isError ? <ErrorState error={cat.error} onRetry={() => cat.refetch()} /> : cat.isPending ? <Skeleton h={400} /> : (
        <Card style={{ padding: 18 }}>
          <h3 style={{ marginBottom: 4 }}>{spec?.label}</h3>
          {spec?.date_filter && <p style={{ color: "var(--muted)", margin: "0 0 10px", fontSize: 12 }}>Rows are limited to the date range chosen in the top bar. Shift+click a column header to sort by several columns.</p>}
          {["customers", "merchants", "branches"].includes(tab) && <Notice>Click a row to open its detail page.</Notice>}
          <ServerTable key={tab} dataset={tab} testId={"explorer-" + tab} filterOptions={OPTIONS[tab] || {}} pageSize={25}
            onRowClick={LINKS[tab] ? (r) => nav(LINKS[tab](r)) : undefined} />
        </Card>
      )}
    </>
  );
}
