"""Small native transparent surfaces. No browser, screenshots, or network here."""
import logging
import math
import queue
import re
import textwrap
import threading
import time

ORB_SIZE = 48
ACTION_WIDTH, ACTION_HEIGHT = 64, 60


def bubble_lifetime(text):
    return min(45, max(10, 5 + len(text.split()) / 3.0))


def split_bubbles(text):
    text = re.sub(r"```[^\n]*\n(.*?)```", r"\1", text, flags=re.S)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", text).strip()
    return [part for paragraph in re.split(r"\n\s*\n", text)
            for part in textwrap.wrap(paragraph, 420, break_long_words=True, break_on_hyphens=False) if part]


def dock_position(x, y, bounds):
    left, top, right, bottom = bounds
    x = min(max(left + 12, x), right - ORB_SIZE - 12)
    if x - left - 12 < 72:
        x = left + 12
    elif right - ORB_SIZE - 12 - x < 72:
        x = right - ORB_SIZE - 12
    return x, min(max(top + 12, y), bottom - ORB_SIZE - 12)


def radial_positions(x, y, bounds, count=3):
    left, top, right, bottom = bounds
    center_x, center_y = x + ORB_SIZE / 2, y + ORB_SIZE / 2
    direction = math.atan2((top + bottom) / 2 - center_y, (left + right) / 2 - center_x)
    if count == 4:
        for radius in (76, 84, 96, 108, 120, 136, 152, 176, 208, 240):
            candidates = []
            for span in (75, 90, 105, 120, 135, 150, 165, 180, 210, 240):
                for start in range(0, 360, 5):
                    angles = [math.radians(start + span * i / 3) for i in range(4)]
                    positions = [(round(center_x + math.cos(a) * radius - ACTION_WIDTH/2), round(center_y + math.sin(a) * radius - ACTION_HEIGHT/2)) for a in angles]
                    if any(not (left + 8 <= px <= right - ACTION_WIDTH - 8 and top + 8 <= py <= bottom - ACTION_HEIGHT - 8) for px, py in positions):
                        continue
                    if any(abs(px+ACTION_WIDTH/2-center_x) < 60 and abs(py+ACTION_HEIGHT/2-center_y) < 58 for px, py in positions):
                        continue
                    if any(abs(px-qx) < ACTION_WIDTH+8 and abs(py-qy) < ACTION_HEIGHT+8 for i, (px, py) in enumerate(positions) for qx, qy in positions[i+1:]):
                        continue
                    axis = math.radians(start + span / 2)
                    distance = abs(math.atan2(math.sin(axis-direction), math.cos(axis-direction)))
                    candidates.append((distance + abs(span-150) / 300, positions))
            if candidates:
                return min(candidates, key=lambda item: item[0])[1]
        grid = [(px, py) for px in range(left+8, right-ACTION_WIDTH-7, ACTION_WIDTH+8) for py in range(top+8, bottom-ACTION_HEIGHT-7, ACTION_HEIGHT+8)
                if abs(px+ACTION_WIDTH/2-center_x) >= 60 or abs(py+ACTION_HEIGHT/2-center_y) >= 58]
        return sorted(grid, key=lambda point: (point[0]+ACTION_WIDTH/2-center_x)**2 + (point[1]+ACTION_HEIGHT/2-center_y)**2)[:4]
    return [(round(min(max(left + 8, x + 32 + math.cos(direction + math.radians(a)) * 116 - 36), right - 80)),
             round(min(max(top + 8, y + 32 + math.sin(direction + math.radians(a)) * 116 - 33), bottom - 78)))
            for a in (-55, 0, 55)]


def motion_enabled():
    import ctypes
    enabled = ctypes.c_int(1)
    ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
    return bool(enabled.value)


