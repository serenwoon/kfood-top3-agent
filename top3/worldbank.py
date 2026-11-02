"""세계은행 API — 카드의 맥락 열(인구, 1인당 GDP). 값이 없으면 None."""
import time
import urllib.request
from pathlib import Path

from .comtrade import _download, read_cache

INDICATORS = {"population": "SP.POP.TOTL", "gdp_pc": "NY.GDP.PCAP.CD"}
URL = "https://api.worldbank.org/v2/country/all/indicator/{id}?format=json&date={year}&per_page=400"


def _rows(raw_dir: Path, ind: str, year: int, opener, sleep) -> list[dict]:
    path = raw_dir / f"wb_{ind}_{year}.json"
    data = read_cache(path)
    if data is None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        # 정상 응답은 [메타, 행 목록] 두 칸. 오류는 [{"message": ...}] 한 칸이라 저장하지 않는다
        data = _download(URL.format(id=ind, year=year), path, opener, sleep,
                         valid=lambda d: isinstance(d, list) and len(d) == 2)
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
