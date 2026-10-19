import json
from types import SimpleNamespace

import pytest
import requests

from conftest import load_script

download = load_script("01_download_trials.py")


def fake_response(status_code, body=None):
    """A stand-in for a requests response."""
    return SimpleNamespace(status_code=status_code, json=lambda: body, text=json.dumps(body))


def test_condition_query_limits_expansion():
    assert download.build_condition_query("oral cancer") == 'EXPANSION[Term]"oral cancer"'


def test_term_to_filename():
    assert download.term_to_filename("Dental Caries") == "trials_dental_caries.json"


def test_get_json_retries_busy_server_then_succeeds(monkeypatch):
    replies = [fake_response(503), fake_response(200, {"studies": []})]
    monkeypatch.setattr(download.requests, "get", lambda url, params, timeout: replies.pop(0))
    assert download.get_json("http://x.test", {}, wait_seconds=0) == {"studies": []}


def test_get_json_stops_immediately_on_bad_request(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(1)
        return fake_response(400, {"error": "bad field"})

    monkeypatch.setattr(download.requests, "get", fake_get)
    with pytest.raises(RuntimeError, match="HTTP 400"):
        download.get_json("http://x.test", {}, wait_seconds=0)
    assert len(calls) == 1


def test_get_json_gives_up_after_network_errors(monkeypatch):
    def fake_get(url, params, timeout):
        raise requests.ConnectionError("no internet")

    monkeypatch.setattr(download.requests, "get", fake_get)
    with pytest.raises(RuntimeError, match="after 3 attempts.*no internet"):
        download.get_json("http://x.test", {}, wait_seconds=0)


def test_fetch_follows_page_tokens(monkeypatch):
    pages = [
        fake_response(200, {"studies": [{"id": 1}, {"id": 2}], "nextPageToken": "abc"}),
        fake_response(200, {"studies": [{"id": 3}]}),
    ]
    seen_tokens = []

    def fake_get(url, params, timeout):
        seen_tokens.append(params.get("pageToken"))
        return pages.pop(0)

    monkeypatch.setattr(download.requests, "get", fake_get)
    studies = download.fetch_studies_for_term("gingivitis", wait_seconds=0)
    assert [s["id"] for s in studies] == [1, 2, 3]
    assert seen_tokens == [None, "abc"]


def test_fetch_handles_empty_results(monkeypatch):
    monkeypatch.setattr(download.requests, "get", lambda url, params, timeout: fake_response(200, {"studies": []}))
    assert download.fetch_studies_for_term("nothing", wait_seconds=0) == []


def test_save_studies_writes_payload(tmp_path):
    path = download.save_studies("tooth loss", [{"a": 1}], tmp_path)
    payload = json.loads(path.read_text())
    assert path.name == "trials_tooth_loss.json"
    assert payload["study_count"] == 1
    assert payload["query"] == 'EXPANSION[Term]"tooth loss"'


def test_main_exits_when_api_returns_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(download, "RAW_DIR", tmp_path)
    monkeypatch.setattr(download, "fetch_studies_for_term", lambda term: [])
    with pytest.raises(SystemExit):
        download.main()
    assert "returned no studies for any term" in capsys.readouterr().out


def test_default_expansion_check_is_saved(tmp_path, monkeypatch):
    seen = {}

    def fake_get(url, params, timeout):
        seen.update(params)
        return fake_response(200, {"totalCount": 4552, "studies": []})

    monkeypatch.setattr(download.requests, "get", fake_get)
    assert download.count_with_default_expansion("oral cancer", tmp_path, wait_seconds=0) == 4552
    assert seen["query.cond"] == "oral cancer"
    saved = json.loads((tmp_path / "check_default_expansion_oral_cancer.json").read_text())
    assert saved["total_count_default_expansion"] == 4552
