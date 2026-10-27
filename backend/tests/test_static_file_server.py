import os
import threading
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import urlopen

import pytest

from utilities.file_processing.static_file_server import StaticFileServer


@pytest.fixture
def file_server(tmp_path, monkeypatch):
    static_root = tmp_path / "static"
    static_root.mkdir()
    server = StaticFileServer(static_root)
    httpd = HTTPServer(("localhost", 0), server.request_handler_class)
    monkeypatch.setattr(StaticFileServer, "port", httpd.server_port)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_url_quotes_filesystem_characters_and_normalizes_windows_separators():
    url = StaticFileServer.get_file_url(r"C:\输出 folder\page #%23?.html")
    assert urlsplit(url).path == "/C:/%E8%BE%93%E5%87%BA%20folder/page%20%23%2523%3F.html"
    assert urlsplit(url).query == urlsplit(url).fragment == ""


def test_relative_html_and_assets_decode_once(file_server):
    folder = file_server.static_folder_path / "输出 folder # %23"
    page = folder / "pages" / "report # %25.html"
    page.parent.mkdir(parents=True)
    page.write_text('<img src="../image%20%23%20%2523.png">', encoding="utf-8")
    image = folder / "image # %23.png"
    image.write_bytes(b"image bytes")
    css = page.parent / "style # %25.css"
    css.write_bytes(b"body { color: red; }")
    url = file_server.get_file_url(page.relative_to(file_server.static_folder_path))

    with urlopen(url + "?cache=1") as response:
        assert response.read() == page.read_bytes()
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        base_url = response.url
    for relative, expected in (("../" + quote(image.name), image), (quote(css.name), css)):
        with urlopen(urljoin(base_url, relative)) as response:
            assert response.read() == expected.read_bytes()


@pytest.mark.skipif(os.name != "nt", reason="Existing absolute output URL contract uses Windows drive paths")
def test_absolute_output_html_and_legacy_windows_url(file_server, tmp_path):
    folder = tmp_path / "输出 outside static # %23"
    folder.mkdir()
    page = folder / "page # %25.html"
    page.write_bytes(b"<p>output</p>")
    image = folder / "image # %23.png"
    image.write_bytes(b"image")
    url = file_server.get_file_url(page)
    with urlopen(url) as response:
        assert response.read() == page.read_bytes()
        with urlopen(urljoin(response.url, quote(image.name))) as asset:
            assert asset.read() == image.read_bytes()

    legacy = tmp_path / "legacy folder" / "old.html"
    legacy.parent.mkdir()
    legacy.write_bytes(b"historical output")
    legacy_url = f"http://localhost:{StaticFileServer.port}/" + quote(str(legacy), safe="/:\\")
    with urlopen(legacy_url) as response:
        assert response.read() == legacy.read_bytes()


def test_encoded_question_mark_is_not_a_query(file_server):
    handler = object.__new__(file_server.request_handler_class)
    expected = file_server.static_folder_path / "file?.html"
    assert Path(handler.translate_path("/file%3F.html?cache=1")) == expected


def test_missing_file_returns_404(file_server):
    with pytest.raises(HTTPError) as error:
        urlopen(file_server.get_file_url("missing.html"))
    assert error.value.code == 404
