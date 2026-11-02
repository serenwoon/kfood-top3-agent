"""공개 저장소 kfood-export-backtest 의 out/run_log.txt 숫자를 그대로 재현해야 한다."""
from conftest import needs_real_raw
from top3.backtest import run_fold

THREE = ["formula07", "size", "trend"]


def musd(values):
    """공개 저장소처럼 시점마다 백만 달러 소수 한 자리로 반올림한 뒤 더한다."""
    return round(sum(round(v / 1e6, 1) for v in values), 1)


@needs_real_raw
def test_reproduces_public_repo_expand(ds_real, reg):
    folds = [run_fold(ds_real, T, "expand", THREE, reg) for T in range(2016, 2021)]
    assert sum(f.picks["formula07"].hits for f in folds) == 9
    assert sum(f.picks["size"].hits for f in folds) == 11
    assert sum(f.picks["trend"].hits for f in folds) == 10
    assert round(sum(f.random_hits for f in folds), 2) == 8.66
    assert musd(f.picks["formula07"].gain for f in folds) == 254.4
    assert musd(f.picks["size"].gain for f in folds) == 287.3
    assert musd(f.best3_gain for f in folds) == 443.5


@needs_real_raw
def test_reproduces_public_repo_next(ds_real, reg):
    folds = [run_fold(ds_real, T, "next", THREE, reg) for T in range(2016, 2021)]
    assert [sum(f.picks[m].hits for f in folds) for m in THREE] == [5, 9, 9]
    assert round(sum(f.random_hits for f in folds), 2) == 5.19
    assert musd(f.picks["trend"].gain for f in folds) == 82.6


@needs_real_raw
def test_fold_2016_picks_match_run_log(ds_real, reg):
    f = run_fold(ds_real, 2016, "expand", THREE, reg)
    assert [ds_real.names[c] for c in f.picks["formula07"].codes] == ["USA", "China", "United Arab Emirates"]
    assert len(f.truth) == 10 and ds_real.names[f.truth[0]] == "USA"
