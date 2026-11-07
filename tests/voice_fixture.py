"""Synthetic recorder for UI checks: never opens the microphone."""
import time
import io
import struct
import wave


def wav_clip():
    data = io.BytesIO()
    with wave.open(data, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(struct.pack("<h", 1000) * 8000)
    return {"bytes": data.getvalue(), "duration": .5}


class FakeRecorder:
    active = False
    full = False

    def start(self):
        self.started = time.monotonic()
        self.active = True

    def snapshot(self):
        return {"active": self.active, "seconds": .5 if self.active else 0, "level": .6}

    def stop(self, discard=False):
        self.active = False
        return None if discard else wav_clip()
