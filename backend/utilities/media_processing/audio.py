# @Author: Bi Ying
# @Date:   2024-06-09 15:53:58
import re
import time
import json
import wave
import platform
import threading
import subprocess
from io import IOBase
from os import PathLike
from pathlib import Path
from datetime import datetime
from typing import Literal, cast
from abc import ABC, abstractmethod

import pyaudio
import numpy as np
from openai import OpenAI
from openai._types import FileTypes
from deepgram_captions import DeepgramConverter, srt
from deepgram import DeepgramClient
from deepgram.types.listen_v1response import ListenV1Response
from deepgram.types.listen_v1accepted_response import ListenV1AcceptedResponse
from deepgram.listen.client import ListenClient
from deepgram.listen.v1.client import V1Client

from utilities.config import Settings, config
from utilities.general import mprint_with_name
from utilities.network import new_httpx_client


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
                if platform.system() == "Windows":
                    ffmpeg_process = subprocess.Popen(
                        ffmpeg_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
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
            thread = threading.Thread(target=self._stream_audio, args=(text, voice))
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


class DeepgramProvider(ASRProvider):
    def __init__(self, client: DeepgramClient, model_id: str, language: str):
        super().__init__(model_id, language)
        self.client = client

    def transcribe(self, file: FileTypes, output_type: str):
        # Deepgram SDK v5: use listen.v1.media.transcribe_file/url with kwargs
        # Help Pylance with dynamic router types using explicit casts
        listen_v1 = cast(V1Client, cast(ListenClient, self.client.listen).v1)
        response: ListenV1Response | ListenV1AcceptedResponse
        if isinstance(file, IOBase):
            payload_bytes = file.read()
            response = listen_v1.media.transcribe_file(
                request=payload_bytes,
                model=self.model_id,
                language=self.language,
                smart_format=True,
                paragraphs=True,
                punctuate=True,
            )
        elif isinstance(file, bytes):
            response = listen_v1.media.transcribe_file(
                request=file,
                model=self.model_id,
                language=self.language,
                smart_format=True,
                paragraphs=True,
                punctuate=True,
            )
        elif isinstance(file, (str, PathLike)):
            file_str = str(file)
            if file_str.startswith("http://") or file_str.startswith("https://"):
                response = listen_v1.media.transcribe_url(
                    url=file_str,
                    model=self.model_id,
                    language=self.language,
                    smart_format=True,
                    paragraphs=True,
                    punctuate=True,
                )
            else:
                with open(file_str, "rb") as f:
                    payload_bytes = f.read()
                response = listen_v1.media.transcribe_file(
                    request=payload_bytes,
                    model=self.model_id,
                    language=self.language,
                    smart_format=True,
                    paragraphs=True,
                    punctuate=True,
                )
        else:
            raise TypeError("Unsupported source type")
        # Narrow union to completed response with results
        if isinstance(response, ListenV1AcceptedResponse):
            raise RuntimeError(
                "Deepgram returned an accepted response without results. "
                "Remove callback/async options or poll for completion."
            )
        resp = cast(ListenV1Response, response)
        if (
            resp.results is None
            or resp.results.channels is None
            or resp.results.channels[0].alternatives is None
        ):
            return ""

        if output_type == "text":
            return resp.results.channels[0].alternatives[0].transcript or ""
        elif output_type == "list":
            words = []
            for word in resp.results.channels[0].alternatives[0].words or []:
                # Deepgram v5 response objects are Pydantic models
                words.append(getattr(word, "model_dump", getattr(word, "dict"))())
            return words
        elif output_type == "srt":
            # Convert to a plain dict for the captions helper
            transcription = DeepgramConverter(getattr(resp, "model_dump", resp.dict)())
            return srt(transcription)
        else:
            raise ValueError(f"Unsupported ASR output type: {output_type}")


class SpeechRecognitionClient:
    def __init__(
        self,
        provider: Literal["openai", "deepgram"] | None = None,
        model: str | None = None,
        language: str | None = None,
    ):
        settings = Settings()

        if provider is None:
            provider = settings.get("asr.provider", "openai")

        if model is None:
            if provider == "openai":
                _model = "whisper-1"
            elif provider == "deepgram":
                _model = settings.get("asr.deepgram.speech_to_text.model", "nova-2")
            else:
                raise ValueError(f"Unsupported ASR provider: {provider}")
        else:
            _model = model

        if language is None:
            if provider == "openai":
                _language = "en"
            elif provider == "deepgram":
                _language = settings.get("asr.deepgram.speech_to_text.language", "en")
            else:
                raise ValueError(f"Unsupported ASR provider: {provider}")
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
                    http_client=new_httpx_client(is_async=False),
                )
                model_id = settings.get("asr.openai.model", "whisper-1")
            self.provider = OpenAIProvider(client, model_id, _language)
        elif provider == "deepgram":
            client = DeepgramClient(settings.get("asr.deepgram.api_key"))
            self.provider = DeepgramProvider(client, _model, _language)
        else:
            raise ValueError(f"Unsupported ASR provider: {provider}")

    def batch_transcribe(self, files: list, output_type: str = "text"):
        outputs = []
        for file_data in files:
            outputs.append(self.transcribe(file_data, output_type))
        return outputs

    def transcribe(self, file: FileTypes, output_type: str = "text"):
        return self.provider.transcribe(file, output_type)


