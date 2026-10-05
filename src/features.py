"""Build one row of model features per transaction, using only past data.

Run from the project root with:  python -m src.features
"""

import duckdb

from src.load import DB_PATH

EARTH_RADIUS_KM = 6371.0  # mean Earth radius, a physical constant

# The only columns a model may use. Everything else in the features table is
# an ID, a timestamp or the label. Gender, date of birth, age, name and address
# are never here (CLAUDE.md rule 9); home lat/long are used only inside
# distance_km.
FEATURE_COLUMNS = [
    "amt",
    "txn_count_1h",
    "txn_count_24h",
    "amt_to_median_ratio",
    "hour_of_day",
    "day_of_week",
    "distance_km",
    "category",
]

# Each historical window looks at the same card, in time order, and stops
# 1 microsecond before the current transaction. Ending it there (instead of at
# CURRENT ROW) means a transaction never sees itself, or another transaction on
# the same card with the identical timestamp.
FEATURES_SQL = """
SELECT
    trans_num,
    cc_num,
    trans_date_trans_time,
    is_fraud,

    amt,

    COUNT(*) OVER (
        card_history
        RANGE BETWEEN INTERVAL 1 HOUR PRECEDING AND INTERVAL 1 MICROSECOND PRECEDING
    ) AS txn_count_1h,

    COUNT(*) OVER (
        card_history
        RANGE BETWEEN INTERVAL 24 HOUR PRECEDING AND INTERVAL 1 MICROSECOND PRECEDING
    ) AS txn_count_24h,

    amt / NULLIF(MEDIAN(amt) OVER (
        card_history
        RANGE BETWEEN UNBOUNDED PRECEDING AND INTERVAL 1 MICROSECOND PRECEDING
    ), 0) AS amt_to_median_ratio,

    hour(trans_date_trans_time) AS hour_of_day,
    dayofweek(trans_date_trans_time) AS day_of_week,  -- 0 = Sunday

    -- Haversine formula: great-circle distance between home and merchant
    2 * {radius} * asin(sqrt(
        pow(sin(radians(merch_lat - lat) / 2), 2)
        + cos(radians(lat)) * cos(radians(merch_lat))
          * pow(sin(radians(merch_long - "long") / 2), 2)
    )) AS distance_km,

    category

FROM {source}
WINDOW card_history AS (PARTITION BY cc_num ORDER BY trans_date_trans_time)
ORDER BY trans_date_trans_time, trans_num
"""


def build_features(
    con: duckdb.DuckDBPyConnection, source: str = "transactions", target: str = "features"
) -> int:
    """Create (or rebuild) the `target` table from `source` and return its row count."""
    query = FEATURES_SQL.format(radius=EARTH_RADIUS_KM, source=source)
    con.execute(f"CREATE OR REPLACE TABLE {target} AS {query}")
    return con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]


def print_summary(con: duckdb.DuckDBPyConnection, target: str = "features") -> None:
    """Print row counts and the average of each numeric feature."""
    total, no_history = con.execute(
        f"SELECT COUNT(*), COUNT(*) - COUNT(amt_to_median_ratio) FROM {target}"
    ).fetchone()
    print(f"Feature rows: {total:,} ({no_history:,} first-ever transactions with no history)")
    print(
        con.sql(
            f"SELECT is_fraud, "
            f"ROUND(AVG(amt), 2) AS amt, "
            f"ROUND(AVG(txn_count_1h), 2) AS count_1h, "
            f"ROUND(AVG(txn_count_24h), 2) AS count_24h, "
            f"ROUND(MEDIAN(amt_to_median_ratio), 2) AS median_ratio, "
            f"ROUND(AVG(distance_km), 1) AS distance_km "
            f"FROM {target} GROUP BY 1 ORDER BY 1"
        )
    )


if __name__ == "__main__":
    with duckdb.connect(str(DB_PATH)) as con:
        build_features(con)
        print_summary(con)
