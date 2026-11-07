r"""Real WebView2 integration check. Offline fixture; never reads the user's workspace.

Run explicitly: .venv\Scripts\python.exe -B tests\smoke_webview.py
Screenshots go to output/playwright/ (ignored by git).
"""
import base64
import faulthandler
import json
import os
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding"
import webview
from desktop import Desktop
from utils.storage import Store
from tests.voice_fixture import FakeRecorder

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "playwright"
OUTPUT.mkdir(parents=True, exist_ok=True)
failures = []
verified = threading.Event()
faulthandler.dump_traceback_later(25, repeat=False)


def fixture_stream(*args, **kwargs):
    if kwargs.get("audio_bytes") and args[3] == "You transcribe user-provided voice messages.":
        yield {"type": "text", "text": "A synthetic voice message for the interface check."}
        return
    for text in ["Here’s a clearer way to look at it.\n\n", "**Start small.** Find the one thing that moves your idea forward.\n\n", "- A useful next step\n- A little room to experiment\n\n", "```python\nprint('A little more possible.')\n```\n\n", '<img src="https://example.com/tracker" onerror="alert(1)">']:
        time.sleep(0.03)
        yield {"type": "text", "text": text}
    yield {"type": "sources", "sources": [{"title": "Example source", "url": "https://example.com/"}]}


