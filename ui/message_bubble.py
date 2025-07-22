# --- ui/message_bubble.py ---
import tkinter as tk
import re

# NEW: Imports for syntax highlighting
from pygments import lex
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.styles import get_style_by_name
from pygments.token import Token

class MessageBubble(tk.Frame):
    def __init__(self, parent, message_data, app_instance, **kwargs):
        super().__init__(parent, **kwargs)
        self.app_instance = app_instance
        self.message_data = message_data
        
        
        author = message_data.get("role", "user")
        text = message_data["parts"][0].get("text", "")
        is_user = author == "user"
        is_system = author == "system"
        
        # --- Styling ---
        if is_user:
            bubble_bg = "#DBEAFE"
        elif is_system:
            bubble_bg = parent.cget("bg")
        else: # AI/Model
            bubble_bg = "#F3F4F6"
        
        # This is now the bubble's colored background
        self.config(bg=bubble_bg)

        # --- Top Frame for Author and Pin Button ---
        top_frame = tk.Frame(self, bg=bubble_bg)
        top_frame.pack(side="top", fill="x", padx=10, pady=(5,0))

        author_font = ("Segoe UI", 9, 'italic') if is_system else ("Segoe UI", 9, 'bold')
        author_fg = "#6B7280" if is_system else ("#3B82F6" if is_user else "#111827")
        author_label = tk.Label(top_frame, text=author.capitalize(), font=author_font, fg=author_fg, bg=bubble_bg)
        author_label.pack(side="left")

        if author == "AI":
            is_pinned = self.message_data.get('pinned', False)
            pin_char = "★" if is_pinned else "☆"
            pin_fg = "#F59E0B" if is_pinned else "#6B7280"
            self.pin_button = tk.Button(top_frame, text=pin_char, fg=pin_fg, bg=bubble_bg, relief='flat', font=("Segoe UI", 12), cursor="hand2", command=self.toggle_pin, bd=0, highlightthickness=0)
            self.pin_button.pack(side="right")

        # --- Message Area (Text widget) ---
        text_fg = "#6B7280" if is_system else "#1F2937"
        self.message_text = tk.Text(self, font=("Segoe UI", 10), wrap=tk.WORD, bg=bubble_bg, fg=text_fg, relief="flat", borderwidth=0, state="disabled", highlightthickness=0, height=1, padx=5)
        self.message_text.pack(side="top", fill="x", expand=True, padx=10, pady=(0, 5))
        
        # --- NEW: Configure a whole bunch of tags for Markdown and Syntax Highlighting ---
        self.message_text.tag_configure("h1", font=("Segoe UI", 14, 'bold'))
        self.message_text.tag_configure("bold", font=("Segoe UI", 10, 'bold'))
        self.message_text.tag_configure("italic", font=("Segoe UI", 10, 'italic'))
        self.message_text.tag_configure("list_item", lmargin1=20, lmargin2=20)
        self.message_text.tag_configure("code_block", font=("Consolas", 9), background="#282c34", foreground="#abb2bf", relief="solid", borderwidth=1, lmargin1=15, lmargin2=15, rmargin=15, wrap="word")

        # Configure tags from a Pygments style
        self.configure_pygments_tags()
        
        self.message_text.tag_configure("normal", font=("Segoe UI", 10))
        self.set_text(text)

# Find the set_text method in the MessageBubble class and replace it with this:
    # NEW: Method to create Tkinter tags from a Pygments style
    def configure_pygments_tags(self):
        style = get_style_by_name('monokai') # You can try other styles like 'default', 'solarized-dark', etc.
        for token_type, token_style in style:
            tag_name = str(token_type)
            # Create a tag with the style's properties
            self.message_text.tag_configure(tag_name, foreground=f"#{token_style['color']}" if token_style['color'] else None, font=(("Consolas", 9, 'bold') if token_style['bold'] else ("Consolas", 9)))
    
    def set_text(self, new_text):
        self.message_text.config(state="normal")
        self.message_text.delete("1.0", tk.END)

        in_code_block = False
        code_language = 'text' # Default language
        code_buffer = []

        for line in new_text.split('\n'):
            if line.strip().startswith('```'):
                if in_code_block:
                    # End of a code block -> highlight and insert
                    try:
                        lexer = get_lexer_by_name(code_language)
                    except:
                        lexer = guess_lexer("\n".join(code_buffer))
                    
                    tokens = lex("\n".join(code_buffer), lexer)
                    self.message_text.insert(tk.END, '\n')
                    for token_type, token_value in tokens:
                        self.message_text.insert(tk.END, token_value, (str(token_type), "code_block"))
                    self.message_text.insert(tk.END, '\n\n', "code_block")
                    
                    in_code_block, code_buffer, code_language = False, [], 'text'
                else:
                    # Start of a code block
                    in_code_block = True
                    code_language = line.strip()[3:] or 'text'
                continue

            if in_code_block:
                code_buffer.append(line)
            else:
                # Handle normal Markdown lines
                if line.startswith('# '):
                    self.message_text.insert(tk.END, line[2:] + '\n', 'h1')
                elif line.strip().startswith('* ') or line.strip().startswith('- '):
                    self.message_text.insert(tk.END, f"• {line.strip()[2:]}\n", 'list_item')
                else:
                    parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', line)
                    for part in parts:
                        if part.startswith('**') and part.endswith('**'): self.message_text.insert(tk.END, part[2:-2], 'bold')
                        elif part.startswith('*') and part.endswith('*'): self.message_text.insert(tk.END, part[1:-1], 'italic')
                        else: self.message_text.insert(tk.END, part)
                    self.message_text.insert(tk.END, '\n')

        # CRITICAL FIX 1: Re-calculate the required height
        self.message_text.update_idletasks()
        # The height is the number of lines from start to finish
        height = int(self.message_text.index('end-1c').split('.')[0])
        self.message_text.config(height=height)
        
        self.message_text.config(state="disabled")

        # CRITICAL FIX 2: Tell the main window that we have resized
        self.app_instance._on_bubble_resize()

    def get_text(self):
        return self.message_text.get("1.0", "end-1c")
    
    def get_text_from_parts(self, parts):
        """Helper to extract text from the 'parts' list."""
        if parts and isinstance(parts, list) and len(parts) > 0 and 'text' in parts[0]:
            return parts[0]['text']
        return ""

    def add_copy_button(self):
        # THE CRITICAL FIX IS HERE: We now use .pack() instead of .grid()
        copy_button = tk.Button(self, text="📋 Copy", command=lambda: self.app_instance.copy_to_clipboard(self.get_text()), 
                                bg="#E5E7EB", fg="#4B5563", relief='flat', font=("Segoe UI", 8), cursor="hand2")
        copy_button.pack(side="bottom", anchor="e", padx=10, pady=(0, 5))

    def toggle_pin(self):
        is_currently_pinned = self.message_data.get('pinned', False)
        self.message_data['pinned'] = not is_currently_pinned
        self.app_instance.rebuild_chat_display() # Tell the main app to refresh the view