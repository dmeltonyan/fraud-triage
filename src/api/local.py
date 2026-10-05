"""Local development mode (DATA_BACKEND=duckdb): scores transactions live with the
trained model, reading the full dataset from DuckDB."""

from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query, Request

from src.api.schemas import QueueResponse, ReviewRequest, ReviewResponse, ScoreRequest, ScoreResponse
from src.api.service import FraudService, NotFound
from src.config import load_config
from src.load import DB_PATH

router = APIRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts: load config and the model a single time.
    app.state.service = FraudService(DB_PATH, load_config())
    yield


def get_service(request: Request) -> FraudService:
    return request.app.state.service


Service = Annotated[FraudService, Depends(get_service)]


@router.post("/score", response_model=ScoreResponse)
def score(body: ScoreRequest, service: Service):
    """Calibrated fraud probability, chosen action, expected cost of each action, and top three reasons."""
    try:
        return service.score(body.transaction_id)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get("/queue", response_model=QueueResponse)
def queue(service: Service, date: Annotated[date, Query(description="Day to list, as YYYY-MM-DD")]):
    """That day's review cases, largest expected loss first."""
    try:
        return service.queue(date)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.post("/review/{transaction_id}", response_model=ReviewResponse)
def review(
    transaction_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$", description="32-character transaction ID")],
    body: ReviewRequest,
    service: Service,
):
    """Save an analyst's decision (fraud or legitimate) and an optional note."""
    try:
        return service.save_review(transaction_id, body.decision, body.note)
    except NotFound as error:
        raise HTTPException(status_code=404, detail=str(error))
