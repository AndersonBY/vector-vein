import base64
from types import SimpleNamespace
from io import BytesIO

import pytest
from PIL import Image, PngImagePlugin

from utilities import attachment_preview as preview


def decode_url(url):
    header, encoded = url.split(",", 1)
    return header, base64.b64decode(encoded, validate=True)


@pytest.fixture
def image_file(tmp_path):
    path = tmp_path / "attachment.PNG"
    Image.new("RGB", (320, 80), "red").save(path)
    return path


@pytest.mark.parametrize("image_format,extension,mime", [
    ("PNG", ".PnG", "image/png"), ("JPEG", ".JpEg", "image/jpeg"),
    ("GIF", ".GiF", "image/gif"), ("WEBP", ".WeBp", "image/webp"),
    ("BMP", ".BmP", "image/bmp"),
])
def test_supported_formats_thumbnail_and_full_preserve_source(tmp_path, image_format, extension, mime):
    path = tmp_path / ("photo" + extension)
    Image.new("RGB", (320, 80), "red").save(path, format=image_format)
    original = path.read_bytes()
    header, thumbnail = decode_url(preview.attachment_image_url({"path": str(path)}))
    assert header == "data:image/png;base64"
    with Image.open(BytesIO(thumbnail)) as image:
        assert image.size == (160, 40)
    header, full = decode_url(preview.attachment_image_url({"path": str(path), "thumbnail": False}))
    assert header == f"data:{mime};base64" and full == original
    assert path.read_bytes() == original


def test_real_format_determines_full_mime_and_gif_frames_are_retained(tmp_path):
    disguised = tmp_path / "actually-jpeg.PNG"
    Image.new("RGB", (10, 20)).save(disguised, format="JPEG")
    assert preview.attachment_image_url({"path": str(disguised), "thumbnail": False}).startswith("data:image/jpeg;base64,")
    animated = tmp_path / "animated.gif"
    Image.new("RGB", (20, 10), "red").save(animated, save_all=True, append_images=[Image.new("RGB", (20, 10), "blue")], duration=50, loop=0)
    header, full = decode_url(preview.attachment_image_url({"path": str(animated), "thumbnail": False}))
    assert header == "data:image/gif;base64" and full == animated.read_bytes()
    with Image.open(BytesIO(full)) as image:
        assert image.n_frames == 2


def test_exif_orientation_and_thumbnail_metadata_removal(tmp_path):
    oriented = tmp_path / "portrait.jpg"
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "private author"
    Image.new("RGB", (80, 320), "red").save(oriented, exif=exif)
    _, content = decode_url(preview.attachment_image_url({"path": str(oriented), "thumbnail": True}))
    with Image.open(BytesIO(content)) as image:
        assert image.size == (160, 40)
        assert not image.getexif() and not image.info
    assert decode_url(preview.attachment_image_url({"path": str(oriented), "thumbnail": False}))[1] == oriented.read_bytes()
    metadata = tmp_path / "metadata.png"
    text = PngImagePlugin.PngInfo()
    text.add_text("private text", "must not survive thumbnail")
    Image.new("RGB", (10, 20)).save(metadata, pnginfo=text)
    _, content = decode_url(preview.attachment_image_url({"path": str(metadata)}))
    with Image.open(BytesIO(content)) as image:
        assert image.size == (10, 20) and not image.info


@pytest.mark.parametrize("payload", [None, [], "image.png", {}, {"path": None}, {"path": 12}, {"path": ""},
                                     {"path": "  "}, {"path": "bad\x00.png"}, {"path": "image.png", "thumbnail": 1},
                                     {"path": "image.png", "thumbnail": "false"}, {"path": "image.png", "thumbnail": None}])
def test_invalid_payloads_are_rejected_before_reading(payload, monkeypatch):
    monkeypatch.setattr(preview, "_read_source", lambda *_: pytest.fail("invalid payload touched filesystem"))
    with pytest.raises(preview.AttachmentPreviewError) as error:
        preview.attachment_image_url(payload)
    assert error.value.status == 400


@pytest.mark.parametrize("path", ["https://example.invalid/private.png", "http://localhost/a.jpg", "file:///C:/a.png",
                                  "data:image/png;base64,secret", "ftp://server/a.png", "C:relative.png",
                                  "//server/share/a.png", "\\\\server\\share\\a.png", "\\\\?\\C:\\private.png",
                                  "/\\server/share/a.png", "\\/server/share/a.png"])
def test_nonlocal_paths_never_touch_filesystem(path, monkeypatch):
    monkeypatch.setattr(preview, "_read_source", lambda *_: pytest.fail("nonlocal path touched filesystem"))
    with pytest.raises(preview.AttachmentPreviewError) as error:
        preview.attachment_image_url({"path": path})
    assert error.value.status == 400 and path not in str(error.value)


def test_local_paths_and_relative_paths_are_accepted(image_file, monkeypatch):
    monkeypatch.chdir(image_file.parent)
    assert preview.attachment_image_url({"path": image_file.name}).startswith("data:image/png;base64,")
    assert preview.attachment_image_url({"path": image_file.as_posix()}).startswith("data:image/png;base64,")


