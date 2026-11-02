"""홈 폴더와 그 아래 경로. 환경변수 TOP3_HOME 이 있으면 그것을, 없으면 저장소 폴더를 쓴다."""
import os
from pathlib import Path


def home() -> Path:
    env = os.environ.get("TOP3_HOME")
    return Path(env) if env else Path(__file__).resolve().parents[1]


def raw_dir() -> Path:
    return home() / "data" / "raw"


def sources_dir() -> Path:
    return home() / "sources"


def out_dir() -> Path:
    return home() / "out"


def registry_path() -> Path:
    return home() / "registry.json"
