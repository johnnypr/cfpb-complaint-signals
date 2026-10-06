"""End-to-end pipeline:  PYTHONPATH=src python -m cfpbsignals.pipeline

 1. Download CFPB archive exports (May 2018 - Aug 2026) and filter to the universe.
 2. Load into DuckDB; sanity-check counts against the live CFPB API.
 3. Clean narratives, fit TF-IDF + NMF topics on a stratified sample, score all narratives.
 4. Build quarterly volume / topic signals in SQL (sql/quarterly_signals.sql).
 5. Join to quarterly stock returns (vs XLF) and write processed tables for the report.
"""
from __future__ import annotations

import json
import sys
import time

import duckdb
import numpy as np
import pandas as pd
import requests

from . import config, download, ingest, market, text


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def validate_against_api(con, years=(2019, 2022, 2025)) -> pd.DataFrame:
    """Compare archive counts with the live search API for a few company-years."""
    rows = []
    for company, ticker in list(config.COMPANIES.items())[:3]:
        for y in years:
            r = requests.get(config.API_URL, params={"size": 0, "no_aggs": "true", "company": company,
                             "date_received_min": f"{y}-01-01", "date_received_max": f"{y}-12-31"}, timeout=60)
            api_n = r.json()["hits"]["total"]["value"]
            arch_n = con.execute("SELECT COUNT(*) FROM complaints WHERE ticker=? AND year(date_received)=?",
                                 [ticker, y]).fetchone()[0]
            rows.append({"ticker": ticker, "year": y, "archive": arch_n, "live_api": api_n})
    return pd.DataFrame(rows)


def run_topics(con) -> list[list[str]]:
    df = con.execute(f"""
        SELECT complaint_id, ticker, CAST(date_trunc('quarter', date_received) AS DATE) AS quarter, narrative
        FROM complaints
        WHERE narrative IS NOT NULL
          AND date_received BETWEEN DATE '{config.TOPIC_START}' AND DATE '{config.TOPIC_END}'
    """).df()
    log(f"narratives in topic window: {len(df):,}")
    df["clean"] = df["narrative"].map(text.clean)
    df = df[df["clean"].str.len() > 50].reset_index(drop=True)
    # stratified sample so that big issuers / busy quarters don't dominate the topic definitions
    per_cell = max(1, config.FIT_SAMPLE // df.groupby(["ticker", "quarter"]).ngroups)
    sample = df.groupby(["ticker", "quarter"], group_keys=False).apply(
        lambda g: g.sample(min(len(g), per_cell), random_state=config.SEED))
    log(f"fitting TF-IDF + NMF on {len(sample):,} narratives (<= {per_cell} per company-quarter)")
    vec, nmf, top = text.fit_topics(sample["clean"], config.N_TOPICS, config.SEED)
    W = text.topic_weights(vec, nmf, df["clean"])
    long = pd.DataFrame(W, columns=range(config.N_TOPICS))
    long["complaint_id"] = df["complaint_id"].values
    long = long.melt(id_vars="complaint_id", var_name="topic", value_name="weight")
    long["topic"] = long["topic"].astype(int)
    con.register("long_df", long)
    con.execute("CREATE OR REPLACE TABLE complaint_topics_long AS SELECT * FROM long_df")
    keys = df["clean"].map(text.template_key)
    copies = keys.map(keys.value_counts())
    dom = pd.DataFrame({"complaint_id": df["complaint_id"], "dominant_topic": W.argmax(axis=1),
                        "has_signal": W.sum(axis=1) > 0,
                        "is_template": (copies >= config.TEMPLATE_MIN_COPIES).values})
    log(f"template / copy-paste narratives: {dom.is_template.mean():.1%}")
    con.register("dom_df", dom)
    con.execute("CREATE OR REPLACE TABLE complaint_dominant AS SELECT * FROM dom_df")
    # keep a tiny, de-identified sample of example narratives per topic for the README / notes
    ex = df.assign(topic=W.argmax(axis=1), w=W.max(axis=1)).sort_values("w", ascending=False)
    ex = ex.groupby("topic").head(2)[["topic", "ticker", "quarter", "narrative"]]
    ex["narrative"] = ex["narrative"].str.slice(0, 400)
    ex.sort_values("topic").to_csv(config.PROCESSED / "topic_examples.csv", index=False)
    return top


def run_returns() -> pd.DataFrame:
    bench = market.quarterly_returns(config.BENCHMARK)
    rows = []
    for t in sorted(set(config.COMPANIES.values())):
        r = market.quarterly_returns(t)
        d = pd.DataFrame({"ticker": t, "quarter": r.index.date, "ret": r.values})
        d["xret"] = d["ret"] - bench.reindex(r.index).values
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


def build_signals(con) -> None:
    """Returns + SQL signal tables + CSV exports (re-runnable alone with --sql-only)."""
    rets = run_returns()
    con.register("rets_df", rets)
    con.execute("CREATE OR REPLACE TABLE returns AS SELECT ticker, CAST(quarter AS DATE) AS quarter, ret, xret FROM rets_df")
    sql = (config.SQL_DIR / "quarterly_signals.sql").read_text().format(
        volume_start=config.VOLUME_START, volume_end=config.VOLUME_END,
        topic_start=config.TOPIC_START, topic_end=config.TOPIC_END)
    con.execute(sql)
    for tbl in ("q_volume", "q_topics", "q_templates", "weekly_volume", "signal_panel"):
        con.execute(f"SELECT * FROM {tbl} ORDER BY ALL").df().to_csv(config.PROCESSED / f"{tbl}.csv", index=False)


def main() -> None:
    if "--sql-only" in sys.argv:   # reuse the DuckDB tables from a previous full run
        con = duckdb.connect(str(config.DB_PATH))
        build_signals(con)
        con.close()
        log("done: SQL signal tables rebuilt")
        return
    for d in (config.RAW, config.INTERIM, config.PROCESSED, config.FIGURES):
        d.mkdir(parents=True, exist_ok=True)
    log("downloading exports")
    paths = download.download_all()
    log(f"{len(paths)} exports on disk; ingesting")
    df = ingest.load_exports(paths)
    log(f"universe complaints: {len(df):,}")
    ingest.to_duckdb(df)
    del df
    con = duckdb.connect(str(config.DB_PATH))
    val = validate_against_api(con)
    val.to_csv(config.PROCESSED / "validation_vs_api.csv", index=False)
    log("validation vs live API:\n" + val.to_string(index=False))
    top = run_topics(con)
    (config.PROCESSED / "topics_top_terms.json").write_text(json.dumps(top, indent=1))
    for i, t in enumerate(top):
        log(f"topic {i}: {', '.join(t)}")
    build_signals(con)
    log("done: processed tables written to data/processed/")
    con.close()


if __name__ == "__main__":
    main()
