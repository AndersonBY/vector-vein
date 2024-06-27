# @Author: Bi Ying
# @Date:   2024-06-09 00:21:23
import base64
from io import BytesIO
from pathlib import Path
from datetime import datetime
from functools import cached_property

import mss
import httpx
import mss.tools
from PIL import Image

from utilities.config import config


class ImageProcessor:
    def __init__(self, image_source: Image.Image | str | Path, max_size: int | None = 5 * 1024 * 1024):
        self.image_source = image_source
        if isinstance(image_source, (Image.Image, Path)):
            self.is_local = True
        else:
            self.is_local = not image_source.startswith("http")
        self.max_size = max_size
        self._image = self._load_image()

    def _load_image(self):
        if not self.is_local:
            image_url = self.image_source
            response = httpx.get(image_url)
            return Image.open(BytesIO(response.content))
        else:
            return Image.open(self.image_source)

    def _resize_image(self, img, max_size):
        img_bytes = BytesIO()
        img.save(img_bytes, format=img.format, optimize=True)

        if img_bytes.getbuffer().nbytes <= max_size:
            return img_bytes

        original_size = img.size
        scale_factor = 0.9

        while True:
            new_size = (int(original_size[0] * scale_factor), int(original_size[1] * scale_factor))
            img_resized = img.resize(new_size, Image.Resampling.LANCZOS)

            img_bytes_resized = BytesIO()
            img_resized.save(img_bytes_resized, format=img.format, optimize=True)

            if img_bytes_resized.getbuffer().nbytes <= max_size:
                return img_bytes_resized

            scale_factor -= 0.1
            if scale_factor < 0.1:
                return img_bytes_resized

    @cached_property
    def base64_image(self):
        if self.max_size is None:
            return base64.b64encode(self._image.getvalue()).decode()

        img_bytes_resized = self._resize_image(self._image, self.max_size)
        return base64.b64encode(img_bytes_resized.getvalue()).decode()

    @cached_property
    def mime_type(self):
        return Image.MIME[self._image.format]

    @cached_property
    def data_url(self):
        return f"data:{self.mime_type};base64,{self.base64_image}"


def get_screenshot(
    output_type: str = "base64", monitor_number: int = 0, compression_level: int = 1, max_length: int = 1920
):
    """
    Get a screenshot of the specified monitor.

    Parameters:
    output_type (str): The type of the output. "base64" or "file_path".
    monitor_number (int): The number of the monitor to take a screenshot of.
    compression_level (int): The compression level of the screenshot. Default to 1 to make the screenshot function fast.
    max_length (int): The maximum length of the screenshot.

    Returns:
    str: The screenshot in the specified format.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_number]
        sct_img = sct.grab(monitor)

        if output_type == "base64":
            image = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            image.format = "PNG"
            return ImageProcessor(image).base64_image
        elif output_type == "file_path":
            screenshots_path = Path(config.data_path) / "images" / "screenshots"
            screenshots_path.mkdir(parents=True, exist_ok=True)
            datetime_string = datetime.now().strftime("%Y%m%d%H%M%S")
            width, height = sct_img.size
            if width > height:
                if width > max_length:
                    height = int(height * max_length / width)
                    width = max_length
            else:
                if height > max_length:
                    width = int(width * max_length / height)
                    height = max_length

            output = (
                screenshots_path
                / "{datetime_string}_sct-mon{monitor_number}_{top}x{left}_{width}x{height}.png".format(
                    datetime_string=datetime_string,
                    monitor_number=monitor_number,
                    top=monitor["top"],
                    left=monitor["left"],
                    width=width,
                    height=height,
                )
            )

            image = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            image.format = "PNG"
            image = image.resize((width, height), Image.LANCZOS)
            image.save(output, format="PNG", compress_level=compression_level)

            return str(output.absolute())
