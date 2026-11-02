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


def test_cli_prints_korean_on_cp949(tmp_home_with_fixture_raw):
    env = {**os.environ, "PYTHONIOENCODING": "cp949", "TOP3_HOME": str(tmp_home_with_fixture_raw)}
    env.pop("PYTHONUTF8", None)
    p = subprocess.run([sys.executable, "-m", "top3", "run", "--auto", "--offline"],
                       env=env, capture_output=True)
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")
