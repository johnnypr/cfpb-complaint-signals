"""Quarterly total returns from Yahoo Finance's public chart endpoint (no API key)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

from . import config


def daily_prices(symbol: str, start: str = "2017-01-01", cache_dir: Path = config.RAW / "prices") -> pd.Series:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{symbol}.json"
    if not path.exists():
        params = {"period1": int(pd.Timestamp(start).timestamp()), "period2": int(time.time()),
                  "interval": "1d", "events": "div,split"}
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", params=params,
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        path.write_text(r.text)
        time.sleep(0.5)
    res = json.loads(path.read_text())["chart"]["result"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s").normalize()
    s = pd.Series(res["indicators"]["adjclose"][0]["adjclose"], index=idx, dtype="float64").dropna()
    return s[~s.index.duplicated(keep="last")]


def quarterly_returns(symbol: str) -> pd.Series:
    """Quarter-over-quarter adjusted-close return, indexed by quarter start date."""
    daily = daily_prices(symbol)
    px = daily.resample("QE").last()
    px = px[px.index <= daily.index.max()]  # drop the current, incomplete quarter
    ret = px.pct_change().dropna()
    ret.index = ret.index.to_period("Q").start_time
    return ret.rename(symbol)
