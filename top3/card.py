"""TOP3 카드(마크다운) · JSON · 지표. 숫자는 프로그램이 넣고, 빈 값은 「—」와 빈칸 목록으로 보인다."""
from dataclasses import asdict, dataclass, field

from .approval import Approval
from .backtest import FoldResult
from .data import export, market
from .recommend import Recommendation
from .select import Selection

QUESTION_TITLE = {"expand": "큰 시장 확대 TOP3", "next": "다음 시장 TOP3"}
QUESTION_DESC = {"expand": "전체 상대국 중 앞으로 4년 수출이 가장 크게 늘 나라",
                 "next": "그해 수출 상위 3개국을 뺀 나라 중 다음으로 키울 나라"}
METHOD_LABEL = {"size": "크기순(지금 큰 시장)", "trend": "추세순(최근 3년 증가)", "formula07": "실측 07 공식",
                "market_growth": "수입 시장 성장", "remaining_market": "남은 시장 크기",
                "hs6_mix": "세부 품목 수요(HS 6단위)"}
REASON_LABEL = {"beat_baseline": "기준선보다 앞섰다", "baseline_default": "앞선 방식이 없어 상식 기준선",
                "confirm_dropped": "확인 구간에서 떨어져 기준선"}


@dataclass
class RunResult:
    run_id: str
    started: str
    reg: object
    selections: dict[str, Selection]
    recs: dict[str, Recommendation]
    final: dict[str, Approval]
    timings: dict[str, float]
    missing: list[str]
    blanks: list[str]
    baseline_tops: dict[str, dict[str, list[str]]]
    folds: dict[str, list[FoldResult]] = field(default_factory=dict)
    kr_context: dict[int, float] = field(default_factory=dict)
    sources_failed: list[str] = field(default_factory=list)
    reproducibility: float | None = None
    fetched_range: tuple[str, str] | None = None
    excluded_methods: list[str] = field(default_factory=list)


def _musd(v) -> str:
    return "—" if v is None else f"{v / 1e6:,.1f}"


def _approval_label(a: Approval) -> str:
    if a.kind == "hold":
        return {"자동": "자동(보류 적용 안 함)", "응답 없음": "사람 응답 없음(보류 적용 안 함)"}.get(
            a.by, "사람이 보류를 승인" if a.approved else "사람이 보류를 거절")
    if a.by == "자동":
        return "자동(사람 확인 안 함)"
    if a.by == "응답 없음":
        return "사람 응답 없음(확정 안 됨)"
    return "사람이 확정" if a.approved else "사람이 확정하지 않음"


def _score(method: str, v) -> str:
    if v is None:
        return "—"
    return _musd(v) if method in ("size", "trend") else f"{v:.3f}"


