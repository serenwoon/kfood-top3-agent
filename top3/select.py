"""되감기 결과로 이번 TOP3 에 쓸 방식을 고른다(설계 9-1 ①②).

1. 기준선 중 (앞 구간 적중, 앞 구간 증가액)이 큰 쪽. 그래도 같으면 단순한 쪽(simplicity_order 앞).
2. 후보 방식은 그 기준선보다 앞 구간 적중이 margin_hits 이상 많아야 한다. 없으면 기준선으로 낸다.
3. 고른 방식이 확인 구간에서 기준선보다 적중이 낮으면 기준선으로 되돌린다.
"""
from dataclasses import dataclass, field

from .backtest import FoldResult


@dataclass
class Totals:
    method: str
    sel_hits: int
    sel_gain: float
    conf_hits: int
    conf_gain: float


@dataclass
class Selection:
    question: str
    method: str
    baseline: str
    reason: str            # beat_baseline | baseline_default | confirm_dropped
    near_tie: bool
    notes: list[str] = field(default_factory=list)
    totals: dict[str, Totals] = field(default_factory=dict)


def totals(sel: list[FoldResult], conf: list[FoldResult]) -> dict[str, Totals]:
    methods = list(sel[0].picks) if sel else []
    return {m: Totals(m,
                      sum(f.picks[m].hits for f in sel), sum(f.picks[m].gain for f in sel),
                      sum(f.picks[m].hits for f in conf), sum(f.picks[m].gain for f in conf))
            for m in methods}


def choose(t: dict[str, Totals], reg, question: str) -> Selection:
    order = {m: i for i, m in enumerate(reg.simplicity_order)}
    key = lambda x: (x.sel_hits, x.sel_gain, -order.get(x.method, len(order)))
    bases = [t[b] for b in reg.baselines if b in t]
    base = max(bases, key=key)
    notes, near = [], False
    tied = [b for b in bases if b is not base and b.sel_hits == base.sel_hits]
    if tied:
        notes.append("두 기준선의 앞 구간 적중이 같아 실현 증가액으로 골랐다")
        if any(abs(b.sel_gain - base.sel_gain) < reg.near_tie_gain_musd * 1e6 for b in tied):
            near = True
            notes.append(f"두 기준선의 증가액 차이가 {reg.near_tie_gain_musd:g}백만 달러 미만이라 사실상 같다")

    cands = [t[m] for m in reg.methods if m in t and t[m].sel_hits >= base.sel_hits + reg.margin_hits]
    if not cands:
        notes.append(f"기준선보다 앞 구간 적중이 {reg.margin_hits}개 이상 많은 방식이 없어 상식 기준선으로 냈다")
        return Selection(question, base.method, base.method, "baseline_default", near, notes, t)
    best = max(cands, key=key)
    if best.conf_hits < base.conf_hits:
        notes.append(f"{best.method} 가 앞 구간에서 앞섰지만 확인 구간에서 기준선보다 적중이 낮아 기준선으로 되돌렸다")
        return Selection(question, base.method, base.method, "confirm_dropped", near, notes, t)
    notes.append(f"{best.method} 가 앞 구간에서 기준선보다 {best.sel_hits - base.sel_hits}개 더 맞혔고 확인 구간에서도 떨어지지 않았다")
    return Selection(question, best.method, base.method, "beat_baseline", near, notes, t)
