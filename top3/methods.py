"""점수 방식 여섯. 값이 없는 나라는 결과 사전에서 빠진다(0 을 넣지 않는다).

formula07 은 kfood-export-backtest/backtest.py 의 s1·s2·s3 과 pct_ranks 를 그대로 옮겼다.
"""
import math

from .data import Dataset, export, market

METHODS = ("size", "trend", "formula07", "market_growth", "remaining_market", "hs6_mix")


def cagr(a, b, n):
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return (b / a) ** (1 / n) - 1


def pct_ranks(values: dict) -> dict:
    """{key: value or None} -> {key: 백분위(0~1)}, None 은 빠진다."""
    items = sorted((v, k) for k, v in values.items() if v is not None)
    n = len(items)
    return {k: (i / (n - 1) if n > 1 else 0.5) for i, (v, k) in enumerate(items)}


def eligible(ds: Dataset, T: int, partners, reg) -> list[int]:
    return [p for p in partners if export(ds, T, p) >= reg.min_export]


def _s1(ds, T, p, reg):
    return cagr(export(ds, T - reg.lookback, p), export(ds, T, p), reg.lookback)


def _s2(ds, T, p, reg):
    return cagr(market(ds, T - reg.lookback, p, reg.hs), market(ds, T, p, reg.hs), reg.lookback)


def _s3(ds, T, p, reg):
    m = market(ds, T, p, reg.hs)
    if m and m > 0:
        share = min(export(ds, T, p) / m, 1.0)
        return math.log(m * (1 - share)) if share < 1 else None
    return None


def _hs6_mix(ds, T, p, reg):
    num = den = 0.0
    for k in reg.hs6:
        w = ds.kr_hs6_world.get((T, k))
        g = cagr(ds.hs6_imports.get((T - reg.lookback, p, k)), ds.hs6_imports.get((T, p, k)), reg.lookback)
        if w and g is not None:
            num += w * g
            den += w
    return num / den if den else None


def scores(method: str, ds: Dataset, T: int, cands: list[int], reg) -> dict[int, float]:
    if method == "size":
        return {p: export(ds, T, p) for p in cands}
    if method == "trend":
        return {p: export(ds, T, p) - export(ds, T - reg.lookback, p) for p in cands}
    if method == "formula07":
        r1 = pct_ranks({p: _s1(ds, T, p, reg) for p in cands})
        r2 = pct_ranks({p: _s2(ds, T, p, reg) for p in cands})
        r3 = pct_ranks({p: _s3(ds, T, p, reg) for p in cands})
        out = {}
        for p in cands:
            parts = [r[p] for r in (r1, r2, r3) if p in r]
            if parts:
                out[p] = sum(parts) / len(parts)
        return out
    one = {"market_growth": _s2, "remaining_market": _s3, "hs6_mix": _hs6_mix}.get(method)
    if one is None:
        raise ValueError(f"등록되지 않은 방식: {method}")
    out = {}
    for p in cands:
        v = one(ds, T, p, reg)
        if v is not None:
            out[p] = v
    return out


def ranked(method: str, ds: Dataset, T: int, cands: list[int], reg) -> list[int]:
    s = scores(method, ds, T, cands, reg)
    return sorted(s, key=lambda p: -s[p])
