import os
import subprocess
import sys

import pytest

from top3 import cli, pipeline


def test_end_to_end_offline_auto(tmp_home_with_fixture_raw):
    run, ds = pipeline.run(tmp_home_with_fixture_raw, auto=True, offline=True)
    path = pipeline.write(run, ds, tmp_home_with_fixture_raw / "out")
    text = (path / "card.md").read_text(encoding="utf-8")
    assert "큰 시장 확대 TOP3" in text and "다음 시장 TOP3" in text and "자동(사람 확인 안 함)" in text
    for name in ("card.json", "metrics.json", "log.txt"):
        assert (path / name).exists()


def test_offline_without_raw_exits_with_message(tmp_path):
    with pytest.raises(SystemExit) as e:
        pipeline.run(tmp_path, auto=True, offline=True)
    assert "다시 돌리면" in str(e.value)


def test_run_ids_do_not_collide(tmp_home_with_fixture_raw):
    assert cli.main(["run", "--auto", "--offline"]) == 0
    assert cli.main(["run", "--auto", "--offline"]) == 0
    assert len(list((tmp_home_with_fixture_raw / "out").iterdir())) == 2


def test_repeat_writes_reproducibility(tmp_home_with_fixture_raw):
    assert cli.main(["run", "--auto", "--offline", "--repeat", "2"]) == 0
    out = next((tmp_home_with_fixture_raw / "out").iterdir())
    assert '"reproducibility": 1.0' in (out / "metrics.json").read_text(encoding="utf-8")


def test_missing_core_file_exits_with_names(tmp_home_with_fixture_raw):
    """리뷰 C1: 되감기 범위 원자료가 하나라도 없으면 0 으로 계산하지 않고 이름과 명령을 말하고 멈춘다."""
    (tmp_home_with_fixture_raw / "data" / "raw" / "kr_export_2020_1806.json").unlink()
    for offline in (True, False):
        with pytest.raises(SystemExit) as e:
            pipeline.run(tmp_home_with_fixture_raw, auto=True, offline=offline,
                         opener=_fail, sleep=lambda s: None)
        msg = str(e.value)
        assert "kr_export_2020_1806" in msg and "-m top3 run" in msg


def test_hs6_missing_excludes_method_not_zero(tmp_home_with_fixture_raw):
    """리뷰 C1: 세부 품목 자료가 없으면 hs6_mix 를 0 으로 겨루지 않고 이번 실행에서 뺀다."""
    run, _ = pipeline.run(tmp_home_with_fixture_raw, auto=True, offline=True)
    sel = run.selections["expand"]
    assert "hs6_mix" not in sel.totals
    assert any("hs6_mix" in n for n in sel.notes)


def test_llm_setting_checked_before_download(tmp_home_with_fixture_raw, monkeypatch):
    """TOP3_LLM 오타는 10분 받기 전에 알려야 한다."""
    calls = []
    monkeypatch.setenv("TOP3_LLM", "anthropic")
    with pytest.raises(SystemExit):
        pipeline.run(tmp_home_with_fixture_raw, auto=True, offline=False,
                     opener=lambda *a, **k: calls.append(a), sleep=lambda s: None)
    assert calls == []


def test_repeat_forces_auto_on_first_run(tmp_home_with_fixture_raw, monkeypatch):
    """리뷰 I5: --repeat 는 첫 실행도 자동으로 돌려 같은 조건끼리 비교한다."""
    seen = []
    real = pipeline.run

    def spy(home, auto, offline, **kw):
        seen.append(auto)
        return real(home, auto=auto, offline=offline, **kw)
    monkeypatch.setattr(pipeline, "run", spy)
    assert cli.main(["run", "--offline", "--repeat", "2"]) == 0
    assert seen == [True, True]


def _fail(req, timeout=None):
    raise OSError("down")


def test_cli_prints_korean_on_cp949(tmp_home_with_fixture_raw):
    env = {**os.environ, "PYTHONIOENCODING": "cp949", "TOP3_HOME": str(tmp_home_with_fixture_raw)}
    env.pop("PYTHONUTF8", None)
    p = subprocess.run([sys.executable, "-m", "top3", "run", "--auto", "--offline"],
                       env=env, capture_output=True)
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")
