"""Explicit billable integration check: synthetic speech, never the microphone or saved workspace."""
import argparse
import sys
import tempfile
import time
import wave
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop import Desktop
from utils.storage import Store
from utils.google_connection import DEFAULT_MODEL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--account", required=True)
    args = parser.parse_args()
    import pythoncom
    import win32com.client
    with tempfile.TemporaryDirectory(prefix="cutex-synthetic-vertex-") as folder:
        path = Path(folder) / "synthetic.wav"
        pythoncom.CoInitialize()
        try:
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Open(str(path), 3)
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.AudioOutputStream = stream
            speaker.Speak("Please reply with the words, voice messages are working.")
            stream.Close()
        finally:
            pythoncom.CoUninitialize()
        with wave.open(str(path), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
        store = Store(Path(folder) / "data", Path(folder) / "no-legacy")
        app = Desktop(store)
        app._speak = Mock()
        app._settings({"provider": "vertex", "vertex_project": args.project,
                       "vertex_account": args.account, "model": DEFAULT_MODEL})
        app._voice_attachment = {"bytes": path.read_bytes(), "duration": duration}
        app._send({})
        deadline = time.monotonic() + 90
        while app._busy and time.monotonic() < deadline:
            time.sleep(.1)
        assert not app._busy, "Live voice check timed out"
        user, reply = store.session()["messages"]
        assert user.get("voice_transcribed"), reply.get("error", "No transcript")
        assert reply["status"] == "done", reply.get("error", "Reply failed")
        assert app._speak.called, "Voice response did not reach the local speech boundary"
        print("PASS: requested ADC identity, Vertex Gemini 3.8 Flash, real synthetic-audio transcription and streamed reply.")
        print("Synthetic transcript:", user["text"][:180])
        print("Live reply:", reply["text"][:180])


if __name__ == "__main__":
    main()
