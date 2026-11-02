from conftest import needs_real_raw
from top3.backtest import run_fold
from top3.select import Totals, choose, totals


def T(method, sel_hits, sel_gain, conf_hits, conf_gain):
    return Totals(method, sel_hits, sel_gain, conf_hits, conf_gain)


def test_baseline_tie_broken_by_gain(reg):
    t = {"size": T("size", 7, 147.8e6, 4, 0), "trend": T("trend", 7, 106.6e6, 3, 0),
         "formula07": T("formula07", 6, 0, 3, 0)}
    s = choose(t, reg, "expand")
    assert (s.method, s.reason, s.near_tie) == ("size", "baseline_default", False)
    assert any("적중이 같아" in n for n in s.notes)


def test_near_tie_flagged_under_one_million(reg):
    t = {"size": T("size", 6, 44.2e6, 3, 0), "trend": T("trend", 6, 44.5e6, 3, 0)}
    s = choose(t, reg, "next")
    assert s.method == "trend" and s.near_tie is True


def test_margin_boundary(reg):
    base = T("size", 7, 1e6, 4, 0)
    assert choose({"size": base, "hs6_mix": T("hs6_mix", 9, 0, 5, 0)}, reg, "expand").method == "hs6_mix"
    assert choose({"size": base, "hs6_mix": T("hs6_mix", 8, 0, 5, 0)}, reg, "expand").method == "size"


def test_confirm_drop_reverts_to_baseline(reg):
    s = choose({"size": T("size", 7, 1e6, 4, 0), "hs6_mix": T("hs6_mix", 9, 0, 3, 0)}, reg, "expand")
    assert (s.method, s.reason) == ("size", "confirm_dropped")


@needs_real_raw
def test_real_data_known_scope(ds_real, reg):
    three = ["formula07", "size", "trend"]
    for q, want, near in (("expand", "size", False), ("next", "trend", True)):
        sel = [run_fold(ds_real, y, q, three, reg) for y in reg.select_folds]
        conf = [run_fold(ds_real, y, q, three, reg) for y in reg.confirm_folds]
        s = choose(totals(sel, conf), reg, q)
        assert (s.method, s.reason, s.near_tie) == (want, "baseline_default", near)