@pytest.mark.parametrize("thumbnail", [True, False])
def test_missing_directory_disguised_and_corrupt_images_are_safe(tmp_path, thumbnail, capsys):
    candidates = [(tmp_path / "missing.png", 404), (tmp_path, 422)]
    for name, content in (("fake.jpg", b"private text"), ("svg.png", b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
                          ("bad.png", b"\x89PNG\r\n\x1a\ntruncated"), ("vector.svg", b"<svg/>")):
        path = tmp_path / name
        path.write_bytes(content)
        candidates.append((path, 422))
    png_txt = tmp_path / "real-image.txt"
    Image.new("RGB", (10, 10)).save(png_txt, format="PNG")
    candidates.append((png_txt, 422))
    tiff = tmp_path / "tiff.png"
    Image.new("RGB", (10, 10)).save(tiff, format="TIFF")
    candidates.append((tiff, 422))
    for path, expected in candidates:
        with pytest.raises(preview.AttachmentPreviewError) as error:
            preview.attachment_image_url({"path": str(path), "thumbnail": thumbnail})
        assert error.value.status == expected and str(path) not in str(error.value)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("thumbnail", [True, False])
def test_source_size_and_pixel_limits_are_enforced_before_decode(tmp_path, image_file, thumbnail, monkeypatch):
    oversized = tmp_path / "large.png"
    with oversized.open("wb") as source:
        source.truncate(preview.MAX_SOURCE_BYTES + 1)
    with pytest.raises(preview.AttachmentPreviewError) as error:
        preview.attachment_image_url({"path": str(oversized), "thumbnail": thumbnail})
    assert error.value.status == 413
    monkeypatch.setattr(preview, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(preview.AttachmentPreviewError) as error:
        preview.attachment_image_url({"path": str(image_file), "thumbnail": thumbnail})
    assert error.value.status == 413


def test_read_and_parser_failures_hide_details(image_file, monkeypatch, capsys):
    def denied(*args):
        raise PermissionError(f"secret path {image_file}")
    with monkeypatch.context() as context:
        context.setattr(preview.os, "open", denied)
        with pytest.raises(preview.AttachmentPreviewError) as error:
            preview.attachment_image_url({"path": str(image_file)})
        assert error.value.status == 422 and "secret" not in str(error.value)
    def broken(*args, **kwargs):
        raise RuntimeError(f"parser secret {image_file}")
    monkeypatch.setattr(preview.Image, "open", broken)
    with pytest.raises(preview.AttachmentPreviewError) as error:
        preview.attachment_image_url({"path": str(image_file)})
    assert error.value.status == 422 and "secret" not in str(error.value)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("pillow_limit", [20000, 20])
def test_pillow_decompression_warning_and_error_are_safe_limits(image_file, monkeypatch, pillow_limit, capsys):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", pillow_limit)
    with pytest.raises(preview.AttachmentPreviewError) as error:
        preview.attachment_image_url({"path": str(image_file)})
    assert error.value.status == 413 and str(image_file) not in str(error.value)
    assert capsys.readouterr() == ("", "")


def test_truncated_jpeg_cannot_pass_header_only_verification(tmp_path):
    path = tmp_path / "truncated.jpg"
    Image.new("RGB", (60, 40), "blue").save(path)
    path.write_bytes(path.read_bytes()[:-30])
    for thumbnail in (True, False):
        with pytest.raises(preview.AttachmentPreviewError) as error:
            preview.attachment_image_url({"path": str(path), "thumbnail": thumbnail})
        assert error.value.status == 422


def test_read_is_bounded_even_when_file_size_changes(image_file, monkeypatch):
    monkeypatch.setattr(preview, "MAX_SOURCE_BYTES", 8)
    fake_stat = SimpleNamespace(st_mode=0o100644, st_size=0)
    monkeypatch.setattr(preview.Path, "stat", lambda *args, **kwargs: fake_stat)
    monkeypatch.setattr(preview.os, "fstat", lambda *args: fake_stat)
    with pytest.raises(preview.AttachmentPreviewError) as error:
        preview.attachment_image_url({"path": str(image_file)})
    assert error.value.status == 413


def test_thumbnail_preserves_transparency(tmp_path):
    path = tmp_path / "transparent.png"
    Image.new("RGBA", (50, 20), (20, 40, 60, 0)).save(path)
    _, content = decode_url(preview.attachment_image_url({"path": str(path)}))
    with Image.open(BytesIO(content)) as image:
        assert image.mode == "RGBA" and image.getpixel((0, 0))[3] == 0


def test_setting_api_response_contract(image_file):
    from api.user_api import SettingAPI
    response = SettingAPI().attachment_image({"path": str(image_file)})
    assert response["status"] == 200 and response["data"]["url"].startswith("data:image/png;base64,")
    response = SettingAPI().attachment_image({"path": str(image_file.parent)})
    assert response["status"] == 422 and response["data"] == {}
    assert str(image_file.parent) not in response["msg"]
