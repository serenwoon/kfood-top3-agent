import io
import json

from conftest import make_ds
from top3.data import attach_context
from top3.worldbank import fetch


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def wb_body(rows):
    return json.dumps([{"page": 1}, rows]).encode()


def test_null_value_stays_none(tmp_path):
    bodies = iter([
        wb_body([{"countryiso3code": "CAN", "value": 41_262_329}, {"countryiso3code": "MNG", "value": None}]),
        wb_body([{"countryiso3code": "CAN", "value": 55_015.7}, {"countryiso3code": "MNG", "value": 5_000.0}]),
    ])
    out = fetch(tmp_path, 2024, opener=lambda req, timeout=None: _Resp(next(bodies)), sleep=lambda s: None)
    assert out["CAN"] == {"population": 41_262_329.0, "gdp_pc": 55_015.7}
    assert out["MNG"]["population"] is None and out["MNG"]["gdp_pc"] == 5_000.0


def test_unknown_code_gets_none_context():
    ds = make_ds(kr={(2024, 124): 1.0, (2024, 490): 1.0}, names={124: "Canada", 490: "Other Asia, nes"})
    table = {124: {"name": "Canada", "iso3": "CAN"}, 490: {"name": "Other Asia, nes", "iso3": "S19"}}
    wb = {"CAN": {"population": 41e6, "gdp_pc": 55e3}}
    attach_context(ds, table, wb, 2024)
    assert ds.context[124] == {"iso3": "CAN", "name": "Canada", "population": 41e6, "gdp_pc": 55e3, "year": 2024}
    assert ds.context[490]["population"] is None and ds.context[490]["gdp_pc"] is None
