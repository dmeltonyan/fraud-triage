"""Load the two Kaggle fraud CSVs into one table in a local DuckDB file.

Run from the project root with:  python -m src.load
"""

from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "fraud.duckdb"
DATASET_URL = "https://www.kaggle.com/datasets/kartik2112/fraud-detection"

# Which file each row came from, stored in the source_file column.
CSV_FILES = {"train": "fraudTrain.csv", "test": "fraudTest.csv"}

# Every column in the CSVs, in file order, with its type written out so
# DuckDB never has to guess. The first column has no name in the files; it is
# a row number that restarts at 0 in each file, so we read it and then drop it.
COLUMN_TYPES = {
    "row_number": "BIGINT",  # dropped: not unique across the two files
    "trans_date_trans_time": "TIMESTAMP",  # when the transaction happened
    "cc_num": "BIGINT",  # card number, 16 digits
    "merchant": "VARCHAR",
    "category": "VARCHAR",
    "amt": "DOUBLE",  # amount in dollars
    "first": "VARCHAR",
    "last": "VARCHAR",
    "gender": "VARCHAR",  # kept in the raw table, never used as a feature
    "street": "VARCHAR",
    "city": "VARCHAR",
    "state": "VARCHAR",
    "zip": "INTEGER",
    "lat": "DOUBLE",  # cardholder home latitude
    "long": "DOUBLE",  # cardholder home longitude
    "city_pop": "INTEGER",
    "job": "VARCHAR",
    "dob": "DATE",  # kept in the raw table, never used as a feature
    "trans_num": "VARCHAR",  # unique transaction ID
    "unix_time": "BIGINT",  # shifted by 7 years in the source data; use trans_date_trans_time
    "merch_lat": "DOUBLE",
    "merch_long": "DOUBLE",
    "is_fraud": "INTEGER",  # 1 = fraud, 0 = legitimate
}
KEPT_COLUMNS = [name for name in COLUMN_TYPES if name != "row_number"]


def read_csv_sql(path: Path, source: str) -> str:
    """Build a SELECT that reads one CSV with fixed column types."""
    columns = ", ".join(f"'{name}': '{type_}'" for name, type_ in COLUMN_TYPES.items())
    kept = ", ".join(f'"{name}"' for name in KEPT_COLUMNS)
    return (
        f"SELECT {kept}, '{source}' AS source_file "
        f"FROM read_csv('{path.as_posix()}', header = true, columns = {{{columns}}})"
    )


def load_transactions(data_dir: Path = DATA_DIR, db_path: Path = DB_PATH) -> int:
    """Combine the CSVs into a `transactions` table and return its row count.

    Rebuilds the table from scratch each time, so it is safe to rerun.
    """
    selects = []
    for source, filename in CSV_FILES.items():
        path = data_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Download the dataset from {DATASET_URL} "
                f"and put {filename} in {data_dir}."
            )
        selects.append(read_csv_sql(path, source))

    with duckdb.connect(str(db_path)) as con:
        con.execute(
            "CREATE OR REPLACE TABLE transactions AS "
            + " UNION ALL ".join(selects)
            + " ORDER BY trans_date_trans_time, trans_num"
        )

        total, distinct = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT trans_num) FROM transactions"
        ).fetchone()
        if total != distinct:
            con.execute("DROP TABLE transactions")
            raise ValueError(f"trans_num is not unique: {total} rows but {distinct} distinct IDs.")

    return total


def print_summary(db_path: Path = DB_PATH) -> None:
    """Print the headline numbers for the loaded table."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        total, fraud, rate, first, last = con.execute(
            "SELECT COUNT(*), SUM(is_fraud), AVG(is_fraud), "
            "MIN(trans_date_trans_time), MAX(trans_date_trans_time) FROM transactions"
        ).fetchone()
    print(f"Transactions: {total:,}")
    print(f"Fraud cases:  {fraud:,} ({rate:.3%})")
    print(f"Date range:   {first} to {last}")


if __name__ == "__main__":
    load_transactions()
    print_summary()
