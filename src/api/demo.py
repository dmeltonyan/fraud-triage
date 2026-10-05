"""Production demo mode (DATA_BACKEND=postgres): serves the precomputed sample from
Supabase Postgres. Scoring happened offline (src/export_demo.py), so nothing here
imports LightGBM, SHAP, pandas or DuckDB.

The public can call POST /review, so it is protected by: strict input checks (the
Pydantic models), a per-IP rate limit, a cap on total reviews, and a script that
empties the reviews table (python -m src.api.reset_reviews).
"""

import json
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query, Request
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, MetaData, Numeric, String, Table, Text,
    create_engine, func, insert, select,
)

from src.api.schemas import DemoReviewResponse, QueueResponse, ReviewRequest, TransactionDetail
from src.api.ratelimit import RateLimiter
from src.config import PROJECT_ROOT, database_url, load_config

STATS_PATH = PROJECT_ROOT / "reports" / "policy_results.json"

# The two tables from sql/schema.sql, described for SQLAlchemy so queries are built
# in Python rather than pasted together as strings.
metadata = MetaData()
transactions_demo = Table(
    "transactions_demo", metadata,
    Column("transaction_id", String(32), primary_key=True),
    Column("transaction_time", DateTime, nullable=False),
    Column("merchant", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("amount", Numeric(10, 2, asdecimal=False), nullable=False),
    Column("city", Text, nullable=False),
    Column("state", String(2), nullable=False),
    Column("fraud_probability", Float, nullable=False),
    Column("action", Text, nullable=False),
    Column("cost_approve", Float, nullable=False),
    Column("cost_review", Float, nullable=False),
    Column("cost_block", Float, nullable=False),
    Column("loss_prevented", Float, nullable=False),
    Column("reason_1", Text, nullable=False),
    Column("reason_2", Text, nullable=False),
    Column("reason_3", Text, nullable=False),
    Column("is_fraud", Boolean, nullable=False),
)
reviews = Table(
    "reviews", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("transaction_id", String(32), ForeignKey("transactions_demo.transaction_id"), nullable=False),
    Column("decision", Text, nullable=False),
    Column("note", Text),
    Column("reviewed_at", DateTime(timezone=True), nullable=False),
)


class DemoRepository:
    """All database reads and writes for the demo."""

    def __init__(self, engine):
        self.engine = engine

    def queue(self, day: date) -> list[dict]:
        start = datetime.combine(day, time())
        t = transactions_demo.c
        query = (
            select(transactions_demo)
            .where(t.action == "review", t.transaction_time >= start, t.transaction_time < start + timedelta(days=1))
            .order_by(t.cost_approve.desc())  # expected loss if approved
        )
        with self.engine.connect() as con:
            return [dict(row._mapping) for row in con.execute(query)]

    def transaction(self, transaction_id: str) -> dict | None:
        query = select(transactions_demo).where(transactions_demo.c.transaction_id == transaction_id)
        with self.engine.connect() as con:
            row = con.execute(query).first()
        return dict(row._mapping) if row else None

    def review_count(self) -> int:
        with self.engine.connect() as con:
            return con.execute(select(func.count()).select_from(reviews)).scalar_one()

    def save_review(self, transaction_id: str, decision: str, note: str | None) -> dict:
        reviewed_at = datetime.now(timezone.utc)
        with self.engine.begin() as con:
            con.execute(insert(reviews).values(
                transaction_id=transaction_id, decision=decision, note=note, reviewed_at=reviewed_at,
            ))
        return {"transaction_id": transaction_id, "decision": decision, "note": note, "reviewed_at": reviewed_at}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup. pool_pre_ping checks a pooled connection still works
    # before using it, since hosted databases close idle connections.
    config = load_config()
    app.state.repository = DemoRepository(create_engine(database_url(), pool_pre_ping=True))
    app.state.config = config
    app.state.stats = json.loads(STATS_PATH.read_text())
    app.state.limiter = RateLimiter(config["api"]["review_rate_limit_per_minute"])
    yield


router = APIRouter()


def get_repository(request: Request) -> DemoRepository:
    return request.app.state.repository


Repository = Annotated[DemoRepository, Depends(get_repository)]
TransactionIdPath = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$", description="32-character transaction ID")]


def detail(row: dict) -> dict:
    return {
        "transaction_id": row["transaction_id"],
        "timestamp": row["transaction_time"],
        "merchant": row["merchant"],
        "category": row["category"],
        "amount": row["amount"],
        "city": row["city"],
        "state": row["state"],
        "fraud_probability": row["fraud_probability"],
        "action": row["action"],
        "expected_costs": {"approve": row["cost_approve"], "review": row["cost_review"], "block": row["cost_block"]},
        "loss_prevented": row["loss_prevented"],
        "reasons": [row["reason_1"], row["reason_2"], row["reason_3"]],
    }


@router.get("/queue", response_model=QueueResponse)
def queue(request: Request, repository: Repository, date: Annotated[date, Query(description="Day to list, as YYYY-MM-DD")]):
    """That day's review cases, largest expected loss first."""
    rows = repository.queue(date)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No review cases on {date}. The demo covers 2020-10-01 to 2020-12-31.")
    return {
        "date": date.isoformat(),
        "review_budget": request.app.state.config["review"]["daily_review_budget"],
        "cases": [
            {
                "transaction_id": r["transaction_id"],
                "timestamp": r["transaction_time"],
                "merchant": r["merchant"],
                "category": r["category"],
                "amount": r["amount"],
                "fraud_probability": r["fraud_probability"],
                "expected_loss": r["cost_approve"],
                "loss_prevented": r["loss_prevented"],
            }
            for r in rows
        ],
    }


@router.get("/transactions/{transaction_id}", response_model=TransactionDetail)
def transaction(transaction_id: TransactionIdPath, repository: Repository):
    """Full detail for one case. The true label is only returned after a review."""
    row = repository.transaction(transaction_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found.")
    return detail(row)


@router.post("/review/{transaction_id}", response_model=DemoReviewResponse)
def review(transaction_id: TransactionIdPath, body: ReviewRequest, request: Request, repository: Repository):
    """Save an analyst's decision and return the true label."""
    if not request.app.state.limiter.allow(request.client.host):
        raise HTTPException(status_code=429, detail="Too many reviews from your address. Please wait a minute.")
    if repository.review_count() >= request.app.state.config["api"]["max_total_reviews"]:
        raise HTTPException(status_code=503, detail="The demo has reached its review limit. It is reset regularly.")
    row = repository.transaction(transaction_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found.")
    saved = repository.save_review(transaction_id, body.decision, body.note)
    return {**saved, "is_fraud": row["is_fraud"], "correct": (body.decision == "fraud") == row["is_fraud"]}


@router.get("/stats")
def stats(request: Request):
    """The policy comparison results (reports/policy_results.json)."""
    return request.app.state.stats
