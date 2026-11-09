# @Author: Bi Ying
# @Date:   2024-06-09 15:53:58
import re
import json
import platform
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Literal, cast
from abc import ABC, abstractmethod

import pyaudio
from openai import OpenAI
from openai._types import FileTypes

from utilities.config import Settings, config
from utilities.general import mprint_with_name
from utilities.network import new_httpx_client
from utilities.network.llm_client import new_llm_http_client


OpenAIVoiceType = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

mprint = mprint_with_name(name="Audio Processing")

class TTSClient:
    def __init__(self, provider: str = "openai", model: str = ""):
        self.audio_sample_rate = 24_000
        self.streaming = False
        self._stop_flag = False

        settings = Settings()
        self.provider = provider

        if self.provider == "openai":
            from utilities.ai_utils import get_openai_client_and_model_id

            if len(model) == 0:
                model = "tts-1"
            self.client, self.model_id = get_openai_client_and_model_id(is_async=False, model_id=model)
        elif self.provider == "minimax":
            if len(model) == 0:
                model = "speech-01-turbo"
            self.api_key = settings.minimax_api_key
            self.model_id = model
        elif self.provider == "piper":
            self.api_base = settings.get("tts.piper.api_base")
            self.model_id = model
        elif self.provider == "reecho":
            self.api_key = settings.get("tts.reecho.api_key")
            self.model_id = model
        elif self.provider == "azure":
            self.api_key = settings.get("tts.azure.api_key")
            self.service_region = settings.get("tts.azure.service_region")
            self.model_id = model
            self.audio_sample_rate = 16_000
        else:
            raise ValueError(f"Unsupported TTS provider: {self.provider}")

    def create(self, text: str, voice: str = "", output_folder: str | None = None):
        datetime_string = datetime.now().strftime("%Y%m%d%H%M%S")
        if output_folder is None:
            audio_path = Path(config.data_path) / "audio"
            audio_path.mkdir(parents=True, exist_ok=True)
            output_file_path = audio_path / f"{datetime_string}.mp3"
        else:
            output_file_path = Path(output_folder) / f"{datetime_string}.mp3"

        if self.provider == "openai":
            if voice not in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
                voice = "alloy"
            typed_voice = cast(OpenAIVoiceType, voice)
            response = self.client.audio.speech.create(model=self.model_id, voice=typed_voice, input=text)
            response.write_to_file(output_file_path)
        elif self.provider == "minimax":
            url = "https://api.minimax.chat/v1/t2a_pro"
            headers = {"authorization": f"Bearer {self.api_key}"}
            data = {
                "voice_id": voice,
                "text": text,
                "model": "speech-02",
                "speed": 1.0,
                "vol": 1.0,
                "pitch": 0,
                "output_format": "mp3",
                "audio_sample_rate": self.audio_sample_rate,
                "bitrate": 128000,
            }
            http_client = new_httpx_client(is_async=False)
            response = http_client.post(url, headers=headers, json=data)
            if response.status_code != 200:
                mprint.error("Minimax TTS failed", response.status_code, response.text)
                return None
            result = response.json()
            audio_url = result["audio_file"]
            response = http_client.get(audio_url)
            with open(output_file_path, "wb") as f:
                f.write(response.content)
        elif self.provider == "reecho":
            url = "https://v1.reecho.cn/api/tts/simple-generate"
            payload = {
                "voiceId": voice,
                "text": text,
                "promptId": "default",
                "randomness": 95,
                "stability_boost": 100,
                "probability_optimization": 99,
                "break_clone": False,
                "flash": True,
                "origin_audio": False,
                "stream": False,
            }
            headers = {"Authorization": f"Bearer {self.api_key}"}
            http_client = new_httpx_client(is_async=False)
            response = http_client.post(url, headers=headers, json=payload, timeout=None)
            audio_url = response.json()["data"]["audio"]
            response = http_client.get(audio_url, headers=headers, timeout=None)
            with open(output_file_path, "wb") as f:
                f.write(response.content)
        elif self.provider == "azure":
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            }

            ssml = f"""
            <speak version='1.0' xml:lang='en-US'>
                <voice xml:lang='en-US' xml:gender='Female' name='{voice}'>
                    {text}
                </voice>
            </speak>
            """

            url = f"https://{self.service_region}.tts.speech.microsoft.com/cognitiveservices/v1"

            http_client = new_httpx_client(is_async=False)
            response = http_client.post(url, headers=headers, content=ssml)

            if response.status_code == 200:
                output_file_path = Path(output_file_path)
                with open(output_file_path, "wb") as audio_file:
                    audio_file.write(response.content)
            else:
                mprint.error(f"Error: {response.status_code}")
                mprint.error(response.text)

        return output_file_path

    def _stream_audio(self, text: str, voice: str = ""):
        self.streaming = True
        self._stop_flag = False
        p = pyaudio.PyAudio()
        if self.provider == "openai":
            if voice not in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
                voice = "alloy"
            stream = p.open(format=8, channels=1, rate=self.audio_sample_rate, output=True)
            with self.client.audio.speech.with_streaming_response.create(
                model=self.model_id, voice=voice, input=text, response_format="pcm"
            ) as response:
                for chunk in response.iter_bytes(1024):
                    if self._stop_flag:
                        break
                    stream.write(chunk)
        elif self.provider == "minimax":
            stream = p.open(format=8, channels=1, rate=self.audio_sample_rate, output=True)
            url = "https://api.minimax.chat/v1/t2a_v2"
            headers = {
                "accept": "application/json, text/plain, */*",
                "content-type": "application/json",
                "authorization": f"Bearer {self.api_key}",
            }
            body = {
                "model": self.model_id,
                "text": text,
                "voice_setting": {
                    "voice_id": voice,
                    "speed": 1,
                    "vol": 1,
                    "pitch": 0,
                },
                "audio_setting": {
                    "sample_rate": self.audio_sample_rate,
                    "bitrate": 128000,
                    "format": "pcm",
                },
                "stream": True,
            }
            http_client = new_httpx_client(is_async=False)
            with http_client.stream("POST", url, headers=headers, json=body) as response:
                for chunk in response.iter_lines():
                    if self._stop_flag:
                        break
                    if not chunk.startswith("data:"):
                        continue
                    data = json.loads(chunk[5:])
                    if "data" not in data or "extra_info" not in data:
                        continue
                    if "audio" in data["data"]:
                        audio = bytes.fromhex(data["data"]["audio"])
                        stream.write(audio)
        elif self.provider == "piper":
            stream = p.open(format=8, channels=1, rate=self.audio_sample_rate, output=True)
            headers = {"content-type": "text/plain"}
            http_client = new_httpx_client(is_async=False)
            # httpx typing: use `content` for raw string/bytes bodies (not `data`)
            with http_client.stream("POST", self.api_base, headers=headers, content=text) as response:
                for chunk in response.iter_bytes():
                    if self._stop_flag:
                        break
                    stream.write(chunk)
        elif self.provider == "reecho":
            url = "https://v1.reecho.cn/api/tts/simple-generate"
            payload = {
                "voiceId": voice,
                "text": text,
                "promptId": "default",
                "randomness": 95,
                "stability_boost": 100,
                "probability_optimization": 99,
                "break_clone": False,
                "flash": True,
                "origin_audio": False,
                "stream": True,
            }
            headers = {"Authorization": f"Bearer {self.api_key}"}
            http_client = new_httpx_client(is_async=False)
            response = http_client.post(url, headers=headers, json=payload, timeout=None)
            stream_url = response.json()["data"]["streamUrl"]

            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 2
            RATE = 44100

            p = pyaudio.PyAudio()
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True)

            ffmpeg_command = [
                "ffmpeg",
                "-headers",
                f"Authorization: Bearer {self.api_key}",
                "-i",
                stream_url,
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ac",
                str(CHANNELS),
                "-ar",
                str(RATE),
                "-",
            ]

            try:
                create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if platform.system() == "Windows":
                    ffmpeg_process = subprocess.Popen(
                        ffmpeg_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        creationflags=create_no_window,
                    )
                else:
                    ffmpeg_process = subprocess.Popen(
                        ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
                    )

                # Read decoded PCM audio data from ffmpeg's stdout and play it
                while True:
                    if ffmpeg_process.stdout is None:
                        break
                    data = ffmpeg_process.stdout.read(CHUNK)
                    if len(data) == 0 or self._stop_flag:
                        break
                    stream.write(data)

                # Wait for ffmpeg process to finish
                ffmpeg_process.wait()
            except KeyboardInterrupt:
                print("Stream stopped")
        elif self.provider == "azure":
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "raw-16khz-16bit-mono-pcm",
            }

            ssml = f"""
            <speak version='1.0' xml:lang='zh-CN'>
                <voice xml:lang='zh-CN' xml:gender='Female' name='{voice}'>
                    {text}
                </voice>
            </speak>
            """

            url = f"https://{self.service_region}.tts.speech.microsoft.com/cognitiveservices/v1"

            stream = p.open(format=pyaudio.paInt16, channels=1, rate=self.audio_sample_rate, output=True)

            try:
                http_client = new_httpx_client(is_async=False)
                with http_client.stream("POST", url, headers=headers, content=ssml) as response:
                    if response.status_code == 200:
                        for chunk in response.iter_bytes():
                            if self._stop_flag:
                                break
                            if chunk:
                                stream.write(chunk)
                    else:
                        mprint.error(f"Error: {response.status_code}")
                        mprint.error(response.text)
            finally:
                stream.stop_stream()
                stream.close()
                p.terminate()
        else:
            raise ValueError(f"Unsupported TTS provider: {self.provider}")

        stream.stop_stream()
        stream.close()
        p.terminate()
        self.streaming = False

    def stream(self, text: str, voice: str = "", non_block: bool = False, skip_code_block: bool = False):
        if skip_code_block:
            text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

        if non_block:
            thread = threading.Thread(target=self._stream_audio, args=(text, voice), daemon=True)
            thread.start()
            return thread
        else:
            self._stream_audio(text, voice)
            return True

    def stop(self):
        self._stop_flag = True