with tempfile.TemporaryDirectory(prefix="cutex-webview-test-") as temporary:
    store = Store(Path(temporary) / "data", Path(temporary) / "no-legacy")
    store.api_key = "offline-fixture-key"
    app = Desktop(store)
    copied = []
    app._copy = lambda data: copied.append(data["text"])
    window = webview.create_window("Cutex — Offline UI verification",
        url=str(ROOT / "ui" / "web" / "index.html"), js_api=app,
        width=1280, height=820, min_size=(420, 520), focus=False,
        frameless=True, easy_drag=False, background_color="#151815", text_select=True)
    app._window = window

    def js(code):
        return window.evaluate_js(code)

    def wait_for(expression, seconds=8):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if js(expression):
                return
            time.sleep(0.05)
        raise AssertionError("UI condition not met: " + expression)

    def screenshot(name):
        from System import Action
        js("document.getElementById('toast').hidden=true")
        time.sleep(0.25)
        tasks = []
        def start_capture():
            core = window.native.browser.webview.CoreWebView2
            tasks.append(core.CallDevToolsProtocolMethodAsync("Page.captureScreenshot", '{"format":"png","captureBeyondViewport":false}'))
        window.native.Invoke(Action(start_capture))
        if not tasks[0].Wait(5000):
            raise AssertionError("WebView2 screenshot timed out: " + name)
        result = json.loads(str(tasks[0].Result))
        (OUTPUT / name).write_bytes(base64.b64decode(result["data"]))

    def verify():
        try:
            wait_for("typeof state !== 'undefined' && state !== null")
            js("window.__testErrors=[]; addEventListener('error',e=>__testErrors.push(e.message)); addEventListener('unhandledrejection',e=>__testErrors.push(String(e.reason)))")
            assert js("document.querySelectorAll('i[data-lucide]').length") == 0, js("[...document.querySelectorAll('i[data-lucide]')].map(e=>e.dataset.lucide)")
            screenshot("cutex-workspace-dark.png")
            print("PASS: initial render", flush=True)
            js("document.querySelector('[data-mode=focus]').click()")
            wait_for("state.settings.mode === 'focus'")
            print("PASS: mode change", flush=True)
            js("document.getElementById('prompt').value='Help me make this idea a little clearer.'; document.getElementById('composer').requestSubmit()")
            wait_for("!state.busy && document.querySelectorAll('.message.model').length === 1")
            assert len(store.session()["messages"]) == 2
            assert js("document.querySelectorAll('.message.model img').length") == 0
            assert js("document.querySelectorAll('.message.model pre code').length") == 1
            assert js("document.querySelectorAll('.source-link').length") == 1
            js("document.querySelector('[data-copy-message]').click()")
            wait_for("document.getElementById('toast').textContent.includes('Copied')")
            assert copied and copied[0].startswith("Here’s a clearer way")
            screenshot("cutex-conversation-dark.png")
            js("document.getElementById('record-button').click()")
            wait_for("state.voice.active && document.getElementById('record-button').getAttribute('aria-pressed')==='true'")
            assert len(store.session()["messages"]) == 2, "Recording must not upload automatically"
            screenshot("cutex-voice-recording.png")
            js("document.getElementById('record-button').click()")
            wait_for("!state.voice.active && state.voice.draft_seconds!==null")
            screenshot("cutex-voice-review.png")
            js("document.getElementById('composer').requestSubmit()")
            wait_for("!state.busy && document.querySelectorAll('.message.model').length===2")
            assert store.session()["messages"][-2]["voice_transcribed"]
            assert store.session()["messages"][-2]["text"] == "A synthetic voice message for the interface check."
            screenshot("cutex-voice-conversation.png")
            js("document.querySelector('[data-view=memories]').click(); document.querySelector('[data-action=add-memory]').click()")
            wait_for("document.getElementById('memory-dialog').open")
            js("document.getElementById('memory-title').value='A little about this project'; document.getElementById('memory-text').value='Build a useful, thoughtful desktop companion. Keep the experience calm and the context explicit.'; document.getElementById('memory-form').requestSubmit()")
            wait_for("state.memories.length===1 && !document.getElementById('memory-dialog').open")
            assert store.data["memories"][0]["enabled"]
            screenshot("cutex-memories-dark.png")
            js("document.querySelector('[data-view=companion]').click()")
            wait_for("!document.getElementById('view-companion').hidden")
            original_companion = store.data["active_companion"]
            js("document.getElementById('new-companion').click(); document.getElementById('persona-name').value='Nora'; document.getElementById('persona-instructions').value='Be thoughtful and practical.'; document.querySelector('[data-avatar-icon=\"⭐\"]').click(); document.getElementById('persona-form').requestSubmit()")
            wait_for("state.companions.length===2 && state.settings.persona_name==='Nora'")
            assert store.data["settings"]["persona_avatar"].startswith("data:image/png;base64,")
            wait_for("document.getElementById('avatar-preview').querySelector('img')?.naturalWidth === 96")
            added_companion = store.data["active_companion"]
            js(f"document.querySelector('[data-companion=\"{original_companion}\"]').click()")
            wait_for("state.settings.persona_name==='Anna'")
            js(f"document.querySelector('[data-companion=\"{added_companion}\"]').click()")
            wait_for("state.settings.persona_name==='Nora'")
            js("document.getElementById('view-companion').scrollTop=0")
            screenshot("cutex-companion-dark.png")
            import mss.tools
            upload = base64.b64encode(mss.tools.to_png(bytes([140, 175, 125]) * (16 * 8), (16, 8))).decode()
            js("window.__beforeAvatar=draftAvatar")
            js(f"{{const transfer=new DataTransfer(); transfer.items.add(new File([Uint8Array.from(atob('{upload}'),c=>c.charCodeAt(0))],'portrait.png',{{type:'image/png'}})); const picker=document.getElementById('avatar-file'); picker.files=transfer.files; picker.dispatchEvent(new Event('change'));}}")
            wait_for("draftAvatar!==window.__beforeAvatar")
            js("document.getElementById('persona-form').requestSubmit()")
            wait_for("state.settings.persona_avatar===draftAvatar && document.getElementById('persona-form').dataset.dirty==='false'")
            js("document.querySelector('[data-avatar-icon=\"⭐\"]').click(); document.getElementById('persona-form').requestSubmit()")
            wait_for("document.getElementById('persona-form').dataset.dirty==='false'")
            js("document.querySelector('[data-action=settings]').click()")
            wait_for("document.getElementById('settings-dialog').open")
            screenshot("cutex-settings-dark.png")
            app._settings({"autopilot_interval": 137})
            js("document.getElementById('settings-dialog').close()")
            js("document.querySelector('[data-action=settings]').click()")
            assert js("document.getElementById('autopilot-interval').value") == "137"
            js("document.getElementById('provider-input').value='vertex'; document.getElementById('provider-input').dispatchEvent(new Event('change')); document.getElementById('vertex-project').value='test-project-123'; document.getElementById('vertex-account').value='test@example.com'; document.getElementById('vertex-location').value='global'; document.querySelector('[data-action=test-connection]').click()")
            wait_for("state.settings.provider==='vertex' && document.getElementById('connection-status').textContent.includes('Connected')")
            assert js("document.getElementById('key-form').hidden")
            screenshot("cutex-vertex-settings.png")
            js("document.getElementById('provider-input').value='gemini'; document.getElementById('provider-input').dispatchEvent(new Event('change'))")
            js("document.getElementById('settings-form').requestSubmit()")
            wait_for("!document.getElementById('settings-dialog').open")
            assert store.data["settings"]["autopilot_interval"] == 137
            js("document.querySelector('[data-action=palette]').click()")
            wait_for("document.getElementById('palette-dialog').open")
            assert js("document.querySelectorAll('.command-item').length") >= 10
            js("document.getElementById('palette-dialog').close(); document.querySelector('[data-view=chat]').click()")
            app._toggle_overlay()
            wait_for("innerWidth < 600 && state.overlay")
            screenshot("cutex-overlay-dark.png")
            assert js("document.documentElement.scrollWidth <= innerWidth"), "Compact view overflows horizontally"
            assert js("document.getElementById('send-button').getBoundingClientRect().right <= innerWidth"), "Send button outside compact view"
            app._toggle_overlay()
            wait_for("innerWidth > 1000 && !state.overlay")
            app._settings({"theme": "light"})
            wait_for("document.documentElement.dataset.theme==='light'")
            app._new_session()
            screenshot("cutex-workspace-light.png")
            app._collapse_to_dock()
            assert not app._visible and app._hud
            native_probe = []
            app._hud.post("callback", lambda: native_probe.append(bool(app._hud._root.winfo_viewable())), wait=True)
            assert native_probe == [True], "Native orb did not appear beside WebView2"
            assert app._workspace_frozen, "The hidden workspace lifecycle did not pause"
            app._quick_reply()
            native_probe.clear()
            app._hud.post("callback", lambda: native_probe.append(bool(app._hud._panel.winfo_viewable())), wait=True)
            assert native_probe == [True], "Quick reply did not open"
            app._restore_workspace()
            wait_for("state.docked === false")
            wait_for("innerWidth > 1000 && innerHeight > 600 && document.visibilityState==='visible'")
            app._collapse_to_dock()
            app._open_surface({"overlay": True})
            wait_for("state.overlay && innerWidth < 600 && innerWidth > 400 && document.visibilityState==='visible'")
            app._collapse_to_dock()
            app._open_surface({"overlay": False})
            wait_for("!state.overlay && innerWidth > 1000 && document.visibilityState==='visible'")
            assert js("window.__testErrors.length") == 0, js("window.__testErrors")
            app._collapse_to_dock()
            hud = app._hud
            def menu_quit():
                hud._menu(SimpleNamespace(x_root=hud._x, y_root=hud._y))
                hud._context_menu.invoke("Quit Cutex")
            with patch("tkinter.Menu.tk_popup"):
                hud.post("callback", menu_quit, wait=True)
            assert app._closed.wait(5), "Menu Quit did not save and exit while docked"
            assert hud._closed.wait(3), "Native companion remained after Quit"
            print("PASS: real WebView2 startup, icons, mode, streaming, sanitized Markdown, sources, copy, memory save, navigation, settings, command palette, compact layout and themes.", flush=True)
            print("Screenshots:", OUTPUT, flush=True)
        except Exception as error:
            import traceback
            failures.append(str(error))
            traceback.print_exc()
        finally:
            faulthandler.cancel_dump_traceback_later()
            if not app._closed.is_set():
                window.destroy()
            verified.set()

    window.events.loaded += app._on_loaded
    window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
    window.events.closing += app._on_closing
    with patch("desktop.gemini_client.stream_events", side_effect=fixture_stream), patch("keyboard.add_hotkey", return_value="offline-fixture"), patch("keyboard.remove_hotkey"), patch("utils.voice.Recorder", FakeRecorder), patch.object(app, "_speak"), patch.object(app, "_test_connection", return_value={"message": "Connected · offline fixture"}):
        webview.start(gui="edgechromium", storage_path=str(Path(temporary) / "webview"))

if not verified.wait(3) or failures:
    raise SystemExit(1)
