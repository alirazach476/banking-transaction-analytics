import pytest
from fastapi.testclient import TestClient

from src.api.main import app

c = TestClient(app)


def _db_ok():
    try:
        return c.get("/kpis/summary").status_code == 200
    except Exception:
        return False


def test_health():
    assert c.get("/health").json()["status"] == "ok"


def test_auth_enforced(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    assert c.get("/models").status_code == 401
    assert c.get("/models", headers={"X-API-Key": "secret"}).status_code == 200


def test_score_decline_risky_higher():
    safe = c.post("/score/decline", json={"amount": 20, "hour": 14}).json()["decline_probability"]
    risky = c.post("/score/decline", json={"amount": 2000, "hour": 2, "is_international": True,
                                           "channel": "E-commerce"}).json()["decline_probability"]
    assert 0 <= safe < risky <= 1


def test_score_fraud_burst_scores_higher():
    base = c.post("/score/fraud", json={"amount": 30, "hour": 14}).json()["fraud_probability"]
    burst = c.post("/score/fraud", json={"amount": 300, "hour": 3, "channel": "E-commerce", "foreign_merchant": True,
                                         "is_international": True, "card_txn_60m": 8,
                                         "amt_vs_card_mean": 6}).json()["fraud_probability"]
    assert burst > base


def test_validation_rejects_bad_input():
    assert c.post("/score/decline", json={"amount": -1, "hour": 30}).status_code == 422


@pytest.mark.skipif(not _db_ok(), reason="database/marts unavailable")
def test_kpis_and_queue():
    s = c.get("/kpis/summary").json()
    assert 0 < s["approval_rate"] < 1
    assert len(c.get("/kpis/daily?limit=5").json()) == 5
    assert c.get("/decline-reasons").status_code == 200
    assert c.get("/reconciliation/queue?limit=3").status_code == 200


def test_rate_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "3")
    from src.api import main
    main._hits.clear()
    codes = [c.get("/models", headers={"X-API-Key": "rl-test"}).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
    assert c.get("/health").status_code == 200  # exempt
    main._hits.clear()


@pytest.mark.skipif(not _db_ok(), reason="database/marts unavailable")
def test_fraud_by_card_computes_features():
    from src.api import main
    main._hits.clear()
    row = main.q("SELECT card_id, authorization_ts FROM intermediate.int_card_payments ORDER BY authorization_ts DESC LIMIT 1")[0]
    r = c.post("/score/fraud/card", json={"card_id": row["card_id"], "authorization_ts": row["authorization_ts"].isoformat(),
                                          "amount": 50, "channel": "E-commerce"})
    assert r.status_code == 200
    f = r.json()["computed_features"]
    assert f["card_txn_60m"] >= 1 and f["prior_payments_on_card"] >= 1
    assert 0 <= r.json()["fraud_probability"] <= 1
