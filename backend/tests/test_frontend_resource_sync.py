import pytest

import build


@pytest.fixture
def frontend(tmp_path, monkeypatch):
    source, target = tmp_path / "frontend", tmp_path / "web"
    (source / "dist/assets").mkdir(parents=True)
    (target / "assets").mkdir(parents=True)
    (source / "dist/index.html").write_text('new entry', encoding="utf-8")
    (source / "dist/assets/new-chunk.js").write_text('new chunk', encoding="utf-8")
    (target / "index.html").write_text('old entry', encoding="utf-8")
    (target / "assets/old-chunk.js").write_text('old chunk', encoding="utf-8")
    monkeypatch.setattr(build, "FRONTEND_DIR", source)
    monkeypatch.setattr(build, "WEB_DIR", target)
    return source, target


def test_sync_preserves_chunks_needed_by_open_windows_and_publishes_entry_last(frontend, monkeypatch):
    _, target = frontend
    copy = build.shutil.copy2

    def checked_copy(source, destination, *args, **kwargs):
        assert (target / "index.html").read_text() == 'old entry'
        return copy(source, destination, *args, **kwargs)

    monkeypatch.setattr(build.shutil, "copy2", checked_copy)
    build.sync_frontend()
    assert (target / "assets/old-chunk.js").read_text() == 'old chunk'
    assert (target / "assets/new-chunk.js").read_text() == 'new chunk'
    assert (target / "index.html").read_text() == 'new entry'
    assert not (target / "index.html.next").exists()


def test_failed_asset_copy_keeps_current_entry_and_chunks(frontend, monkeypatch):
    _, target = frontend

    def fail_copy(*_args, **_kwargs):
        raise OSError("Disposable copy failure")

    monkeypatch.setattr(build.shutil, "copytree", fail_copy)
    with pytest.raises(OSError):
        build.sync_frontend()
    assert (target / "index.html").read_text() == 'old entry'
    assert (target / "assets/old-chunk.js").read_text() == 'old chunk'
