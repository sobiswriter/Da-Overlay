# --- ui/placeholder_entry.py ---
import tkinter as tk

class PlaceholderEntry(tk.Entry):
    def __init__(self, master=None, placeholder="...", color='grey', **kwargs):
        super().__init__(master, **kwargs)

        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg_color = self['fg']

        self.bind("<FocusIn>", self.foc_in)
        self.bind("<FocusOut>", self.foc_out)

        self.put_placeholder()

    def put_placeholder(self):
        self.insert(0, self.placeholder)
        self['fg'] = self.placeholder_color

    def foc_in(self, *args):
        if self['fg'] == self.placeholder_color:
            self.delete('0', 'end')
            self['fg'] = self.default_fg_color

    def foc_out(self, *args):
        if not self.get():
            self.put_placeholder()

    def update_colors(self, bg, fg, insert_bg, placeholder_color):
        """Updates the widget's colors to match the current theme."""
        # Check if the placeholder is currently being displayed by checking its color
        is_placeholder_active = self['fg'] == self.placeholder_color

        self.default_fg_color = fg
        self.placeholder_color = placeholder_color
        self.config(bg=bg, insertbackground=insert_bg)

        # Set the foreground color based on whether the placeholder was active
        self.config(fg=self.placeholder_color if is_placeholder_active else self.default_fg_color)