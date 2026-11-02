import io
import json

from top3.comtrade import country_table, fetch_all, get


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_opener(bodies):
    it = iter(bodies)

    def opener(req, timeout=None):
        return _Resp(next(it))
    return opener


def always_fail(req, timeout=None):
    raise OSError("network down")


def test_get_uses_cache_without_request(tmp_path):
    (tmp_path / "x.json").write_text('{"data": [1]}', encoding="utf-8")
    calls = []
    assert get("x", "q", tmp_path, opener=lambda *a, **k: calls.append(a)) == {"data": [1]}
    assert calls == []


def test_get_saves_response_verbatim(tmp_path):
    body = b'{"count": 1, "data": [{"a": 1}]}'
    get("y", "q", tmp_path, opener=fake_opener([body]), sleep=lambda s: None)
    assert (tmp_path / "y.json").read_bytes() == body


def test_get_treats_error_key_as_failure(tmp_path):
    bodies = [b'{"error": "rate limit"}'] * 4
    try:
        get("z", "q", tmp_path, opener=fake_opener(bodies), sleep=lambda s: None)
        assert False, "FetchError 가 나야 한다"
    except Exception as e:
        assert type(e).__name__ == "FetchError"
    assert not (tmp_path / "z.json").exists()


def test_fetch_all_reports_failures_instead_of_zero(tmp_path):
    missing = fetch_all(tmp_path, ["1704"], [], range(2024, 2025), range(2024, 2025),
                        opener=always_fail, sleep=lambda s: None)
    assert set(missing) == {"kr_export_2024_1704", "world_import_2024_1704"}
    assert not any(tmp_path.glob("*.json"))


def test_country_table_maps_code_to_iso3(tmp_path):
    body = json.dumps({"results": [
        {"PartnerCode": 124, "PartnerDesc": "Canada", "PartnerCodeIsoAlpha3": "CAN"},
        {"PartnerCode": 490, "PartnerDesc": "Other Asia, nes", "PartnerCodeIsoAlpha3": "S19"},
    ]}).encode()
    t = country_table(tmp_path, opener=fake_opener([body]), sleep=lambda s: None)
    assert t[124] == {"name": "Canada", "iso3": "CAN"}
    assert (tmp_path / "ref_partner_areas.json").exists()
