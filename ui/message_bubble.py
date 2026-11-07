# --- ui/message_bubble.py ---
import tkinter as tk
from tkinter import ttk
import re
import webbrowser
import uuid

class MessageBubble(tk.Frame):
    """Professional, WhatsApp-style message bubble using the active theme."""
    def __init__(self, parent, message_data, app_instance, **kwargs):
        # The true outer frame is transparent, acting as a full-width container row
        super().__init__(parent, bg=app_instance.BG_COLOR, **kwargs)
        self.app_instance = app_instance
        self.message_data = message_data
        
        author = message_data.get("role", "system")
        text = message_data.get("parts", [{}])[0].get("text", "")
        self.is_user = author == "user"
        self.is_system = author == "system"
        
        # Deriving colors from ThemeProvider
        p = self.app_instance.theme_provider.get_palette()
        is_light = self.app_instance.current_theme.get() == "light"
        
        self.bubble_bg = p["C_CARD"] if not self.is_user else p["C_ACCENT"]
        self.text_fg = p["C_TEXT_PRIMARY"] if not self.is_user else "#FFFFFF"
        self.author_fg = p["C_ACCENT"] if not self.is_user else ("#E0E0E0" if not is_light else "#F0F0F0")
        
        if self.is_system:
            self.bubble_bg = p["C_BG"]
            self.text_fg = p["C_TEXT_SECONDARY"]

        # Add a subtle border in light mode for "card" definition
        border_thickness = 1 if (is_light and not self.is_user) else 0
        
        # --- INNER BUBBLE FRAME ---
        # This frame holds the actual visible bubble content and hugs it tightly
        self.bubble_frame = tk.Frame(self, bg=self.bubble_bg, padx=12, pady=10, 
                                     highlightthickness=border_thickness, highlightbackground=p["C_BORDER"])
        
        # Align WhatsApp style: User on Right, AI on Left. System messages in center or left.
        if self.is_user:
            self.bubble_frame.pack(side="right", anchor="e", padx=(60, 0))
        elif self.is_system:
            self.bubble_frame.pack(side="top", anchor="center", padx=30)
        else:
            self.bubble_frame.pack(side="left", anchor="w", padx=(0, 60))
        
        # Apply rounding to the inner bubble frame
        try:
            import pywinstyles
            pywinstyles.apply_style(self.bubble_frame, "rounded")
        except: pass
        
        # --- Header ---
        header_frame = tk.Frame(self.bubble_frame, bg=self.bubble_bg)
        header_frame.pack(side="top", fill="x")
        
        # Author Label
        author_txt = "YOU" if self.is_user else author.upper()
        author_font = ("Segoe UI", 8, "bold") if self.is_user else ("Segoe UI", 9, "bold")
        author_lbl = tk.Label(header_frame, text=author_txt, font=author_font, 
                 bg=self.bubble_bg, fg=self.author_fg)
        author_lbl.pack(side="right" if self.is_user else "left")

        # --- Content ---
        self.text_frame = tk.Frame(self.bubble_frame, bg=self.bubble_bg)
        self.text_frame.pack(side="top", fill="x", expand=True, pady=(3, 0))

        # Start with small width, it will grow dynamically in _adjust_size
        start_width = 2 if not text else min(68, len(text))
        self.message_text = tk.Text(self.text_frame, font=("Segoe UI", 11), wrap=tk.WORD, 
                                   bg=self.bubble_bg, fg=self.text_fg, 
                                   relief="flat", bd=0, highlightthickness=0, 
                                   state="disabled", height=1, width=start_width)
        self.message_text.pack(side="left", fill="both", expand=True)
        
        # Markdown Tags
        self.message_text.tag_configure("h1", font=("Segoe UI", 16, "bold"), spacing1=10, spacing3=5)
        self.message_text.tag_configure("h2", font=("Segoe UI", 14, "bold"), spacing1=8, spacing3=4)
        self.message_text.tag_configure("h3", font=("Segoe UI", 12, "bold"), spacing1=6, spacing3=3)
        self.message_text.tag_configure("bold", font=("Segoe UI", 11, "bold"))
        self.message_text.tag_configure("italic", font=("Segoe UI", 11, "italic"))
        self.message_text.tag_configure("bold_italic", font=("Segoe UI", 11, "bold italic"))
        
        self.message_text.tag_configure("blockquote", font=("Segoe UI", 11, "italic"), lmargin1=15, lmargin2=15, foreground=p["C_TEXT_SECONDARY"])
        self.message_text.tag_configure("list_item", lmargin1=15, lmargin2=30, spacing1=2, spacing3=2)
        
        code_bg = p["C_INPUT"] if is_light else p["C_BG"]
        self.message_text.tag_configure("code_block", font=("Consolas", 10), 
                                       background=code_bg, foreground=p["C_TEXT_PRIMARY"],
                                       spacing1=2, spacing3=2, lmargin1=10, lmargin2=10)
        self.message_text.tag_configure("inline_code", font=("Consolas", 10), background=code_bg)
        
        self.scrollbar = ttk.Scrollbar(self.text_frame, command=self.message_text.yview)
        # Scrollbar is packed dynamically in _adjust_size
        self.message_text.config(yscrollcommand=self.scrollbar.set)
        
        self.set_text(text, is_final=True)

    def set_text(self, text, is_final=True):
        self.message_text.config(state="normal")
        self.message_text.delete("1.0", tk.END)
        
        if not is_final:
            self.message_text.insert("1.0", text)
            self._adjust_size()
            self.message_text.config(state="disabled")
            return
        
        lines = text.split("\n")
        in_code = False
        
        for line in lines:
            if line.strip().startswith("```"):
                in_code = not in_code
                self.message_text.insert(tk.END, line + "\n", "code_block" if not in_code else ())
                continue
            
            if in_code:
                self.message_text.insert(tk.END, line + "\n", "code_block")
            else:
                self._parse_markdown_line(line)
        
        # Remove trailing newline if present
        if self.message_text.get("end-2c", "end-1c") == "\n":
            self.message_text.delete("end-2c", "end-1c")
            
        # Adjust Size
        self.message_text.bind("<Configure>", lambda e: self._adjust_size())
        self._adjust_size()
        self.message_text.config(state="disabled")

    def _parse_markdown_line(self, line):
        if line.startswith("# "):
            self.message_text.insert(tk.END, line[2:] + "\n", "h1")
        elif line.startswith("## "):
            self.message_text.insert(tk.END, line[3:] + "\n", "h2")
        elif line.startswith("### "):
            self.message_text.insert(tk.END, line[4:] + "\n", "h3")
        elif line.startswith("> "):
            self.message_text.insert(tk.END, line[2:] + "\n", "blockquote")
        elif line.strip().startswith("- ") or line.strip().startswith("* "):
            item_text = line.lstrip()[2:]
            self.message_text.insert(tk.END, "• ", "list_item")
            self._insert_inline_markdown(item_text, "list_item")
            self.message_text.insert(tk.END, "\n")
        elif re.match(r'^\s*\d+\.\s', line):
            match = re.match(r'^(\s*\d+\.\s)(.*)', line)
            prefix = match.group(1).lstrip()
            item_text = match.group(2)
            self.message_text.insert(tk.END, prefix, "list_item")
            self._insert_inline_markdown(item_text, "list_item")
            self.message_text.insert(tk.END, "\n")
        else:
            self._insert_inline_markdown(line)
            self.message_text.insert(tk.END, "\n")

    def _insert_inline_markdown(self, text, base_tag=None):
        pattern = r'(\*\*\*(.*?)\*\*\*|\*\*(.*?)\*\*|\*([^\*]+?)\*|`([^`]+?)`|\[(.*?)\]\((.*?)\))'
        last_idx = 0
        
        for match in re.finditer(pattern, text):
            pre_text = text[last_idx:match.start()]
            if pre_text:
                self.message_text.insert(tk.END, pre_text, base_tag if base_tag else ())
                
            full_match = match.group(0)
            target_tags = []
            if base_tag:
                target_tags.append(base_tag)
                
            if full_match.startswith('***'):
                target_tags.append("bold_italic")
                self.message_text.insert(tk.END, match.group(2), tuple(target_tags))
            elif full_match.startswith('**'):
                target_tags.append("bold")
                self.message_text.insert(tk.END, match.group(3), tuple(target_tags))
            elif full_match.startswith('*'):
                target_tags.append("italic")
                self.message_text.insert(tk.END, match.group(4), tuple(target_tags))
            elif full_match.startswith('`'):
                target_tags.append("inline_code")
                self.message_text.insert(tk.END, match.group(5), tuple(target_tags))
            elif full_match.startswith('['):
                link_text = match.group(6)
                url = match.group(7)
                url_tag = f"link_{uuid.uuid4().hex}"
                
                self.message_text.tag_configure(url_tag, foreground=self.app_instance.theme_provider.get_palette()["C_ACCENT"], underline=True)
                self.message_text.tag_bind(url_tag, "<Enter>", lambda e, t=url_tag: self.message_text.config(cursor="hand2"))
                self.message_text.tag_bind(url_tag, "<Leave>", lambda e, t=url_tag: self.message_text.config(cursor=""))
                self.message_text.tag_bind(url_tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
                
                target_tags.append(url_tag)
                self.message_text.insert(tk.END, link_text, tuple(target_tags))
                
            last_idx = match.end()
            
        post_text = text[last_idx:]
        if post_text:
            self.message_text.insert(tk.END, post_text, base_tag if base_tag else ())

    def _adjust_size(self):
        """Dynamically adjusts both width and height of the text widget to wrap tightly."""
        self.message_text.update_idletasks()
        content = self.message_text.get("1.0", "end-1c")
        
        # --- Width Calculation ---
        lines = content.split("\n")
        max_line_len = 1
        for l in lines:
            if len(l) > max_line_len:
                max_line_len = len(l)
                
        # Cap the width at roughly 68 characters to simulate WhatsApp wrapping
        target_width = min(68, max_line_len + 1)
        if target_width < 4:
            target_width = 4
            
        self.message_text.config(width=target_width)
        
        # --- Height Calculation ---
        try:
            d_lines = self.message_text.count("1.0", "end-1c", "displaylines")
            num_lines = (d_lines[0] if d_lines else 1) or 1
        except:
            # Fallback if displaylines fails
            num_lines = 0
            for l in lines:
                wraps = (len(l) // target_width) + 1 if target_width > 0 else 1
                num_lines += wraps
            
        h1_count = content.count("\n# ") + (1 if content.startswith("# ") else 0)
        h2_count = content.count("\n## ") + (1 if content.startswith("## ") else 0)
        
        # Add extra height allowance for large markdown elements
        target_height = int(num_lines + (h1_count * 1.5) + (h2_count * 1.0))
        if target_height < 1:
            target_height = 1
            
        max_lines = 25
        if target_height > max_lines:
            self.message_text.config(height=max_lines)
            if not self.scrollbar.winfo_ismapped():
                self.message_text.pack_forget()
                self.scrollbar.pack(side="right", fill="y")
                self.message_text.pack(side="left", fill="both", expand=True)
        else:
            self.message_text.config(height=target_height)
            if self.scrollbar.winfo_ismapped():
                self.scrollbar.pack_forget()

    def add_copy_button(self):
        text = self.message_data.get("parts", [{}])[0].get("text", "")
        btn = tk.Button(self.bubble_frame, text="COPY LOG", font=("Segoe UI", 7, "bold"),
                        bg=self.bubble_bg, fg=self.author_fg, relief="flat", bd=0,
                        activebackground=self.bubble_bg, activeforeground=self.text_fg,
                        command=lambda: self.app_instance.copy_to_clipboard(text))
        # Align button correctly based on user side
        btn.pack(side="bottom", anchor="e" if not self.is_user else "w", pady=(2, 0))