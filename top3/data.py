"""원자료(Comtrade 응답 JSON) → Dataset.

load() 의 앞부분은 kfood-export-backtest/backtest.py 의 load() 를 그대로 옮겼다.
사전에 넣는 순서가 되감기 무작위 기준선의 결과를 정하므로 순서를 바꾸지 않는다.
"""
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Dataset:
    kr: dict[tuple[int, int], float]                 # (연도, 상대국) -> 한국 수출 합(달러)
    world: dict[tuple[int, int], float]              # (연도, 신고국) -> 그 나라 세계 수입 합
    reported: dict[tuple[int, int], set[str]]        # (연도, 신고국) -> 신고한 HS 코드
    names: dict[int, str]
    hs6_imports: dict[tuple[int, int, str], float] = field(default_factory=dict)  # (연도, 신고국, 6단위)
    kr_hs6_world: dict[tuple[int, str], float] = field(default_factory=dict)      # (연도, 6단위) -> 한국의 세계 수출
    context: dict[int, dict] = field(default_factory=dict)


def keep(row: dict) -> bool:
    return row.get("partner2Code") == 0 and row.get("customsCode") == "C00" and row.get("motCode") == 0


def is_aggregate(code: int, desc: str | None) -> bool:
    if code == 0:
        return True
    if code == 490:  # Other Asia, nes = 대만
        return False
    d = (desc or "").lower()
    return "nes" in d or "bunker" in d or "free zone" in d or "special categor" in d


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("data") or []


def load(raw_dir: Path, hs: list[str], years: range, hs6: list[str] = ()) -> Dataset:
    kr = defaultdict(float)
    world = defaultdict(float)
    names: dict[int, str] = {}
    for y in years:
        for h in hs:
            for r in _rows(raw_dir / f"kr_export_{y}_{h}.json"):
                if keep(r) and not is_aggregate(r["partnerCode"], r.get("partnerDesc")):
                    kr[(y, r["partnerCode"])] += r["primaryValue"] or 0
                    names[r["partnerCode"]] = r.get("partnerDesc")
            for r in _rows(raw_dir / f"world_import_{y}_{h}.json"):
                if keep(r) and r.get("partnerCode") == 0:
                    world[(y, r["reporterCode"])] += r["primaryValue"] or 0
                    names.setdefault(r["reporterCode"], r.get("reporterDesc"))
    reported = defaultdict(set)
    for y in years:
        for h in hs:
            for r in _rows(raw_dir / f"world_import_{y}_{h}.json"):
                if keep(r) and r.get("partnerCode") == 0:
                    reported[(y, r["reporterCode"])].add(h)

    hs6_imports: dict[tuple[int, int, str], float] = {}
    kr_hs6_world: dict[tuple[int, str], float] = {}
    for y in years:
        for k in hs6:
            for r in _rows(raw_dir / f"world_import_{y}_{k}.json"):
                if keep(r) and r.get("partnerCode") == 0 and r.get("primaryValue") is not None:
                    hs6_imports[(y, r["reporterCode"], k)] = float(r["primaryValue"])
        if hs6:
            for r in _rows(raw_dir / f"kr_export_world_{y}_hs6.json"):
                if keep(r) and r.get("partnerCode") == 0 and r.get("primaryValue") is not None:
                    kr_hs6_world[(y, str(r["cmdCode"]))] = float(r["primaryValue"])
    return Dataset(kr, world, reported, names, hs6_imports, kr_hs6_world)


def attach_context(ds: Dataset, table: dict[int, dict], wb: dict[str, dict], year: int) -> None:
    """나라마다 맥락 값(인구·1인당 GDP)을 붙인다. 코드표나 세계은행에 없으면 None."""
    for code in {c for (_, c) in ds.kr}:
        iso3 = table.get(code, {}).get("iso3")
        v = wb.get(iso3, {}) if iso3 else {}
        ds.context[code] = {"iso3": iso3, "name": table.get(code, {}).get("name") or ds.names.get(code),
                            "population": v.get("population"), "gdp_pc": v.get("gdp_pc"), "year": year}


def export(ds: Dataset, year: int, code: int) -> float:
    """한국이 직접 신고한 수출. 행이 없으면 거래 없음 = 0."""
    return ds.kr.get((year, code), 0.0)


def market(ds: Dataset, year: int, code: int, hs: list[str]) -> float | None:
    """그 나라 세계 수입. 네 코드를 다 신고하지 않았으면 None(0 아님)."""
    if len(ds.reported.get((year, code), ())) != len(hs):
        return None
    return ds.world.get((year, code))
