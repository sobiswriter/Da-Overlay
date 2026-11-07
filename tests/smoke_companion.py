"""Native presence verification with a synthetic backdrop and no network calls."""
import ctypes
import base64
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ctypes.windll.shcore.SetProcessDpiAwareness(2)
from desktop import Desktop
from utils.storage import Store
from tests.voice_fixture import FakeRecorder
from ui.companion_dock import ORB_SIZE, ACTION_WIDTH, ACTION_HEIGHT, motion_enabled
import win32gui

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "playwright"
OUTPUT.mkdir(parents=True, exist_ok=True)


def fixture(*args, **kwargs):
    if kwargs.get("audio_bytes") and args[3] == "You transcribe user-provided voice messages.":
        yield {"type": "text", "text": "Can we talk with a voice message?"}
        return
    for text in ["I’m here with you. ", "We can think this through without opening the big workspace."]:
        time.sleep(.12)
        yield {"type": "text", "text": text}


with tempfile.TemporaryDirectory(prefix="cutex-native-check-") as folder:
    app = Desktop(Store(Path(folder), Path(folder) / "no-legacy"))
    app._store.api_key = "offline-native-fixture"
    app._window = SimpleNamespace(hide=Mock(), show=Mock(), destroy=Mock(), evaluate_js=Mock())
    app._set_on_top = Mock()
    app._apply_opacity = Mock()
    hud = app._ensure_hud()

    def probe(callback):
        result = []
        hud.post("callback", lambda: result.append(callback()), wait=True)
        return result[0] if result else None

    def wait_for(callback, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = callback()
            if value:
                return value
            time.sleep(.05)
        raise AssertionError("Native companion condition did not complete")

    try:
        def backdrop():
            tk = hud._tk
            bounds = hud._bounds()
            x, y, width, height = bounds[2] - 450, bounds[1], 450, bounds[3] - bounds[1]
            win = tk.Toplevel(hud._root)
            win.title("Cutex offline presence test backdrop")
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg="#101923")
            hud._place(win, width, height, x, y)
            win.focus_force()
            return (x, y, width, height)

        x, y, width, height = probe(backdrop)
        foreground = win32gui.GetForegroundWindow()
        app._collapse_to_dock()
        wait_for(lambda: probe(lambda: hud._root.winfo_viewable()))
        assert win32gui.GetForegroundWindow() == foreground, "Showing the orb stole focus"
        hud.notify("A little company, without getting in your way. Click the orb to talk here. Double-click to open your workspace.")
        wait_for(lambda: probe(lambda: len(hud._bubbles) == 1))
        time.sleep(.25)
        assert win32gui.GetForegroundWindow() == foreground, "A passive message stole focus"
        assert probe(lambda: bool(win32gui.GetWindowLong(win32gui.GetAncestor(hud._bubbles[0]["win"].winfo_id(), 2), -20) & 0x08000000))
        import mss
        import mss.tools

        def screenshot(name, region=None):
            with mss.mss() as capture:
                image = capture.grab(region or {"left": x, "top": y, "width": width, "height": height})
                mss.tools.to_png(image.rgb, image.size, output=str(OUTPUT / name))

        screenshot("cutex-companion-orb.png")
        probe(hud._toggle_radial)
        wait_for(lambda: probe(lambda: len(hud._radial) == 4))
        time.sleep(.3)
        screenshot("cutex-radial-menu.png")
        assert probe(lambda: hud._root.winfo_width()) == 48
        assert probe(lambda: all(win.winfo_width() == 64 and win.winfo_height() == 60 for win in hud._radial))
        menu_top = probe(lambda: min([hud._y] + [win.winfo_rooty() for win in hud._radial])) - 16
        menu_region = {"left": x, "top": menu_top, "width": width, "height": min(y+height, probe(lambda: max([hud._y+ORB_SIZE] + [win.winfo_rooty()+ACTION_HEIGHT for win in hud._radial])) + 16) - menu_top}
        screenshot("cutex-radial-closeup.png", menu_region)
        probe(lambda: next(win for win in hud._root.winfo_children() if isinstance(win, hud._tk.Toplevel) and win.title() == "Cutex offline presence test backdrop").configure(bg="#f5f1f8"))
        screenshot("cutex-radial-on-light.png", menu_region)
        probe(lambda: next(win for win in hud._root.winfo_children() if isinstance(win, hud._tk.Toplevel) and win.title() == "Cutex offline presence test backdrop").configure(bg="#101923"))
        closing = probe(lambda: (hud._hide_radial(), len(hud._retiring))[1])
        assert closing == (4 if motion_enabled() else 0), "Radial close skipped its animation"
        wait_for(lambda: probe(lambda: len(hud._retiring) == 0))
        probe(hud._toggle_radial)
        probe(hud._hide_radial)
        probe(hud._toggle_radial)
        assert probe(lambda: len(hud._radial) == 4 and not hud._retiring), "Quick reopen left ghost actions"
        probe(lambda: hud._radial[0].winfo_children()[0].event_generate("<ButtonRelease-1>", x=36, y=26))
        wait_for(lambda: probe(lambda: bool(hud._panel and hud._panel.winfo_viewable())))
        with patch("desktop.gemini_client.stream_events", side_effect=fixture):
            probe(lambda: hud._input.insert("1.0", "Can we talk right here?"))
            probe(lambda: hud._submit())
            wait_for(lambda: len(app._store.session()["messages"]) == 2 and not app._busy)
            wait_for(lambda: probe(lambda: "without opening" in hud._chat.get("1.0", "end")))
        assert app._store.session()["messages"][0]["text"] == "Can we talk right here?"
        assert not app._visible
        app._window.show.assert_not_called()
        probe(hud._close_panel)
        probe(hud._toggle_radial)
        with patch("utils.voice.Recorder", FakeRecorder), patch.object(app, "_speak") as speak:
            probe(lambda: hud._radial[3].winfo_children()[0].event_generate("<ButtonRelease-1>", x=48, y=28))
            wait_for(lambda: app._recorder and app._recorder.active)
            wait_for(lambda: probe(lambda: hud._state.get("voice", {}).get("active")))
            probe(lambda: hud._voice_button.invoke())
            wait_for(lambda: app._voice_attachment is not None)
            wait_for(lambda: probe(lambda: hud._state.get("voice", {}).get("draft_seconds") is not None))
            with patch("desktop.gemini_client.stream_events", side_effect=fixture):
                probe(hud._submit)
                wait_for(lambda: not app._busy and len(app._store.session()["messages"]) == 4)
            assert app._store.session()["messages"][-2]["text"] == "Can we talk with a voice message?"
            speak.assert_called_once()
        probe(lambda: hud._panel.withdraw())
        probe(lambda: hud._add_bubble("Your work keeps focus. These small thoughts rise above the orb, then make room again."))
        probe(lambda: hud._add_bubble("Click a thought to answer right here. The rest of your desktop stays yours."))
        time.sleep(.2)
        screenshot("cutex-floating-thoughts.png")
        app._quick_reply()
        time.sleep(.35)
        screenshot("cutex-quick-reply.png")
        png = mss.tools.to_png(bytes([217, 233, 175]) * (96 * 96), (96, 96))
        avatar = "data:image/png;base64," + base64.b64encode(png).decode()
        assert app.dispatch("save_companion", {"name": "Nora", "persona": "Be thoughtful.", "avatar": avatar})["ok"]
        wait_for(lambda: probe(lambda: hud._avatar_image is not None and hud._state["settings"]["persona_name"] == "Nora"))
        probe(lambda: hud._panel.withdraw())
        probe(hud._toggle_radial)
        preview = {"kind": "region", "width": 96, "height": 96, "data_url": avatar}
        def capture_fixture(data):
            app._attachment = {"bytes": png, "preview": preview}
            app._state_changed()
            return preview
        with patch.object(app, "_capture", side_effect=capture_fixture):
            probe(lambda: hud._radial[1].winfo_children()[0].event_generate("<ButtonRelease-1>", x=36, y=26))
            wait_for(lambda: probe(lambda: bool(hud._panel.winfo_viewable() and hud._attachment_image)))
        app._window.show.assert_not_called()
        probe(lambda: hud._clear_capture_button.invoke())
        wait_for(lambda: app._attachment is None)
        probe(lambda: hud._panel.withdraw())
        probe(lambda: hud._add_bubble("I follow the orb, wherever you place it."))
        old_x = probe(lambda: hud._bubbles[-1]["win"].winfo_rootx())
        px, py = probe(lambda: (hud._x, hud._y))
        probe(lambda: hud._press(SimpleNamespace(x_root=px+32, y_root=py+32)))
        probe(lambda: hud._dragging(SimpleNamespace(x_root=px-120, y_root=py-48)))
        assert probe(lambda: hud._bubbles[-1]["win"].winfo_rootx()) != old_x
        probe(lambda: hud._release(SimpleNamespace()))
        probe(hud._close_panel)
        with patch.object(app, "_capture", return_value=None):
            probe(hud._capture_reply)
            time.sleep(.15)
            assert not probe(lambda: hud._panel.winfo_viewable()), "Cancelled capture opened chat"
        hud.move(0, -30)
        time.sleep(.2)
        assert app._store.data["settings"]["dock_y"] >= 0
        hud.move(0, -100000)
        time.sleep(.15)
        probe(lambda: hud._panel.withdraw())
        probe(lambda: hud._add_bubble("Even near the top edge, thoughts should remain visible."))
        assert probe(lambda: len(hud._bubbles)) >= 1
        probe(hud._toggle_radial)
        probe(lambda: hud._radial[2].winfo_children()[0].event_generate("<ButtonRelease-1>", x=36, y=26))
        wait_for(lambda: app._visible)
        app._window.show.assert_called()
        app._collapse_to_dock()
        def menu_action(label):
            def invoke():
                hud._menu(SimpleNamespace(x_root=hud._x, y_root=hud._y))
                assert hud._context_menu.winfo_exists(), "Posted menu lost its callbacks"
                hud._context_menu.invoke(label)
            with patch("tkinter.Menu.tk_popup"):
                probe(invoke)
        menu_action("Talk here                 Alt A")
        wait_for(lambda: probe(lambda: hud._panel.winfo_viewable()))
        with patch("tkinter.Menu.tk_popup"):
            probe(hud._mode_menu)
            probe(lambda: hud._mode_popup.invoke("Study"))
        wait_for(lambda: app._store.data["settings"]["mode"] == "study")
        menu_action("Hide Cutex             Alt Shift H")
        wait_for(lambda: app._presence_hidden and probe(lambda: not hud._root.winfo_viewable() and not hud._panel.winfo_viewable()))
        app._window.show.reset_mock()
        app._toggle_visible()
        wait_for(lambda: probe(lambda: hud._root.winfo_viewable()))
        app._window.show.assert_not_called()
        menu_action("Quit Cutex")
        assert app._closed.wait(3), "Quit did not enter the saved-exit path"
        assert hud._closed.wait(3), "Quit did not close the companion"
        print("PASS: compact orb/actions, close animation and quick reopen, live Tk context/mode menu callbacks, hide/shortcut restore, Quit save/cleanup, plus voice/capture/chat regressions.")
        print("Native screenshots:", OUTPUT)
    finally:
        app._finish_close()
        assert hud._closed.wait(3), "Native UI thread did not shut down"
