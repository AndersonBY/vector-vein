"""Bounded, in-memory previews of local image attachments."""
import base64
import os
import re
import stat
import warnings
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 32 * 1024 * 1024
THUMBNAIL_SIZE = (160, 160)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
IMAGE_MIMES = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif", "WEBP": "image/webp", "BMP": "image/bmp"}


class AttachmentPreviewError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _read_source(path):
    try:
        source_stat = path.stat()
        if not stat.S_ISREG(source_stat.st_mode):
            raise AttachmentPreviewError(422, "Attachment must be a regular file")
        if source_stat.st_size > MAX_SOURCE_BYTES:
            raise AttachmentPreviewError(413, "Attachment exceeds preview limits")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as source:
            opened_stat = os.fstat(source.fileno())
            if not stat.S_ISREG(opened_stat.st_mode):
                raise AttachmentPreviewError(422, "Attachment must be a regular file")
            if opened_stat.st_size > MAX_SOURCE_BYTES:
                raise AttachmentPreviewError(413, "Attachment exceeds preview limits")
            content = source.read(MAX_SOURCE_BYTES + 1)
        if len(content) > MAX_SOURCE_BYTES:
            raise AttachmentPreviewError(413, "Attachment exceeds preview limits")
        return content
    except FileNotFoundError:
        raise AttachmentPreviewError(404, "Attachment not found") from None
    except (OSError, ValueError):
        raise AttachmentPreviewError(422, "Attachment could not be read") from None


def _check_pixels(image):
    if image.width < 1 or image.height < 1 or image.width * image.height > MAX_IMAGE_PIXELS:
        raise AttachmentPreviewError(413, "Attachment exceeds preview limits")


def attachment_image_url(payload):
    """Return a PNG thumbnail or byte-preserving original data URL; never fetch URLs."""
    if not isinstance(payload, dict):
        raise AttachmentPreviewError(400, "Invalid attachment preview request")
    file_path = payload.get("path")
    thumbnail = payload.get("thumbnail", True)
    if not isinstance(file_path, str) or not file_path.strip() or "\x00" in file_path or not isinstance(thumbnail, bool):
        raise AttachmentPreviewError(400, "Invalid attachment preview request")
    # Drive-rooted Windows paths are local; URI schemes and network/device paths are not.
    has_scheme = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", file_path)
    if re.match(r"^[\\/]{2}", file_path) or (has_scheme and not re.match(r"^[A-Za-z]:[\\/]", file_path)):
        raise AttachmentPreviewError(400, "Only local attachment paths are supported")
    path = Path(file_path)
    content = _read_source(path)
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise AttachmentPreviewError(422, "Unsupported attachment image")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content), formats=tuple(IMAGE_MIMES)) as image:
                _check_pixels(image)
                image_format = image.format
                if image_format not in IMAGE_MIMES:
                    raise AttachmentPreviewError(422, "Unsupported attachment image")
                image.verify()
            # Verify does not decode every supported format; decode the bounded first frame too.
            with Image.open(BytesIO(content), formats=tuple(IMAGE_MIMES)) as image:
                _check_pixels(image)
                image.load()
                if thumbnail:
                    preview = ImageOps.exif_transpose(image)
                    preview.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                    preview = preview.convert("RGBA" if "A" in preview.getbands() or "transparency" in preview.info else "RGB")
                    preview.info.clear()
                    output = BytesIO()
                    preview.save(output, format="PNG")
                    content = output.getvalue()
                    image_format = "PNG"
    except AttachmentPreviewError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise AttachmentPreviewError(413, "Attachment exceeds preview limits") from None
    except Exception:
        raise AttachmentPreviewError(422, "Attachment is not a readable supported image") from None
    return f"data:{IMAGE_MIMES[image_format]};base64,{base64.b64encode(content).decode('ascii')}"
