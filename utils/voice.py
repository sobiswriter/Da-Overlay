"""Bounded microphone clips in RAM and Windows' local read-aloud voice."""
import io
import re
import struct
import threading
import time
import wave

MAX_SECONDS = 120


class Recorder:
    def __init__(self):
        self._lock = threading.Lock()
        self._stream = None
        self._pcm = bytearray()
        self.active = False
        self.rate = 16000
        self.level = 0
        self.started = 0
        self.full = False
        self.warning = False

    def start(self):
        import sounddevice as sd
        with self._lock:
            if self.active:
                raise ValueError("A voice recording is already in progress.")
            self._pcm.clear()
            self.level = 0
            self.full = False
            self.warning = False
        try:
            try:
                sd.check_input_settings(channels=1, dtype="int16", samplerate=16000)
                self.rate = 16000
            except sd.PortAudioError:
                self.rate = min(48000, int(sd.query_devices(kind="input")["default_samplerate"]))
            self._stream = sd.RawInputStream(samplerate=self.rate, channels=1,
                dtype="int16", blocksize=1024, callback=self._capture, finished_callback=self._finished)
            self.active = True
            self.started = time.monotonic()
            self._stream.start()
        except (sd.PortAudioError, OSError, ValueError):
            self.stop(discard=True)
            raise ValueError("The microphone could not open. Check your default input device and Windows microphone access, then try again.") from None

    def _capture(self, data, frames, timing, status):
        chunk = bytes(data)
        with self._lock:
            if not self.active:
                return
            remaining = MAX_SECONDS * self.rate * 2 - len(self._pcm)
            self._pcm.extend(chunk[:remaining])
            self.full = len(self._pcm) >= MAX_SECONDS * self.rate * 2
            self.warning |= bool(getattr(status, "input_overflow", False))
            samples = [abs(struct.unpack_from("<h", chunk, i)[0]) for i in range(0, len(chunk) - 1, 32)]
            self.level = min(1, max(samples, default=0) / 18000)

    def snapshot(self):
        return {"active": self.active, "seconds": min(MAX_SECONDS, max(0, time.monotonic() - self.started)) if self.active else 0,
                "level": self.level, "warning": self.warning}

    def _finished(self):
        with self._lock:
            if self.active:
                self.full = self.warning = True

    def stop(self, discard=False):
        with self._lock:
            self.active = False
            stream, self._stream = self._stream, None
        if stream:
            try:
                stream.stop()
            except Exception:
                self.warning = True
            finally:
                try:
                    stream.close()
                except Exception:
                    self.warning = True
        with self._lock:
            pcm = bytes(self._pcm)
            self._pcm.clear()
        if discard:
            return None
        if len(pcm) < self.rate * 2 * .2:
            raise ValueError("That clip was too short. Record at least a moment of speech.")
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.rate)
            wav.writeframes(pcm)
        return {"bytes": output.getvalue(), "duration": round(len(pcm) / (self.rate * 2), 1)}


def speak(text, cancelled):
    import pythoncom
    import win32com.client
    text = re.sub(r"```.*?```", " Code example. ", text, flags=re.S)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # shortcut: read-aloud is capped at 6k characters; use a segmented player for long documents.
    text = text[:6000]
    pythoncom.CoInitialize()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        if cancelled.is_set():
            return
        voice.Speak(text, 17)  # Async, plain text: model output must never be interpreted as speech XML.
        while not voice.WaitUntilDone(100):
            if cancelled.is_set():
                voice.Speak("", 3)
                break
    finally:
        pythoncom.CoUninitialize()
