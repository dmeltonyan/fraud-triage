import duckdb

from src.load import CSV_FILES, KEPT_COLUMNS, load_transactions

HEADER = ",trans_date_trans_time,cc_num,merchant,category,amt,first,last,gender,street,city,state,zip,lat,long,city_pop,job,dob,trans_num,unix_time,merch_lat,merch_long,is_fraud"


def make_row(index: int, timestamp: str, trans_num: str, is_fraud: int) -> str:
    """One CSV line in the same format as the Kaggle files."""
    return (
        f'{index},{timestamp},4000000000000002,"fraud_Rippin, Kub and Mann",misc_net,4.97,'
        f"Test,Person,F,1 Example Street,Springfield,NC,10001,40.0,-75.0,3495,"
        f'"Psychologist, counselling",1990-01-01,{trans_num},1325376018,40.1,-75.1,{is_fraud}'
    )


def test_load_combines_both_files(tmp_path):
    # Both files start their row numbers at 0, like the real data.
    train_rows = [make_row(0, "2019-01-01 00:00:18", "a1", 0), make_row(1, "2019-01-02 10:00:00", "a2", 1)]
    test_rows = [make_row(0, "2020-07-01 08:30:00", "b1", 0)]
    (tmp_path / CSV_FILES["train"]).write_text("\n".join([HEADER, *train_rows]) + "\n")
    (tmp_path / CSV_FILES["test"]).write_text("\n".join([HEADER, *test_rows]) + "\n")
    db_path = tmp_path / "test.duckdb"

    assert load_transactions(data_dir=tmp_path, db_path=db_path) == 3

    with duckdb.connect(str(db_path), read_only=True) as con:
        columns = [row[0] for row in con.execute("DESCRIBE transactions").fetchall()]
        sources = con.execute("SELECT source_file FROM transactions").fetchall()
        fraud = con.execute("SELECT SUM(is_fraud) FROM transactions").fetchone()[0]

    assert columns == [*KEPT_COLUMNS, "source_file"]  # unnamed row number is gone
    assert [s[0] for s in sources] == ["train", "train", "test"]  # sorted by time
    assert fraud == 1


def test_load_is_safe_to_rerun(tmp_path):
    (tmp_path / CSV_FILES["train"]).write_text(HEADER + "\n" + make_row(0, "2019-01-01 00:00:18", "a1", 0) + "\n")
    (tmp_path / CSV_FILES["test"]).write_text(HEADER + "\n" + make_row(0, "2020-07-01 08:30:00", "b1", 0) + "\n")
    db_path = tmp_path / "test.duckdb"

    load_transactions(data_dir=tmp_path, db_path=db_path)
    assert load_transactions(data_dir=tmp_path, db_path=db_path) == 2  # not 4
