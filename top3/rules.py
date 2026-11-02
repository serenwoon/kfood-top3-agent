"""규칙 반론 — LLM 없이 통계 숫자로 판정한다(설계 5절 ④). 기준값은 registry.json 의 rules.

반론은 후보를 조건부로 만들거나(조건) 빼자고 제안할(보류제안) 뿐, 순위를 올리지 못한다.
보류제안을 실제로 적용할지는 사람이 정한다(approval.py).
"""
from dataclasses import dataclass

from .data import export, market
from .methods import cagr


@dataclass
class Rebuttal:
    kind: str            # 조건 | 보류제안
    rule: str
    text: str
    origin: str          # 규칙 | LLM
    source: str
    year: int
    value: float | None
    url: str | None = None
    quote: str | None = None


def rule_rebuttals(ds, code: int, T: int, reg) -> list[Rebuttal]:
    r = reg.rules
    out: list[Rebuttal] = []
    if code in r["reexport_hubs"]:
        out.append(Rebuttal("조건", "reexport", "재수출 거점이라 수입이 곧 소비가 아니다",
                            "규칙", "UN Comtrade", T, None))
    m_now, m_then = market(ds, T, code, reg.hs), market(ds, T - reg.lookback, code, reg.hs)
    if m_now is None or m_then is None:
        out.append(Rebuttal("조건", "market_blank", "시장 자료가 비어 판단 근거가 부족하다",
                            "규칙", "UN Comtrade", T, None))
        return out
    g_market = cagr(m_then, m_now, reg.lookback)
    if g_market is not None and g_market < r["shrink_cagr_max"]:
        out.append(Rebuttal("조건", "market_shrink", f"시장이 줄고 있다(3년 연평균 {g_market:+.1%})",
                            "규칙", "UN Comtrade", T, g_market))
    share = export(ds, T, code) / m_now if m_now else None
    if share is not None and share >= r["korea_share_min"]:
        out.append(Rebuttal("조건", "korea_share", f"한국 몫이 {share:.0%}로 커 남은 자리가 작다",
                            "규칙", "UN Comtrade", T, share))
    g_korea = cagr(export(ds, T - reg.lookback, code), export(ds, T, code), reg.lookback)
    if g_market is not None and g_korea is not None and g_market < 0 and g_korea < 0:
        out.append(Rebuttal("보류제안", "both_shrink",
                            f"시장(3년 연평균 {g_market:+.1%})과 한국 수출({g_korea:+.1%})이 함께 줄고 있다",
                            "규칙", "UN Comtrade", T, g_korea))
    return out
