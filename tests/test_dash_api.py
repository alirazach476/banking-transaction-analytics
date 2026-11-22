"""Analytics-UI API (/v1): dashboard numbers are checked against independent SQL on the same database; table, export and
write endpoints are exercised. Tests skip themselves when the database or the UI objects (scripts/create_ui_objects.py) are absent."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def _ready() -> bool:
    try:
        from sqlalchemy import text
        from src.utils.db import get_engine
        with get_engine().connect() as c:
            return bool(c.execute(text("SELECT to_regclass('ui.payments_usd') IS NOT NULL AND to_regclass('ui.core_txn_usd') IS NOT NULL AND to_regclass('monitoring.anomaly_investigations') IS NOT NULL")).scalar())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _ready(), reason="database / UI objects not available")


@pytest.fixture(scope="module")
def client():
    from src.api.main import app
    return TestClient(app)


def sql(query: str, **p):
    from sqlalchemy import text
    from src.utils.db import get_engine
    with get_engine().connect() as c:
        return c.execute(text(query), p).fetchall()


R = "from=2024-01-01&to=2024-12-31"


def test_overview_payment_kpis_match_sql(client):
    j = client.get(f"/v1/overview?{R}").json()
    k = {x["key"]: x for x in j["headline"] + j["secondary"]}
    n, ap, de = sql("""SELECT count(*), sum(authorized::int), sum(declined::int) FROM intermediate.int_payment_outcomes WHERE payment_date BETWEEN '2024-01-01' AND '2024-12-31'""")[0]
    assert k["payment_volume"]["value"] == n
    assert k["approval_rate"]["value"] == pytest.approx(ap / (ap + de))
    assert k["decline_rate"]["value"] == pytest.approx(de / (ap + de))
    assert k["approval_rate"]["value"] + k["decline_rate"]["value"] == pytest.approx(1.0)


def test_overview_value_is_usd_converted_and_matches_sql(client):
    j = client.get(f"/v1/overview?{R}").json()
    v = sql("SELECT sum(amount_usd) FROM ui.payments_usd WHERE payment_date BETWEEN '2024-01-01' AND '2024-12-31'")[0][0]
    assert {x["key"]: x for x in j["headline"]}["payment_value_usd"]["value"] == pytest.approx(float(v))
    # converting must matter: summing raw amounts across currencies gives a different (wrong) total
    raw = sql("SELECT sum(amount) FROM ui.payments_usd WHERE payment_date BETWEEN '2024-01-01' AND '2024-12-31'")[0][0]
    assert float(raw) > float(v) * 1.5


def test_period_over_period_delta_is_correct(client):
    j = client.get(f"/v1/overview?{R}").json()
    assert j["range"]["prior_from"] == "2023-01-31" or j["range"]["days"] == 366
    vol = {x["key"]: x for x in j["headline"]}["payment_volume"]
    assert vol["delta"] == pytest.approx((vol["value"] - vol["prior"]) / vol["prior"] * 100)
    ar = {x["key"]: x for x in j["headline"]}["approval_rate"]
    assert ar["delta_unit"] == "pp" and ar["delta"] == pytest.approx((ar["value"] - ar["prior"]) * 100)


def test_core_and_anomaly_kpis_match_sql(client):
    j = client.get(f"/v1/overview?{R}").json()
    k = {x["key"]: x for x in j["headline"] + j["secondary"]}
    n, failed = sql("SELECT count(*), sum((transaction_status='Failed')::int) FROM warehouse.fact_transactions WHERE transaction_timestamp::date BETWEEN '2024-01-01' AND '2024-12-31'")[0]
    a = sql("SELECT count(*) FROM monitoring.transaction_anomalies WHERE transaction_timestamp::date BETWEEN '2024-01-01' AND '2024-12-31'")[0][0]
    assert k["core_volume"]["value"] == n
    assert k["core_failure_rate"]["value"] == pytest.approx(failed / n)
    assert k["anomaly_rate"]["value"] == pytest.approx(a / n)


def test_bad_date_range_rejected(client):
    assert client.get("/v1/overview?from=2025-02-01&to=2025-01-01").status_code == 422


def test_lifecycle_flow_is_conserved(client):
    j = client.get(f"/v1/payments/lifecycle?{R}").json()
    out: dict = {}
    inn: dict = {}
    for l in j["links"]:
        out[l["source"]] = out.get(l["source"], 0) + l["value"]
        inn[l["target"]] = inn.get(l["target"], 0) + l["value"]
    for node in ("Approved", "Cleared", "Settled"):
        assert out.get(node, 0) == inn[node]
    assert out["Authorization attempts"] == j["totals"]["attempts"]


def test_payment_filters_change_results_and_match_sql(client):
    j = client.get(f"/v1/payments/kpis?{R}&channel=E-commerce&status=declined").json()
    n = sql("SELECT count(*) FROM ui.payments_usd WHERE payment_date BETWEEN '2024-01-01' AND '2024-12-31' AND channel = 'E-commerce' AND declined")[0][0]
    assert j["payments"] == n and j["approved"] == 0


def test_table_pagination_sort_and_filter(client):
    a = client.get("/v1/tables/transactions?size=10&page=0&sort=amount_usd:desc").json()
    b = client.get("/v1/tables/transactions?size=10&page=1&sort=amount_usd:desc").json()
    assert a["total"] == sql("SELECT count(*) FROM ui.core_txn_usd WHERE d BETWEEN '2023-01-01' AND '2025-12-31'")[0][0]
    assert len(a["rows"]) == 10 and a["rows"][0]["transaction_id"] != b["rows"][0]["transaction_id"]
    vals = [r["amount_usd"] for r in a["rows"]]
    assert vals == sorted(vals, reverse=True)
    f = json.dumps([{"id": "status", "op": "in", "value": ["Failed"]}])
    j = client.get("/v1/tables/transactions", params={"filters": f, "size": 5}).json()
    assert j["total"] == sql("SELECT count(*) FROM ui.core_txn_usd WHERE status = 'Failed' AND d BETWEEN '2023-01-01' AND '2025-12-31'")[0][0]
    assert {r["status"] for r in j["rows"]} == {"Failed"}
    g = client.get("/v1/tables/transactions", params={"filters": json.dumps([{"id": "amount_usd", "op": "between", "value": [100, 200]}]), "size": 50}).json()
    assert all(100 <= r["amount_usd"] <= 200 for r in g["rows"])


def test_table_search_and_rejects_unsafe_input(client):
    j = client.get("/v1/tables/customers?q=CUST-00000&size=5").json()
    assert j["total"] > 0 and all("CUST-00000" in r["customer_id"] for r in j["rows"])
    assert client.get("/v1/tables/transactions?sort=amount;DROP TABLE x").status_code == 422
    assert client.get("/v1/tables/transactions", params={"filters": json.dumps([{"id": "amount; DROP", "op": "eq", "value": 1}])}).status_code == 422
    assert client.get("/v1/tables/transactions", params={"filters": json.dumps([{"id": "amount_usd", "op": "contains", "value": 1}])}).status_code == 422
    assert client.get("/v1/tables/not_a_table").status_code == 404
    assert client.get("/v1/tables/transactions?size=500").status_code == 422


def test_export_csv_and_xlsx_respect_filters(client):
    f = json.dumps([{"id": "status", "op": "eq", "value": "Reversed"}])
    r = client.get("/v1/tables/transactions/export", params={"fmt": "csv", "filters": f, "limit": 100})
    lines = r.text.strip().splitlines()
    assert r.status_code == 200 and lines[0].startswith("transaction_id,ts") and len(lines) == 101 and all("Reversed" in l for l in lines[1:])
    x = client.get("/v1/tables/transactions/export", params={"fmt": "xlsx", "limit": 50})
    assert x.status_code == 200 and x.content[:2] == b"PK"


def test_anomaly_summary_and_comparison_consistent(client):
    s = client.get("/v1/anomalies/summary").json()
    assert s["alerts"] == s["high"] + s["medium"] + s["low"] == sum(m["alerts"] for m in s["methods"])
    c = client.get("/v1/anomalies/comparison").json()
    any_ = next(d for d in c["detectors"] if d["detector"] == "Any detector")
    assert 0 <= any_["recall"] <= 1 and any_["alerts"] == s["alerts"] and "SYNTHETIC" in c["note"]


def test_investigation_status_roundtrip_and_validation(client):
    aid = sql("SELECT anomaly_id FROM monitoring.transaction_anomalies ORDER BY anomaly_id LIMIT 1")[0][0]
    try:
        assert client.put(f"/v1/anomalies/{aid}/investigation", json={"status": "FALSE_POSITIVE", "note": "pytest"}).status_code == 200
        assert client.get(f"/v1/anomalies/{aid}").json()["investigation_status"] == "FALSE_POSITIVE"
        assert client.put(f"/v1/anomalies/{aid}/investigation", json={"status": "NOT_A_STATUS"}).status_code == 422
        assert client.put("/v1/anomalies/999999999/investigation", json={"status": "NEW"}).status_code == 404
    finally:
        client.put(f"/v1/anomalies/{aid}/investigation", json={"status": "NEW"})


def test_rfm_covers_all_customers(client):
    j = client.get("/v1/customers/rfm?from=2023-01-01&to=2025-12-31").json()
    assert sum(s["customers"] for s in j["segments"]) + j["customers_without_completed_txn_in_range"] == j["customers_total"]
    assert {s["segment"] for s in j["segments"]} <= {"Champions", "Loyal", "At risk", "Potential loyalists", "Need attention", "Hibernating", "Promising"}


def test_clv_is_an_estimate_with_assumptions(client):
    j = client.get("/v1/customers/clv?revenue_rate=0.02&lifetime_months=24").json()
    assert j["assumptions"]["revenue_rate"] == 0.02 and "ESTIMATE" in j["note"]
    assert all(t["clv"] == pytest.approx(t["monthly_value"] * 0.02 * 24) for t in j["top"])


def test_branch_map_uses_city_centroids_and_discloses_it(client):
    j = client.get("/v1/branches/map").json()
    assert "not branch addresses" in j["note"]
    total = sql("SELECT count(*) FROM warehouse.dim_branch")[0][0]
    assert sum(m["branches"] for m in j["markers"]) + len(j["unmapped_cities"]) >= total - 5
    assert all(-90 < m["lat"] < 90 and -180 < m["lon"] < 0 for m in j["markers"])  # US longitudes


def test_observability_reports_real_sources_and_disconnected_airflow(client, monkeypatch):
    monkeypatch.delenv("AIRFLOW_BASE_URL", raising=False)
    a = client.get("/v1/observability/airflow").json()
    assert a["connected"] is False and a["definitions"] and "no run status" in a["reason"]
    runs = client.get("/v1/observability/pipelines").json()
    assert sum(s["runs"] for s in runs["stats"]) == sql("SELECT count(*) FROM audit.pipeline_runs")[0][0]
    assert client.get("/v1/observability/dbt").json()["available"] in (True, False)


def test_api_key_is_enforced_when_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret-for-test")
    assert client.get("/v1/meta").status_code == 401
    assert client.get("/v1/meta", headers={"X-API-Key": "secret-for-test"}).status_code == 200


# ---- real-vs-synthetic benchmarks ----
def test_benchmarks_dashboard_metrics_match_independent_sql(client):
    d = client.get("/v1/benchmarks").json()
    row = {r["key"]: r for r in d["scorecard"]}
    n = dict(sql("""SELECT channel, count(*) FROM ui.payments_usd WHERE channel IN ('POS Chip','POS Contactless','E-commerce')
                    AND NOT coalesce(synthetic_fraud_label, false) GROUP BY 1"""))
    assert row["cnp_share"]["dashboard"] == pytest.approx(n["E-commerce"] / sum(n.values()))
    pos = sql("""SELECT avg(amount_usd) FROM ui.payments_usd WHERE channel IN ('POS Chip','POS Contactless') AND NOT coalesce(synthetic_fraud_label, false)""")[0][0]
    assert row["avg_ticket_usd.pos"]["dashboard"] == pytest.approx(float(pos))
    y = dict(sql("""SELECT EXTRACT(year FROM payment_date)::int, count(*) FROM ui.payments_usd WHERE channel IN ('POS Chip','POS Contactless','E-commerce')
                    AND NOT coalesce(synthetic_fraud_label, false) GROUP BY 1"""))
    assert row["annual_volume_growth"]["dashboard"] == pytest.approx(y[2025] / y[2024] - 1)


def test_benchmarks_real_values_come_from_the_sbp_table_and_statuses_are_honest(client):
    d = client.get("/v1/benchmarks").json()
    row = {r["key"]: r for r in d["scorecard"]}
    assert row["cnp_share"]["real"] == pytest.approx(16.4 / (143.2 + 16.4), rel=1e-3)
    assert row["avg_ticket_usd.pos"]["real"] == pytest.approx(5573 / d["real"]["usd_pkr"], rel=1e-3)
    assert row["decline_rate"]["real"] is None and row["decline_rate"]["status_dashboard"] == "no real target"
    # the dashboard's own synthetic data is NOT calibrated and the page must say so
    assert row["avg_ticket_usd.pos"]["status_dashboard"] == "far off"
    assert "not calibrated" in d["note"].lower()
    assert d["not_calibrated"] and d["assumptions"]
    if d["calibrated_available"]:
        assert row["cnp_share"]["status_calibrated"] == "matches"
        assert len(d["real_channels"]) >= 9
