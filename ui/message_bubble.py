# --- ui/message_bubble.py ---
import tkinter as tk
from tkinter import ttk
import re
import webbrowser
import uuid

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
        self.text_frame = tk.Frame(self, bg=self.bubble_bg)
        self.text_frame.pack(side="top", fill="x", expand=True, pady=(5, 0))

        self.message_text = tk.Text(self.text_frame, font=("Segoe UI", 11), wrap=tk.WORD, 
                                   bg=self.bubble_bg, fg=self.text_fg, 
                                   relief="flat", bd=0, highlightthickness=0, 
                                   state="disabled", height=1, width=1) # Width=1 allows expansion
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
        self.message_text.config(yscrollcommand=self.scrollbar.set)
        
        self.set_text(text, is_final=True)

    def set_text(self, text, is_final=True):
        self.message_text.config(state="normal")
        self.message_text.delete("1.0", tk.END)
        
        if not is_final:
            self.message_text.insert("1.0", text)
            self._adjust_height()
            self.message_text.config(state="disabled")
            return
        
        lines = text.split("\n")
        in_code = False
        
        for line in lines:
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            
            if in_code:
                self.message_text.insert(tk.END, line + "\n", "code_block")
            else:
                self._parse_markdown_line(line)
        
        # Remove trailing newline if present
        if self.message_text.get("end-2c", "end-1c") == "\n":
            self.message_text.delete("end-2c", "end-1c")
            
        # Adjust Height
        self.message_text.bind("<Configure>", lambda e: self._adjust_height())
        self._adjust_height()
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

    def _adjust_height(self):
        """Dynamically adjusts the height of the text widget and enables scrolling if too tall."""
        self.message_text.update_idletasks()
        try:
            d_lines = self.message_text.count("1.0", "end-1c", "displaylines")
            num_lines = (d_lines[0] if d_lines else 1) or 1
        except:
            num_lines = int(self.message_text.index("end-1c").split('.')[0])
            
        content = self.message_text.get("1.0", "end")
        h1_count = content.count("\n# ") + (1 if content.startswith("# ") else 0)
        h2_count = content.count("\n## ") + (1 if content.startswith("## ") else 0)
        
        # Add extra height allowance for large markdown elements
        target_height = int(num_lines + (h1_count * 1.5) + (h2_count * 1.0)) + 2
            
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
        btn = tk.Button(self, text="COPY LOG", font=("Segoe UI", 8, "bold"),
                        bg=self.bubble_bg, fg=self.author_fg, relief="flat", bd=0,
                        activebackground=self.bubble_bg, activeforeground=self.text_fg,
                        command=lambda: self.app_instance.copy_to_clipboard(text))
        btn.pack(side="bottom", anchor="e", pady=(5, 0))