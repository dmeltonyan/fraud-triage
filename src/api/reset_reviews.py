"""Empty the demo's reviews table in Supabase.

Run from the project root with:  python -m src.api.reset_reviews
"""

from sqlalchemy import create_engine, delete

from src.api.demo import reviews
from src.config import database_url


def main() -> None:
    engine = create_engine(database_url())
    with engine.begin() as con:
        deleted = con.execute(delete(reviews)).rowcount
    print(f"Deleted {deleted} reviews.")


if __name__ == "__main__":
    main()
