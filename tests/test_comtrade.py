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


def test_fetch_all_stops_after_three_consecutive_failures(tmp_path):
    """리뷰 I1: 인터넷이 끊기면 280건을 다 기다리지 않는다."""
    calls = []

    def counting_fail(req, timeout=None):
        calls.append(1)
        raise OSError("down")
    missing = fetch_all(tmp_path, ["1704", "1806"], [], range(2023, 2025), range(2023, 2025),
                        opener=counting_fail, sleep=lambda s: None)
    assert len(missing) == 8                 # 받으려던 것 전부가 목록에 남는다
    assert len(calls) == 3 * 4               # 세 건 연속 실패(건마다 4번 시도)에서 멈춘다


def test_fetch_all_reports_progress(tmp_path):
    lines = []
    fetch_all(tmp_path, ["1704"], [], range(2024, 2025), range(2024, 2025),
              opener=fake_opener([b'{"data": []}', b'{"data": []}']), sleep=lambda s: None,
              progress=lines.append)
    assert lines and "1/2" in lines[0] and "kr_export_2024_1704" in lines[0]


def test_corrupt_cache_is_downloaded_again(tmp_path):
    """리뷰 I2: 0바이트·잘린 파일은 없는 것으로 보고 다시 받는다."""
    (tmp_path / "x.json").write_text("", encoding="utf-8")
    assert get("x", "q", tmp_path, opener=fake_opener([b'{"data": [2]}']), sleep=lambda s: None) == {"data": [2]}


def test_error_shapes_not_cached(tmp_path):
    """리뷰 I3: error 키가 없는 오류 응답도 정상 캐시로 저장하지 않는다."""
    bodies = [b'{"statusCode": 429, "message": "Rate limit"}'] * 4
    try:
        get("r", "q", tmp_path, opener=fake_opener(bodies), sleep=lambda s: None)
        assert False, "FetchError 가 나야 한다"
    except Exception as e:
        assert type(e).__name__ == "FetchError"
    assert not (tmp_path / "r.json").exists()


def test_download_records_fetched_time(tmp_path):
    """리뷰 I4: 받은 시각을 _fetched.json 에 남긴다."""
    get("t", "q", tmp_path, opener=fake_opener([b'{"data": []}']), sleep=lambda s: None)
    rec = json.loads((tmp_path / "_fetched.json").read_text(encoding="utf-8"))
    assert "t" in rec and rec["t"][:2] == "20"


def test_country_table_maps_code_to_iso3(tmp_path):
    body = json.dumps({"results": [
        {"PartnerCode": 124, "PartnerDesc": "Canada", "PartnerCodeIsoAlpha3": "CAN"},
        {"PartnerCode": 490, "PartnerDesc": "Other Asia, nes", "PartnerCodeIsoAlpha3": "S19"},
    ]}).encode()
    t = country_table(tmp_path, opener=fake_opener([body]), sleep=lambda s: None)
    assert t[124] == {"name": "Canada", "iso3": "CAN"}
    assert (tmp_path / "ref_partner_areas.json").exists()
