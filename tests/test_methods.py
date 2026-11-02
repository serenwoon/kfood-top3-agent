import pytest

from conftest import make_ds
from top3.methods import cagr, eligible, ranked, scores


def test_market_growth_skips_missing_market_not_zero(reg):
    ds = make_ds(world={(2017, 124): 100.0, (2020, 124): 133.1, (2017, 784): 50.0},
                 kr={(2020, 124): 5e6, (2020, 784): 5e6})
    s = scores("market_growth", ds, 2020, [124, 784], reg)
    assert 124 in s and 784 not in s          # 784 는 2020 시장값 None → 빠짐
    assert s[124] == pytest.approx(0.1)


def test_hs6_mix_weighted_by_korea_mix(reg):
    # 한국 6단위 수출: A=3, B=1 / 나라 124 의 3년 연평균 성장률: A=+10%, B=-10%
    ds = make_ds(kr_hs6_world={(2020, "170410"): 3.0, (2020, "170490"): 1.0},
                 hs6_imports={(2017, 124, "170410"): 100.0, (2020, 124, "170410"): 133.1,
                              (2017, 124, "170490"): 100.0, (2020, 124, "170490"): 72.9})
    assert scores("hs6_mix", ds, 2020, [124], reg)[124] == pytest.approx(0.05)


def test_hs6_mix_without_any_subheading_has_no_value(reg):
    ds = make_ds(kr_hs6_world={(2020, "170410"): 3.0})
    assert scores("hs6_mix", ds, 2020, [124], reg) == {}


def test_ranked_is_stable_on_ties(reg):
    ds = make_ds(kr={(2020, 156): 9e6, (2020, 124): 9e6})
    assert ranked("size", ds, 2020, [156, 124], reg) == [156, 124]
    assert ranked("size", ds, 2020, [124, 156], reg) == [124, 156]


def test_eligible_uses_min_export(reg):
    ds = make_ds(kr={(2020, 124): 3_000_000, (2020, 156): 2_999_999})
    assert eligible(ds, 2020, {124, 156}, reg) == [124]


def test_cagr_none_on_nonpositive():
    assert cagr(0, 10, 3) is None and cagr(10, None, 3) is None
    assert cagr(100, 133.1, 3) == pytest.approx(0.1)
