from pathlib import Path
from types import SimpleNamespace

import pytest

from utilities.workflow import Workflow
from utilities.file_processing import pdf_process
from worker.tasks import file_processing, image_generation, output, tools, web_crawlers


def workflow_data(task_name, **values):
    return {"nodes": [{"id": "node", "type": "Test", "category": "tools", "data": {
        "task_name": task_name, "template": {key: {"value": value} for key, value in values.items()}
    }}], "edges": []}


def artifacts(data):
    return data["nodes"][0]["data"].get("artifacts", [])


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(Workflow, "report_node_status", lambda *args: True)
    monkeypatch.setattr(Workflow, "report_workflow_status", lambda *args: True)
    for module in (output, tools, file_processing):
        monkeypatch.setattr(module, "Settings", lambda: SimpleNamespace(output_folder=str(tmp_path / "output")))


def test_document_registers_final_file_and_preserves_output(tmp_path):
    data = workflow_data("output.document", file_name="report", content="hello", export_type=".txt")
    result = output.document(data, "node")
    path = tmp_path / "output" / "report.txt"
    assert path.read_text(encoding="utf-8") == "hello"
    assert Workflow(result).get_node_field_value("node", "output") == str(path)
    assert [item["path"] for item in artifacts(result)] == [str(path)]
    assert artifacts(result)[0]["name"] == "report.txt"
    assert isinstance(artifacts(result)[0]["created_at"], int)


def test_python_registers_created_file_even_when_code_fails(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    data = workflow_data("tools.programming_function", language="python", list_input=False,
        code="def main():\n    from pathlib import Path\n    Path('created.txt').write_text('saved')\n    raise ValueError('later failure')")
    with pytest.raises(RuntimeError, match="indexes"):
        tools.programming_function(data, "node")
    path = tmp_path / "output" / "created.txt"
    assert path.read_text() == "saved"
    assert [item["path"] for item in artifacts(data)] == [str(path)]
    assert Workflow(data).get_node_field_value("node", "files") == [str(path)]


def test_conversion_retains_first_artifact_when_second_write_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(file_processing, "get_files_contents", lambda files: ["first", object()])
    data = workflow_data("file_processing.document_convert", files=["first.pdf", "second.pdf"], output_format="txt")
    with pytest.raises(TypeError):
        file_processing.document_convert(data, "node")
    assert len(artifacts(data)) == 1
    assert Path(artifacts(data)[0]["path"]).read_text() == "first"


def test_screenshot_base64_and_existing_audio_are_not_artifacts(monkeypatch, tmp_path):
    path = tmp_path / "existing.wav"
    path.write_bytes(b"audio")
    monkeypatch.setattr(tools, "get_screenshot", lambda **kwargs: str(path))
    image = tools.screenshot(workflow_data("tools.screenshot", monitor_number=1, output_type="base64"), "node")
    audio = output.audio(workflow_data("output.audio", audio_type="play_audio", file_link=str(path), output_type="only_link"), "node")
    assert artifacts(image) == artifacts(audio) == []
    image = tools.screenshot(workflow_data("tools.screenshot", monitor_number=1, output_type="file_path"), "node")
    assert artifacts(image)[0]["path"] == str(path)


def test_html_and_generated_audio_keep_url_outputs(monkeypatch, tmp_path):
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(output, "static_file_server", SimpleNamespace(get_file_url=lambda path: "https://local/" + Path(path).name))
    html = output.html(workflow_data("output.html", html_code="<p>hello</p>"), "node")
    html_path = Path(artifacts(html)[0]["path"])
    assert html_path.read_text() == "<p>hello</p>"
    assert Workflow(html).get_node_field_value("node", "output") == "https://local/" + html_path.name
    audio_path = tmp_path / "voice.wav"
    def create(**kwargs):
        audio_path.write_bytes(b"voice")
        return audio_path
    monkeypatch.setattr(output, "TTSClient", lambda **kwargs: SimpleNamespace(create=create))
    audio = output.audio(workflow_data("output.audio", audio_type="text_to_speech", content="hello", direct_play=False, output_type="only_link"), "node")
    assert artifacts(audio)[0]["path"] == str(audio_path)
    assert Workflow(audio).get_node_field_value("node", "output") == "https://local/voice.wav"


def test_generated_images_register_before_later_provider_failure(monkeypatch, tmp_path):
    image_folder = tmp_path / "images"
    image_folder.mkdir()
    responses = [SimpleNamespace(data=[SimpleNamespace(b64_json="aW1hZ2U=")]), RuntimeError("provider failed")]
    def generate(**kwargs):
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(image_generation, "get_openai_client_and_model_id", lambda **kwargs: (SimpleNamespace(images=SimpleNamespace(generate=generate)), "model"))
    monkeypatch.setattr(image_generation, "static_file_server", SimpleNamespace(static_folder_path=tmp_path, get_file_url=lambda path: "https://local/" + str(path)))
    data = workflow_data("image_generation.dall_e", prompt=["one", "two"], model="model", size="small", quality="standard", style="natural", output_type="only_link")
    with pytest.raises(RuntimeError, match="provider failed"):
        image_generation.dall_e(data, "node")
    assert len(artifacts(data)) == 1
    assert Path(artifacts(data)[0]["path"]).read_bytes() == b"image"


def test_pdf_page_callback_preserves_saved_page_before_later_failure(monkeypatch, tmp_path):
    class PDF:
        def __len__(self):
            return 2

        def load_page(self, index):
            if index:
                raise RuntimeError("second page failed")
            return SimpleNamespace(rect=SimpleNamespace(width=100, height=100), get_pixmap=lambda **kwargs: SimpleNamespace(save=lambda path: Path(path).write_bytes(b"page")))

    monkeypatch.setattr(pdf_process.pymupdf, "open", lambda path: PDF())
    saved = []
    with pytest.raises(RuntimeError, match="second page failed"):
        pdf_process.process_pdf("input.pdf", "render_images", tmp_path, on_image_saved=saved.append)
    assert saved == [tmp_path / "page_1.png"]
    assert saved[0].read_bytes() == b"page"


def test_bilibili_registers_only_completed_download_hook(monkeypatch, tmp_path):
    folder = tmp_path / "video"
    folder.mkdir()
    stale = folder / "stale.mp4"
    stale.write_bytes(b"old")
    completed = folder / "completed.mp4"
    monkeypatch.setattr(web_crawlers, "Settings", lambda: SimpleNamespace(output_folder=str(tmp_path)))
    monkeypatch.setattr(web_crawlers, "get_aid_cid", lambda *args, **kwargs: (1, 2))
    monkeypatch.setattr(web_crawlers, "get_acg_video_subtitle", lambda **kwargs: [])
    monkeypatch.setattr(web_crawlers, "new_httpx_client", lambda **kwargs: SimpleNamespace(get=lambda *args, **kwargs: SimpleNamespace(json=lambda: {"data": {"title": "video"}})))

    class Downloader:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def download(self, urls):
            completed.write_bytes(b"new")
            for hook in self.options["post_hooks"]:
                hook(str(completed))

    monkeypatch.setattr(web_crawlers.yt_dlp, "YoutubeDL", Downloader)
    result = web_crawlers.bilibili_crawler(workflow_data("web_crawlers.bilibili_crawler", url_or_bvid="https://www.bilibili.com/video/BV1234567890", download_video=True, output_type="str"), "node")
    assert [item["path"] for item in artifacts(result)] == [str(completed)]
