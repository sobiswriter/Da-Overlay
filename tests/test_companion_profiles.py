import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desktop import Desktop
from utils.storage import Store


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name), Path(self.temp.name) / "no-legacy")
        self.app = Desktop(self.store)

    def test_add_switch_restart_and_delete_preserve_other_companions_and_chat(self):
        original = self.store.data["active_companion"]
        chat = self.store.session()["id"]
        result = self.app.dispatch("save_companion", {"name": "Moon", "persona": "Be thoughtful."})
        self.assertTrue(result["ok"])
        added = result["data"]["active_companion"]
        self.assertNotEqual(original, added)
        self.assertTrue(self.app.dispatch("select_companion", {"id": original})["ok"])
        self.assertEqual(self.store.data["settings"]["persona_name"], "Anna")
        saved = Store(self.store.directory)
        self.assertEqual(len(saved.data["companions"]), 2)
        self.assertEqual(saved.session()["id"], chat)
        self.assertTrue(self.app.dispatch("delete_companion", {"id": added})["ok"])
        self.assertEqual(len(self.store.data["companions"]), 1)
        self.assertFalse(self.app.dispatch("delete_companion", {"id": original})["ok"])

    def test_invalid_avatar_and_busy_switch_leave_library_unchanged(self):
        self.assertFalse(self.app.dispatch("save_companion", {"name": "Bad", "persona": "", "avatar": "https://outside/image.png"})["ok"])
        self.app._busy = True
        self.assertFalse(self.app.dispatch("select_companion", {"id": self.store.data["active_companion"]})["ok"])
        self.assertEqual(len(self.store.data["companions"]), 1)

    def test_failed_save_rolls_back_profile_and_active_personality(self):
        previous = self.app._snapshot()
        with patch.object(self.store, "save", side_effect=OSError("disk full")):
            self.assertFalse(self.app.dispatch("save_companion", {"name": "Moon", "persona": "Be thoughtful."})["ok"])
        self.assertEqual(self.app._snapshot(), previous)

    def test_existing_custom_personality_becomes_first_saved_companion(self):
        import json
        data = self.store.data.copy()
        data.pop("companions")
        data.pop("active_companion")
        data["settings"] = {**data["settings"], "persona_name": "My custom friend", "persona": "Keep this exact personality."}
        self.store.path.write_text(json.dumps(data), encoding="utf-8")
        migrated = Desktop(Store(self.store.directory))._snapshot()
        self.assertEqual(len(migrated["companions"]), 1)
        self.assertEqual(migrated["companions"][0]["name"], "My custom friend")
        self.assertEqual(migrated["companions"][0]["persona"], "Keep this exact personality.")


if __name__ == "__main__":
    unittest.main()
