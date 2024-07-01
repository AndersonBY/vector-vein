# @Author: Bi Ying
# @Date:   2024-07-01 14:38:03
import time
from threading import Thread

from utilities.media_processing import TTSClient
from utilities.general import mprint


class TTSServer:
    def __init__(self):
        self.tts_client = None
        self.thread = None
        self.playing = False
        self.terminate_requested = False

    def start(self):
        if self.thread is not None:
            mprint("TTSServer is already running")
            return

        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        mprint("TTSServer is running")
        while not self.terminate_requested:
            time.sleep(0.1)  # Keep the thread alive

    def stop(self):
        if self.tts_client is not None and self.playing:
            mprint("Stopping current TTS playback")
            self.tts_client.stop()
            self.playing = False
            self.tts_client = None

    def terminate(self):
        if self.thread is None:
            mprint("TTSServer is not running")
            return

        mprint("Terminating TTSServer")
        self.terminate_requested = True
        self.stop()
        self.thread.join()
        self.thread = None
        self.terminate_requested = False

    def stream(
        self,
        text: str,
        provider: str = "openai",
        voice: str = "onyx",
        skip_code_block: bool = True,
    ):
        if self.thread is None:
            raise RuntimeError("TTSServer is not running")

        self.stop()  # Ensure any previous TTS is stopped before starting a new one

        self.tts_client = TTSClient(provider=provider)
        self.playing = True

        def _stream():
            self.tts_client.stream(text=text, voice=voice, non_block=False, skip_code_block=skip_code_block)
            self.playing = False

        stream_thread = Thread(target=_stream)
        stream_thread.start()

    @property
    def is_playing(self):
        return self.playing


tts_server = TTSServer()
