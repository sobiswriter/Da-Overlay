import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop import Desktop
from utils.storage import Store


class DesktopTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "data", Path(temp.name) / "legacy")
        self.store.api_key = "offline-test-key"
        self.app = Desktop(self.store)
        self.events = []
        self.app._emit = self.events.append

    def wait_done(self):
        deadline = time.monotonic() + 3
        while self.app._busy and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(self.app._busy, "Worker did not complete")

    def test_multi_paragraph_reply_is_one_message_and_copy_uses_real_text(self):
        with patch("desktop.gemini_client.stream_events", return_value=iter([
            {"type": "text", "text": "First paragraph.\n\n"},
            {"type": "text", "text": "Second paragraph."},
        ])):
            self.assertTrue(self.app.dispatch("send", {"text": "Hi"})["ok"])
            self.wait_done()
        messages = self.store.session()["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[1]["text"], "First paragraph.\n\nSecond paragraph.")
        saved = Store(self.store.directory, self.store.directory / "missing")
        self.assertEqual(saved.session()["messages"][1]["text"], messages[1]["text"])

    def test_disabled_context_is_never_read_even_with_a_screenshot(self):
        self.app._attachment = {"bytes": b"image", "preview": {"kind": "region"}}
        self.store.data["settings"]["share_context"] = False
        seen = []

        def stream(*args, **kwargs):
            seen.append(kwargs)
            yield {"type": "text", "text": "A response."}

        with patch.object(self.app, "_window_context", side_effect=AssertionError("Privacy leak")), patch("desktop.gemini_client.stream_events", side_effect=stream):
            self.assertTrue(self.app.dispatch("send", {"text": "Look at this"})["ok"])
            self.wait_done()
        self.assertIsNone(seen[0]["active_context"])
        self.assertEqual(seen[0]["image_bytes"], b"image")

    def test_concurrent_send_is_rejected_and_cancelled_worker_cannot_overwrite(self):
        started, release, finished = threading.Event(), threading.Event(), threading.Event()

        def stream(*args, **kwargs):
            started.set()
            release.wait(3)
            yield {"type": "text", "text": "This stale text must not appear"}
            finished.set()

        with patch("desktop.gemini_client.stream_events", side_effect=stream):
            self.app.dispatch("send", {"text": "First"})
            self.assertTrue(started.wait(1))
            self.assertFalse(self.app.dispatch("send", {"text": "Second"})["ok"])
            self.assertTrue(self.app.dispatch("stop")["ok"])
            release.set()
            time.sleep(0.03)
        messages = self.store.session()["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[-1]["text"], "")
        self.assertEqual(messages[-1]["status"], "stopped")

    def test_failed_memory_generation_never_closes_or_clears_chat(self):
        self.store.session()["messages"].append({"id": "u", "role": "user", "text": "Keep this", "created_at": "now"})
        with patch("desktop.gemini_client.generate_memory_blob", return_value="Error: unavailable"):
            self.app.dispatch("summarize")
            self.wait_done()
        self.assertEqual(len(self.store.session()["messages"]), 1)
        self.assertEqual(self.store.data["memories"], [])
        self.assertFalse(self.app._closed.is_set())

    def test_settings_reject_invalid_values_without_partial_update(self):
        old = self.store.data["settings"].copy()
        result = self.app.dispatch("settings", {"mode": "focus", "autopilot_interval": -1})
        self.assertFalse(result["ok"])
        self.assertEqual(self.store.data["settings"], old)

    def test_autopilot_cannot_be_enabled_without_window_context(self):
        result = self.app.dispatch("settings", {"autopilot_enabled": True})
        self.assertFalse(result["ok"])
        self.assertFalse(self.store.data["settings"]["autopilot_enabled"])

    def test_javascript_and_file_urls_cannot_be_opened(self):
        for url in ["javascript:alert(1)", "file:///C:/secret", "ms-settings:privacy"]:
            with self.subTest(url=url):
                self.assertFalse(self.app.dispatch("open_link", {"url": url})["ok"])

    def test_public_state_and_exportable_messages_do_not_contain_key(self):
        import json
        self.assertNotIn(self.store.api_key, json.dumps(self.app.dispatch("state")))

    def test_full_opacity_from_javascript_is_accepted_as_a_number(self):
        self.assertTrue(self.app.dispatch("settings", {"opacity": 1})["ok"])

    def test_send_save_failure_restores_the_draft_and_does_not_lock_chat(self):
        with patch.object(self.store, "save", side_effect=OSError("disk full")):
            result = self.app.dispatch("send", {"text": "Do not lose this"})
        self.assertFalse(result["ok"])
        self.assertFalse(self.app._busy)
        self.assertEqual(self.store.session()["messages"], [])

    def test_failed_settings_save_keeps_previous_preferences(self):
        original = self.store.data["settings"].copy()
        with patch.object(self.store, "save", side_effect=OSError("disk full")):
            result = self.app.dispatch("settings", {"theme": "light"})
        self.assertFalse(result["ok"])
        self.assertEqual(self.store.data["settings"], original)

    def test_failed_close_keeps_window_open_and_conversation_in_memory(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        close = Mock()
        self.app._window = SimpleNamespace(destroy=close)
        self.store.session()["messages"].append({"id": "one", "role": "user", "text": "Still here"})
        with patch.object(self.store, "save", side_effect=OSError("disk full")):
            self.app._finish_close()
        close.assert_not_called()
        self.assertFalse(self.app._closed.is_set())
        self.assertEqual(self.store.session()["messages"][0]["text"], "Still here")

    def test_failed_delete_restores_conversation(self):
        original = self.store.session()
        with patch.object(self.store, "save", side_effect=OSError("disk full")):
            result = self.app.dispatch("delete_session", {"id": original["id"]})
        self.assertFalse(result["ok"])
        self.assertEqual(self.store.session()["id"], original["id"])

    def test_cancelled_region_selection_restores_window_and_never_calls_ai(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        self.app._window = SimpleNamespace(hide=Mock(), show=Mock())
        with patch("mss.mss") as capture, patch.object(self.app, "_select_region", return_value=None), patch("desktop.gemini_client.stream_events") as stream:
            capture.return_value.__enter__.return_value.monitors = [{"left": 0, "top": 0, "width": 100, "height": 100}]
            result = self.app.dispatch("capture", {"kind": "region"})
        self.assertTrue(result["ok"])
        self.assertIsNone(self.app._attachment)
        self.app._window.show.assert_called_once()
        stream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