class NativeCompanion:
    def __init__(self, callback, state):
        self._callback = callback
        self._state = state
        self._queue = queue.Queue()
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._error = None
        self._visible = False
        self._suspended = False
        self._pending = []
        self._bubbles = []
        self._next_bubble_at = 0
        self._radial = []
        self._retiring = set()
        self._context_menu = self._mode_popup = None
        self._motion_jobs = {}
        self._avatar_image = None
        self._avatar_value = None
        self._attachment_image = None
        self._preview_value = None
        self._capture_button = self._clear_capture_button = self._preview_label = None
        self._panel_canvas = self._panel_frame = None
        self._history_visible = False
        self._voice_button = self._voice_row = self._voice_label = None
        self._voice_play_button = self._voice_discard_button = self._voice_stop_button = None
        self._voice_layout = None
        self._root = self._panel = self._canvas = self._input = self._chat = None
        self._send_button = self._pause_button = self._status_label = self._mode_button = None
        self._thread = threading.Thread(target=self._run, name="Cutex companion", daemon=True)
        self._thread.start()
        if not self._ready.wait(4) or self._error:
            raise RuntimeError("The floating companion could not start.")

    def post(self, kind, value=None, wait=False):
        if self._closed.is_set():
            return
        done = threading.Event() if wait else None
        self._queue.put((kind, value, done))
        if done and not done.wait(2):
            raise RuntimeError("The companion is busy. Please try the capture again.")

    def update(self, state):
        self.post("state", state)

    def notify(self, text):
        self.post("notify", text)

    def show(self, reply=False):
        self.post("show", reply)

    def hide(self):
        self.post("hide")

    def suspend(self):
        self.post("suspend", wait=True)

    def resume(self):
        self.post("resume", wait=True)

    def move(self, dx, dy):
        self.post("move", (dx, dy))

    def close(self):
        self.post("close")
        if threading.current_thread() is not self._thread:
            self._thread.join(3)

    def anchor(self):
        point = []
        self.post("callback", lambda: point.extend((self._x, self._y)), wait=True)
        return tuple(point)

    def _colors(self):
        light = self._state["settings"].get("theme") == "light"
        return {"bg": "#f5f5ef" if light else "#191e18", "text": "#253020" if light else "#f0f2e9",
                "muted": "#5d6c52" if light else "#a5b19a", "accent": "#364b22" if light else "#d9e9af",
                "on_accent": "#f3f8e8" if light else "#233016", "border": "#b8c6a8" if light else "#536444"}

    @staticmethod
    def _bounds(point=None):
        import win32api
        monitor = win32api.MonitorFromPoint(point or (0, 0), 2)
        return win32api.GetMonitorInfo(monitor)["Work"]

    @staticmethod
    def _style(window, passive):
        import win32con
        import win32gui
        window.update_idletasks()
        hwnd = win32gui.GetAncestor(window.winfo_id(), 2)
        style = (win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) | win32con.WS_EX_TOOLWINDOW) & ~win32con.WS_EX_APPWINDOW
        if passive:
            style |= 0x08000000  # WS_EX_NOACTIVATE: notifications never steal game/work focus.
        else:
            style &= ~0x08000000
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

    @staticmethod
    def _place(window, width, height, x, y):
        import win32con
        import win32gui
        window.geometry(f"{width}x{height}")
        window.update_idletasks()
        hwnd = win32gui.GetAncestor(window.winfo_id(), 2)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, int(x), int(y), width, height, win32con.SWP_NOACTIVATE)

    def _run(self):
        import tkinter as tk
        self._tk = tk
        try:
            self._root = tk.Tk()
            self._root.withdraw()
            self._root.title("Cutex companion orb")
            self._root.overrideredirect(True)
            self._root.attributes("-topmost", True)
            self._root.configure(bg="#010203")
            self._root.wm_attributes("-transparentcolor", "#010203")
            self._canvas = tk.Canvas(self._root, width=ORB_SIZE, height=ORB_SIZE, bg="#010203", highlightthickness=0, cursor="hand2")
            self._canvas.pack()
            self._x = self._state["settings"].get("dock_x", -1)
            self._y = self._state["settings"].get("dock_y", -1)
            if (self._x, self._y) == (-1, -1):
                bounds = self._bounds()
                self._x, self._y = bounds[2] - ORB_SIZE - 12, bounds[3] - 200
            self._x, self._y = dock_position(self._x, self._y, self._bounds((self._x, self._y)))
            self._place(self._root, ORB_SIZE, ORB_SIZE, self._x, self._y)
            self._drag = None
            self._click_job = None
            self._canvas.bind("<ButtonPress-1>", self._press)
            self._canvas.bind("<B1-Motion>", self._dragging)
            self._canvas.bind("<ButtonRelease-1>", self._release)
            self._canvas.bind("<Double-Button-1>", self._restore)
            self._canvas.bind("<Button-3>", self._menu)
            self._root.bind("<Escape>", lambda event: self._hide_radial())
            self._draw_orb()
            self._style(self._root, True)
            self._ready.set()
            self._last_tick = time.monotonic()
            self._root.after(80, self._pump)
            self._root.mainloop()
        except Exception as error:
            self._error = error
            logging.exception("Companion surface failed")
            self._ready.set()
        finally:
            self._closed.set()
            self._bubbles.clear()
            self._radial.clear()
            self._retiring.clear()
            self._context_menu = self._mode_popup = None
            self._motion_jobs.clear()
            self._avatar_image = self._attachment_image = None
            self._capture_button = self._clear_capture_button = self._preview_label = None
            self._panel_canvas = self._panel_frame = None
            self._voice_button = self._voice_row = self._voice_label = None
            self._voice_play_button = self._voice_discard_button = self._voice_stop_button = None
            self._root = self._panel = self._canvas = self._input = self._chat = None
            self._send_button = self._pause_button = self._status_label = self._mode_button = None
            import gc
            gc.collect()  # Tk objects must be finalized on the thread that created their interpreter.

    def _draw_orb(self):
        c, p = self._canvas, self._colors()
        c.delete("all")
        c.create_oval(3, 3, 61, 61, fill=p["bg"], outline=p["border"], width=1)
        c.create_oval(8, 8, 56, 56, outline=p["accent"], width=1)
        avatar = self._state["settings"].get("persona_avatar", "")
        if avatar != self._avatar_value:
            self._avatar_value = avatar
            try:
                self._avatar_image = self._tk.PhotoImage(data=avatar.split(",", 1)[1]).subsample(3) if avatar else None
            except self._tk.TclError:
                self._avatar_image = None
        if self._radial:
            c.create_line(23, 23, 41, 41, fill=p["accent"], width=2)
            c.create_line(41, 23, 23, 41, fill=p["accent"], width=2)
        elif self._avatar_image:
            c.create_image(32, 32, image=self._avatar_image)
        elif self._state.get("busy"):
            for x in (23, 32, 41):
                c.create_oval(x - 2, 30, x + 2, 34, fill=p["accent"], outline="")
        else:
            for angle in range(0, 360, 90):
                points = []
                for x, y in [(0, 0), (-3, -15), (8, -20), (12, -13), (0, 0)]:
                    radians = math.radians(angle + 30)
                    points.extend((32 + x * math.cos(radians) - y * math.sin(radians),
                                   32 + x * math.sin(radians) + y * math.cos(radians)))
                c.create_polygon(points, smooth=True, splinesteps=20, fill=p["accent"], outline="")
        recording = self._state.get("voice", {}).get("active")
        observing = self._state["settings"].get("autopilot_enabled") and not self._state.get("autopilot_paused")
        c.create_oval(48, 47, 59, 58, fill="#f5a49d" if recording else p["accent"] if observing else p["bg"], outline=p["border"], width=2)
        c.scale("all", 0, 0, ORB_SIZE/64, ORB_SIZE/64)

    def _invoke(self, action, data=None, on_success=None):
        def work():
            result = self._callback(action, data or {})
            if not result.get("ok"):
                self.post("error", result.get("error", "That did not work. Please try again."))
            elif on_success and result.get("data") is not None and not (isinstance(result["data"], dict) and result["data"].get("cancelled")):
                self.post("callback", on_success)
        threading.Thread(target=work, daemon=True).start()

    def _press(self, event):
        self._motion_jobs.pop(str(self._root), None)
        self._root.attributes("-alpha", 1)
        self._drag = (event.x_root, event.y_root, self._x, self._y, False)

    def _dragging(self, event):
        if not self._drag:
            return
        sx, sy, x, y, moved = self._drag
        dx, dy = event.x_root - sx, event.y_root - sy
        if abs(dx) + abs(dy) <= 5 and not moved:
            return
        self._hide_radial()
        self._drag = sx, sy, x, y, moved or abs(dx) + abs(dy) > 5
        self._x, self._y = x + dx, y + dy
        self._place(self._root, ORB_SIZE, ORB_SIZE, self._x, self._y)
        self._layout_bubbles(animate=False)
        if self._panel and self._panel.winfo_viewable():
            self._position_panel()

    def _release(self, event):
        if not self._drag:
            return
        moved = self._drag[-1]
        self._drag = None
        if moved:
            self._snap()
        else:
            self._click_job = self._root.after(220, self._toggle_radial)

    def _restore(self, event=None):
        if self._click_job:
            self._root.after_cancel(self._click_job)
            self._click_job = None
        self._hide_radial()
        self._invoke("workspace")
        return "break"

    def _hide_radial(self, animate=True):
        for win in self._radial:
            self._motion_jobs.pop(str(win), None)
            if animate and not self._suspended and motion_enabled():
                self._retire_action(win)
            else:
                win.destroy()
        self._radial.clear()
        if not animate:
            for win in list(self._retiring):
                self._motion_jobs.pop(str(win), None)
                win.destroy()
            self._retiring.clear()
        if self._canvas:
            self._draw_orb()

    def _retire_action(self, win):
        self._retiring.add(win)
        token = object()
        self._motion_jobs[str(win)] = token
        start_x, start_y = win.winfo_rootx(), win.winfo_rooty()
        alpha = float(win.attributes("-alpha"))
        win.attributes("-disabled", True)
        self._style(win, True)
        def step(frame=1):
            if not win.winfo_exists() or self._motion_jobs.get(str(win)) is not token:
                self._retiring.discard(win)
                return
            progress = (frame / 8) ** 2
            self._place(win, ACTION_WIDTH, ACTION_HEIGHT,
                start_x + (self._x - 8 - start_x) * progress,
                start_y + (self._y + 5 - start_y) * progress)
            win.attributes("-alpha", max(0, alpha * (1-progress)))
            if frame < 8:
                self._root.after(16, step, frame+1)
            else:
                self._motion_jobs.pop(str(win), None)
                self._retiring.discard(win)
                win.destroy()
        self._root.after(16, step)

    def _toggle_radial(self):
        self._click_job = None
        if self._radial:
            self._hide_radial()
            return
        self._hide_radial(animate=False)
        if self._panel:
            self._panel.withdraw()
        self._dismiss_all()
        self._radial_opened = time.monotonic()
        self._radial_had_focus = False
        positions = radial_positions(self._x, self._y, self._bounds((self._x + ORB_SIZE//2, self._y + ORB_SIZE//2)), count=4)
        actions = [("Chat", self._open_panel), ("Capture", self._capture_reply),
                   ("Overlay" if self._state.get("overlay") else "Workspace", self._restore),
                   ("Voice", lambda: self._invoke("record"))]
        p = self._colors()
        for index, ((label, command), (x, y)) in enumerate(zip(actions, positions)):
            win = self._tk.Toplevel(self._root)
            win.withdraw()
            win.title("Cutex action · " + label)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg="#010203")
            win.wm_attributes("-transparentcolor", "#010203")
            c = self._tk.Canvas(win, width=ACTION_WIDTH, height=ACTION_HEIGHT, bg="#010203", highlightthickness=0, cursor="hand2", takefocus=True)
            c.pack()
            c.create_oval(21, 2, 75, 56, fill=p["bg"], outline=p["border"], width=1, tags="disc")
            if index == 0:
                c.create_rectangle(25, 15, 47, 31, outline=p["accent"], width=2)
                c.create_line(29, 32, 29, 37, 36, 32, fill=p["accent"], width=2)
                c.create_line(30, 21, 42, 21, fill=p["accent"])
            elif index == 1:
                c.create_rectangle(23, 18, 49, 35, outline=p["accent"], width=2)
                c.create_rectangle(28, 14, 36, 18, fill=p["accent"], outline="")
                c.create_oval(31, 21, 41, 31, outline=p["accent"], width=2)
            elif index == 2:
                c.create_rectangle(24, 15, 48, 35, outline=p["accent"], width=2)
                c.create_line(24, 21, 48, 21, fill=p["accent"])
                c.create_line(34, 29, 41, 24, 41, 29, fill=p["accent"], width=1)
            else:
                c.create_oval(30, 14, 42, 31, fill=p["accent"], outline="")
                c.create_arc(25, 20, 47, 38, start=180, extent=180, style="arc", outline=p["accent"], width=2)
                c.create_line(36, 37, 36, 43, fill=p["accent"], width=2)
                c.create_line(30, 43, 42, 43, fill=p["accent"], width=2)
            for item in c.find_all()[1:]:
                c.move(item, 12, 1)
            c.create_polygon(9, 63, 87, 63, 95, 63, 95, 83, 87, 87, 9, 87, 1, 83, 1, 67,
                smooth=True, fill=p["bg"], outline=p["border"])
            c.create_text(48, 75, text=label, fill=p["text"], font=("Segoe UI", 8, "bold"))
            c.scale("all", 0, 0, ACTION_WIDTH/96, ACTION_WIDTH/96)
            def activate(event=None, callback=command):
                self._hide_radial()
                callback()
                return "break"
            c.bind("<ButtonRelease-1>", activate)
            c.bind("<Return>", activate)
            c.bind("<space>", activate)
            c.bind("<Escape>", lambda event: self._hide_radial())
            c.bind("<Tab>", lambda event, i=index: self._focus_radial((i + 1) % len(self._radial)))
            c.bind("<Shift-Tab>", lambda event, i=index: self._focus_radial((i - 1) % len(self._radial)))
            c.bind("<Enter>", lambda event: event.widget.itemconfigure("disc", outline=self._colors()["accent"], width=2))
            c.bind("<Leave>", lambda event: event.widget.itemconfigure("disc", outline=self._colors()["border"], width=1))
            c.bind("<FocusIn>", lambda event: event.widget.itemconfigure("disc", outline=self._colors()["accent"], width=2))
            c.bind("<FocusOut>", lambda event: event.widget.itemconfigure("disc", outline=self._colors()["border"], width=1))
            self._place(win, ACTION_WIDTH, ACTION_HEIGHT, self._x - 8, self._y + 5)
            self._style(win, False)
            self._radial.append(win)
            win.deiconify()
            self._slide(win, ACTION_WIDTH, ACTION_HEIGHT, x, y, origin=(self._x - 8, self._y + 5))
        self._draw_orb()
        self._focus_radial(0)

    def _focus_radial(self, index):
        if self._radial:
            win = self._radial[index]
            win.focus_force()
            win.winfo_children()[0].focus_set()
        return "break"

    def _capture_reply(self):
        self._hide_radial()
        self._invoke("capture", {"kind": "region"}, self._open_panel)

    def _snap(self):
        self._hide_radial()
        self._x, self._y = dock_position(self._x, self._y, self._bounds((self._x + ORB_SIZE//2, self._y + ORB_SIZE//2)))
        self._place(self._root, ORB_SIZE, ORB_SIZE, self._x, self._y)
        self._layout_bubbles()
        if self._panel and self._panel.winfo_viewable():
            self._position_panel()
        self._invoke("dock_position", {"x": self._x, "y": self._y})

    def _menu(self, event):
        if self._context_menu and self._context_menu.winfo_exists():
            self._context_menu.destroy()
        menu = self._tk.Menu(self._root, tearoff=False, font=("Segoe UI", 10))
        self._context_menu = menu
        def add(label, callback):
            menu.add_command(label=label, command=lambda: self._root.after_idle(callback))
        add("Talk here                 Alt A", self._toggle_panel)
        add("Open workspace          Alt X", self._restore)
        add("Open full workspace", lambda: self._invoke("open_surface", {"overlay": False}))
        add("Open compact overlay", lambda: self._invoke("open_surface", {"overlay": True}))
        companions = self._tk.Menu(menu, tearoff=False)
        for companion in self._state.get("companions", []):
            companions.add_command(label=("✓ " if companion["id"] == self._state.get("active_companion") else "") + companion["name"],
                command=lambda i=companion["id"]: self._root.after_idle(self._invoke, "select_companion", {"id": i}))
        menu.add_cascade(label="Switch companion", menu=companions)
        menu.add_separator()
        add("Capture a region", self._capture_reply)
        add("Record voice              Alt Shift V", lambda: self._invoke("record"))
        add("Pause / resume Autopilot", lambda: self._invoke("toggle_autopilot"))
        add("Dismiss bubbles", self._dismiss_all)
        add("Hide Cutex             Alt Shift H", lambda: self._invoke("hide_companion"))
        menu.add_separator()
        add("Quit Cutex", lambda: self._invoke("quit"))
        self._root.focus_force()  # A user-opened Windows context menu needs a foreground owner.
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _surface(self, title, width):
        tk, p = self._tk, self._colors()
        win = tk.Toplevel(self._root)
        win.withdraw()
        win.title(title)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#010203")
        win.wm_attributes("-transparentcolor", "#010203")
        canvas = tk.Canvas(win, width=width, bg="#010203", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        frame = tk.Frame(canvas, bg=p["bg"], padx=16, pady=13)
        canvas.create_window(1, 1, window=frame, anchor="nw", width=width - 2)
        return win, canvas, frame

    def _round_surface(self, win, canvas, frame, width, height):
        p = self._colors()
        canvas.configure(height=height)
        canvas.delete("surface")
        radius = 16
        canvas.create_polygon(1 + radius, 1, width - radius, 1, width - 1, 1,
            width - 1, radius, width - 1, height - radius, width - 1, height - 1,
            width - radius, height - 1, radius, height - 1, 1, height - 1,
            1, height - radius, 1, radius, 1, 1, smooth=True, splinesteps=20,
            fill=p["bg"], outline=p["border"], width=1, tags="surface")
        canvas.tag_lower("surface")
        win.geometry(f"{width}x{height}")
        win.update_idletasks()
        import win32gui
        hwnd = win32gui.GetAncestor(win.winfo_id(), 2)
        win32gui.SetWindowRgn(hwnd, win32gui.CreateRoundRectRgn(0, 0, width + 1, height + 1, 28, 28), True)

    def _toggle_panel(self):
        self._click_job = None
        if self._panel and self._panel.winfo_viewable():
            self._close_panel()
            return
        self._open_panel()

    def _open_panel(self):
        self._hide_radial()
        if not self._panel:
            self._build_panel()
        self._next_bubble_at = 0
        self._render_panel()
        self._position_panel()
        self._panel.deiconify()
        self._slide(self._panel, 350, self._panel.winfo_reqheight(), self._panel.winfo_rootx(), self._panel.winfo_rooty(),
                    origin=(self._aligned_x(350), self._y + 10))
        self._panel.lift()
        self._panel.focus_force()
        self._input.focus_set()
        self._layout_bubbles()

    def _close_panel(self):
        if self._panel:
            self._motion_jobs.pop(str(self._panel), None)
            self._panel.withdraw()
            self._layout_bubbles()

    def _toggle_history(self):
        self._history_visible = not self._history_visible
        if self._history_visible:
            self._chat.pack(fill="both", expand=True, after=self._status_label)
        else:
            self._chat.pack_forget()
        self._panel_frame.update_idletasks()
        self._round_surface(self._panel, self._panel_canvas, self._panel_frame, 350, self._panel_frame.winfo_reqheight() + 2)
        self._position_panel()

    def _build_panel(self):
        tk, p = self._tk, self._colors()
        win, canvas, frame = self._surface("Cutex quick conversation", 350)
        self._panel = win
        self._panel_canvas, self._panel_frame = canvas, frame
        self._preview_value = None
        header = tk.Frame(frame, bg=p["bg"])
        header.pack(fill="x", pady=(0, 9))
        name = self._state["settings"]["persona_name"]
        self._tk.Label(header, text="✳  " + (name[:15] + "…" if len(name) > 16 else name), fg=p["accent"], bg=p["bg"], font=("Segoe UI", 12, "bold")).pack(side="left")
        self._button(header, "↗", self._restore).pack(side="right")
        self._button(header, "×", self._close_panel).pack(side="right", padx=4)
        self._button(header, "History", self._toggle_history).pack(side="right", padx=4)
        self._status_label = tk.Label(frame, bg=p["bg"], fg=p["muted"], font=("Segoe UI", 9), anchor="w")
        self._status_label.pack(fill="x", pady=(0, 9))
        self._preview_label = tk.Label(frame, bg=p["bg"], borderwidth=0)
        self._chat = tk.Text(frame, height=4, width=38, wrap="word", bg=p["bg"], fg=p["text"],
            font=("Segoe UI", 10), relief="flat", borderwidth=0, highlightthickness=0, padx=0, pady=6)
        self._chat.tag_configure("author", foreground=p["accent"], font=("Segoe UI", 9, "bold"), spacing1=8)
        self._chat.tag_configure("user", foreground=p["muted"])
        if self._history_visible:
            self._chat.pack(fill="both", expand=True)
        input_row = tk.Frame(frame, bg=p["bg"])
        input_row.pack(fill="x", pady=(10, 8))
        self._input = tk.Text(input_row, height=1, width=24, wrap="word", bg=p["bg"], fg=p["text"],
            insertbackground=p["accent"], font=("Segoe UI", 10), relief="flat", highlightthickness=1,
            highlightbackground=p["border"], highlightcolor=p["accent"], padx=10, pady=8, undo=True)
        self._input.pack(side="left", fill="x", expand=True)
        self._voice_button = self._button(input_row, "● Mic", lambda: self._invoke("record"))
        self._voice_button.pack(side="right", padx=(5, 0))
        self._voice_row = tk.Frame(frame, bg=p["bg"])
        self._voice_label = tk.Label(self._voice_row, bg=p["bg"], fg=p["muted"], font=("Segoe UI", 9))
        self._voice_label.pack(side="left")
        self._voice_play_button = self._button(self._voice_row, "▶", lambda: self._invoke("play_voice"))
        self._voice_discard_button = self._button(self._voice_row, "×", lambda: self._invoke("cancel_recording" if self._state.get("voice", {}).get("active") else "clear_voice"))
        self._voice_stop_button = self._button(self._voice_row, "Mute", lambda: self._invoke("stop_audio"))
        self._voice_layout = None
        self._input.bind("<Return>", self._submit)
        self._input.bind("<Shift-Return>", lambda event: None)
        self._input.bind("<Escape>", lambda event: self._close_panel())
        self._input.bind("<Tab>", lambda event: (event.widget.tk_focusNext().focus_set(), "break")[-1])
        self._input.bind("<Shift-Tab>", lambda event: (event.widget.tk_focusPrev().focus_set(), "break")[-1])
        self._last_typing = 0
        self._input.bind("<KeyRelease>", self._typing)
        controls = tk.Frame(frame, bg=p["bg"])
        controls.pack(fill="x")
        self._capture_button = self._button(controls, "Capture", self._capture_reply)
        self._capture_button.pack(side="left")
        self._clear_capture_button = self._button(controls, "× screen", lambda: self._invoke("clear_attachment"))
        self._mode_button = self._button(controls, "Companion", self._mode_menu)
        self._mode_button.pack(side="left", padx=4)
        self._send_button = self._button(controls, "Send ↑", self._submit, True)
        self._send_button.pack(side="right")
        self._pause_button = self._button(frame, "Autopilot paused", lambda: self._invoke("toggle_autopilot"))
        self._pause_button.pack(anchor="w", pady=(8, 0))
        frame.update_idletasks()
        height = frame.winfo_reqheight() + 2
        self._round_surface(win, canvas, frame, 350, height)
        self._style(win, False)
        win.bind("<Escape>", lambda event: self._close_panel())

    def _button(self, parent, text, command, primary=False):
        p = self._colors()
        return self._tk.Button(parent, text=text, command=command, font=("Segoe UI", 9), relief="flat",
            bd=0, padx=8, pady=5, cursor="hand2", takefocus=True,
            bg=p["accent"] if primary else p["bg"], fg=p["on_accent"] if primary else p["muted"],
            activebackground=p["accent"], activeforeground=p["on_accent"])

    def _mode_menu(self):
        if self._mode_popup and self._mode_popup.winfo_exists():
            self._mode_popup.destroy()
        menu = self._tk.Menu(self._panel, tearoff=False)
        self._mode_popup = menu
        for mode in ("companion", "focus", "study", "play"):
            menu.add_command(label=mode.title(), command=lambda m=mode: self._root.after_idle(self._invoke, "settings", {"mode": m}))
        try:
            menu.tk_popup(self._mode_button.winfo_rootx(), self._mode_button.winfo_rooty())
        finally:
            menu.grab_release()

    def _render_panel(self):
        if not self._panel:
            return
        state = self._state
        session = next((s for s in state["sessions"] if s["id"] == state["active_session"]), None)
        self._chat.configure(state="normal")
        self._chat.delete("1.0", "end")
        messages = [m for m in (session or {}).get("messages", []) if not m.get("hidden")][-8:]
        if not messages:
            self._chat.insert("end", "A little company, right here.\n\nThink out loud, ask about your screen, or just say hello.", "user")
        for message in messages:
            label = "YOU" if message["role"] == "user" else message.get("persona_name", state["settings"]["persona_name"]).upper()
            self._chat.insert("end", label + "\n", "author")
            text = message.get("error") or message["text"] or "A thought is taking shape…"
            self._chat.insert("end", text[:12000] + "\n\n", "user" if message["role"] == "user" else ())
        self._chat.configure(state="disabled")
        self._chat.see("end")
        attached = "Screen attached · " if state.get("attachment") else ""
        preview = (state.get("attachment") or {}).get("data_url")
        if preview != self._preview_value:
            self._preview_value = preview
            self._preview_label.pack_forget()
            self._attachment_image = None
            if preview:
                try:
                    image = self._tk.PhotoImage(data=preview.split(",", 1)[1])
                    factor = max(1, math.ceil(image.width() / 280), math.ceil(image.height() / 64))
                    self._attachment_image = image.subsample(factor)
                    self._preview_label.configure(image=self._attachment_image)
                    self._preview_label.pack(fill="x", after=self._status_label, pady=(0, 8))
                except self._tk.TclError:
                    pass
            self._panel_frame.update_idletasks()
            self._round_surface(self._panel, self._panel_canvas, self._panel_frame, 350, self._panel_frame.winfo_reqheight() + 2)
            if self._panel.winfo_viewable():
                self._position_panel()
        self._status_label.configure(text=attached + ("Transcribing voice…" if state.get("busy_kind") == "transcribing" else "Thinking…" if state.get("busy") else "Enter to send · Shift Enter for a new line"))
        self._mode_button.configure(text=state["settings"]["mode"].title())
        self._send_button.configure(text="Stop ■" if state.get("busy") else "Send ↑")
        if state.get("attachment"):
            self._clear_capture_button.pack(side="left", after=self._capture_button)
        else:
            self._clear_capture_button.pack_forget()
        active = state["settings"].get("autopilot_enabled") and not state.get("autopilot_paused")
        self._pause_button.configure(text="◉ Autopilot on · click to pause" if active else "○ Autopilot paused · click to resume")
        self._render_voice()

    def _render_voice(self):
        if not self._panel:
            return
        voice = self._state.get("voice", {})
        active, draft, speaking = voice.get("active"), voice.get("draft_seconds"), voice.get("speaking")
        self._voice_button.configure(text="■ Stop" if active else "● Mic", fg="#f5a49d" if active else self._colors()["muted"])
        seconds = int(voice.get("seconds", 0) if active else draft or 0)
        self._voice_label.configure(text=f"● Recording {seconds//60}:{seconds%60:02d}" if active else f"Voice · {seconds//60}:{seconds%60:02d}" if draft is not None else "Reading reply…" if speaking else "")
        if voice.get("warning") and (active or draft is not None):
            self._voice_label.configure(text="Audio skipped · review clip")
        layout = (bool(active), draft is not None, bool(speaking))
        if layout != self._voice_layout:
            self._voice_layout = layout
            for button in (self._voice_play_button, self._voice_discard_button, self._voice_stop_button):
                button.pack_forget()
            if active or draft is not None or speaking:
                self._voice_row.pack(fill="x", before=self._pause_button, pady=(6, 0))
                if active or draft is not None:
                    self._voice_discard_button.pack(side="right")
                if draft is not None and not active:
                    self._voice_play_button.pack(side="right")
                if speaking:
                    self._voice_stop_button.pack(side="right")
            else:
                self._voice_row.pack_forget()
            self._panel_frame.update_idletasks()
            self._round_surface(self._panel, self._panel_canvas, self._panel_frame, 350, self._panel_frame.winfo_reqheight() + 2)
            if self._panel.winfo_viewable():
                self._position_panel()

    def _submit(self, event=None):
        if event and event.state & 1:
            return None
        if self._state.get("busy"):
            self._invoke("stop")
            return "break"
        if self._state.get("voice", {}).get("active"):
            self._invoke("record")
            return "break"
        text = self._input.get("1.0", "end-1c").strip()
        if not text and not self._state.get("attachment") and self._state.get("voice", {}).get("draft_seconds") is None:
            return "break"

        def clear():
            if self._input and self._input.get("1.0", "end-1c").strip() == text:
                self._input.delete("1.0", "end")
        self._invoke("send", {"text": text}, clear)
        return "break"

    def _typing(self, event):
        if time.monotonic() - self._last_typing > 2:
            self._last_typing = time.monotonic()
            self._invoke("activity")

    def _aligned_x(self, width):
        bounds = self._bounds((self._x + ORB_SIZE//2, self._y + ORB_SIZE//2))
        x = self._x if self._x + ORB_SIZE//2 < (bounds[0] + bounds[2]) / 2 else self._x + ORB_SIZE - width
        return min(max(bounds[0] + 8, x), bounds[2] - width - 8)

    def _position_panel(self):
        if self._panel:
            self._motion_jobs.pop(str(self._panel), None)
            bounds = self._bounds((self._x + ORB_SIZE//2, self._y + ORB_SIZE//2))
            height = self._panel.winfo_reqheight()
            y = self._y - height - 10
            if y < bounds[1] + 8:
                y = min(self._y + ORB_SIZE + 10, bounds[3] - height - 8)
            self._panel_top = y
            self._place(self._panel, 350, height, self._aligned_x(350), y)
            self._layout_bubbles()

    def _add_bubble(self, text):
        tk, p = self._tk, self._colors()
        win, canvas, frame = self._surface("Cutex companion thought", 320)
        header = tk.Frame(frame, bg=p["bg"])
        header.pack(fill="x", pady=(0, 8))
        tk.Label(header, text="✳  " + self._state["settings"]["persona_name"], bg=p["bg"], fg=p["accent"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self._button(header, "×", lambda: self._remove_bubble(win)).pack(side="right")
        body = tk.Label(frame, text=text, justify="left", anchor="w", wraplength=284, bg=p["bg"], fg=p["text"], font=("Segoe UI", 10), cursor="hand2")
        body.pack(fill="x")
        body.bind("<Button-1>", lambda event: self._open_panel())
        frame.update_idletasks()
        height = frame.winfo_reqheight() + 2
        self._round_surface(win, canvas, frame, 320, height)
        self._style(win, True)
        self._bubbles.append({"win": win, "text": text, "height": height,
                              "deadline": time.monotonic() + bubble_lifetime(text)})
        while len(self._bubbles) > 3:
            self._remove_bubble(self._bubbles[0]["win"])
        self._layout_bubbles()
        if not self._suspended and win.winfo_exists():
            win.deiconify()

    def _layout_bubbles(self, animate=True):
        bounds = self._bounds((self._x + ORB_SIZE//2, self._y + ORB_SIZE//2))
        bottom = self._y - 10
        top = self._y + ORB_SIZE + 10
        if self._panel and self._panel.winfo_viewable():
            if self._panel_top < self._y:
                bottom = self._panel_top - 10
            else:
                top = self._panel_top + self._panel.winfo_reqheight() + 10
        downward = bool(self._bubbles and bottom - self._bubbles[-1]["height"] < bounds[1] + 8)
        for bubble in reversed(list(self._bubbles)):
            y = top if downward else bottom - bubble["height"]
            if y < bounds[1] + 8 or y + bubble["height"] > bounds[3] - 8:
                self._remove_bubble(bubble["win"], layout=False)
                continue
            if animate:
                self._slide(bubble["win"], 320, bubble["height"], self._aligned_x(320), y,
                            origin=None if bubble["win"].winfo_viewable() else (self._aligned_x(320), self._y + 16))
            else:
                self._motion_jobs.pop(str(bubble["win"]), None)
                self._place(bubble["win"], 320, bubble["height"], self._aligned_x(320), y)
            bottom = y - 10
            top = y + bubble["height"] + 10

    def _slide(self, window, width, height, x, y, origin=None):
        start_x, start_y = origin or (window.winfo_rootx(), window.winfo_rooty())
        token = object()
        self._motion_jobs[str(window)] = token
        frames = 12 if motion_enabled() else 1
        if frames == 1:
            self._place(window, width, height, x, y)
            window.attributes("-alpha", 1)
            self._motion_jobs.pop(str(window), None)
            return
        self._place(window, width, height, start_x, start_y)
        if origin:
            window.attributes("-alpha", .01)

        def step(frame=1):
            if not window.winfo_exists() or self._motion_jobs.get(str(window)) is not token:
                return
            progress = 1 - (1 - frame / frames) ** 3
            self._place(window, width, height, start_x + (x - start_x) * progress, start_y + (y - start_y) * progress)
            if origin:
                window.attributes("-alpha", progress)
            if frame < frames:
                self._root.after(16, step, frame + 1)
            else:
                self._motion_jobs.pop(str(window), None)
        self._root.after(16, step)

    def _remove_bubble(self, window, layout=True):
        self._motion_jobs.pop(str(window), None)
        self._bubbles = [b for b in self._bubbles if b["win"] is not window]
        window.destroy()
        if layout:
            self._layout_bubbles()

    def _dismiss_all(self):
        for item in self._bubbles:
            self._motion_jobs.pop(str(item["win"]), None)
            item["win"].destroy()
        self._bubbles.clear()
        self._pending.clear()

    def _pump(self):
        try:
            for _ in range(80):
                try:
                    kind, value, done = self._queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    if kind == "close":
                        self._hide_radial(animate=False)
                        self._dismiss_all()
                        self._root.destroy()
                        return
                    if kind == "state":
                        changed = any(self._state["settings"].get(k) != value["settings"].get(k) for k in ("theme", "persona_name", "persona_avatar"))
                        self._state = value
                        if changed:
                            self._hide_radial()
                            self._dismiss_all()
                        if changed and self._panel:
                            draft = self._input.get("1.0", "end-1c")
                            showing = self._panel.winfo_viewable()
                            self._panel.destroy()
                            self._panel = None
                            self._build_panel()
                            self._input.insert("1.0", draft)
                            if showing:
                                self._open_panel()
                        self._draw_orb()
                        if self._panel and self._panel.winfo_viewable():
                            self._render_panel()
                    elif kind == "chunk":
                        session = next((s for s in self._state["sessions"] if s["id"] == value["session_id"]), None)
                        message = next((m for m in (session or {}).get("messages", []) if m["id"] == value["message_id"]), None)
                        if message:
                            message["text"] += value["text"]
                            if self._panel and self._panel.winfo_viewable():
                                self._render_panel()
                    elif kind == "voice":
                        self._state["voice"] = value
                        self._draw_orb()
                        self._render_voice()
                    elif kind == "show":
                        appearing = not self._visible
                        self._visible = True
                        self._root.deiconify()
                        if appearing:
                            self._slide(self._root, ORB_SIZE, ORB_SIZE, self._x, self._y, origin=(self._x, self._y + 16))
                        if value:
                            self._open_panel()
                    elif kind == "hide":
                        self._hide_radial(animate=False)
                        for menu in (self._context_menu, self._mode_popup):
                            if menu and menu.winfo_exists():
                                menu.unpost()
                        self._visible = False
                        self._root.withdraw()
                        if self._panel:
                            self._panel.withdraw()
                        self._dismiss_all()
                    elif kind in ("suspend", "resume"):
                        self._suspended = kind == "suspend"
                        if self._suspended:
                            self._hide_radial(animate=False)
                            self._panel_was_open = bool(self._panel and self._panel.winfo_viewable())
                            self._root.withdraw()
                            if self._panel:
                                self._panel.withdraw()
                            for bubble in self._bubbles:
                                bubble["win"].withdraw()
                        elif self._visible:
                            self._root.deiconify()
                            if self._panel and self._panel_was_open:
                                self._style(self._panel, True)
                                self._panel.deiconify()
                                self._style(self._panel, False)
                            for bubble in self._bubbles:
                                bubble["win"].deiconify()
                    elif kind in ("notify", "error") and self._visible:
                        if kind == "error" and self._panel and self._panel.winfo_viewable():
                            self._status_label.configure(text=value[:110])
                        self._pending.extend(split_bubbles(value))
                        if self._panel and self._panel.winfo_viewable():
                            self._next_bubble_at = 0
                    elif kind == "move":
                        if value[0]:
                            bounds = self._bounds((self._x + ORB_SIZE//2, self._y + ORB_SIZE//2))
                            self._x = bounds[0] + 12 if value[0] < 0 else bounds[2] - ORB_SIZE - 12
                        self._y += value[1]
                        self._snap()
                    elif kind == "callback":
                        value()
                finally:
                    if done:
                        done.set()
            current = time.monotonic()
            delta = current - self._last_tick
            self._last_tick = current
            px, py = self._root.winfo_pointerxy()
            hovering = False
            for bubble in list(self._bubbles):
                win = bubble["win"]
                over = win.winfo_rootx() <= px <= win.winfo_rootx() + 320 and win.winfo_rooty() <= py <= win.winfo_rooty() + bubble["height"]
                if over or self._suspended:
                    hovering |= over
                    bubble["deadline"] += delta
                elif current >= bubble["deadline"]:
                    self._remove_bubble(win)
            if self._radial and current - self._radial_opened > .4:
                import win32gui
                foreground = win32gui.GetForegroundWindow()
                owned = [win32gui.GetAncestor(win.winfo_id(), 2) for win in [self._root, *self._radial]]
                if foreground in owned:
                    self._radial_had_focus = True
                elif self._radial_had_focus:
                    self._hide_radial()
            if self._pending and not hovering and not self._suspended and not self._radial and current >= self._next_bubble_at:
                text = self._pending.pop(0)
                self._add_bubble(text)
                self._next_bubble_at = current + max(4, min(14, bubble_lifetime(text) * .7))
        except Exception:
            logging.exception("Companion event failed")
        if not self._closed.is_set() and self._root:
            self._root.after(80, self._pump)
