import pytest

from conftest import make_ds
from top3.approval import Approval
from top3.backtest import FoldResult, Pick
from top3.card import RunResult, card_json, metrics, render_card
from top3.llm import LlmStats
from top3.recommend import Entry, Recommendation
from top3.rules import Rebuttal
from top3.select import Selection, Totals


@pytest.fixture
def ds_card():
    kr = {(2024, 124): 50e6, (2021, 124): 40e6, (2024, 496): 20e6, (2021, 496): 10e6}
    world = {(2021, 124): 500e6, (2024, 124): 600e6}
    ds = make_ds(kr=kr, world=world, names={124: "Canada", 496: "Mongolia"})
    ds.context = {124: {"iso3": "CAN", "name": "Canada", "population": 41e6, "gdp_pc": 55e3, "year": 2024},
                  496: {"iso3": "MNG", "name": "Mongolia", "population": None, "gdp_pc": None, "year": 2024}}
    return ds


def _run(reg, near_tie=False, final_by="자동", llm_status="건너뜀(키 없음)"):
    tot = {"size": Totals("size", 7, 147.8e6, 4, 80e6), "trend": Totals("trend", 7, 106.6e6, 3, 70e6)}
    sel = Selection("expand", "size", "size", "baseline_default", near_tie,
                    ["두 기준선의 앞 구간 적중이 같아 실현 증가액으로 골랐다"], tot)
    hold = Rebuttal("보류제안", "both_shrink", "시장과 한국 수출이 함께 줄고 있다", "규칙", "UN Comtrade", 2024, -0.1)
    top = [Entry(124, "Canada", 1, 50e6, [], False),
           Entry(496, "Mongolia", 2, 20e6, [hold], True)]
    rec = Recommendation("expand", "size", top, [], [Approval(False, "자동", "Mongolia 보류")],
                         ["후보가 셋보다 적다"], LlmStats(llm_status))
    folds = [FoldResult(2016, "expand", [124], 100e6, {"size": Pick([124], 1, 60e6), "trend": Pick([124], 1, 50e6)}, 1.0, 10e6)]
    return RunResult(
        run_id="20261102-120000", started="2026-11-02T12:00:00", reg=reg,
        selections={"expand": sel, "next": sel}, recs={"expand": rec, "next": rec},
        final={"expand": Approval(True, final_by, "확정"), "next": Approval(True, final_by, "확정")},
        timings={"collect": 1.0}, missing=[], blanks=["Mongolia: 인구", "Mongolia: 1인당 GDP"],
        baseline_tops={"expand": {"size": ["Canada", "USA", "Japan"], "trend": ["Canada", "Mongolia", "Viet Nam"]}} if near_tie else {},
        folds={"expand": folds, "next": folds}, kr_context={124: 55e6})


def test_card_has_both_questions_and_definitions(ds_card, reg):
    text = render_card(_run(reg), ds_card)
    assert "큰 시장 확대 TOP3" in text and "다음 시장 TOP3" in text
    assert "T→T+4 한국 수출 증가액" in text
    assert "실측 07" in text                        # 등록부를 결과를 본 뒤 썼다는 사실


def test_auto_approval_labeled_not_human(ds_card, reg):
    text = render_card(_run(reg, final_by="자동"), ds_card)
    assert "자동(사람 확인 안 함)" in text and "사람이 확정" not in text
    assert "사람 확인을 기다리는 보류 제안" in text


def test_near_tie_shows_both_baselines(ds_card, reg):
    text = render_card(_run(reg, near_tie=True), ds_card)
    assert "두 기준선의 TOP3" in text and "Viet Nam" in text


def test_llm_skipped_shown(ds_card, reg):
    assert "LLM 반론: 건너뜀(키 없음)" in render_card(_run(reg), ds_card)


def test_blank_values_listed_not_zero(ds_card, reg):
    text = render_card(_run(reg), ds_card)
    mongolia_row = next(l for l in text.splitlines() if l.startswith("| 2 | Mongolia"))
    assert "—" in mongolia_row and " 0.0 " not in mongolia_row
    assert "Mongolia: 인구" in text


def test_metrics_and_json(ds_card, reg):
    m = metrics(_run(reg))
    assert m["expand"]["method"] == "size"
    assert m["expand"]["citation_rate"] is None and m["expand"]["llm_calls"] == 0
    assert m["expand"]["realized_gain_ratio"] == pytest.approx(0.6)
    assert card_json(_run(reg))["recs"]["expand"]["top"][0]["name"] == "Canada"
