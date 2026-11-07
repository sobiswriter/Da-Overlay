"""Local conversations and memories, saved without truncating the last good file."""
import copy
import json
import os
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from utils.google_connection import DEFAULT_MODEL

DEFAULT_PERSONA = (
    "You are Anna, a warm, perceptive desktop companion. Be curious, candid, and "
    "practical. Match the user's energy. Have a sense of humor without forcing it. "
    "Be a thoughtful friend who can also help untangle difficult work."
)
DEFAULT_SETTINGS = {
    "model": DEFAULT_MODEL, "persona_name": "Anna", "persona": DEFAULT_PERSONA,
    "mode": "companion", "theme": "dark", "share_context": False,
    "share_time": True, "grounding_enabled": True, "autopilot_enabled": False,
    "autopilot_interval": 180, "on_top": False, "opacity": 1.0,
    "autopilot_screenshots": False, "autopilot_cooldown_seconds": 50,
    "capture_mode": "off", "dock_x": -1, "dock_y": -1,
    "autopilot_schedule": "", "persona_avatar": "",
    "provider": "gemini", "vertex_project": "", "vertex_location": "global", "vertex_account": "",
    "voice_replies": True,
}


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return uuid.uuid4().hex


def data_directory():
    base = os.getenv("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(os.getenv("CUTEX_DATA_DIR") or Path(base) / "OverlayCutex").resolve()


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path, data):
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def validate_history(value):
    """Read original Gemini-format exports as well as new text messages."""
    if isinstance(value, dict):
        value = value.get("messages")
    if not isinstance(value, list) or len(value) > 20000:
        raise ValueError("Choose a chat containing a list of up to 20,000 messages.")
    messages = []
    feedback = ("Capture mode:", "Date/Time Sharing", "Google Grounding",
                "Autopilot Enabled", "Autopilot Disabled", "UI Refreshed", "Chat loaded",
                "Generating memory", "Memory collapsed", "Memory saved", "Chat is empty", "Save cancelled")
    for item in value:
        if not isinstance(item, dict) or item.get("role") not in ("user", "model", "system"):
            raise ValueError("Each message needs a valid user or model role.")
        text = item.get("text")
        if text is None:
            parts = item.get("parts")
            if not isinstance(parts, list) or not parts or not all(
                isinstance(p, dict) and isinstance(p.get("text"), str) for p in parts
            ):
                raise ValueError("Each message needs nonempty text parts.")
            text = "\n".join(p["text"] for p in parts)
        if not isinstance(text, str) or len(text) > 500000:
            raise ValueError("A message is not text or exceeds the size limit.")
        if item["role"] == "system" and text.startswith(feedback):
            continue
        if not text.strip() or text == "...":
            continue
        messages.append({"id": new_id(), "role": "user" if item["role"] == "system" else item["role"],
                         "text": text, "created_at": now()})
    return messages


class Store:
    def __init__(self, data_dir=None, legacy_dir=None):
        self.directory = Path(data_dir) if data_dir else data_directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "state.json"
        self.lock = threading.RLock()
        self.save_error = False
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.data = {"version": 2, "settings": copy.deepcopy(DEFAULT_SETTINGS),
                     "sessions": [], "memories": [], "active_session": None}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if (not isinstance(loaded, dict) or loaded.get("version") != 2
                        or not isinstance(loaded.get("settings"), dict)
                        or not isinstance(loaded.get("sessions"), list)
                        or not isinstance(loaded.get("memories"), list)):
                    raise ValueError("Unexpected state format")
                self.data.update(loaded)
                self.data["settings"] = {**DEFAULT_SETTINGS, **loaded["settings"]}
            except (ValueError, OSError) as error:
                raise ValueError(f"Cannot read your saved workspace. The original is untouched: {self.path}") from error
        else:
            legacy = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
            self._migrate_settings(Path(legacy_dir) if legacy_dir else legacy)
            self.save()
        if "companions" not in self.data:
            settings = self.data["settings"]
            companion = {"id": new_id(), "name": settings["persona_name"],
                         "persona": settings["persona"], "avatar": settings["persona_avatar"]}
            self.data["companions"] = [companion]
            self.data["active_companion"] = companion["id"]
        secret = self.directory / "key.bin"
        if secret.exists():
            try:
                import win32crypt
                self.api_key = win32crypt.CryptUnprotectData(secret.read_bytes(), None, None, None, 0)[1].decode()
            except Exception as error:
                raise ValueError("Windows could not unlock your saved API key. Your workspace is intact.") from error

    def _migrate_settings(self, legacy_dir):
        path = legacy_dir / "settings.json"
        if not path.exists():
            return
        try:
            old = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            return
        if not isinstance(old, dict):
            return
        for key in DEFAULT_SETTINGS:
            if key in old and isinstance(old[key], type(DEFAULT_SETTINGS[key])):
                self.data["settings"][key] = old[key]
        self.data["settings"]["autopilot_enabled"] = False
        intervals = old.get("autopilot_intervals")
        if isinstance(intervals, list) and intervals and all(type(i) is int and i > 0 for i in intervals):
            self.data["settings"]["autopilot_schedule"] = ", ".join(map(str, intervals))
        if isinstance(old.get("api_key"), str) and old["api_key"].strip():
            self.save_key(old["api_key"].strip())

    def save_key(self, value):
        import win32crypt
        if not isinstance(value, str) or len(value) > 512:
            raise ValueError("Enter a valid API key.")
        value = value.strip()
        encrypted = win32crypt.CryptProtectData(value.encode(), "Cutex Gemini key", None, None, None, 0)
        fd, temporary = tempfile.mkstemp(prefix="key-", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(encrypted)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.directory / "key.bin")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.api_key = value

    def public_settings(self):
        settings = self.data["settings"]
        return {**settings, "key_present": bool(self.api_key),
                "connection_ready": bool(settings["vertex_project"]) if settings["provider"] == "vertex" else bool(self.api_key)}

    def save(self):
        with self.lock:
            try:
                atomic_json(self.path, self.data)
                self.save_error = False
            except OSError:
                self.save_error = True
                raise

    def new_session(self, title="New conversation", messages=None):
        with self.lock:
            previous = self.data["active_session"]
            session = {"id": new_id(), "title": title[:100], "created_at": now(),
                       "updated_at": now(), "messages": messages or []}
            self.data["sessions"].insert(0, session)
            self.data["active_session"] = session["id"]
            try:
                self.save()
            except OSError:
                self.data["sessions"].remove(session)
                self.data["active_session"] = previous
                raise
            return session

    def session(self, session_id=None):
        session_id = session_id or self.data["active_session"]
        return next((s for s in self.data["sessions"] if s["id"] == session_id), None)

    def import_chat(self, value, title="Imported conversation"):
        messages = validate_history(value)
        if not messages:
            raise ValueError("This file contains no conversation messages.")
        with self.lock:
            return self.new_session(title, messages)

    def add_memory(self, title, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 16000:
            raise ValueError("A memory needs 1–16,000 characters.")
        with self.lock:
            memory = {"id": new_id(), "title": str(title).strip()[:100] or "A little memory",
                      "text": text.strip(), "enabled": True, "created_at": now()}
            self.data["memories"].insert(0, memory)
            try:
                self.save()
            except OSError:
                self.data["memories"].remove(memory)
                raise
            return memory
