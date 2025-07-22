# --- ui/region_selector.py ---
import tkinter as tk

class RegionSelector:
    def __init__(self, parent, on_selection_callback):
        self.parent = parent; self.on_selection_callback = on_selection_callback
        self.selector_window = tk.Toplevel(parent)
        self.selector_window.attributes('-fullscreen', True); self.selector_window.attributes('-alpha', 0.3)
        self.selector_window.overrideredirect(True); self.selector_window.wait_visibility(self.selector_window)
        self.canvas = tk.Canvas(self.selector_window, cursor="crosshair", bg="black")
        self.canvas.pack(fill="both", expand=True)
        self.start_x = None; self.start_y = None; self.rect = None
        self.canvas.bind("<ButtonPress-1>", self.on_button_press); self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x); self.start_y = self.canvas.canvasy(event.y)
        if not self.rect: self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='#3B82F6', width=2, dash=(4, 4))
    def on_mouse_drag(self, event):
        cur_x, cur_y = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
    def on_button_release(self, event):
        end_x, end_y = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y); x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        self.selector_window.destroy()
        if x2 - x1 > 10 and y2 - y1 > 10: self.on_selection_callback({'left': int(x1), 'top': int(y1), 'width': int(x2 - x1), 'height': int(y2 - y1)})
        else: self.on_selection_callback(None)