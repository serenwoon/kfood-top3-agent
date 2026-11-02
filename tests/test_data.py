from top3.data import export, load, market


def test_load_keeps_taiwan_drops_aggregates(raw_small):
    ds = load(raw_small, ["1704"], range(2019, 2021))
    assert ds.kr[(2020, 490)] == 2_000_000.0      # Other Asia, nes = 대만, 남김
    assert (2020, 0) not in ds.kr                  # 세계 합계는 뺌
    assert (2020, 899) not in ds.kr                # Areas, nes 는 뺌
    assert all("nes" not in (ds.names[c] or "").lower() for (_, c) in ds.kr if c != 490)


def test_market_none_when_not_all_codes_reported(raw_small):
    ds = load(raw_small, ["1704", "1806"], range(2019, 2021))
    assert market(ds, 2020, 124, ["1704", "1806"]) == 300_000_000.0   # 둘 다 신고
    assert market(ds, 2020, 784, ["1704", "1806"]) is None            # 1704만 신고 → None, 0 아님


def test_export_missing_row_is_zero(raw_small):
    ds = load(raw_small, ["1704"], range(2019, 2021))
    assert export(ds, 2020, 999) == 0.0
