"""명령줄: python -m top3 run [--auto] [--offline] [--repeat N]"""
import argparse
import sys

from . import paths, pipeline
from .card import QUESTION_TITLE


def _signature(run) -> dict:
    return {q: ([e.code for e in r.top], [[(b.rule, b.text) for b in e.rebuttals] for e in r.top])
            for q, r in run.recs.items()}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="top3", description="K-과자·빙과 수출 유망국 TOP3 카드를 만든다")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="수집부터 카드까지 한 번에")
    r.add_argument("--auto", action="store_true", help="승인을 묻지 않는다(보류 제안은 적용하지 않고 카드에 표시)")
    r.add_argument("--offline", action="store_true", help="새로 받지 않고 data\\raw 의 원자료만 쓴다")
    r.add_argument("--repeat", type=int, default=1, help="같은 원자료로 N번 돌려 재현성을 잰다(오프라인)")
    args = ap.parse_args(argv)

    home = paths.home()
    # --repeat 는 같은 조건끼리 비교하려고 첫 실행도 자동으로 돌린다(사람 승인이 섞이면 거짓으로 1 미만이 된다)
    run, ds = pipeline.run(home, auto=args.auto or args.repeat > 1, offline=args.offline)
    if args.repeat > 1:
        first = _signature(run)
        same = sum(_signature(pipeline.run(home, auto=True, offline=True)[0]) == first
                   for _ in range(args.repeat - 1))
        run.reproducibility = round((1 + same) / args.repeat, 3)
    path = pipeline.write(run, ds, paths.out_dir())
    print(f"카드: {path / 'card.md'}")
    for q, rec in run.recs.items():
        names = ", ".join(e.name for e in rec.top) or "(없음)"
        print(f"  {QUESTION_TITLE[q]}: {names}  [{rec.method}]")
    return 0
