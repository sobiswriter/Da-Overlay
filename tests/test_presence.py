import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop import Desktop, compact_rgb
from utils.storage import Store


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name), Path(self.temp.name) / "no-legacy")
        self.store.api_key = "offline-fixture"
        self.app = Desktop(self.store)
        self.app._window = SimpleNamespace(hide=Mock(), show=Mock(), evaluate_js=Mock())
        self.app._hud = Mock()

    def test_hide_collapses_to_orb_and_focus_opens_quick_reply(self):
        self.app._toggle_visible()
        self.assertFalse(self.app._visible)
        self.app._window.hide.assert_called_once()
        self.app._hud.show.assert_called_once()
        self.app._show_and_focus()
        self.app._hud.show.assert_called_with(reply=True)
        self.app._window.show.assert_not_called()

    def test_quit_while_docked_saves_and_closes_the_native_companion(self):
        self.app._visible = False
        self.app._window.destroy = Mock()
        self.assertTrue(self.app.dispatch("quit")["ok"])
        self.assertTrue(self.app._closed.wait(2))
        deadline = time.monotonic() + 2
        while not self.app._window.destroy.called and time.monotonic() < deadline:
            time.sleep(.01)
        self.app._hud.close.assert_called_once()
        self.app._window.destroy.assert_called_once()

    def test_hide_everything_can_be_restored_to_the_orb_with_either_shortcut(self):
        self.app._visible = False
        self.app._hide_companion()
        self.assertTrue(self.app._snapshot()["hidden"])
        self.app._hud.hide.assert_called_once()
        self.app._toggle_visible()
        self.assertFalse(self.app._snapshot()["hidden"])
        self.app._hud.show.assert_called_once_with()
        self.app._window.show.assert_not_called()
        self.app._toggle_companion()
        self.assertTrue(self.app._presence_hidden)
        self.app._toggle_companion()
        self.assertFalse(self.app._presence_hidden)

    def test_fully_hidden_companion_does_not_capture_for_autopilot(self):
        self.app._presence_hidden = True
        self.app._visible = False
        self.store.data["settings"].update(autopilot_enabled=True, autopilot_screenshots=True)
        self.app._last_activity = 0
        with patch.object(self.app, "_screen_snapshot") as capture:
            self.app._background_tick()
        capture.assert_not_called()

    def test_failed_quit_while_hidden_opens_workspace_for_recovery(self):
        self.app._visible = False
        self.app._presence_hidden = True
        self.app._window.destroy = Mock()
        with patch.object(self.store, "save", side_effect=OSError("disk full")):
            self.app.dispatch("quit")
            deadline = time.monotonic() + 2
            while self.app._closing and time.monotonic() < deadline:
                time.sleep(.01)
        self.assertFalse(self.app._closed.is_set())
        self.assertFalse(self.app._presence_hidden)
        self.app._window.show.assert_called_once()
        self.app._window.destroy.assert_not_called()

    def test_second_launch_requests_a_real_restore_instead_of_unhiding_a_frozen_page(self):
        self.app._activate_event = object()
        with patch("win32event.WaitForSingleObject", return_value=0), patch.object(self.app, "_restore_workspace") as restore:
            self.app._background_tick()
        restore.assert_called_once()

    def test_opening_full_window_from_docked_overlay_fits_the_monitor(self):
        self.app._overlay = True
        self.app._visible = False
        self.app._window.width, self.app._window.height = 440, 680
        self.app._window.move = Mock()
        self.app._window.resize = Mock()
        with patch.object(self.app, "_window_rectangle", return_value=(1500, 600, 440, 680)), patch.object(self.app, "_set_on_top"), patch.object(self.app, "_restore_workspace"), patch("win32api.GetMonitorInfo", return_value={"Work": (0, 0, 1920, 1040)}), patch("win32api.MonitorFromPoint"):
            self.app._open_surface({"overlay": False})
        self.app._window.move.assert_called_with(640, 220)
        self.app._window.resize.assert_called_with(1280, 820)
        self.assertEqual(self.app._docked_rect, (640, 220, 1280, 820))

    def test_background_snapshot_requires_separate_permission(self):
        self.store.data["settings"].update(autopilot_enabled=True, share_context=True)
        self.app._last_activity = 0
        with patch.object(self.app, "_screen_snapshot") as snapshot, patch.object(self.app, "_window_context", return_value="Editor"), patch.object(self.app, "_send"):
            self.app._background_tick()
        snapshot.assert_not_called()

    def test_hidden_workspace_does_not_block_visual_autopilot(self):
        self.store.data["settings"].update(autopilot_enabled=True, autopilot_screenshots=True, share_context=False)
        self.app._visible = False
        self.app._last_activity = 0
        with patch.object(self.app, "_screen_snapshot", return_value=b"fresh screen") as capture, patch.object(self.app, "_send") as send:
            self.app._background_tick()
            self.app._last_observation_at = 0
            self.app._background_tick()
        self.assertEqual(capture.call_count, 2)
        self.assertEqual(send.call_count, 1, "Unchanged screens should not generate duplicate check-ins")
        self.assertTrue(send.call_args.kwargs["proactive"])
        self.assertEqual(send.call_args.kwargs["screen_bytes"], b"fresh screen")

    def test_paused_or_busy_autopilot_never_captures(self):
        self.store.data["settings"].update(autopilot_enabled=True, autopilot_screenshots=True)
        self.app._last_activity = 0
        with patch.object(self.app, "_screen_snapshot") as capture:
            self.app._autopilot_paused = "billing error"
            self.app._background_tick()
            self.app._autopilot_paused = None
            self.app._busy = True
            self.app._background_tick()
        capture.assert_not_called()

    def test_every_original_hotkey_is_registered(self):
        self.app._apply_opacity = Mock()
        with patch("keyboard.add_hotkey", return_value="fixture") as hotkey, patch("desktop.threading.Thread"):
            self.app._on_loaded()
        registered = {call.args[0] for call in hotkey.call_args_list}
        self.assertTrue({"alt+x", "alt+a", "alt+0", "alt+5", "alt+7", "alt+d", "alt+w", "alt+s",
                         "alt+up", "alt+down", "alt+left", "alt+right", "alt+8", "alt+4", "alt+2", "alt+6", "alt+shift+h"} <= registered)
        self.assertTrue(all(call.kwargs["suppress"] for call in hotkey.call_args_list))

    def test_hidden_stream_does_not_keep_rendering_the_browser(self):
        self.app._visible = False
        self.app._emit({"type": "chunk", "session_id": "s", "message_id": "m", "text": "Hi"})
        self.app._window.evaluate_js.assert_not_called()
        self.app._hud.post.assert_called_once()

    def test_background_vision_downsamples_without_mixing_color_channels(self):
        pixels = bytes([10, 20, 30, 40, 50, 60, 70, 80, 90]) * 854
        compact, size = compact_rgb(pixels, 1281, 2)
        self.assertEqual(size, (641, 1))
        self.assertEqual(len(compact), 641 * 3)
        self.assertEqual(compact[:6], bytes([10, 20, 30, 70, 80, 90]))

    def test_original_persona_library_is_still_available(self):
        personas = self.app.dispatch("personas")["data"]
        self.assertEqual(len(personas), 13)
        self.assertTrue({"GLaDOS", "Kaguya Shinomiya", "Tom", "Anri", "TARS"} <= personas.keys())

    def test_pausing_while_a_snapshot_is_taken_prevents_upload(self):
        self.store.data["settings"].update(autopilot_enabled=True, autopilot_screenshots=True)
        self.app._last_activity = 0
        def capture():
            self.store.data["settings"]["autopilot_enabled"] = False
            return b"must stay local"
        with patch.object(self.app, "_screen_snapshot", side_effect=capture), patch.object(self.app, "_send") as send:
            self.app._background_tick()
        send.assert_not_called()

    def test_collapse_to_memory_preserves_original_conversation(self):
        self.app._hud = None
        original = self.store.session()
        original["messages"].append({"id": "u", "role": "user", "text": "Remember this project"})
        with patch("desktop.gemini_client.generate_memory_blob", return_value="We are building a thoughtful companion."):
            self.assertTrue(self.app.dispatch("collapse_memory")["ok"])
            deadline = time.monotonic() + 2
            while self.app._busy and time.monotonic() < deadline:
                time.sleep(.01)
        self.assertNotEqual(self.store.session()["id"], original["id"])
        self.assertEqual(original["messages"][0]["text"], "Remember this project")
        self.assertEqual(len(self.store.data["memories"]), 1)


if __name__ == "__main__":
    unittest.main()
