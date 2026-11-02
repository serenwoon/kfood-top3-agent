"""사람 승인 두 자리 — 반론으로 후보를 뺄지, 최종 TOP3 를 확정할지.

--auto 는 보류 제안을 적용하지 않는다(LLM·규칙 혼자 TOP3 를 바꾸지 못하게).
입력을 받을 수 없는 창(EOFError)은 「응답 없음」으로 적고 멈추지 않는다.
"""
from dataclasses import dataclass

YES = {"y", "yes", "예", "네", "ㅇ"}


@dataclass
class Approval:
    approved: bool
    by: str          # 사람 | 자동 | 응답 없음
    what: str
    kind: str = "top3"   # top3 | hold


def _ask(prompt: str, input_fn) -> tuple[bool | None, str]:
    try:
        answer = input_fn(prompt)
    except EOFError:
        return None, "응답 없음"
    return answer.strip().lower() in YES, "사람"


def confirm_hold(country: str, reasons: list[str], auto: bool, input_fn=input) -> Approval:
    what = f"{country} 보류 — " + " / ".join(reasons)
    if auto:
        return Approval(False, "자동", what, kind="hold")
    ok, by = _ask(f"[승인 1] {country}: 보류 제안 — {' / '.join(reasons)}\n  후보에서 뺄까요? [y/N] ", input_fn)
    return Approval(bool(ok), by, what, kind="hold")


def confirm_top3(summary: str, auto: bool, input_fn=input) -> Approval:
    if auto:
        return Approval(True, "자동", summary)
    ok, by = _ask(f"[승인 2] 최종 TOP3\n{summary}\n  이대로 확정할까요? [y/N] ", input_fn)
    return Approval(bool(ok), by, summary)
