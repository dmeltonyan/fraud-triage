import re

import pandas as pd

from src.export_demo import DEMO_COLUMNS, SCHEMA_PATH, select_demo_rows, to_demo_table

PERSONAL_FIELDS = {"first", "last", "street", "dob", "cc_num", "gender", "job", "zip", "lat", "long"}


def make_decisions():
    actions = ["approve"] * 10 + ["review"] * 3 + ["block"] * 2
    return pd.DataFrame(
        {
            "trans_num": [f"{i:032x}" for i in range(15)],
            "trans_date_trans_time": pd.date_range("2020-10-01", periods=15, freq="h"),
            "action": actions,
        }
    )


def test_sample_keeps_every_flagged_case_and_respects_the_limit():
    sample = select_demo_rows(make_decisions(), max_rows=8)
    assert len(sample) == 8
    assert (sample["action"] != "approve").sum() == 5  # all 3 reviews and 2 blocks
    assert (sample["action"] == "approve").sum() == 3


def test_sample_never_drops_flagged_cases_even_over_the_limit():
    sample = select_demo_rows(make_decisions(), max_rows=2)
    assert len(sample) == 5
    assert set(sample["action"]) == {"review", "block"}


def test_demo_table_has_only_the_schema_columns_and_no_personal_fields():
    df = make_decisions().assign(
        merchant="fraud_Kirlin and Sons", category="misc_net", amt=12.3456, city="Springfield", state="NC",
        p_fraud=0.01, approve=0.1, review=5.0, block=9.9, loss_prevented=-4.9, is_fraud=0,
        first="Test", last="Person", street="1 Example Street", dob="1990-01-01", cc_num=4000000000000002,
    )
    reasons = [["a", "b", "c"]] * len(df)
    table = to_demo_table(df, reasons)

    assert list(table.columns) == DEMO_COLUMNS
    assert PERSONAL_FIELDS.isdisjoint(table.columns)
    assert table.loc[0, "merchant"] == "Kirlin and Sons"  # simulator's "fraud_" prefix removed
    assert table.loc[0, "amount"] == 12.35  # rounded to cents


def test_demo_columns_match_the_postgres_schema():
    schema = SCHEMA_PATH.read_text()
    table_sql = schema.split("CREATE TABLE IF NOT EXISTS transactions_demo (")[1].split(");")[0]
    schema_columns = [m.group(1) for m in re.finditer(r"^\s+(\w+)\s+[A-Z]", table_sql, re.MULTILINE)]
    assert schema_columns == DEMO_COLUMNS
