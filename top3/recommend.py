"""현재 연도(target_year) 추천. 점수 순서대로 후보를 보며 반론을 붙이고, 사람이 승인한 보류만 적용한다.

반론은 후보를 빼거나 조건을 붙일 뿐 순위를 올리지 못한다. 빈자리는 점수 다음 순위로만 채운다.
"""
from dataclasses import dataclass, field

from .approval import Approval, confirm_hold
from .data import export
from .llm import LlmStats, llm_rebuttals
from .methods import eligible, ranked, scores
from .rules import Rebuttal, rule_rebuttals

TOPN = 3


@dataclass
class Entry:
    code: int
    name: str
    rank: int
    score: float | None
    rebuttals: list[Rebuttal]
    hold_pending: bool


@dataclass
class Recommendation:
    question: str
    method: str
    top: list[Entry]
    excluded: list[Entry]
    approvals: list[Approval]
    notes: list[str] = field(default_factory=list)
    llm: LlmStats = field(default_factory=lambda: LlmStats("건너뜀(키 없음)"))


def candidates(ds, reg, question: str, T: int) -> list[int]:
    partners = {p for (_, p) in ds.kr}
    drop = reg.questions[question]["drop_top"]
    if drop:
        partners -= set(sorted(partners, key=lambda p: -export(ds, T, p))[:drop])
    return eligible(ds, T, partners, reg)


def recommend(ds, reg, question: str, method: str, provider, docs, auto: bool, input_fn=input) -> Recommendation:
    T = reg.target_year
    cands = candidates(ds, reg, question, T)
    order = ranked(method, ds, T, cands, reg)
    sc = scores(method, ds, T, cands, reg)
    rec = Recommendation(question, method, [], [], [])
    stats = LlmStats("건너뜀(키 없음)" if provider.name == "none" else "돎")
    for i, code in enumerate(order, start=1):
        if len(rec.top) == TOPN:
            break
        name = ds.names.get(code) or str(code)
        rebs = rule_rebuttals(ds, code, T, reg)
        extra, st = llm_rebuttals(provider, name, docs)
        rebs += extra
        stats.calls += st.calls
        stats.docs = st.docs
        stats.claimed += st.claimed
        stats.verified += st.verified
        entry = Entry(code, name, i, sc.get(code), rebs, False)
        holds = [r.text for r in rebs if r.kind == "보류제안"]
        if holds:
            a = confirm_hold(name, holds, auto, input_fn)
            rec.approvals.append(a)
            if a.approved:
                rec.excluded.append(entry)
                continue
            entry.hold_pending = a.by != "사람"
        rec.top.append(entry)
    if len(rec.top) < TOPN:
        rec.notes.append("후보가 셋보다 적다")
    rec.llm = stats
    return rec
