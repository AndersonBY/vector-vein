# @Author: Bi Ying
# @Date:   2023-05-15 02:02:39
# @Last Modified by:   Bi Ying
# @Last Modified time: 2024-06-25 15:22:18
import os
import re
from pathlib import Path

from utilities.general import mprint_with_name
from utilities.config import Settings, cache
from utilities.network import new_httpx_client
from .utils import JResponse


mprint = mprint_with_name(name="Official Site API")

headers = {"user-agent": "vector-vein client"}


def request(method: str, path: str, payload=None):
    settings = Settings()
    client = new_httpx_client(is_async=False)
    url = f"https://{settings.website_domain}{path}"
    try_times = 0
    while try_times < 3:
        try:
            if method == "POST" and payload:
                response = client.request(method, url, headers=headers, timeout=15, json=payload)
            else:
                response = client.request(method, url, headers=headers, timeout=15, params=payload)
            return response.json()
        except Exception as e:
            mprint.error(e)
            try_times += 1
    return JResponse(status=500, msg="request failed")


class OfficialSiteAPI:
    name = "official_site"

    def __init__(self):
        self.version = os.environ.get("VECTORVEIN_VERSION", "0.3.7")

        version_file = Path(__file__).parent.parent / "version.txt"
        if version_file.exists():
            self.version = version_file.read_text().strip()

    def get_update_info(self, payload):
        cached = cache.get("update_info")
        if cached:
            return JResponse(data=cached)
        response = request("GET", "/api/v1/client-software/update-info", payload)
        if not isinstance(response, dict) or response.get("status") != 200:
            return JResponse(status=502, msg="Update information unavailable")
        response_data = response.get("data")
        if not isinstance(response_data, dict):
            return JResponse(status=502, msg="Invalid update information")
        official_version = response_data.get("version")
        versions = (official_version, self.version)
        if any(not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
               for version in versions):
            return JResponse(status=502, msg="Invalid update version")
        try:
            official, current = (tuple(map(int, version.split("."))) for version in versions)
        except ValueError:
            return JResponse(status=502, msg="Invalid update version")
        response_data = {**response_data, "updatable": official > current}
        cache.set("update_info", response_data, expire=600)
        return JResponse(data=response_data)

    def list_templates(self, payload):
        path = "/api/v1/client-software/template/list"
        return request("GET", path, payload)

    def get_template(self, payload):
        path = "/api/v1/client-software/template/get"
        return request("GET", path, payload)

    def list_tags(self, payload):
        path = "/api/v1/client-software/tag/list"
        return request("GET", path, payload)

    def get_document(self, payload):
        path = "/api/v1/client-software/document/get"
        return request("GET", path, payload)
