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
        # Use the color palette from the main app instance for a consistent theme
        if is_user:
            bubble_bg = self.app_instance.C_USER_BUBBLE_BG
            author_fg = self.app_instance.C_USER_BUBBLE_FG
            text_fg = self.app_instance.C_USER_BUBBLE_FG
        elif is_system:
            bubble_bg = self.app_instance.C_BG
            author_fg = self.app_instance.C_TEXT_SECONDARY
            text_fg = self.app_instance.C_TEXT_SECONDARY
        else: # AI/Model
            bubble_bg = self.app_instance.C_WIDGET_BG
            author_fg = self.app_instance.C_TEXT_PRIMARY
            text_fg = self.app_instance.C_TEXT_PRIMARY

        # This is now the bubble's colored background
        self.config(bg=bubble_bg)

        # --- Top Frame for Author and Pin Button ---
        top_frame = tk.Frame(self, bg=bubble_bg)
        top_frame.pack(side="top", fill="x", padx=10, pady=(5,0))

        author_font = ("Segoe UI", 10, 'italic') if is_system else ("Segoe UI", 10, 'bold')
        author_label = tk.Label(top_frame, text=author.capitalize(), font=author_font, fg=author_fg, bg=bubble_bg)
        author_label.pack(side="left")

        if author == "model":
            is_pinned = self.message_data.get('pinned', False)
            pin_char = "★" if is_pinned else "☆"
            pin_fg = "#F59E0B" if is_pinned else self.app_instance.C_TEXT_SECONDARY
            self.pin_button = tk.Button(top_frame, text=pin_char, fg=pin_fg, bg=bubble_bg, relief='flat', font=("Segoe UI", 14), cursor="hand2", command=self.toggle_pin, bd=0, highlightthickness=0)
            self.pin_button.pack(side="right")

        # --- Message Area (Text widget) ---
        # text_fg is defined above based on role
        self.message_text = tk.Text(self, font=("Segoe UI", 11), wrap=tk.WORD, bg=bubble_bg, fg=text_fg, relief="flat", borderwidth=0, state="disabled", highlightthickness=0, height=1, padx=10)
        self.message_text.pack(side="top", fill="x", expand=True, padx=10, pady=(0, 5))
        
        # --- NEW: Configure a whole bunch of tags for Markdown and Syntax Highlighting ---
        self.message_text.tag_configure("h1", font=("Segoe UI", 16, 'bold'), spacing1=5, spacing3=5)
        self.message_text.tag_configure("bold", font=("Segoe UI", 11, 'bold'))
        self.message_text.tag_configure("italic", font=("Segoe UI", 11, 'italic'))
        self.message_text.tag_configure("list_item", lmargin1=20, lmargin2=20)
        self.message_text.tag_configure("code_block", font=("Consolas", 10), background="#282c34", foreground="#abb2bf", relief="flat", borderwidth=1, lmargin1=15, lmargin2=15, rmargin=15, wrap="word", spacing1=5, spacing3=5)

        # Configure tags from a Pygments style
        self.configure_pygments_tags()

        self.message_text.tag_configure("normal", font=("Segoe UI", 11))
        self.set_text(text)

# Find the set_text method in the MessageBubble class and replace it with this:
    # NEW: Method to create Tkinter tags from a Pygments style
    def configure_pygments_tags(self):
        style = get_style_by_name('monokai') # You can try other styles like 'default', 'solarized-dark', etc.
        for token_type, token_style in style:
            tag_name = str(token_type)
            # Create a tag with the style's properties
            self.message_text.tag_configure(tag_name, foreground=f"#{token_style['color']}" if token_style['color'] else None, font=(("Consolas", 10, 'bold') if token_style['bold'] else ("Consolas", 10)))
    
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
    
    def add_copy_button(self):
        # THE CRITICAL FIX IS HERE: We now use .pack() instead of .grid()
        copy_button = tk.Button(self, text="📋 Copy", 
                                command=lambda: self.app_instance.copy_to_clipboard(self.get_text()), 
                                bg=self.cget('bg'), # Match the bubble background
                                fg=self.app_instance.C_TEXT_SECONDARY, 
                                activeforeground=self.app_instance.C_TEXT_PRIMARY,
                                activebackground=self.cget('bg'),
                                relief='flat', font=("Segoe UI", 9), cursor="hand2", bd=0)
        copy_button.pack(side="bottom", anchor="e", padx=10, pady=(0, 5))

    def toggle_pin(self):
        is_currently_pinned = self.message_data.get('pinned', False)
        self.message_data['pinned'] = not is_currently_pinned
        self.app_instance.rebuild_chat_display() # Tell the main app to refresh the view