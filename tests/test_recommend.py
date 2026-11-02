import pytest

from conftest import make_ds
from top3.llm import NoneProvider
from top3.methods import eligible, ranked
from top3.recommend import recommend

A, HOLD, C, D, E = 1, 2, 3, 4, 5


@pytest.fixture
def ds_rec():
    kr = {(2024, A): 50e6, (2021, A): 40e6,
          (2024, HOLD): 40e6, (2021, HOLD): 60e6,
          (2024, C): 30e6, (2021, C): 20e6,
          (2024, D): 20e6, (2021, D): 10e6,
          (2024, E): 10e6, (2021, E): 5e6}
    world = {(2021, HOLD): 200e6, (2024, HOLD): 100e6}
    for c in (A, C, D, E):
        world[(2021, c)] = 500e6
        world[(2024, c)] = 600e6
    return make_ds(kr=kr, world=world, names={A: "A", HOLD: "Hold", C: "C", D: "D", E: "E"})


@pytest.fixture
def ds_two_countries():
    kr = {(2024, A): 50e6, (2021, A): 40e6, (2024, C): 30e6, (2021, C): 20e6, (2024, D): 1e6}
    world = {(2021, A): 500e6, (2024, A): 600e6, (2021, C): 500e6, (2024, C): 600e6}
    return make_ds(kr=kr, world=world, names={A: "A", C: "C", D: "D"})


def test_hold_needs_human_yes(ds_rec, reg):
    r = recommend(ds_rec, reg, "expand", "size", NoneProvider(), [], auto=False, input_fn=lambda p: "y")
    assert HOLD in [e.code for e in r.excluded]
    assert [e.code for e in r.top] == [A, C, D]
    assert any(a.by == "사람" and a.approved for a in r.approvals)


def test_human_no_keeps_candidate_without_pending(ds_rec, reg):
    r = recommend(ds_rec, reg, "expand", "size", NoneProvider(), [], auto=False, input_fn=lambda p: "n")
    held = [e for e in r.top if e.code == HOLD]
    assert held and held[0].hold_pending is False and r.excluded == []


def test_auto_does_not_apply_hold(ds_rec, reg):
    r = recommend(ds_rec, reg, "expand", "size", NoneProvider(), [], auto=True)
    held = [e for e in r.top if e.code == HOLD]
    assert held and held[0].hold_pending is True and r.excluded == []


def test_eof_means_no_answer_not_crash(ds_rec, reg):
    def eof(p):
        raise EOFError
    r = recommend(ds_rec, reg, "expand", "size", NoneProvider(), [], auto=False, input_fn=eof)
    assert any(a.by == "응답 없음" and not a.approved for a in r.approvals)
    assert [e for e in r.top if e.code == HOLD][0].hold_pending is True


def test_fewer_than_three_noted(ds_two_countries, reg):
    r = recommend(ds_two_countries, reg, "expand", "size", NoneProvider(), [], auto=True)
    assert len(r.top) == 2 and "후보가 셋보다 적다" in r.notes


def test_rebuttal_never_raises_rank(ds_rec, reg):
    r = recommend(ds_rec, reg, "expand", "size", NoneProvider(), [], auto=True)
    cands = eligible(ds_rec, 2024, {p for (_, p) in ds_rec.kr}, reg)
    assert [e.code for e in r.top] == ranked("size", ds_rec, 2024, cands, reg)[:3]


def test_next_question_drops_top_markets(ds_rec, reg):
    r = recommend(ds_rec, reg, "next", "size", NoneProvider(), [], auto=True)
    assert [e.code for e in r.top] == [D, E]      # 2024 수출 상위 3(A·Hold·C)을 뺀다
    assert r.llm.status == "건너뜀(키 없음)"
