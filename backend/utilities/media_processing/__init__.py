# @Author: Bi Ying
# @Date:   2024-06-09 12:04:08
from importlib import import_module

from .image import get_screenshot, ImageProcessor


_AUDIO_EXPORTS = {"TTSClient", "SpeechRecognitionClient", "Microphone"}

__all__ = [
    "TTSClient",
    "Microphone",
    "get_screenshot",
    "ImageProcessor",
    "SpeechRecognitionClient",
]


def __getattr__(name: str):
    if name in _AUDIO_EXPORTS:
        audio_module = import_module(".audio", __name__)
        value = getattr(audio_module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
