# @Author: Bi Ying
# @Date:   2024-06-09 00:21:23
import base64
from io import BytesIO
from pathlib import Path
from typing import Literal
from datetime import datetime
from functools import cached_property

import mss
import httpx
import mss.tools
from PIL.ImageFile import ImageFile
from PIL import Image, ImageDraw, ImageFont

from utilities.config import config


class ImageProcessor:
    def __init__(
        self,
        image_source: Image.Image | str | Path,
        max_size: int | None = 5 * 1024 * 1024,
        max_width: int | None = None,
        max_height: int | None = None,
    ):
        self.image_source = image_source
        if isinstance(image_source, (Image.Image, Path)):
            self.is_local = True
        else:
            self.is_local = not image_source.startswith("http")
        self.max_size = max_size
        self.max_width = max_width
        self.max_height = max_height
        self._image = self._load_image()
        self._image_format = self._image.format or "JPEG"

    def _load_image(self):
        if not self.is_local:
            image_url = self.image_source
            print(f"Downloading image from {image_url}")
            response = httpx.get(image_url, timeout=30)
            return Image.open(BytesIO(response.content))
        else:
            return Image.open(self.image_source)

    def _resize_image(
        self,
        img: ImageFile,
        max_size: int | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
    ):
        img_bytes = BytesIO()
        image_format = img.format or "JPEG"
        img.save(img_bytes, format=image_format, optimize=True)

        if max_width is not None and img.width > max_width:
            new_size = (max_width, int(max_width * img.height / img.width))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        if max_height is not None and img.height > max_height:
            new_size = (int(max_height * img.width / img.height), max_height)
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        img_bytes = BytesIO()
        img.save(img_bytes, format=image_format, optimize=True)

        if img_bytes.getbuffer().nbytes <= max_size:
            return img_bytes

        original_size = img.size
        scale_factor = 0.9

        while True:
            new_size = (int(original_size[0] * scale_factor), int(original_size[1] * scale_factor))
            img_resized = img.resize(new_size, Image.Resampling.LANCZOS)

            img_bytes_resized = BytesIO()
            img_resized.save(img_bytes_resized, format=image_format, optimize=True)

            if img_bytes_resized.getbuffer().nbytes <= max_size:
                return img_bytes_resized

            scale_factor -= 0.1
            if scale_factor < 0.1:
                return img_bytes_resized

    def crop(
        self,
        method: Literal["proportional", "fixed"] = "proportional",
        width_ratio: float = 1.0,
        height_ratio: float = 1.0,
        position: Literal[
            "top",
            "bottom",
            "left",
            "right",
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
            "center",
            "absolute",
        ] = "center",
        x: int = 1,
        y: int = 1,
        width: int = 300,
        height: int = 300,
    ):
        img = self._image
        self._image_format = img.format or "JPEG"

        if method == "proportional":
            # 计算裁剪区域的宽度和高度
            # 宽高比例是 width_ratio:height_ratio，例如可能是 16:9
            # 要根据原图的宽高来计算，比如 原图宽:原图高 > width_ratio:height_ratio，那么裁剪区域的高度就是原图的高度
            # 如果 原图宽:原图高 < width_ratio:height_ratio，那么裁剪区域的宽度就是原图的宽度
            if img.width / img.height > width_ratio / height_ratio:
                width = img.height * width_ratio / height_ratio
                height = img.height
            else:
                width = img.width
                height = img.width * height_ratio / width_ratio
        elif method == "fixed":
            if width == 0:
                width = img.width
            if height == 0:
                height = img.height

        if position == "absolute":
            self._image = img.crop((x, y, x + width, y + height))
        else:
            img_width, img_height = img.size
            left, top = 0, 0

            if position in ["top", "top_left", "top_right"]:
                top = 0
            elif position in ["bottom", "bottom_left", "bottom_right"]:
                top = img_height - height

            if position in ["left", "top_left", "bottom_left"]:
                left = 0
            elif position in ["right", "top_right", "bottom_right"]:
                left = img_width - width

            if position == "center":
                left = (img_width - width) // 2
                top = (img_height - height) // 2

            self._image = img.crop((left, top, left + width, top + height))

        self._image.format = self._image_format
        return self

    def scale(self, method: str = "proportional_scale", ratio: float = 1.0, width: int = 0, height: int = 0):
        img = self._image
        self._image_format = img.format or "JPEG"
        if method == "proportional_scale":
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            self._image = img.resize((new_width, new_height), Image.LANCZOS)
        elif method == "fixed_width_height":
            if width == 0:
                # If width is 0, then scale the image to the height
                width = int(img.width * height / img.height)
            elif height == 0:
                # If height is 0, then scale the image to the width
                height = int(img.height * width / img.width)
            self._image = img.resize((width, height), Image.LANCZOS)
        else:
            raise ValueError("Invalid scale_method")

        self._image.format = self._image_format
        return self

    def rotate(self, angle: int):
        self._image = self._image.rotate(angle, expand=True)
        self._image.format = self._image_format
        return self

    def compress(self, quality: int):
        """
        Compress the image based on the given quality level.

        This method compresses the image using the specified quality level. It supports various image formats,
        including JPEG, PNG, and attempts to compress other formats if possible.

        Parameters:
        ----------
        quality : int
            An integer between 1 and 100 representing the desired quality level.
            - 100: No compression (original quality)
            - 1: Maximum compression (lowest quality)
            For values between 1 and 99, the compression level is adjusted accordingly.

        Returns:
        -------
        self
            Returns the instance of the class for method chaining.

        Raises:
        ------
        ValueError
            If the quality parameter is not between 1 and 100.

        Notes:
        -----
        - For JPEG images, the quality is mapped to the PIL library's 1-95 scale.
        - For PNG images, the quality is mapped to a compression level (0-9).
        - For other formats, it attempts to use the quality parameter if supported.
          If not supported, it saves the image without compression.
        - Some image formats (e.g., GIF, BMP) may not support quality-based compression.
          In such cases, the method will attempt to save the image as-is.

        Examples:
        --------
        >>> img.compress(75)  # Compress with 75% quality
        >>> img.compress(100)  # No compression
        >>> img.compress(1)   # Maximum compression
        """

        if not 1 <= quality <= 100:
            raise ValueError("Quality should be between 1 and 100")

        if quality == 100:
            return self  # 不进行压缩处理

        img_bytes = BytesIO()

        # 对于JPEG格式，直接使用quality参数
        if self._image.format == "JPEG":
            compressed_quality = int(quality * 0.95)  # 将1-100的范围映射到1-95
            self._image.save(img_bytes, format="JPEG", quality=compressed_quality, optimize=True)

        # 对于PNG格式，使用压缩级别
        elif self._image.format == "PNG":
            compress_level = int(9 - (quality / 100 * 9))  # 将1-100的范围映射到9-0
            self._image.save(img_bytes, format="PNG", optimize=True, compress_level=compress_level)

        # 对于其他格式，尝试使用quality参数，如果不支持则只进行普通保存
        else:
            try:
                self._image.save(img_bytes, format=self._image.format, quality=quality, optimize=True)
            except ValueError:
                self._image.save(img_bytes, format=self._image.format)

        img_bytes.seek(0)
        self._image = Image.open(img_bytes)
        return self

    def add_image_watermark(
        self,
        watermark_image: Image.Image | BytesIO | ImageFile,
        width_ratio: float,
        height_ratio: float,
        position: Literal[
            "top",
            "bottom",
            "left",
            "right",
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
            "center",
        ] = "bottom_right",
        opacity: float = 1,
        vertical_gap: int = 10,
        horizontal_gap: int = 10,
    ):
        # Convert watermark_image to PIL.Image if it's not already
        if isinstance(watermark_image, BytesIO):
            watermark_image = Image.open(watermark_image)

        # Resize watermark image based on the given width and height ratios
        original_width, original_height = self._image.size
        if width_ratio == 0:
            watermark_height = int(original_height * height_ratio)
            watermark_width = int(watermark_image.width * watermark_height / watermark_image.height)
        elif height_ratio == 0:
            watermark_width = int(original_width * width_ratio)
            watermark_height = int(watermark_image.height * watermark_width / watermark_image.width)
        else:
            watermark_width = int(original_width * width_ratio)
            watermark_height = int(original_height * height_ratio)

        watermark_image = watermark_image.resize((watermark_width, watermark_height), Image.Resampling.LANCZOS)

        # Apply opacity to the watermark image
        watermark_image = watermark_image.convert("RGBA")
        watermark_image_with_opacity = Image.new("RGBA", watermark_image.size)
        watermark_image_with_opacity = Image.blend(watermark_image_with_opacity, watermark_image, opacity)

        # Calculate the position to place the watermark
        position_map = {
            "top_left": (horizontal_gap, vertical_gap),
            "top_right": (original_width - watermark_width - horizontal_gap, vertical_gap),
            "bottom_left": (horizontal_gap, original_height - watermark_height - vertical_gap),
            "bottom_right": (
                original_width - watermark_width - horizontal_gap,
                original_height - watermark_height - vertical_gap,
            ),
            "top": ((original_width - watermark_width) // 2, vertical_gap),
            "bottom": ((original_width - watermark_width) // 2, original_height - watermark_height - vertical_gap),
            "left": (horizontal_gap, (original_height - watermark_height) // 2),
            "right": (original_width - watermark_width - horizontal_gap, (original_height - watermark_height) // 2),
            "center": ((original_width - watermark_width) // 2, (original_height - watermark_height) // 2),
        }

        # Paste the watermark image onto the original image
        self._image.paste(watermark_image_with_opacity, position_map[position], watermark_image_with_opacity)
        self._image.format = self._image_format

    def add_text_watermark(
        self,
        watermark_text: str,
        watermark_text_font: str,
        watermark_text_font_size: int,
        watermark_text_font_color: str,
        opacity: float,
        position: Literal[
            "top",
            "bottom",
            "left",
            "right",
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
            "center",
        ] = "bottom_right",
        vertical_gap: int = 10,
        horizontal_gap: int = 10,
    ):
        # Create a blank image with the same size as the original image
        watermark_image = Image.new("RGBA", self._image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark_image)
        font = ImageFont.truetype(watermark_text_font, watermark_text_font_size)

        # Calculate the size of the text
        text_bbox = font.getbbox(watermark_text)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Calculate the position to place the text watermark
        original_width, original_height = self._image.size
        position_map = {
            "top_left": (horizontal_gap, vertical_gap),
            "top_right": (original_width - text_width - horizontal_gap, vertical_gap),
            "bottom_left": (horizontal_gap, original_height - text_height - vertical_gap),
            "bottom_right": (
                original_width - text_width - horizontal_gap,
                original_height - text_height - vertical_gap,
            ),
            "top": ((original_width - text_width) // 2, vertical_gap),
            "bottom": ((original_width - text_width) // 2, original_height - text_height - vertical_gap),
            "left": (horizontal_gap, (original_height - text_height) // 2),
            "right": (original_width - text_width - horizontal_gap, (original_height - text_height) // 2),
            "center": ((original_width - text_width) // 2, (original_height - text_height) // 2),
        }

        # Draw the text on the blank image
        draw.text(
            position_map[position],
            watermark_text,
            fill=(*ImageProcessor.hex_to_rgb(watermark_text_font_color), int(255 * opacity)),
            font=font,
        )

        # Apply the watermark to the original image
        self._image = Image.alpha_composite(self._image.convert("RGBA"), watermark_image)
        self._image.format = self._image_format

    @staticmethod
    def hex_to_rgb(hex_color: str):
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    @property
    def image(self):
        return self._image

    @cached_property
    def bytes(self):
        if self.max_size is None and self.max_width is None and self.max_height is None:
            if isinstance(self._image, Image.Image):
                img_bytes = BytesIO()

                # 检查图像是否有透明通道
                has_transparency = self._image.mode in ("RGBA", "LA") or (
                    self._image.mode == "P" and "transparency" in self._image.info
                )

                if has_transparency:
                    # 如果有透明通道，使用PNG格式
                    save_format = "PNG"
                    self._image_format = "PNG"
                else:
                    # 如果没有透明通道，使用原始格式或默认为JPEG
                    save_format = self._image.format or self._image_format or "JPEG"

                    # 如果图像模式不是RGB（例如RGBA），转换为RGB
                    if self._image.mode != "RGB":
                        self._image = self._image.convert("RGB")

                self._image.save(img_bytes, format=save_format, optimize=True)
                return img_bytes.getvalue()
            elif isinstance(self._image, BytesIO):
                return self._image.getvalue()
            elif isinstance(self._image, ImageFile):
                return self._image.fp.read()
            return self._image.getvalue()

        img_bytes_resized = self._resize_image(self._image, self.max_size, self.max_width, self.max_height)
        return img_bytes_resized.getvalue()

    @cached_property
    def base64_image(self):
        if self.max_size is None and self.max_width is None and self.max_height is None:
            return base64.b64encode(self.bytes).decode()

        img_bytes_resized = self._resize_image(self._image, self.max_size, self.max_width, self.max_height)
        return base64.b64encode(img_bytes_resized.getvalue()).decode()

    @cached_property
    def mime_type(self):
        return Image.MIME[self._image.format or self._image_format]

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
