# --- ui/components/modern_widgets.py ---
import tkinter as tk
from tkinter import ttk

class ModernButton(tk.Canvas):
    """A professional, canvas-based rounded button with hover effects."""
    def __init__(self, parent, text, command=None, width=120, height=40, radius=10, 
                 bg_color="#21262D", hover_color="#30363D", fg_color="#C9D1D9", font=("Segoe UI", 10)):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], 
                         highlightthickness=0, bd=0, cursor="hand2")
        self.text = text
        self.command = command
        self.radius = radius
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.fg_color = fg_color
        self.font = font
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        
        self._draw(self.bg_color)

    def _draw(self, color):
        self.delete("all")
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        r = self.radius
        
        # Draw rounded rectangle
        self.create_arc((0, 0, r*2, r*2), start=90, extent=90, fill=color, outline=color)
        self.create_arc((w-r*2, 0, w, r*2), start=0, extent=90, fill=color, outline=color)
        self.create_arc((0, h-r*2, r*2, h), start=180, extent=90, fill=color, outline=color)
        self.create_arc((w-r*2, h-r*2, w, h), start=270, extent=90, fill=color, outline=color)
        
        self.create_rectangle((r, 0, w-r, h), fill=color, outline=color)
        self.create_rectangle((0, r, w, h-r), fill=color, outline=color)
        
        # Draw text
        self.create_text(w/2, h/2, text=self.text, fill=self.fg_color, font=self.font)

    def _on_enter(self, event):
        self._draw(self.hover_color)

    def _on_leave(self, event):
        self._draw(self.bg_color)

    def _on_click(self, event):
        if self.command:
            self.command()

class ModernEntry(tk.Frame):
    """A sleek, rounded entry field with optional icon."""
    def __init__(self, parent, placeholder="", bg_color="#0D1117", fg_color="#C9D1D9", font=("Segoe UI", 11)):
        super().__init__(parent, bg=parent["bg"])
        self.placeholder = placeholder
        self.bg_color = bg_color
        
        # Background Canvas for rounded look
        self.canvas = tk.Canvas(self, height=40, bg=parent["bg"], highlightthickness=0, bd=0)
        self.canvas.pack(fill="x", expand=True)
        
        self.entry = tk.Entry(self, bg=bg_color, fg=fg_color, font=font, 
                              insertbackground=fg_color, bd=0, relief="flat")
        
        self.canvas.bind("<Configure>", self._draw)
        # Position entry inside canvas-managed space
        self.entry_window = self.canvas.create_window(0, 0, window=self.entry, anchor="w")

    def _draw(self, event=None):
        self.canvas.delete("bg")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        r = 15
        
        self.canvas.create_arc((0, 0, r*2, h), start=90, extent=180, fill=self.bg_color, outline=self.bg_color, tags="bg")
        self.canvas.create_arc((w-r*2, 0, w, h), start=270, extent=180, fill=self.bg_color, outline=self.bg_color, tags="bg")
        self.canvas.create_rectangle((r, 0, w-r, h), fill=self.bg_color, outline=self.bg_color, tags="bg")
        
        # Center the entry widget
        self.canvas.coords(self.entry_window, r, h/2)
        self.canvas.itemconfig(self.entry_window, width=w - r*2)

    def get(self):
        return self.entry.get()

    def delete(self, *args):
        self.entry.delete(*args)

    def focus_set(self):
        self.entry.focus_set()
