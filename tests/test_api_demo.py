"""Postgres (production demo) mode, tested against a temporary SQLite database
through the same SQLAlchemy code."""

import os
import subprocess
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from src.api.demo import DemoRepository, metadata, reviews, transactions_demo
from src.api.main import create_app
from src.api.ratelimit import RateLimiter
from src.config import PROJECT_ROOT


def tid(n: int) -> str:
    return f"{n:032x}"


def case(n, time, action, cost_approve, is_fraud):
    return {
        "transaction_id": tid(n), "transaction_time": datetime.fromisoformat(time), "merchant": "Kirlin and Sons",
        "category": "misc_net", "amount": 400.0, "city": "Freedom", "state": "WY", "fraud_probability": 0.05,
        "action": action, "cost_approve": cost_approve, "cost_review": 5.0, "cost_block": 9.5, "loss_prevented": 4.5,
        "reason_1": "one", "reason_2": "two", "reason_3": "three", "is_fraud": is_fraud,
    }


ROWS = [
    case(1, "2020-10-01 09:00:00", "review", 20.0, False),
    case(2, "2020-10-01 10:00:00", "review", 60.0, True),
    case(3, "2020-10-01 11:00:00", "approve", 0.1, False),
    case(4, "2020-10-02 09:00:00", "review", 30.0, True),
]


@pytest.fixture
def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'demo.db'}")
    metadata.create_all(engine)
    with engine.begin() as con:
        con.execute(insert(transactions_demo), ROWS)

    app = create_app("postgres")
    # Fill in what the startup step would, without connecting to Supabase.
    app.state.repository = DemoRepository(engine)
    app.state.config = {"review": {"daily_review_budget": 30}, "api": {"review_rate_limit_per_minute": 3, "max_total_reviews": 5}}
    app.state.stats = {"default_budget": 30}
    app.state.limiter = RateLimiter(3)
    return TestClient(app), engine, app


def test_health(setup):
    client, _, _ = setup
    assert client.get("/health").json() == {"status": "ok", "backend": "postgres"}


def test_queue_lists_only_that_days_reviews_by_expected_loss(setup):
    client, _, _ = setup
    body = client.get("/queue", params={"date": "2020-10-01"}).json()
    assert [c["transaction_id"] for c in body["cases"]] == [tid(2), tid(1)]
    assert body["cases"][0]["expected_loss"] == 60.0
    assert client.get("/queue", params={"date": "2020-11-30"}).status_code == 404
    assert client.get("/queue", params={"date": "not-a-date"}).status_code == 422


def test_transaction_detail_hides_the_true_label(setup):
    client, _, _ = setup
    body = client.get(f"/transactions/{tid(2)}").json()
    assert body["reasons"] == ["one", "two", "three"]
    assert body["expected_costs"] == {"approve": 60.0, "review": 5.0, "block": 9.5}
    assert "is_fraud" not in body
    assert client.get(f"/transactions/{tid(99)}").status_code == 404
    assert client.get("/transactions/bad-id").status_code == 422


def test_review_saves_and_reveals_the_true_label(setup):
    client, engine, _ = setup
    body = client.post(f"/review/{tid(2)}", json={"decision": "legitimate", "note": "looked fine"}).json()
    assert body["is_fraud"] is True
    assert body["correct"] is False
    with engine.connect() as con:
        saved = con.execute(select(reviews.c.transaction_id, reviews.c.decision, reviews.c.note)).all()
    assert saved == [(tid(2), "legitimate", "looked fine")]


def test_review_input_validation(setup):
    client, _, _ = setup
    assert client.post(f"/review/{tid(99)}", json={"decision": "fraud"}).status_code == 404
    assert client.post(f"/review/{tid(1)}", json={"decision": "maybe"}).status_code == 422
    assert client.post(f"/review/{tid(1)}", json={"decision": "fraud", "note": "x" * 501}).status_code == 422
    assert client.post(f"/review/{tid(1)}", json={"decision": "fraud", "extra": 1}).status_code == 200  # extra fields ignored


def test_review_rate_limit_per_address(setup):
    client, _, _ = setup
    codes = [client.post(f"/review/{tid(1)}", json={"decision": "fraud"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_review_cap_on_total_reviews(setup):
    client, _, app = setup
    app.state.limiter = RateLimiter(100)
    codes = [client.post(f"/review/{tid(1)}", json={"decision": "fraud"}).status_code for _ in range(6)]
    assert codes == [200] * 5 + [503]


def test_stats(setup):
    client, _, _ = setup
    assert client.get("/stats").json() == {"default_budget": 30}


def test_rate_limiter_window():
    now = [0.0]
    limiter = RateLimiter(2, window_seconds=60, clock=lambda: now[0])
    assert [limiter.allow("a"), limiter.allow("a"), limiter.allow("a")] == [True, True, False]
    assert limiter.allow("b")  # each address has its own limit
    now[0] = 60.0
    assert limiter.allow("a")  # old requests have left the window


def test_cors_allows_only_configured_origins(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.vercel.app")
    client = TestClient(create_app("postgres"))
    allowed = client.get("/health", headers={"Origin": "https://example.vercel.app"})
    blocked = client.get("/health", headers={"Origin": "https://evil.example"})
    assert allowed.headers.get("access-control-allow-origin") == "https://example.vercel.app"
    assert "access-control-allow-origin" not in blocked.headers


def test_production_mode_never_imports_the_ml_stack():
    # A fresh Python process, so imports made by other tests don't count.
    code = (
        "import sys; import src.api.main; "
        "heavy = [m for m in ('lightgbm', 'shap', 'sklearn', 'pandas', 'duckdb') if m in sys.modules]; "
        "print(','.join(heavy))"
    )
    env = {**os.environ, "DATA_BACKEND": "postgres"}
    result = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
