# --- ui/message_bubble.py ---
import tkinter as tk
import re
from pygments import lex
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.styles import get_style_by_name
from pygments.token import Token

class MessageBubble(tk.Frame):
    """Professional, card-style message bubble using the active theme."""
    def __init__(self, parent, message_data, app_instance, **kwargs):
        super().__init__(parent, **kwargs)
        self.app_instance = app_instance
        self.message_data = message_data
        
        author = message_data.get("role", "system")
        text = message_data.get("parts", [{}])[0].get("text", "")
        is_user = author == "user"
        is_system = author == "system"
        
        # Deriving colors from ThemeProvider
        p = self.app_instance.theme_provider.get_palette()
        is_light = self.app_instance.current_theme.get() == "light"
        
        self.bubble_bg = p["C_CARD"] if not is_user else p["C_ACCENT"]
        self.text_fg = p["C_TEXT_PRIMARY"] if not is_user else "#FFFFFF"
        self.author_fg = p["C_ACCENT"] if not is_user else ("#E0E0E0" if not is_light else "#F0F0F0")
        
        if is_system:
            self.bubble_bg = p["C_BG"]
            self.text_fg = p["C_TEXT_SECONDARY"]

        # Add a subtle border in light mode for "card" definition
        border_thickness = 1 if (is_light and not is_user) else 0
        self.config(bg=self.bubble_bg, padx=12, pady=10, 
                    highlightthickness=border_thickness, highlightbackground=p["C_BORDER"])
        
        # Apply rounding to the bubble frame
        try:
            import pywinstyles
            pywinstyles.apply_style(self, "rounded")
        except: pass
        
        # --- Header ---
        header_frame = tk.Frame(self, bg=self.bubble_bg)
        header_frame.pack(side="top", fill="x")
        
        # Author Label
        author_txt = "YOU" if is_user else author.upper()
        tk.Label(header_frame, text=author_txt, font=("Segoe UI", 9, "bold"), 
                 bg=self.bubble_bg, fg=self.author_fg).pack(side="left")

        # --- Content ---
        self.message_text = tk.Text(self, font=("Segoe UI", 11), wrap=tk.WORD, 
                                   bg=self.bubble_bg, fg=self.text_fg, 
                                   relief="flat", bd=0, highlightthickness=0, 
                                   state="disabled", height=1, width=1) # Width=1 allows expansion
        self.message_text.pack(side="top", fill="x", expand=True, pady=(5, 0))
        
        # Markdown Tags
        self.message_text.tag_configure("h1", font=("Segoe UI", 14, "bold"), spacing1=5)
        self.message_text.tag_configure("bold", font=("Segoe UI", 11, "bold"))
        
        code_bg = p["C_INPUT"] if is_light else p["C_BG"]
        self.message_text.tag_configure("code_block", font=("Consolas", 10), 
                                       background=code_bg, foreground=p["C_TEXT_PRIMARY"],
                                       spacing1=5, spacing3=5, lmargin1=10, lmargin2=10)
        
        self.configure_pygments(p)
        self.set_text(text)

    def configure_pygments(self, palette):
        """Minimalist professional code highlighting."""
        # Simple high-contrast colors for Obsidian theme
        self.message_text.tag_configure(str(Token.Keyword), foreground=palette["C_ACCENT"])
        self.message_text.tag_configure(str(Token.String), foreground="#A5D6FF")
        self.message_text.tag_configure(str(Token.Comment), foreground=palette["C_TEXT_SECONDARY"])

    def set_text(self, text):
        self.message_text.config(state="normal")
        self.message_text.delete("1.0", tk.END)
        
        # Simple Markdown parsing (optimized)
        lines = text.split("\n")
        in_code = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            
            tag = "code_block" if in_code else None
            self.message_text.insert(tk.END, line + "\n", tag)
            
        # Adjust Height
        self.message_text.bind("<Configure>", lambda e: self._adjust_height())
        self._adjust_height()
        self.message_text.config(state="disabled")

    def _adjust_height(self):
        """Dynamically adjusts the height of the text widget based on content wrapping."""
        # This calculation needs to happen after layout is settled
        self.message_text.update_idletasks()
        # count how many lines are currently visible on screen (including wrapped ones)
        # Using 1.0 to end-1c and checking displaylines
        d_lines = self.message_text.count("1.0", "end-1c", "displaylines")
        num_lines = (d_lines[0] if d_lines else 1) or 1
        self.message_text.config(height=num_lines)

    def add_copy_button(self):
        text = self.message_data.get("parts", [{}])[0].get("text", "")
        btn = tk.Button(self, text="COPY LOG", font=("Segoe UI", 8, "bold"),
                        bg=self.bubble_bg, fg=self.author_fg, relief="flat", bd=0,
                        activebackground=self.bubble_bg, activeforeground=self.text_fg,
                        command=lambda: self.app_instance.copy_to_clipboard(text))
        btn.pack(side="bottom", anchor="e", pady=(5, 0))