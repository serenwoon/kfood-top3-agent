"""전체 흐름: 등록부 → 수집 → 되감기 → 방식 고르기 → 추천(반론·승인) → 카드."""
import json
import os
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from . import comtrade, worldbank
from .approval import confirm_top3
from .backtest import run_fold
from .card import QUESTION_TITLE, RunResult, card_json, metrics, render_card
from .config import load_registry
from .data import Dataset, attach_context, load, market
from .llm import get_provider, load_sources
from .methods import ranked
from .recommend import candidates, recommend
from .select import choose, totals

REPO_REGISTRY = Path(__file__).resolve().parents[1] / "registry.json"
QUESTIONS = ("expand", "next")


def _no_network(req, timeout=None):
    raise OSError("오프라인 실행")


def _registry(home: Path):
    own = home / "registry.json"
    return load_registry(own if own.exists() else REPO_REGISTRY)


def run(home: Path, auto: bool, offline: bool, input_fn=input,
        opener=urllib.request.urlopen, sleep=time.sleep) -> tuple[RunResult, Dataset]:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    reg = _registry(home)
    raw = home / "data" / "raw"
    T = reg.target_year
    if offline:
        opener, sleep = _no_network, (lambda s: None)

    missing = [] if offline else comtrade.fetch_all(raw, reg.hs, reg.hs6, reg.world_years(), reg.kr_years(),
                                                    opener=opener, sleep=sleep)
    try:
        table = comtrade.country_table(raw, opener=opener, sleep=sleep)
    except comtrade.FetchError:
        table = {}
    try:
        wb = worldbank.fetch(raw, T, opener=opener, sleep=sleep)
    except comtrade.FetchError:
        wb = {}
    timings["collect"] = round(time.perf_counter() - t0, 2)

    ds = load(raw, reg.hs, reg.world_years(), reg.hs6)   # 2013~2024 — 되감기 재현 범위
    if not ds.kr:
        raise SystemExit(f"한국 수출 원자료가 없다(받지 못한 것 {len(missing)}건). "
                         "인터넷 연결을 확인하고 같은 명령을 다시 돌리면 받은 것은 다시 받지 않는다.")
    nxt = load(raw, reg.hs, range(reg.context_year_kr, reg.context_year_kr + 1))
    kr_context = {p: v for (_, p), v in nxt.kr.items()}
    attach_context(ds, table, wb, T)
    provider = get_provider(os.environ)
    docs, failed = load_sources(home / "sources", opener=opener)

    methods = reg.baselines + reg.methods
    selections, recs, final, folds, baseline_tops = {}, {}, {}, {}, {}
    for q in QUESTIONS:
        t1 = time.perf_counter()
        sel_f = [run_fold(ds, y, q, methods, reg) for y in reg.select_folds]
        conf_f = [run_fold(ds, y, q, methods, reg) for y in reg.confirm_folds]
        folds[q] = sel_f + conf_f
        sel = choose(totals(sel_f, conf_f), reg, q)
        selections[q] = sel
        timings[f"backtest_{q}"] = round(time.perf_counter() - t1, 2)
        if sel.near_tie:
            cands = candidates(ds, reg, q, T)
            baseline_tops[q] = {b: [ds.names.get(c) or str(c) for c in ranked(b, ds, T, cands, reg)[:3]]
                                for b in reg.baselines}
        t2 = time.perf_counter()
        recs[q] = recommend(ds, reg, q, sel.method, provider, docs, auto, input_fn)
        timings[f"recommend_{q}"] = round(time.perf_counter() - t2, 2)
        summary = "\n".join(f"  {i}. {e.name}" for i, e in enumerate(recs[q].top, start=1))
        final[q] = confirm_top3(f"{QUESTION_TITLE[q]}\n{summary}", auto, input_fn)

    blanks: list[str] = []
    for rec in recs.values():
        for e in rec.top:
            ctx = ds.context.get(e.code, {})
            for label, empty in ((f"시장 {T}", market(ds, T, e.code, reg.hs) is None),
                                 ("인구", ctx.get("population") is None),
                                 ("1인당 GDP", ctx.get("gdp_pc") is None)):
                item = f"{e.name}: {label}"
                if empty and item not in blanks:
                    blanks.append(item)
    timings["total"] = round(time.perf_counter() - t0, 2)
    now = datetime.now()
    result = RunResult(now.strftime("%Y%m%d-%H%M%S"), now.isoformat(timespec="seconds"), reg,
                       selections, recs, final, timings, missing, blanks, baseline_tops,
                       folds, kr_context, failed)
    return result, ds


def _log(run: RunResult, ds: Dataset) -> str:
    lines = []
    for q, fs in run.folds.items():
        lines.append(f"######## {QUESTION_TITLE[q]}")
        for f in fs:
            lines.append(f"== T={f.T} 정답: " + " | ".join(ds.names.get(c) or str(c) for c in f.truth))
            for m, p in f.picks.items():
                names = " | ".join(ds.names.get(c) or str(c) for c in p.codes)
                lines.append(f"   {m:16s} 적중 {p.hits}/3 · 증가 {p.gain / 1e6:.1f}M$ · {names}")
            lines.append(f"   {'random':16s} 적중 {f.random_hits}/3")
        lines += [f"-> {n}" for n in run.selections[q].notes]
    return "\n".join(lines) + "\n"


def write(run: RunResult, ds: Dataset, out_dir: Path) -> Path:
    base, n = run.run_id, 1
    path = out_dir / base
    while path.exists():
        n += 1
        path = out_dir / f"{base}-{n}"
    path.mkdir(parents=True)
    run.run_id = path.name
    w = lambda name, text: (path / name).write_text(text, encoding="utf-8", newline="\n")
    w("card.md", render_card(run, ds))
    w("card.json", json.dumps(card_json(run), ensure_ascii=False, indent=1, default=str))
    w("metrics.json", json.dumps(metrics(run), ensure_ascii=False, indent=1))
    w("log.txt", _log(run, ds))
    return path
