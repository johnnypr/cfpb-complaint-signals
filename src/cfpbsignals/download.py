"""Download the CFPB complaint archive exports (public domain, CC0)."""
from __future__ import annotations

import re
from pathlib import Path

import requests

from . import config

UA = {"User-Agent": "Johnny Perez johnnypr11@icloud.com (research project)"}


def export_urls(page_url: str = config.ARCHIVE_PAGE) -> list[str]:
    html = requests.get(page_url, headers=UA, timeout=60).text
    urls = sorted(set(re.findall(r"https://files\.consumerfinance\.gov/f/documents/CCDB_Export_\d+_[^\"']+\.zip", html)))
    return [u for u in urls if int(re.search(r"CCDB_Export_(\d+)_", u).group(1)) >= config.FIRST_EXPORT]


def download_all(dest: Path = config.RAW) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for u in export_urls():
        p = dest / u.rsplit("/", 1)[1]
        if not p.exists():
            print("downloading", p.name, flush=True)
            with requests.get(u, headers=UA, stream=True, timeout=600) as r:
                r.raise_for_status()
                tmp = p.with_suffix(".part")
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                tmp.rename(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    for p in download_all():
        print(p)
