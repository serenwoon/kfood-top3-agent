"""UN Comtrade 공개 API(preview)에서 원자료를 받는다.

받은 응답은 raw_dir 에 그대로 저장하고, 있으면 다시 받지 않는다.
받기에 실패한 것은 0 으로 채우지 않고 이름 목록으로 돌려준다.
"""
import json
import time
import urllib.request
from pathlib import Path

BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
REF_PARTNERS = "https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json"
HEADERS = {"User-Agent": "kfood-top3-agent"}
RETRY_WAIT = (5, 10, 15, 20)
PAUSE = 1.5


class FetchError(Exception):
    """네 번 시도해도 받지 못했다."""


def _download(url: str, path: Path, opener, sleep) -> dict:
    last = None
    for wait in RETRY_WAIT:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with opener(req, timeout=90) as r:
                body = r.read()
            data = json.loads(body)
            if isinstance(data, dict) and data.get("error"):
                raise RuntimeError(data["error"])
            path.write_bytes(body)
            sleep(PAUSE)
            return data
        except Exception as e:  # 잠깐 쉬고 다시
            last = e
            sleep(wait)
    raise FetchError(f"{path.stem}: {last}")


def get(name: str, query: str, raw_dir: Path, opener=urllib.request.urlopen, sleep=time.sleep) -> dict:
    path = raw_dir / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    raw_dir.mkdir(parents=True, exist_ok=True)
    return _download(f"{BASE}?{query}", path, opener, sleep)


def fetch_all(raw_dir: Path, hs: list[str], hs6: list[str], years_world: range, years_kr: range,
              opener=urllib.request.urlopen, sleep=time.sleep) -> list[str]:
    jobs = []
    for y in years_kr:
        for h in hs:
            jobs.append((f"kr_export_{y}_{h}",
                         f"reporterCode=410&period={y}&cmdCode={h}&flowCode=X&includeDesc=true"))
    for y in years_world:
        for h in hs:
            jobs.append((f"world_import_{y}_{h}",
                         f"period={y}&cmdCode={h}&flowCode=M&partnerCode=0&includeDesc=true"))
        for k in hs6:
            jobs.append((f"world_import_{y}_{k}",
                         f"period={y}&cmdCode={k}&flowCode=M&partnerCode=0&includeDesc=true"))
        if hs6:
            jobs.append((f"kr_export_world_{y}_hs6",
                         f"reporterCode=410&period={y}&cmdCode={','.join(hs6)}&flowCode=X&partnerCode=0"))
    missing = []
    for name, query in jobs:
        try:
            get(name, query, raw_dir, opener=opener, sleep=sleep)
        except FetchError:
            missing.append(name)
    return missing


def country_table(raw_dir: Path, opener=urllib.request.urlopen, sleep=time.sleep) -> dict[int, dict]:
    path = raw_dir / "ref_partner_areas.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw_dir.mkdir(parents=True, exist_ok=True)
        data = _download(REF_PARTNERS, path, opener, sleep)
    return {r["PartnerCode"]: {"name": r.get("PartnerDesc"), "iso3": r.get("PartnerCodeIsoAlpha3")}
            for r in data.get("results", [])}
