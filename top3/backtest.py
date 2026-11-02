"""되감기 한 시점(fold). kfood-export-backtest/backtest.py 의 fold() 를 옮겼다.

T년까지의 자료로 방식마다 TOP3 를 뽑고, T→T+horizon 의 실제 한국 수출 증가와 대조한다.
partners 집합과 eligible 의 순서, 무작위 기준선의 시드·횟수를 바꾸지 않는다 — 공개 저장소와 같은 숫자가 나와야 한다.
"""
import random
from dataclasses import dataclass

from .data import Dataset, export
from .methods import eligible, ranked

TOPN = 3


@dataclass
class Pick:
    codes: list[int]
    hits: int
    gain: float          # 달러


@dataclass
class FoldResult:
    T: int
    question: str
    truth: list[int]
    best3_gain: float
    picks: dict[str, Pick]
    random_hits: float   # 소수 둘째 자리 반올림
    random_gain: float


def run_fold(ds: Dataset, T: int, question: str, methods: list[str], reg) -> FoldResult:
    q = reg.questions[question]
    drop_top, truth_n = q["drop_top"], q["truth_n"]
    partners = {p for (y, p) in ds.kr}
    exp = lambda y, p: export(ds, y, p)
    if drop_top:
        partners -= set(sorted(partners, key=lambda p: -exp(T, p))[:drop_top])

    elig = eligible(ds, T, partners, reg)
    gain = {p: exp(T + reg.horizon, p) - exp(T, p) for p in partners}
    truth = sorted(gain, key=lambda p: -gain[p])[:truth_n]
    best3 = sum(gain[p] for p in truth[:TOPN])

    def pack(codes):
        return Pick(codes, sum(1 for p in codes if p in truth), sum(gain[p] for p in codes))

    picks = {m: pack(ranked(m, ds, T, elig, reg)[:TOPN]) for m in methods}

    rng = random.Random(T)
    sims = [rng.sample(elig, TOPN) for _ in range(reg.random_draws)]
    rand_hits = sum(sum(1 for p in s if p in truth) for s in sims) / len(sims)
    rand_gain = sum(sum(gain[p] for p in s) for s in sims) / len(sims)
    return FoldResult(T, question, truth, best3, picks, round(rand_hits, 2), rand_gain)
