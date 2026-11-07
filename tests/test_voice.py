import io
import struct
import tempfile
import time
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

from desktop import Desktop
from utils.storage import Store
from utils.voice import MAX_SECONDS, Recorder, speak
from tests.voice_fixture import wav_clip


class RecorderTests(unittest.TestCase):
    def test_read_aloud_treats_model_markup_as_text_not_xml_or_a_file(self):
        voice = Mock()
        voice.WaitUntilDone.return_value = True
        with patch("pythoncom.CoInitialize"), patch("pythoncom.CoUninitialize"), patch("win32com.client.Dispatch", return_value=voice):
            speak('<speak><audio src="https://example.invalid/audio.wav"/>Hello</speak>', threading.Event())
        flags = voice.Speak.call_args.args[1]
        self.assertTrue(flags & 16)
        self.assertFalse(flags & (4 | 8))

    def test_stop_closes_device_and_produces_bounded_mono_wav_in_memory(self):
        stream = Mock()
        recorder = Recorder()
        with patch("sounddevice.check_input_settings"), patch("sounddevice.RawInputStream", return_value=stream):
            recorder.start()
            recorder._capture(struct.pack("<h", 1000) * 8000, 8000, None, None)
            clip = recorder.stop()
        with wave.open(io.BytesIO(clip["bytes"]), "rb") as wav:
            self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()), (1, 2, 16000, 8000))
        self.assertEqual(clip["duration"], .5)
        self.assertFalse(recorder.active)
        self.assertFalse(recorder._pcm)
        stream.close.assert_called_once()

    def test_recording_buffer_cannot_exceed_two_minutes(self):
        recorder = Recorder()
        recorder.active = True
        data = b"\x00\x00" * (recorder.rate * MAX_SECONDS + 100)
        recorder._capture(data, len(data)//2, None, None)
        self.assertEqual(len(recorder._pcm), recorder.rate * MAX_SECONDS * 2)
        self.assertTrue(recorder.full)
        self.assertIsNone(recorder.stop(discard=True))

    def test_permission_or_device_error_leaves_no_recording_running(self):
        import sounddevice
        recorder = Recorder()
        with patch("sounddevice.check_input_settings"), patch("sounddevice.RawInputStream", side_effect=sounddevice.PortAudioError("No device")):
            with self.assertRaisesRegex(ValueError, "microphone"):
                recorder.start()
        self.assertFalse(recorder.active)
        self.assertIsNone(recorder._stream)

    def test_device_stop_failure_recovers_captured_audio_and_closes_the_device(self):
        recorder = Recorder()
        recorder.active = True
        recorder._stream = stream = Mock()
        stream.stop.side_effect = RuntimeError("Device unplugged")
        recorder._capture(struct.pack("<h", 1000) * 8000, 8000, None, None)
        clip = recorder.stop()
        self.assertEqual(clip["duration"], .5)
        self.assertTrue(recorder.snapshot()["warning"])
        stream.close.assert_called_once()
        self.assertFalse(recorder._pcm)

    def test_unexpected_device_shutdown_finishes_the_clip_with_a_warning(self):
        recorder = Recorder()
        recorder.active = True
        recorder._finished()
        self.assertTrue(recorder.full)
        self.assertTrue(recorder.warning)
        recorder.stop(discard=True)


class VoiceConversationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name), Path(self.folder.name) / "no-legacy")
        self.store.api_key = "offline-fixture"
        self.app = Desktop(self.store)
        self.app._speak = Mock()

    def wait_done(self):
        deadline = time.monotonic() + 3
        while self.app._busy and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertFalse(self.app._busy)

    def test_voice_transcript_is_saved_and_audio_never_enters_public_state_or_disk(self):
        clip = wav_clip()
        self.app._voice_attachment = clip
        self.assertNotIn("bytes", self.app._snapshot()["voice"])
        with patch("desktop.gemini_client.stream_events", side_effect=[
            iter([{"type": "text", "text": "Could you help me plan my project?"}]),
            iter([{"type": "text", "text": "Let's choose the next useful step."}])]) as stream:
            self.assertTrue(self.app.dispatch("send", {"text": ""})["ok"])
            self.wait_done()
        user, reply = self.store.session()["messages"]
        self.assertEqual(user["text"], "Could you help me plan my project?")
        self.assertTrue(user["voice_transcribed"])
        self.assertEqual(stream.call_args_list[0].kwargs["audio_bytes"], clip["bytes"])
        self.assertEqual(stream.call_args_list[1].kwargs["audio_bytes"], clip["bytes"])
        self.assertEqual(reply["status"], "done")
        self.app._speak.assert_called_once_with(reply["text"])
        self.assertFalse(list(Path(self.folder.name).rglob("*.wav")))
        self.assertNotIn("RIFF", self.store.path.read_text(encoding="utf-8"))

    def test_transcription_failure_can_retry_the_clip_without_erasing_history(self):
        self.app._voice_attachment = wav_clip()
        with patch("desktop.gemini_client.stream_events", return_value=iter([{"type": "error", "message": "Offline"}])):
            self.app._send({})
            self.wait_done()
        self.assertEqual(self.store.session()["messages"][-1]["status"], "error")
        with patch("desktop.gemini_client.stream_events", side_effect=[
            iter([{"type": "text", "text": "Hello from a voice message."}]),
            iter([{"type": "text", "text": "Hello!"}])]):
            self.assertTrue(self.app.dispatch("retry")["ok"])
            self.wait_done()
        self.assertEqual(len(self.store.session()["messages"]), 2)
        self.assertEqual(self.store.session()["messages"][0]["text"], "Hello from a voice message.")

    def test_active_recording_blocks_send_and_autopilot(self):
        self.app._recorder = Mock(active=True)
        self.store.data["settings"].update(autopilot_enabled=True, autopilot_screenshots=True)
        self.app._last_activity = 0
        with patch.object(self.app, "_screen_snapshot") as capture:
            self.app._background_tick()
        capture.assert_not_called()
        self.assertFalse(self.app.dispatch("send", {"text": "Don't upload a running recording"})["ok"])
        self.assertFalse(self.store.session()["messages"])

    def test_save_failure_preserves_voice_draft_and_never_calls_the_model(self):
        clip = wav_clip()
        self.app._voice_attachment = clip
        with patch.object(self.store, "save", side_effect=OSError("disk full")), patch("desktop.gemini_client.stream_events") as stream:
            self.assertFalse(self.app.dispatch("send", {})["ok"])
        self.assertIs(self.app._voice_attachment, clip)
        self.assertFalse(self.store.session()["messages"])
        stream.assert_not_called()

    def test_failed_conversation_switch_keeps_the_current_voice_draft(self):
        first = self.store.session()["id"]
        second = self.store.new_session()["id"]
        self.app._voice_attachment = clip = wav_clip()
        with patch.object(self.store, "save", side_effect=OSError("disk full")):
            self.assertFalse(self.app.dispatch("select_session", {"id": first})["ok"])
        self.assertEqual(self.store.session()["id"], second)
        self.assertIs(self.app._voice_attachment, clip)

    def test_retry_does_not_replace_a_new_unsent_voice_clip(self):
        self.app._voice_attachment = clip = wav_clip()
        self.store.session()["messages"] = [{"id": "u", "role": "user", "text": "Earlier"}, {"id": "m", "role": "model", "text": "", "status": "error"}]
        self.assertFalse(self.app.dispatch("retry")["ok"])
        self.assertIs(self.app._voice_attachment, clip)
        self.assertEqual(len(self.store.session()["messages"]), 2)

    def test_stop_recording_remains_available_during_another_action(self):
        from tests.voice_fixture import FakeRecorder
        self.app._recorder = FakeRecorder()
        self.app._recorder.start()
        self.app._busy = True
        self.assertTrue(self.app.dispatch("record")["ok"])
        self.assertFalse(self.app._recorder.active)
        self.assertEqual(self.app._voice_attachment["duration"], .5)

    def test_recording_started_during_capture_blocks_the_pending_send(self):
        self.store.data["settings"]["capture_mode"] = "region"
        def capture(data):
            self.app._recorder = Mock(active=True)
            return {"kind": "region"}
        with patch.object(self.app, "_capture", side_effect=capture), patch("desktop.gemini_client.stream_events") as stream:
            self.assertFalse(self.app.dispatch("send", {"text": "Wait for recording"})["ok"])
        stream.assert_not_called()
        self.assertFalse(self.store.session()["messages"])
