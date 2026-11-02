"""세계은행 API — 카드의 맥락 열(인구, 1인당 GDP). 값이 없으면 None."""
import json
import time
import urllib.request
from pathlib import Path

from .comtrade import _download

INDICATORS = {"population": "SP.POP.TOTL", "gdp_pc": "NY.GDP.PCAP.CD"}
URL = "https://api.worldbank.org/v2/country/all/indicator/{id}?format=json&date={year}&per_page=400"


def _rows(raw_dir: Path, ind: str, year: int, opener, sleep) -> list[dict]:
    path = raw_dir / f"wb_{ind}_{year}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw_dir.mkdir(parents=True, exist_ok=True)
        data = _download(URL.format(id=ind, year=year), path, opener, sleep)
    return data[1] if isinstance(data, list) and len(data) > 1 and data[1] else []


def fetch(raw_dir: Path, year: int, opener=urllib.request.urlopen, sleep=time.sleep) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for field, ind in INDICATORS.items():
        for r in _rows(raw_dir, ind, year, opener, sleep):
            iso3 = r.get("countryiso3code")
            if not iso3:
                continue
            v = r.get("value")
            out.setdefault(iso3, {"population": None, "gdp_pc": None})[field] = float(v) if v is not None else None
    return out
