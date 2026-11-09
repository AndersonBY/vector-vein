from copy import deepcopy
from unittest.mock import Mock

import pytest

from api import remote_api


@pytest.fixture
def update_api(monkeypatch):
    cache = Mock()
    cache.get.return_value = None
    monkeypatch.setattr(remote_api, "cache", cache)
    request = Mock()
    monkeypatch.setattr(remote_api, "request", request)
    api = remote_api.OfficialSiteAPI()
    api.version = "1.2.3"
    return api, request, cache


@pytest.mark.parametrize("response", [
    None, [], {}, {"status": 500, "data": {"version": "2.0.0"}},
    {"status": 200}, {"status": 200, "data": None},
    {"status": 200, "data": []}, {"status": 200, "data": {}},
    *({"status": 200, "data": {"version": version}}
      for version in (None, 2, [], "", "v2.0.0", "2.0", "2.0.0.1", "-2.0.0", "2.x.0", "2.0.0\n")),
])
def test_invalid_update_response_fails_safely_without_caching(update_api, response):
    api, request, cache = update_api
    request.return_value = response
    result = api.get_update_info({})
    assert result["status"] == 502
    assert result["data"] == {}
    cache.set.assert_not_called()
    request.return_value = {"status": 200, "data": {"version": "2.0.0"}}
    assert api.get_update_info({})["data"]["updatable"] is True
    assert request.call_count == 2


@pytest.mark.parametrize("current", [None, "", "release", "1.2", "1.2.-3"])
def test_invalid_current_version_is_not_cached(update_api, current):
    api, request, cache = update_api
    api.version = current
    request.return_value = {"status": 200, "data": {"version": "2.0.0"}}
    assert api.get_update_info({})["status"] == 502
    cache.set.assert_not_called()


@pytest.mark.parametrize("version,updatable", [
    ("1.2.2", False), ("1.2.3", False), ("1.2.4", True),
    ("1.10.0", True), ("2.0.0", True),
])
def test_update_compares_numeric_versions_and_caches_success(update_api, version, updatable):
    api, request, cache = update_api
    response = {"status": 200, "data": {"version": version, "url": "https://example.invalid/download"}}
    original = deepcopy(response)
    request.return_value = response
    result = api.get_update_info({"platform": "windows"})
    assert result["status"] == 200
    assert result["data"] == {**original["data"], "updatable": updatable}
    assert response == original
    cache.set.assert_called_once_with("update_info", result["data"], expire=600)
    request.assert_called_once_with("GET", "/api/v1/client-software/update-info", {"platform": "windows"})
    cache.get.return_value = result["data"]
    assert api.get_update_info({}) == result
    assert request.call_count == 1
