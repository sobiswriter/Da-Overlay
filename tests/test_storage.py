import json
import tempfile
import unittest
from pathlib import Path

from utils.storage import Store, validate_history


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.store = Store(self.path / "data", self.path / "legacy")

    def test_sessions_survive_restart_with_no_duplicate_messages(self):
        session = self.store.new_session()
        session["messages"].append({"id": "one", "role": "user", "text": "Hello"})
        self.store.save()
        restored = Store(self.path / "data", self.path / "legacy")
        self.assertEqual(restored.data["sessions"][0]["messages"], session["messages"])

    def test_invalid_import_does_not_replace_existing_history(self):
        self.store.new_session()
        with self.assertRaises(ValueError):
            self.store.import_chat([{"role": "user", "parts": []}])
        self.assertEqual(len(self.store.data["sessions"]), 1)

    def test_legacy_import_joins_all_text_parts_and_removes_feedback(self):
        result = validate_history([
            {"role": "system", "parts": [{"text": "Capture mode: Fullscreen"}]},
            {"role": "user", "parts": [{"text": "Hello"}, {"text": "again"}]},
            {"role": "model", "parts": [{"text": "Hi!"}]},
        ])
        self.assertEqual([m["text"] for m in result], ["Hello\nagain", "Hi!"])

    def test_atomic_save_keeps_previous_file_when_replace_fails(self):
        from unittest.mock import patch
        self.store.new_session()
        before = (self.path / "data" / "state.json").read_bytes()
        with patch("utils.storage.os.replace", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.store.save()
        self.assertEqual((self.path / "data" / "state.json").read_bytes(), before)

    def test_legacy_settings_migrate_without_exposing_key(self):
        legacy = self.path / "other-legacy"
        legacy.mkdir()
        original = {"api_key": "test-secret", "model": "my-model", "share_context": False}
        (legacy / "settings.json").write_text(json.dumps(original))
        store = Store(self.path / "migrated", legacy)
        self.assertEqual(store.api_key, "test-secret")
        self.assertEqual(store.public_settings()["model"], "my-model")
        self.assertNotIn("test-secret", json.dumps(store.data))
        self.assertNotIn("test-secret", (self.path / "migrated" / "state.json").read_text())
        self.assertEqual(json.loads((legacy / "settings.json").read_text()), original)

    def test_corrupt_state_is_preserved_and_not_overwritten(self):
        folder = self.path / "broken"
        folder.mkdir()
        (folder / "state.json").write_text("{broken")
        with self.assertRaises(ValueError):
            Store(folder, self.path / "legacy")
        self.assertEqual((folder / "state.json").read_text(), "{broken")


if __name__ == "__main__":
    unittest.main()
