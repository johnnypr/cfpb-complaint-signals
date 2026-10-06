import math

import duckdb
import pandas as pd

from cfpbsignals import config
from cfpbsignals.analysis import quarterly_long_short


def test_long_short_spread_sign():
    panel = pd.DataFrame({
        "quarter": ["2024-01-01"] * 6,
        "vol_yoy_log": [0.1, 0.2, 0.3, 0.7, 0.8, 0.9],
        "xret_next_q": [0.05, 0.05, 0.05, -0.05, -0.05, -0.05],
    })
    ls = quarterly_long_short(panel, "vol_yoy_log", "xret_next_q", k=3)
    assert abs(ls.spread.iloc[0] - 0.10) < 1e-12


def test_sql_growth_and_leads():
    """Run the real SQL file on a tiny synthetic dataset."""
    con = duckdb.connect()
    rows = []
    cid = 0
    for qi, q in enumerate(pd.date_range("2019-01-01", periods=6, freq="QS")):
        for _ in range(10 * (qi + 1)):           # complaint counts 10, 20, ..., 60
            cid += 1
            rows.append({"complaint_id": cid, "ticker": "AAA", "date_received": q.date(), "narrative": None,
                         "timely": "Yes", "product": "Credit card"})
    con.register("c", pd.DataFrame(rows))
    con.execute("CREATE TABLE complaints AS SELECT * FROM c")
    con.execute("CREATE TABLE complaint_topics_long (complaint_id BIGINT, topic INT, weight DOUBLE)")
    con.execute("CREATE TABLE complaint_dominant (complaint_id BIGINT, dominant_topic INT, has_signal BOOLEAN, is_template BOOLEAN)")
    rets = pd.DataFrame({"ticker": "AAA", "quarter": pd.date_range("2019-01-01", periods=8, freq="QS").date,
                         "ret": 0.0, "xret": [0.01 * i for i in range(8)]})
    con.register("r", rets)
    con.execute("CREATE TABLE returns AS SELECT * FROM r")
    sql = (config.SQL_DIR / "quarterly_signals.sql").read_text().format(
        volume_start="2019-01-01", volume_end="2020-12-31", topic_start="2019-01-01", topic_end="2020-12-31")
    con.execute(sql)
    p = con.execute("SELECT * FROM signal_panel ORDER BY quarter").df()
    assert p.n_complaints.tolist() == [10, 20, 30, 40, 50, 60]
    assert abs(p.vol_yoy_log.iloc[4] - math.log(50 / 10)) < 1e-9   # same quarter one year earlier
    # last signal quarter still sees the next quarter's return (computed on full return history)
    assert abs(p.xret_next_q.iloc[-1] - 0.06) < 1e-12
    assert abs(p.xret_q_plus_2.iloc[-1] - 0.07) < 1e-12
