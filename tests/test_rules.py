import pytest

from conftest import make_ds
from top3.rules import rule_rebuttals

SHARE_30, SHARE_29, BOTH_DOWN, NO_MARKET, HUB = 1001, 1002, 1003, 1004, 344


@pytest.fixture
def ds_rules():
    world = {(2021, SHARE_30): 100e6, (2024, SHARE_30): 100e6,
             (2021, SHARE_29): 100e6, (2024, SHARE_29): 100e6,
             (2021, BOTH_DOWN): 200e6, (2024, BOTH_DOWN): 100e6,
             (2021, HUB): 100e6, (2024, HUB): 120e6}
    kr = {(2021, SHARE_30): 30e6, (2024, SHARE_30): 30e6,
          (2021, SHARE_29): 29.9e6, (2024, SHARE_29): 29.9e6,
          (2021, BOTH_DOWN): 20e6, (2024, BOTH_DOWN): 10e6,
          (2021, NO_MARKET): 5e6, (2024, NO_MARKET): 6e6,
          (2021, HUB): 5e6, (2024, HUB): 6e6}
    return make_ds(kr=kr, world=world)


def test_korea_share_boundary(ds_rules, reg):
    assert any(r.rule == "korea_share" for r in rule_rebuttals(ds_rules, SHARE_30, 2024, reg))      # 정확히 30%
    assert not any(r.rule == "korea_share" for r in rule_rebuttals(ds_rules, SHARE_29, 2024, reg))  # 29.9%


def test_both_shrink_is_hold_proposal(ds_rules, reg):
    kinds = {r.rule: r.kind for r in rule_rebuttals(ds_rules, BOTH_DOWN, 2024, reg)}
    assert kinds["both_shrink"] == "보류제안"
    assert kinds["market_shrink"] == "조건"


def test_blank_market_is_condition_not_zero(ds_rules, reg):
    rs = rule_rebuttals(ds_rules, NO_MARKET, 2024, reg)
    assert [r.rule for r in rs] == ["market_blank"]
    assert rs[0].kind == "조건" and rs[0].value is None


def test_reexport_hub_condition(ds_rules, reg):
    rs = rule_rebuttals(ds_rules, HUB, 2024, reg)
    assert [r.rule for r in rs] == ["reexport"]
    assert rs[0].origin == "규칙" and rs[0].source == "UN Comtrade"


def test_flat_market_is_not_shrinking(ds_rules, reg):
    assert not any(r.rule == "market_shrink" for r in rule_rebuttals(ds_rules, SHARE_30, 2024, reg))
