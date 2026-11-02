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
    provider = get_provider(os.environ)        # 설정 오타는 받기 전에 알린다
    if offline:
        opener, sleep = _no_network, (lambda s: None)

    missing = [] if offline else comtrade.fetch_all(raw, reg.hs, reg.hs6, reg.world_years(), reg.kr_years(),
                                                    opener=opener, sleep=sleep,
                                                    progress=lambda s: print(s, flush=True))
    core = [f"{kind}_{y}_{h}" for y in reg.world_years() for h in reg.hs
            for kind in ("kr_export", "world_import")]
    lacking = [n for n in core if comtrade.read_cache(raw / f"{n}.json") is None]
    if lacking:
        shown = ", ".join(lacking[:20]) + (f" 외 {len(lacking) - 20}건" if len(lacking) > 20 else "")
        raise SystemExit(
            f"되감기에 필요한 원자료 {len(lacking)}건이 없어 계산하지 않는다(빈 자료를 0으로 셈하지 않으려고): {shown}\n"
            "인터넷 연결을 확인하고 같은 명령을 다시 돌리면 받은 것은 다시 받지 않고 빠진 것만 받는다:\n"
            f'& "{home / ".venv" / "Scripts" / "python.exe"}" -m top3 run')
    hs6_names = [f"world_import_{y}_{k}" for y in reg.world_years() for k in reg.hs6]
    hs6_names += [f"kr_export_world_{y}_hs6" for y in reg.world_years()]
    excluded = []
    if reg.hs6 and any(comtrade.read_cache(raw / f"{n}.json") is None for n in hs6_names):
        excluded.append("hs6_mix")
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
    docs, failed = load_sources(home / "sources", opener=opener)

    methods = [m for m in reg.baselines + reg.methods if m not in excluded]
    selections, recs, final, folds, baseline_tops = {}, {}, {}, {}, {}
    for q in QUESTIONS:
        t1 = time.perf_counter()
        sel_f = [run_fold(ds, y, q, methods, reg) for y in reg.select_folds]
        conf_f = [run_fold(ds, y, q, methods, reg) for y in reg.confirm_folds]
        folds[q] = sel_f + conf_f
        sel = choose(totals(sel_f, conf_f), reg, q)
        if "hs6_mix" in excluded:
            sel.notes.append("세부 품목(HS 6단위) 자료가 일부 없어 hs6_mix 를 이번 실행에서 뺐다(0점으로 겨루지 않았다)")
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
    log = comtrade.read_cache(raw / comtrade.FETCHED_LOG) or {}
    fetched = (min(log.values()), max(log.values())) if log else None
    now = datetime.now()
    result = RunResult(now.strftime("%Y%m%d-%H%M%S"), now.isoformat(timespec="seconds"), reg,
                       selections, recs, final, timings, missing, blanks, baseline_tops,
                       folds, kr_context, failed, fetched_range=fetched, excluded_methods=excluded)
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