class Microphone:
    def __init__(self, device_index: int = 0, output_folder: str | Path | None = None):
        self.chunk = 1024
        self.sample_format = pyaudio.paInt16
        self.channels = 1
        self.fs = 44100
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.thread = None
        self.device_index = device_index
        self.latest_saved_file = ""
        self._stop_signal = threading.Event()
        self._sound_player = SoundPlayer()
        if output_folder is None:
            self.output_folder = Path(config.data_path) / "audio"
            self.output_folder.mkdir(parents=True, exist_ok=True)
        else:
            self.output_folder = Path(output_folder)

    def start(self, auto_stop=False, silence_threshold: int | None = None, silence_duration=2):
        self.auto_stop = auto_stop
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.silence_buffer = 0
        self.__start_recording_time = time.time()
        self.__latest_chunks_amplitude = []
        self.__max_recording_amplitude = 0
        self._stop_signal.clear()

        if not self.is_recording:
            self.is_recording = True
            self.frames = []
            self.stream = self.p.open(
                format=self.sample_format,
                channels=self.channels,
                rate=self.fs,
                frames_per_buffer=self.chunk,
                input=True,
                input_device_index=self.device_index,
            )
            self._sound_player.play("recording-start.wav")
            self.thread = threading.Thread(target=self._record)
            self.thread.start()

    def stop(self):
        if self.is_recording:
            self.is_recording = False
            self._stop_signal.set()
            if self.thread is not None:
                self.thread.join()
            self._sound_player.play("recording-end.wav")
            return self._stop_stream()

    def _stop_stream(self):
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
        self.latest_saved_file = self._save_to_file()
        return self.latest_saved_file

    def _record(self):
        while self.is_recording and not self._stop_signal.is_set():
            if self.stream is None:
                break
            data = self.stream.read(self.chunk)
            self.frames.append(data)

            if self.auto_stop:
                audio_data = np.frombuffer(data, dtype=np.int16)
                max_amplitude = np.max(np.abs(audio_data))
                if max_amplitude > self.__max_recording_amplitude:
                    self.__max_recording_amplitude = max_amplitude
                self.__latest_chunks_amplitude.append(max_amplitude)
                if len(self.__latest_chunks_amplitude) > self.silence_duration:
                    self.__latest_chunks_amplitude.pop(0)
                latest_chunks_average_amplitude = np.mean(self.__latest_chunks_amplitude)

                if time.time() - self.__start_recording_time < 2:
                    continue

                threshold = (
                    self.__max_recording_amplitude * 0.3 if self.silence_threshold is None else self.silence_threshold
                )

                if latest_chunks_average_amplitude < threshold:
                    self.silence_buffer += 1
                else:
                    self.silence_buffer = 0

                if self.silence_buffer > (self.fs / self.chunk) * self.silence_duration:
                    self._stop_signal.set()

        self.is_recording = False
        self._stop_stream()

    def _save_to_file(self):
        datetime_string = datetime.now().strftime("%Y%m%d%H%M%S")
        self.output_file = self.output_folder / f"{datetime_string}.wav"
        wf = wave.open(str(self.output_file.resolve()), "wb")
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.p.get_sample_size(self.sample_format))
        wf.setframerate(self.fs)
        wf.writeframes(b"".join(self.frames))
        wf.close()
        return str(self.output_file.resolve())

    def list_devices(self):
        device_count = self.p.get_host_api_info_by_index(0).get("deviceCount")
        if device_count is None:
            return []
        device_count = int(device_count)
        devices = []
        for i in range(device_count):
            info = self.p.get_device_info_by_host_api_device_index(0, i)
            max_input_channels = info.get("maxInputChannels")
            if max_input_channels is None:
                continue
            if int(max_input_channels) > 0:
                devices.append(
                    {
                        "index": info.get("index"),
                        "name": info.get("name"),
                        "maxInputChannels": info.get("maxInputChannels"),
                    }
                )
        return devices

    def set_device(self, device_index):
        self.device_index = device_index

    def close(self):
        self.p.terminate()


class SoundPlayer:
    def __init__(self, sound_folder: str | Path = "./assets/sound/"):
        self.sound_folder = Path(sound_folder)
        self.p = pyaudio.PyAudio()

    def play(self, sound_name: str, non_block: bool = True):
        sound_path = self.sound_folder / sound_name
        if not sound_path.exists():
            mprint.error(f"Sound file {sound_path} not found.")
            return

        if non_block:
            thread = threading.Thread(target=self._play_sound, args=(sound_path,))
            thread.start()
            return thread
        else:
            self._play_sound(sound_path)
            return True

    def _play_sound(self, sound_path: str | Path):
        sound_path = Path(sound_path)
        mprint(sound_path)
        wf = wave.open(str(sound_path.resolve()), "rb")
        stream = self.p.open(
            format=self.p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
        )

        data = wf.readframes(1024)
        while data:
            stream.write(data)
            data = wf.readframes(1024)

        stream.stop_stream()
        stream.close()
        wf.close()

    def __del__(self):
        self.p.terminate()
