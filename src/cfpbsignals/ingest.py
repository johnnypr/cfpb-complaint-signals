"""Filter the archive CSVs to the company universe and load them into DuckDB."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from . import config

COLS = {
    "Complaint ID": "complaint_id", "Date received": "date_received", "Product": "product",
    "Sub-product": "sub_product", "Issue": "issue", "Sub-issue": "sub_issue",
    "Consumer complaint narrative": "narrative", "Company": "company", "State": "state",
    "Submitted via": "submitted_via", "Company response to consumer": "company_response",
    "Timely response?": "timely",
}


def load_exports(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for p in sorted(paths):
        for chunk in pd.read_csv(p, usecols=list(COLS), dtype=str, chunksize=250_000):
            chunk = chunk[chunk["Company"].isin(config.COMPANIES)]
            frames.append(chunk.rename(columns=COLS))
        print("ingested", p.name, flush=True)
    df = pd.concat(frames, ignore_index=True)
    df["complaint_id"] = df["complaint_id"].astype("int64")
    df["date_received"] = pd.to_datetime(df["date_received"]).dt.date
    df["ticker"] = df["company"].map(config.COMPANIES)
    # exports overlap only at boundaries, but de-duplicate defensively
    return df.drop_duplicates("complaint_id")


def to_duckdb(df: pd.DataFrame, db_path: Path = config.DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.register("df", df)
    con.execute("CREATE OR REPLACE TABLE complaints AS SELECT * FROM df")
    con.close()
