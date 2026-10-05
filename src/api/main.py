"""Scoring and review API, in one of two modes set by the DATA_BACKEND environment variable:

  duckdb    (default, local development) scores transactions live with the trained model
  postgres  (production demo) serves precomputed results from Supabase; never imports
            LightGBM, SHAP, pandas or DuckDB

Run from the project root with:  uvicorn src.api.main:app --reload
then open http://127.0.0.1:8000/docs
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import load_env


def allowed_origins() -> list[str]:
    """Websites allowed to call the API from a browser, from ALLOWED_ORIGINS (comma-separated)."""
    return [origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",") if origin.strip()]


def create_app(backend: str | None = None) -> FastAPI:
    load_env()
    backend = backend or os.environ.get("DATA_BACKEND", "duckdb")
    # Import only the chosen mode, so production never loads the machine-learning stack.
    if backend == "postgres":
        from src.api import demo as mode
    elif backend == "duckdb":
        from src.api import local as mode
    else:
        raise ValueError(f"DATA_BACKEND must be 'duckdb' or 'postgres', not {backend!r}")

    app = FastAPI(
        title="Fraud Triage API",
        description=f"Mode: {backend}. Review queue, case details and analyst decisions for simulated card transactions.",
        lifespan=mode.lifespan,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=allowed_origins(), allow_methods=["GET", "POST"], allow_headers=["Content-Type"]
    )

    @app.get("/health")
    def health():
        """Lets the hosting service check the server is up."""
        return {"status": "ok", "backend": backend}

    app.include_router(mode.router)
    return app


app = create_app()
