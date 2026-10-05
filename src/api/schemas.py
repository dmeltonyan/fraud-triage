"""Shapes of the API's requests and responses. FastAPI uses these to check input,
return clear 422 errors for bad requests, and build the /docs page."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TransactionId = Field(pattern=r"^[0-9a-f]{32}$", description="32-character transaction ID (trans_num)")


class ScoreRequest(BaseModel):
    transaction_id: str = TransactionId


class ExpectedCosts(BaseModel):
    approve: float = Field(description="probability x amount")
    review: float = Field(description="review cost from config.yaml")
    block: float = Field(description="(1 - probability) x false-decline cost")


class ScoreResponse(BaseModel):
    transaction_id: str
    timestamp: datetime
    amount: float
    merchant: str
    category: str
    fraud_probability: float = Field(description="calibrated probability of fraud")
    action: Literal["approve", "review", "block"] = Field(description="decision under the day's review budget")
    expected_costs: ExpectedCosts
    reasons: list[str] = Field(description="top three reasons behind the score")


class QueueItem(BaseModel):
    transaction_id: str
    timestamp: datetime
    merchant: str
    category: str
    amount: float
    fraud_probability: float
    expected_loss: float = Field(description="expected fraud loss if approved: probability x amount")
    loss_prevented: float = Field(description="expected dollars a review saves over the next-best action")


class QueueResponse(BaseModel):
    date: str
    review_budget: int
    cases: list[QueueItem]


class ReviewRequest(BaseModel):
    decision: Literal["fraud", "legitimate"]
    note: str | None = Field(default=None, max_length=500)


class ReviewResponse(BaseModel):
    transaction_id: str
    decision: Literal["fraud", "legitimate"]
    note: str | None
    reviewed_at: datetime