class ASRProvider(ABC):
    def __init__(self, model_id: str, language: str):
        self.model_id = model_id
        self.language = language

    @abstractmethod
    def transcribe(self, file: FileTypes, output_type: str) -> str | list[str]:
        pass


class OpenAIProvider(ASRProvider):
    def __init__(self, client: OpenAI, model_id: str, language: str):
        super().__init__(model_id, language)
        self.client = client

    def transcribe(self, file: FileTypes, output_type: str):
        if output_type == "text":
            transcription = self.client.audio.transcriptions.create(
                model=self.model_id, file=file, response_format="text"
            )
            return transcription
        elif output_type == "list":
            transcription = self.client.audio.transcriptions.create(
                model=self.model_id,
                file=file,
                response_format="verbose_json",
                # timestamp_granularities=["segment"],
            )
            return [segment.text for segment in transcription.segments or []]
        elif output_type == "srt":
            transcription = self.client.audio.transcriptions.create(
                model=self.model_id, file=file, response_format="srt"
            )
            return transcription
        else:
            raise ValueError(f"Unsupported ASR output type: {output_type}")


class SpeechRecognitionClient:
    def __init__(
        self,
        provider: Literal["openai"] | None = None,
        model: str | None = None,
        language: str | None = None,
    ):
        settings = Settings()

        if provider is None:
            provider = settings.get("asr.provider", "openai")

        if model is None:
            if provider != "openai":
                raise ValueError(f"Unsupported ASR provider: {provider}")
            _model = "whisper-1"
        else:
            _model = model

        if language is None:
            if provider != "openai":
                raise ValueError(f"Unsupported ASR provider: {provider}")
            _language = "en"
        else:
            _language = language

        if provider == "openai":
            from utilities.ai_utils import get_openai_client_and_model_id

            if settings.get("asr.openai.same_as_llm", False):
                client, model_id = get_openai_client_and_model_id(is_async=False, model_id=_model)
            else:
                client = OpenAI(
                    api_key=settings.get("asr.openai.api_key"),
                    base_url=settings.get("asr.openai.api_base"),
                    http_client=new_llm_http_client(is_async=False),
                )
                model_id = settings.get("asr.openai.model", "whisper-1")
            self.provider = OpenAIProvider(client, model_id, _language)
        else:
            raise ValueError(f"Unsupported ASR provider: {provider}")

    def batch_transcribe(self, files: list, output_type: str = "text"):
        outputs = []
        for file_data in files:
            outputs.append(self.transcribe(file_data, output_type))
        return outputs

    def transcribe(self, file: FileTypes, output_type: str = "text"):
        return self.provider.transcribe(file, output_type)
