"""UN Comtrade 공개 API(preview)에서 원자료를 받는다.

받은 응답은 raw_dir 에 그대로 저장하고, 있으면 다시 받지 않는다(깨진 파일은 없는 것으로 보고 다시 받는다).
받기에 실패한 것은 0 으로 채우지 않고 이름 목록으로 돌려준다. 세 건이 연달아 실패하면 인터넷이 끊긴 것으로 보고 멈춘다.
"""
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
REF_PARTNERS = "https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json"
HEADERS = {"User-Agent": "kfood-top3-agent"}
RETRY_WAIT = (5, 10, 15, 20)
PAUSE = 1.5
STOP_AFTER = 3          # 연달아 이만큼 실패하면 받기를 멈춘다
FETCHED_LOG = "_fetched.json"


class FetchError(Exception):
    """네 번 시도해도 받지 못했다."""


def is_comtrade(data) -> bool:
    return isinstance(data, dict) and isinstance(data.get("data"), list) and not data.get("error")


def _record(path: Path) -> None:
    log = path.parent / FETCHED_LOG
    try:
        rec = json.loads(log.read_text(encoding="utf-8")) if log.exists() else {}
    except json.JSONDecodeError:
        rec = {}
    rec[path.stem] = datetime.now().isoformat(timespec="seconds")
    log.write_text(json.dumps(rec, ensure_ascii=False, indent=0), encoding="utf-8", newline="\n")


def _download(url: str, path: Path, opener, sleep, valid=lambda d: True):
    last = None
    for wait in RETRY_WAIT:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with opener(req, timeout=90) as r:
                body = r.read()
            data = json.loads(body)
            if not valid(data):
                raise RuntimeError(f"예상과 다른 응답: {str(data)[:120]}")
            path.write_bytes(body)
            _record(path)
            sleep(PAUSE)
            return data
        except Exception as e:  # 잠깐 쉬고 다시
            last = e
            sleep(wait)
    raise FetchError(f"{path.stem}: {last}")


def read_cache(path: Path):
    """캐시를 읽는다. 없거나 깨졌으면 None."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def get(name: str, query: str, raw_dir: Path, opener=urllib.request.urlopen, sleep=time.sleep) -> dict:
    path = raw_dir / f"{name}.json"
    cached = read_cache(path)
    if cached is not None:
        return cached
    raw_dir.mkdir(parents=True, exist_ok=True)
    return _download(f"{BASE}?{query}", path, opener, sleep, valid=is_comtrade)


def jobs_for(hs: list[str], hs6: list[str], years_world: range, years_kr: range) -> list[tuple[str, str]]:
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
    return jobs


def fetch_all(raw_dir: Path, hs: list[str], hs6: list[str], years_world: range, years_kr: range,
              opener=urllib.request.urlopen, sleep=time.sleep, progress=None) -> list[str]:
    jobs = jobs_for(hs, hs6, years_world, years_kr)
    missing: list[str] = []
    streak = 0
    for i, (name, query) in enumerate(jobs, start=1):
        if streak >= STOP_AFTER:
            missing.append(name)
            continue
        if read_cache(raw_dir / f"{name}.json") is not None:
            continue
        if progress:
            progress(f"받는 중 {i}/{len(jobs)} {name}")
        try:
            get(name, query, raw_dir, opener=opener, sleep=sleep)
            streak = 0
        except FetchError:
            missing.append(name)
            streak += 1
    return missing


def country_table(raw_dir: Path, opener=urllib.request.urlopen, sleep=time.sleep) -> dict[int, dict]:
    path = raw_dir / "ref_partner_areas.json"
    data = read_cache(path)
    if data is None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        data = _download(REF_PARTNERS, path, opener, sleep,
                         valid=lambda d: isinstance(d, dict) and isinstance(d.get("results"), list))
    return {r["PartnerCode"]: {"name": r.get("PartnerDesc"), "iso3": r.get("PartnerCodeIsoAlpha3")}
            for r in data.get("results", [])}
