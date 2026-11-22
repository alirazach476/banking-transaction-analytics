import React from "react";
import { Link, useParams } from "react-router-dom";
import { useRange, useRangeApi } from "../lib/context.jsx";
import { date, int, usd } from "../lib/format.js";
import { Badge, Card, ChartCard, EmptyState, ErrorState, PageHeader, Skeleton, Stat } from "../ui/kit.jsx";
import EChart from "../ui/EChart.jsx";
import { donut, timeSeries } from "../ui/charts.js";
import ServerTable from "../ui/ServerTable.jsx";

export default function CustomerDetail() {
  const { id } = useParams();
  const { from, to } = useRange();
  const q = useRangeApi(`/v1/customers/${id}`);
  if (q.isPending) return <><Skeleton h={34} w="30%" /><Skeleton h={120} style={{ margin: "14px 0" }} /><Skeleton h={300} /></>;
  if (q.isError) return q.error.status === 404 ? <EmptyState title={`Customer ${id} not found`} hint="Check the ID or use the global search." /> : <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const { profile: p, kpis: k, monthly, channels, types, alerts, card_payments: cp } = q.data;
  return (
    <>
      <PageHeader title={`${p.first_name || ""} ${p.last_name || ""}`.trim() || p.customer_id} subtitle={`${p.customer_id} · ${p.customer_type || "unknown type"} · ${p.city || "unknown city"}, ${p.region || "unknown region"} · registered ${date(p.registration_date)}`}
        domains={[{ kind: "synthetic", label: "Synthetic customer" }]} actions={<Link className="btn sm" to="/customers">All customers</Link>} />
      <div className="grid g-kpi6">
        <Stat label="Core-banking transactions" value={int(k.transactions)} note={`${date(from)} to ${date(to)}`} />
        <Stat label="Completed" value={int(k.completed)} note={`${int(k.failed)} failed`} />
        <Stat label="Completed value (USD)" value={usd(k.value)} />
        <Stat label="Anomaly alerts" value={int(alerts.alerts)} note={`${int(alerts.high)} high severity (all time)`} />
        <Stat label="Card payments" value={int(cp.payments)} note={`${usd(cp.value)} · ${int(cp.declined || 0)} declined`} />
        <Stat label="Status" value={<Badge value={p.customer_status} kind="neutral" />} note={k.last_txn ? `last transaction ${date(k.last_txn)}` : "no transactions in range"} />
      </div>
      <div className="grid g-21 mb">
        <ChartCard title="Monthly activity" subtitle="Transactions and completed value (USD)" height={280} isEmpty={() => !monthly.length} query={{ isPending: false, data: monthly }}>
          <EChart height={280} ariaLabel="Monthly activity" option={timeSeries(monthly, "period", [{ key: "transactions", name: "Transactions", type: "bar", fmt: int }, { key: "value", name: "Completed value", axis: 1, color: "teal", fmt: (v) => usd(v) }], { y2Fmt: (v) => usd(v) })} />
        </ChartCard>
        <ChartCard title="Channel mix" subtitle="Transactions by channel" height={280} isEmpty={() => !channels.length} query={{ isPending: false, data: channels }}>
          <EChart height={280} ariaLabel="Channel mix" option={donut(channels, "channel", "transactions", { fmt: int })} />
        </ChartCard>
      </div>
      <div className="grid g-2 mb">
        <ChartCard title="Transaction types" subtitle="Core-banking transactions by type" height={240} isEmpty={() => !types.length} query={{ isPending: false, data: types }}>
          <EChart height={240} ariaLabel="Transaction types" option={donut(types, "transaction_type", "transactions", { fmt: int })} />
        </ChartCard>
        <Card style={{ padding: 18 }}><h3>About this view</h3><p style={{ color: "var(--text-2)", margin: "8px 0 0" }}>Core-banking transactions and card payments are separate synthetic datasets linked by customer ID. Completed value is converted to USD with the dataset's synthetic FX table. Anomaly alerts are not confirmed fraud.</p></Card>
      </div>
      <Card style={{ padding: 18 }}>
        <h3 style={{ marginBottom: 10 }}>Transaction history</h3>
        <ServerTable dataset="transactions" testId="customer-transactions" initialSort={{ id: "ts", desc: true }} extraParams={{ filters: JSON.stringify([{ id: "customer_id", op: "eq", value: p.customer_id }]) }} filterOptions={{ status: ["Completed", "Failed", "Pending", "Reversed"] }} />
      </Card>
    </>
  );
}
