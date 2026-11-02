"""시험 공용 도구 — 네트워크 없이 Comtrade 응답 모양의 작은 원자료를 만든다."""
import json
from pathlib import Path

import pytest

REAL_RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def row(reporter, partner, value, *, rdesc=None, pdesc=None, cmd=None):
    """Comtrade preview 응답의 한 행. keep() 이 남기는 기본값으로 채운다."""
    return {
        "reporterCode": reporter, "reporterDesc": rdesc,
        "partnerCode": partner, "partnerDesc": pdesc,
        "partner2Code": 0, "customsCode": "C00", "motCode": 0,
        "cmdCode": cmd, "primaryValue": value,
    }


def write_raw(folder: Path, name: str, rows: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    body = {"count": len(rows), "data": rows}
    (folder / f"{name}.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8", newline="\n")


@pytest.fixture
def raw_small(tmp_path) -> Path:
    """2019·2020 × HS 1704·1806. 캐나다(124)는 두 코드를 다 신고, UAE(784)는 1704만 신고."""
    d = tmp_path / "raw"
    for y in (2019, 2020):
        write_raw(d, f"kr_export_{y}_1704", [
            row(410, 0, 9e9, pdesc="World"),
            row(410, 124, 5_000_000, pdesc="Canada"),
            row(410, 490, 2_000_000 if y == 2020 else 1_000_000, pdesc="Other Asia, nes"),
            row(410, 784, 4_000_000, pdesc="United Arab Emirates"),
            row(410, 899, 7_000_000, pdesc="Areas, nes"),
        ])
        write_raw(d, f"kr_export_{y}_1806", [
            row(410, 124, 1_000_000, pdesc="Canada"),
        ])
        write_raw(d, f"world_import_{y}_1704", [
            row(124, 0, 100_000_000, rdesc="Canada"),
            row(784, 0, 50_000_000, rdesc="United Arab Emirates"),
        ])
        write_raw(d, f"world_import_{y}_1806", [
            row(124, 0, 200_000_000, rdesc="Canada"),
        ])
    return d


@pytest.fixture
def reg():
    from top3.config import load_registry
    return load_registry(Path(__file__).resolve().parents[1] / "registry.json")


def make_ds(kr=None, world=None, reported=None, names=None, hs6_imports=None, kr_hs6_world=None):
    """손으로 Dataset 을 만든다. world 를 주면 reported 는 네 코드 모두 신고한 것으로 채운다."""
    from top3.data import Dataset
    world = world or {}
    if reported is None:
        reported = {k: {"1704", "1806", "1905", "2105"} for k in world}
    return Dataset(kr or {}, world, reported, names or {}, hs6_imports or {}, kr_hs6_world or {})


needs_real_raw = pytest.mark.skipif(
    not (REAL_RAW / "kr_export_2016_1704.json").exists(),
    reason="실측 07 원자료가 data/raw 에 없다",
)


@pytest.fixture(scope="session")
def ds_real():
    """실측 07 과 같은 범위(2013~2024, 4코드)로 읽은 실제 원자료."""
    from top3.data import load
    return load(REAL_RAW, ["1704", "1806", "1905", "2105"], range(2013, 2025))
