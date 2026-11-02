"""방식 등록부 registry.json 을 읽는다. 등록부는 실행 전에 고정하고 결과를 본 뒤 고치지 않는다."""
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Registry:
    registered: str
    note: str
    hs: list[str]
    hs6: list[str]
    years_world: list[int]
    years_kr: list[int]
    lookback: int
    horizon: int
    min_export: int
    select_folds: list[int]
    confirm_folds: list[int]
    questions: dict
    baselines: list[str]
    methods: list[str]
    margin_hits: int
    near_tie_gain_musd: float
    simplicity_order: list[str]
    target_year: int
    context_year_kr: int
    rules: dict
    random_draws: int

    def world_years(self) -> range:
        return range(self.years_world[0], self.years_world[1] + 1)

    def kr_years(self) -> range:
        return range(self.years_kr[0], self.years_kr[1] + 1)


def load_registry(path: Path) -> Registry:
    return Registry(**json.loads(path.read_text(encoding="utf-8")))