def _question_section(run: RunResult, ds, q: str) -> list[str]:
    reg, sel, rec = run.reg, run.selections[q], run.recs[q]
    T = reg.target_year
    out = [f"## {QUESTION_TITLE[q]}", "", f"{QUESTION_DESC[q]}. 기준 연도 {T}.", "",
           f"최종 확정: {_approval_label(run.final[q])}", "",
           f"| 순위 | 나라 | 점수({METHOD_LABEL[rec.method]}) | {T} 한국 수출 | {reg.context_year_kr} 한국 수출(참고) "
           f"| 3년 증가 | 시장 {T} | 한국 몫 | 인구 | 1인당 GDP(달러) | 조건 |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for pos, e in enumerate(rec.top, start=1):
        m = market(ds, T, e.code, reg.hs)
        exp_t = export(ds, T, e.code)
        share = f"{exp_t / m:.1%}" if m else "—"
        ctx = ds.context.get(e.code, {})
        pop = ctx.get("population")
        gdp = ctx.get("gdp_pc")
        conds = " · ".join(r.text for r in e.rebuttals if r.kind == "조건") or "—"
        out.append(f"| {pos} | {e.name} | {_score(rec.method, e.score)} | {_musd(exp_t)} "
                   f"| {_musd(run.kr_context.get(e.code))} | {_musd(exp_t - export(ds, T - reg.lookback, e.code))} "
                   f"| {_musd(m)} | {share} | {'—' if pop is None else f'{pop / 1e6:,.1f}백만'} "
                   f"| {'—' if gdp is None else f'{gdp:,.0f}'} | {conds} |")
    out += ["", "금액 단위: 백만 달러(명목). 출처: UN Comtrade · 세계은행.", ""]

    pending = [e for e in rec.top if e.hold_pending]
    if pending:
        out += ["### 사람 확인을 기다리는 보류 제안", ""]
        for e in pending:
            out += [f"- {e.name}: " + " / ".join(r.text for r in e.rebuttals if r.kind == "보류제안")]
        out.append("")
    if rec.excluded:
        out += ["### 사람이 보류를 승인해 빠진 후보", ""]
        out += [f"- {e.name}: " + " / ".join(r.text for r in e.rebuttals if r.kind == "보류제안") for e in rec.excluded]
        out.append("")

    out += ["### 고른 방식과 이유", "",
            f"**{METHOD_LABEL[sel.method]}** — {REASON_LABEL[sel.reason]}. 기준선: {METHOD_LABEL[sel.baseline]}.", ""]
    n_sel, n_conf = len(reg.select_folds) * 3, len(reg.confirm_folds) * 3
    out += [f"| 방식 | 앞 구간 적중({reg.select_folds[0]}~{reg.select_folds[-1]}, {n_sel}개 중) "
            f"| 확인 구간 적중({reg.confirm_folds[0]}~{reg.confirm_folds[-1]}, {n_conf}개 중) | 앞 구간 증가액 |",
            "|---|---|---|---|"]
    for name, t in sel.totals.items():
        out.append(f"| {METHOD_LABEL.get(name, name)} | {t.sel_hits} | {t.conf_hits} | {_musd(t.sel_gain)} |")
    out.append("")
    out += [f"- {n}" for n in sel.notes + rec.notes]
    if sel.near_tie and q in run.baseline_tops:
        out += ["", "### 두 기준선의 TOP3", ""]
        for name, names in run.baseline_tops[q].items():
            out.append(f"- {METHOD_LABEL.get(name, name)}: {', '.join(names)}")
    out.append("")
    return out


def render_card(run: RunResult, ds) -> str:
    reg = run.reg
    lines = [f"# 수출 유망국 TOP3 카드 — 과자·초콜릿·껌·빙과(HS {' · '.join(reg.hs)})", "",
             f"실행 {run.run_id} · {run.started}", ""]
    for q in ("expand", "next"):
        if q in run.recs:
            lines += _question_section(run, ds, q)
    llm = next(iter(run.recs.values())).llm if run.recs else None
    lines += ["## 이 카드를 읽는 법", "",
              "- 「유망」의 정의: T→T+4 한국 수출 증가액. 되감기 시험의 정답도 이 정의로 셌다.",
              f"- 방식 등록부(registry.json, {reg.registered}): {reg.note}",
              "- 순위는 프로그램이 통계로 계산한다. 반론은 후보를 빼거나 조건을 붙일 뿐 순위를 올리지 못하고, 후보를 빼는 것은 사람이 승인할 때만이다.",
              f"- LLM 반론: {llm.status if llm else '건너뜀(키 없음)'}",
              "- 수입은 소비와 같지 않다. 재수출 거점은 조건으로 표시했다.", ""]
    approvals = [f"- [{QUESTION_TITLE[q]}] {_approval_label(a)} — {a.what}"
                 for q, rec in run.recs.items() for a in rec.approvals]
    approvals += [f"- [{QUESTION_TITLE[q]}] 최종 TOP3: {_approval_label(a)}" for q, a in run.final.items()]
    lines += ["## 승인 기록", ""] + approvals + [""]
    lines += ["## 빈칸", ""] + ([f"- {b}" for b in run.blanks] or ["- 없음"]) + [""]
    if run.missing:
        lines += ["## 받지 못한 원자료", ""] + [f"- {m}" for m in run.missing] + [""]
    if run.sources_failed:
        lines += ["## 받지 못한 글 자료", ""] + [f"- {u}" for u in run.sources_failed] + [""]
    fetched = (f"받은 날짜: {run.fetched_range[0]} ~ {run.fetched_range[1]}" if run.fetched_range
               else "받은 날짜: 기록 없음(이 프로그램이 받지 않은 원자료)")
    lines += ["## 출처", "",
              "- UN Comtrade 공개 API(preview) — 한국의 상대국별 수출, 각국 세계 수입. 받은 응답은 data\\raw\\ 에 그대로 있다",
              "- 세계은행 API — 인구(SP.POP.TOTL), 1인당 GDP(NY.GDP.PCAP.CD)",
              f"- {fetched}", ""]
    return "\n".join(lines)


def card_json(run: RunResult) -> dict:
    return asdict(run)


def metrics(run: RunResult) -> dict:
    out = {}
    for q, sel in run.selections.items():
        rec = run.recs[q]
        folds = run.folds.get(q, [])
        best = sum(f.best3_gain for f in folds)
        got = sum(f.picks[sel.method].gain for f in folds if sel.method in f.picks)
        base = sel.totals.get(sel.baseline)
        chosen = sel.totals.get(sel.method)
        out[q] = {
            "method": sel.method, "reason": sel.reason, "near_tie": sel.near_tie,
            "totals": {m: {"sel_hits": t.sel_hits, "conf_hits": t.conf_hits,
                           "sel_gain_musd": round(t.sel_gain / 1e6, 1), "conf_gain_musd": round(t.conf_gain / 1e6, 1)}
                       for m, t in sel.totals.items()},
            "vs_baseline": {"sel_hits": chosen.sel_hits - base.sel_hits, "conf_hits": chosen.conf_hits - base.conf_hits}
            if chosen and base else None,
            "realized_gain_ratio": round(got / best, 3) if best else None,
            "citation_rate": round(rec.llm.verified / rec.llm.claimed, 3) if rec.llm.claimed else None,
            "citation_note": None if rec.llm.claimed else "해당 없음(LLM 반론 없음)",
            "llm_calls": rec.llm.calls,
        }
    out["timings_sec"] = run.timings
    out["blanks"] = len(run.blanks)
    out["missing_raw"] = len(run.missing)
    out["reproducibility"] = run.reproducibility
    return out
