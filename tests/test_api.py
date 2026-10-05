import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app, get_service
from src.api.service import FraudService

CONFIG = {
    "costs": {"review_cost_usd": 5.0, "false_decline_cost_usd": 10.0},
    "review": {"daily_review_budget": 2},
}
# Fake probabilities by amount, so expected costs are easy to check by hand.
FAKE_P = {20.0: 0.001, 400.0: 0.05, 450.0: 0.02, 300.0: 0.02, 900.0: 0.95}


def tid(n: int) -> str:
    return f"{n:032x}"  # a valid 32-character hex ID


ROWS = [  # (id, time, amount)
    (tid(1), "2020-10-01 09:00:00", 20.0),   # approve
    (tid(2), "2020-10-01 10:00:00", 400.0),  # review-worthy: prevents $4.50 (vs block)
    (tid(3), "2020-10-01 11:00:00", 450.0),  # review-worthy: prevents $4.00 (vs approve $9)
    (tid(4), "2020-10-01 12:00:00", 300.0),  # review-worthy: prevents $1.00 -> outside budget of 2
    (tid(5), "2020-10-01 23:00:00", 900.0),  # block
]


class FakeService(FraudService):
    def probabilities(self, df):
        return df["amt"].map(FAKE_P)

    def reasons(self, df):
        return [["reason one", "reason two", "reason three"] for _ in df.index]


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "test.duckdb"
    features = pd.DataFrame(
        {
            "trans_num": [r[0] for r in ROWS],
            "cc_num": 1,
            "trans_date_trans_time": pd.to_datetime([r[1] for r in ROWS]),
            "is_fraud": 0,
            "amt": [r[2] for r in ROWS],
            "txn_count_1h": 0,
            "txn_count_24h": 0,
            "amt_to_median_ratio": 1.0,
            "hour_of_day": 10,
            "day_of_week": 4,
            "distance_km": 50.0,
            "category": "misc_net",
        }
    )
    transactions = pd.DataFrame({"trans_num": features["trans_num"], "merchant": "fraud_Test Merchant"})
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE TABLE features AS SELECT * FROM features")
        con.execute("CREATE TABLE transactions AS SELECT * FROM transactions")

    service = FakeService(db, CONFIG, load_models=False)
    app.dependency_overrides[get_service] = lambda: service
    yield TestClient(app)  # not used as a context manager, so the real model isn't loaded
    app.dependency_overrides.clear()


def test_score_returns_probability_action_costs_and_reasons(client):
    body = client.post("/score", json={"transaction_id": tid(2)}).json()
    assert body["fraud_probability"] == pytest.approx(0.05)
    assert body["action"] == "review"
    assert body["expected_costs"] == pytest.approx({"approve": 20.0, "review": 5.0, "block": 9.5})
    assert body["reasons"] == ["reason one", "reason two", "reason three"]
    assert body["merchant"] == "fraud_Test Merchant"


def test_score_uses_the_days_budget(client):
    # Review would be cheapest, but the two review slots go to bigger savings: fall back to approve.
    assert client.post("/score", json={"transaction_id": tid(4)}).json()["action"] == "approve"
    assert client.post("/score", json={"transaction_id": tid(5)}).json()["action"] == "block"


def test_score_unknown_id_is_404(client):
    response = client.post("/score", json={"transaction_id": tid(99)})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_score_badly_formed_id_is_422(client):
    assert client.post("/score", json={"transaction_id": "not-an-id"}).status_code == 422
    assert client.post("/score", json={}).status_code == 422


def test_queue_lists_review_cases_by_expected_loss(client):
    body = client.get("/queue", params={"date": "2020-10-01"}).json()
    assert body["review_budget"] == 2
    assert [c["transaction_id"] for c in body["cases"]] == [tid(2), tid(3)]  # $20 then $9 expected loss
    assert body["cases"][0]["expected_loss"] == pytest.approx(20.0)
    assert body["cases"][0]["loss_prevented"] == pytest.approx(4.5)


def test_queue_errors(client):
    empty = client.get("/queue", params={"date": "2021-06-01"})
    assert empty.status_code == 404
    assert "2019-01-01 to 2020-12-31" in empty.json()["detail"]
    assert client.get("/queue", params={"date": "October 1st"}).status_code == 422
    assert client.get("/queue").status_code == 422


def test_review_is_saved(client, tmp_path):
    response = client.post(f"/review/{tid(2)}", json={"decision": "fraud", "note": "card reported stolen"})
    assert response.status_code == 200
    assert response.json()["decision"] == "fraud"
    with duckdb.connect(str(tmp_path / "test.duckdb")) as con:
        saved = con.execute("SELECT transaction_id, decision, note FROM reviews").fetchall()
    assert saved == [(tid(2), "fraud", "card reported stolen")]


def test_review_errors(client):
    assert client.post(f"/review/{tid(99)}", json={"decision": "fraud"}).status_code == 404
    assert client.post(f"/review/{tid(2)}", json={"decision": "maybe"}).status_code == 422
    assert client.post(f"/review/{tid(2)}", json={"decision": "fraud", "note": "x" * 501}).status_code == 422
    assert client.post("/review/bad-id", json={"decision": "fraud"}).status_code == 422
