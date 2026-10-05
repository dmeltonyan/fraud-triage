"""Settings shared across the project. Only light imports (no pandas, DuckDB or
LightGBM), so the production API can use this module too."""

import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def load_env() -> None:
    """Read .env into environment variables if the file exists (local runs). On a
    hosting service the variables are set directly and there is no .env file."""
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")


def database_url() -> str:
    """DATABASE_URL, in the form SQLAlchemy needs for the psycopg (version 3) driver."""
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url or "user:password@host" in url:
        raise SystemExit("DATABASE_URL is not set. Copy .env.example to .env and paste your Supabase connection string.")
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url
