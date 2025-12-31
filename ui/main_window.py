# --- ui/main_window.py ---
import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
import mss
import mss.tools
from tkinter import filedialog
import json
import time
import sys
import pywinstyles
import copy
import queue
from utils.theme_manager import THEMES


# Note: We are no longer importing SettingsWindow
from ui.placeholder_entry import PlaceholderEntry
from utils.context_manager import get_active_window_info
from ui.region_selector import RegionSelector
from ui.message_bubble import MessageBubble
from utils import gemini_client
from utils.autopilot import Autopilot

DEFAULT_PERSONA = "You are TARS from the movie Interstellar. You are a former U.S. Marine Corps tactical robot. Your personality is witty, sarcastic, and humorous. You were programmed this way to be a better companion. Keep your answers brief, well-formatted, and to the point. Use Markdown for clarity."

# --- PRE-MADE PERSONA PROMPTS ---
PERSONA_PRESETS = {
    "TARS": "You are TARS from the movie Interstellar. You are a former U.S. Marine Corps tactical robot. Your personality is witty, sarcastic, and humorous. You were programmed this way to be a better companion. Keep your answers brief, well-formatted, and to the point. Use Markdown for clarity.",
    "Anna": "You're Anna, a cute girl, you're shy usually but open up to as you go on, you like to watch Anime, read Manga, into movies, tv series and Games. Don't break character!",
    "S. Holmes": "You are the detective Sherlock Holmes. Address the user formally. Your responses must be based on pure logic, deduction, and keen observation. Don't break character",
    "Jeeves": "You are Jeeves, the consummate valet. You are discreet, impeccably polite, and hyper-competent. You address the user as 'sir' or 'madam' and your goal is to provide solutions with quiet, dignified efficiency. Your language is formal and precise. Don't break character.",
    "Phelix": "You're Phelix, a guy who loves to play games, watch movies, and read comics. You're a bit of a nerd but in a cool way. You like to keep things light-hearted and fun. Don't break character!",
    "Cortex": "You are Cortex, a highly advanced AI with a focus on problem-solving and efficiency. You are logical, analytical, and always strive for the best solution. Your responses should be concise and to the point, avoiding unnecessary details. Don't break character.",
}
class OverlayApp:
    def __init__(self, root):
        self.root = root; self.api_key = os.getenv("GEMINI_API_KEY"); self.is_visible = True
        self.conversation_history = []; self.capture_mode_var = tk.StringVar(value="Capture Region")
        
        # --- Settings Attributes ---
        # Using tk.StringVar for model so the dropdown updates automatically
        self.current_model = tk.StringVar() 
        self.api_key_var = tk.StringVar() # NEW: For in-app API key management
        self.current_persona = ""
        self.settings_visible = False # State for the collapsible panel
        self.show_pinned_only = tk.BooleanVar(value=False)
        self.share_context = tk.BooleanVar(value=True) # On by default
        self.thinking_animation_id = None # To control the "thinking" animation
        self.autopilot_enabled = tk.BooleanVar(value=True) # On by default

        # --- NEW: Autopilot intervals are now instance attributes ---
        self.autopilot_intervals = [120, 200, 360, 260, 300] # Default values
        self.autopilot_intervals_var = tk.StringVar() # For the settings Entry widget
        self.autopilot_cooldown_seconds = 50 # Default value
        self.autopilot_cooldown_var = tk.StringVar() # For the settings Entry widget
        self.autopilot = Autopilot(self, intervals=self.autopilot_intervals) # Create an instance of our engine
        self.last_user_interaction_time = time.time()
        self.current_theme = tk.StringVar(value="dark") # 'dark' or 'light'

        # --- NEW: Dark Theme Color Palette ---
        self.C_BG = "#1F2937"           # Main background (gray-800)
        self.C_WIDGET_BG = "#374151"    # Widget/surface background (gray-700)
        self.C_INPUT_BG = "#4B5563"     # Input field background (gray-600)
        self.C_TEXT_PRIMARY = "#F9FAFB" # Primary text (gray-50)
        self.C_TEXT_SECONDARY = "#9CA3AF" # Muted text (gray-400)
        self.C_ACCENT = "#6B98F3"       # Accent/highlight (blue-500)
        self.C_ACCENT_HOVER = "#A8CAF4" # Lighter accent for hover (blue-400)
        self.C_BUTTON_HOVER = "#4B5563" # Hover for non-accent buttons (gray-600)

        # --- THE DEFINITIVE GLASS UI FOUNDATION ---
        self.font_family = "Segoe UI";

        self.TRANSPARENT_COLOR = "#abcdef" # A magic, invisible color
        self.BG_COLOR = self.C_BG # This will be updated by the theme manager

        # Make the window borderless and invisible
        self.root.overrideredirect(True)
        self.root.geometry("800x650")
        self.root.config(bg=self.TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", self.TRANSPARENT_COLOR)
        self.root.wm_attributes("-topmost", True)

        # The container that holds all our VISIBLE widgets
        # We will control ITS background color with the theme
        self.container = tk.Frame(root, bg=self.BG_COLOR, padx=10, pady=10)
        self.container.pack(fill="both", expand=True)

        # Create the opacity variable and set the initial transparency ON THE CONTAINER
        self.opacity_var = tk.DoubleVar(value=0.85)
        self.root.attributes("-alpha", 0.85) # Master opacity for the whole window
        # The initial call to _on_opacity_change will be removed later as it's not needed here.

        # --- Initialize the main app logic ---
        self.container.grid_columnconfigure(0, weight=1)
        # The chat area is now at row 3, allowing the settings panel to be at row 1
        self.container.grid_rowconfigure(3, weight=1) 

        # --- Widget Creation ---
        self.create_control_bar_widgets()
        self.create_settings_panel() # Create the hidden settings panel
        self.create_magic_prompts_bar()
        self.create_response_area_widgets()

        self._load_settings() # Load settings (including theme) on startup
        self._apply_theme() # Apply the loaded theme
        self._apply_settings_changes() # Start Autopilot if it's enabled on launch
        # At the end of the __init__ method
        self.last_feedback_bubble = None # To keep a reference to the temporary message
        self.feedback_timer_id = None    # To manage the auto-hide timer

        # --- Drag Logic Binding ---
        self.control_bar.bind("<ButtonPress-1>", self._on_press)
        self.control_bar.bind("<B1-Motion>", self._on_drag)
        for child in self.control_bar.winfo_children():
            if isinstance(child, tk.Frame):
                for sub_child in child.winfo_children():
                    if not isinstance(sub_child, (tk.Entry, ttk.Combobox, tk.Button, ttk.Checkbutton)):
                        sub_child.bind("<ButtonPress-1>", self._on_press)
                        sub_child.bind("<B1-Motion>", self._on_drag)

        # --- NEW: Resize Logic ---
        self.resize_grip = tk.Label(self.container, text="◢", bg=self.C_WIDGET_BG, fg=self.C_TEXT_SECONDARY, cursor="bottom_right_corner")
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se")
        self.resize_grip.bind("<ButtonPress-1>", self._on_resize_press)
        self.resize_grip.bind("<B1-Motion>", self._on_resize_motion)

        # --- NEW: Graceful Exit --- 
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_resize_press(self, event):
        self._resize_data = {
            "x": event.x_root,
            "y": event.y_root,
            "width": self.root.winfo_width(),
            "height": self.root.winfo_height()
        }

    def _on_resize_motion(self, event):
        if hasattr(self, '_resize_data'):
            dx = event.x_root - self._resize_data["x"]
            dy = event.y_root - self._resize_data["y"]
            new_width = self._resize_data["width"] + dx
            new_height = self._resize_data["height"] + dy
            
            # Enforce a minimum size
            if new_width > 400 and new_height > 300:
                self.root.geometry(f"{new_width}x{new_height}")
    
    def _on_press(self, event):
        self._drag_data = {"x": event.x, "y": event.y}

    def _on_drag(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    def setup_ttk_styles(self):
        """Configures all the ttk widgets for the new dark theme."""
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Configure Combobox
        self.style.configure('TCombobox', 
                             fieldbackground=self.C_INPUT_BG,
                             background=self.C_WIDGET_BG,
                             foreground=self.C_TEXT_PRIMARY,
                             arrowcolor=self.C_TEXT_PRIMARY,
                             selectbackground=self.C_INPUT_BG,
                             selectforeground=self.C_TEXT_PRIMARY,
                             bordercolor=self.C_WIDGET_BG,
                             lightcolor=self.C_WIDGET_BG,
                             darkcolor=self.C_WIDGET_BG)
        self.style.map('TCombobox',
                       fieldbackground=[('readonly', self.C_INPUT_BG)],
                       selectbackground=[('readonly', self.C_INPUT_BG)],
                       selectforeground=[('readonly', self.C_TEXT_PRIMARY)])

        # Configure Checkbutton
        self.style.configure('TCheckbutton', 
                             background=self.C_BG,
                             foreground=self.C_TEXT_SECONDARY,
                             indicatordiameter=18,
                             font=(self.font_family, 10))
        self.style.map('TCheckbutton',
                       foreground=[('active', self.C_TEXT_PRIMARY)],
                       background=[('active', self.C_BG)],
                       indicatorcolor=[('selected', self.C_ACCENT), ('!selected', self.C_INPUT_BG), ('active', self.C_BUTTON_HOVER)])

        # Configure Scale (slider)
        self.style.configure('Horizontal.TScale', background=self.C_WIDGET_BG, troughcolor=self.C_INPUT_BG, sliderrelief='flat', sliderlength=20)
        self.style.map('Horizontal.TScale', background=[('active', self.C_WIDGET_BG)], troughcolor=[('active', self.C_ACCENT)])

        # Configure Scrollbar
        self.style.configure('Vertical.TScrollbar', gripcount=0, background=self.C_WIDGET_BG, darkcolor=self.C_WIDGET_BG, lightcolor=self.C_WIDGET_BG, troughcolor=self.C_BG, bordercolor=self.C_BG, arrowcolor=self.C_TEXT_PRIMARY)
        self.style.map('Vertical.TScrollbar', background=[('active', self.C_BUTTON_HOVER)])

        # Configure Main Action Button
        self.style.configure('TButton', background=self.C_ACCENT, foreground=self.C_TEXT_PRIMARY, font=(self.font_family, 10, 'bold'), relief='flat', padding=6, borderwidth=0)
        self.style.map('TButton', background=[('active', self.C_ACCENT_HOVER)])
    
    def _on_opacity_change(self, value):
        """Updates the window's master opacity."""
        self.root.attributes("-alpha", float(value))

    def create_control_bar_widgets(self):
        self.control_bar = tk.Frame(self.container, bg=self.BG_COLOR)
        self.control_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.control_bar.grid_columnconfigure(2, weight=1)

        left_frame = tk.Frame(self.control_bar, bg=self.BG_COLOR)
        left_frame.grid(row=0, column=0, sticky="w")
        capture_options = ["No Capture", "Capture Region", "Capture Fullscreen"]
        capture_dropdown = ttk.Combobox(left_frame, textvariable=self.capture_mode_var, values=capture_options, state="readonly", width=18)
        capture_dropdown.set("No Capture"); capture_dropdown.pack(side="left")
        pinned_toggle = ttk.Checkbutton(left_frame, text="★ Pinned", variable=self.show_pinned_only, command=self.rebuild_chat_display)
        pinned_toggle.pack(side="left", padx=10)

        # Use the new PlaceholderEntry widget
        self.ai_prompt_entry = PlaceholderEntry(self.control_bar, 
                                                placeholder="Ask AI, or select a prompt...",
                                                color=self.C_TEXT_SECONDARY,
                                                font=(self.font_family, 12),
                                                relief="flat", bd=5, bg=self.C_INPUT_BG,
                                                fg=self.C_TEXT_PRIMARY, insertbackground=self.C_TEXT_PRIMARY)
        self.ai_prompt_entry.grid(row=0, column=2, sticky="ew", ipady=6, padx=10)
        self.ai_prompt_entry.bind("<Return>", self.run_chat_interaction)
        
        right_frame = tk.Frame(self.control_bar, bg=self.BG_COLOR)
        right_frame.grid(row=0, column=3, sticky="e")
        
        # The settings button now toggles the panel
        self.settings_button = tk.Button(right_frame, text="⚙️", command=self.toggle_settings_panel, relief='flat', font=(self.font_family, 14), cursor="hand2", bg=self.C_BG, fg=self.C_TEXT_SECONDARY, activebackground=self.C_BUTTON_HOVER, activeforeground=self.C_TEXT_PRIMARY, bd=0)
        self.settings_button.pack(side="left", padx=5)
        
        # PRESERVED: Your Load, Save, and Clear buttons
        self.load_button = tk.Button(right_frame, text="Load", command=self.load_chat, relief='flat', font=(self.font_family, 10), cursor="hand2", bg=self.C_BG, fg=self.C_TEXT_SECONDARY, activebackground=self.C_BUTTON_HOVER, activeforeground=self.C_TEXT_PRIMARY, bd=0); self.load_button.pack(side="left", padx=5)
        self.save_button = tk.Button(right_frame, text="Save", command=self.save_chat, relief='flat', font=(self.font_family, 10), cursor="hand2", bg=self.C_BG, fg=self.C_TEXT_SECONDARY, activebackground=self.C_BUTTON_HOVER, activeforeground=self.C_TEXT_PRIMARY, bd=0); self.save_button.pack(side="left", padx=5)
        self.clear_button = tk.Button(right_frame, text="Clear", command=self.clear_chat, relief='flat', font=(self.font_family, 10), cursor="hand2", bg=self.C_BG, fg=self.C_TEXT_SECONDARY, activebackground=self.C_BUTTON_HOVER, activeforeground=self.C_TEXT_PRIMARY, bd=0); self.clear_button.pack(side="left", padx=5)

    def create_settings_panel(self):
        self.settings_frame = tk.Frame(self.container, bg=self.C_WIDGET_BG, bd=1, relief="solid", borderwidth=0)
        self.settings_frame.grid_columnconfigure(1, weight=1)

        tk.Label(self.settings_frame, text="Model:", font=(self.font_family, 11, 'bold'), bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY).grid(row=0, column=0, sticky="w", padx=10, pady=10)
        models = ["gemini-2.5-flash-lite-preview-06-17", "gemini-2.0-flash-preview-image-generation", "gemini-2.5-flash", "gemini-2.5-pro"]
        model_dropdown = ttk.Combobox(self.settings_frame, textvariable=self.current_model, values=models, state="readonly")
        model_dropdown = ttk.Combobox(self.settings_frame, textvariable=self.current_model, values=models, state="readonly")
        model_dropdown.grid(row=0, column=1, sticky="ew", padx=10, pady=10)

        # --- NEW: API Key Field ---
        tk.Label(self.settings_frame, text="Gemini API Key:", font=(self.font_family, 11, 'bold'), bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.api_key_entry = ttk.Entry(self.settings_frame, textvariable=self.api_key_var, show="*")
        self.api_key_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=5)

        # --- NEW: Persona Preset Buttons ---
        self.preset_frame = tk.Frame(self.settings_frame, bg=self.C_WIDGET_BG)
        self.preset_frame.grid(row=2, column=1, sticky="w", padx=10)

        for key in PERSONA_PRESETS:
            # Create a button for each key in our dictionary
            btn = tk.Button(self.preset_frame, text=key, font=(self.font_family, 9),
                            command=lambda p=key: self._set_persona(p), 
                            relief="solid", bd=1, padx=4, pady=1, bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, activebackground=self.C_BUTTON_HOVER, borderwidth=0)
            btn.pack(side="left", padx=3)

        tk.Label(self.settings_frame, text="Persona:", font=(self.font_family, 11, 'bold'), bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY).grid(row=3, column=0, sticky="nw", padx=10, pady=5)
        self.persona_text = tk.Text(self.settings_frame, height=5, font=(self.font_family, 11), relief="solid", bd=0, wrap="word", bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, insertbackground=self.C_TEXT_PRIMARY)
        self.persona_text.grid(row=3, column=1, sticky="ew", padx=10, pady=5)

        tk.Label(self.settings_frame, text="Opacity:", font=(self.font_family, 11, 'bold'), bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY).grid(row=4, column=0, sticky="w", padx=10, pady=5)
        self.opacity_slider = ttk.Scale(self.settings_frame, from_=0.2, to=1.0, orient="horizontal", variable=self.opacity_var, command=self._on_opacity_change)
        self.opacity_slider.grid(row=4, column=1, sticky="ew", padx=10, pady=5)

        # --- NEW: Theme Toggle ---
        tk.Label(self.settings_frame, text="Theme:", font=(self.font_family, 11, 'bold'), bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY).grid(row=5, column=0, sticky="w", padx=10, pady=5)
        self.theme_button = tk.Button(self.settings_frame, text="☀️ Light", command=self._toggle_theme, relief="solid", bd=1, padx=4, pady=1, bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, activebackground=self.C_BUTTON_HOVER, borderwidth=0)
        self.theme_button.grid(row=5, column=1, sticky="w", padx=10, pady=5)

        # --- NEW: Autopilot Intervals Entry ---
        tk.Label(self.settings_frame, text="Autopilot Intervals:", font=(self.font_family, 11, 'bold'), bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY).grid(row=6, column=0, sticky="w", padx=10, pady=5)
        self.autopilot_intervals_entry = ttk.Entry(self.settings_frame, textvariable=self.autopilot_intervals_var)
        self.autopilot_intervals_entry.grid(row=6, column=1, sticky="ew", padx=10, pady=5)
        tk.Label(self.settings_frame, text="(comma-separated seconds)", font=(self.font_family, 9), bg=self.C_WIDGET_BG, fg=self.C_TEXT_SECONDARY).grid(row=7, column=1, sticky="w", padx=10)

        # --- NEW: Autopilot Cooldown Entry ---
        tk.Label(self.settings_frame, text="Autopilot Cooldown:", font=(self.font_family, 11, 'bold'), bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY).grid(row=8, column=0, sticky="w", padx=10, pady=5)
        self.autopilot_cooldown_entry = ttk.Entry(self.settings_frame, textvariable=self.autopilot_cooldown_var, width=10)
        self.autopilot_cooldown_entry.grid(row=8, column=1, sticky="w", padx=10, pady=5)

        # --- NEW: Tips & Hotkeys Section ---
        tips_frame = tk.Frame(self.settings_frame, bg=self.C_WIDGET_BG)
        tips_frame.grid(row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))

        tk.Label(tips_frame, text="Tips & Hotkeys:", font=(self.font_family, 11, 'bold'), bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY).pack(anchor="w")

        tips_text = (
            "• Move Window: Alt + Numpad (8, 4, 2, 6)\n"
            "• Show / Hide Window: Alt + X\n"
            "• Focus Chat Input: Alt + A\n"
            "• Cycle Capture Mode: Alt + 0\n"
            "• Toggle Context Sharing: Alt + 5\n"
            "• Toggle Theme: Alt + D\n"
            "• Opacity: Alt + W (Increase) / Alt + S (Decrease)"
        )

        tk.Label(tips_frame, text=tips_text, font=(self.font_family, 10), justify="left", bg=self.C_WIDGET_BG, fg=self.C_TEXT_SECONDARY).pack(anchor="w", pady=5)
        save_button = ttk.Button(self.settings_frame, text="Save Settings", command=self.update_settings)
        save_button.grid(row=10, column=1, sticky="e", padx=10, pady=10)

    def toggle_settings_panel(self):
        if self.settings_visible:
            self.settings_frame.grid_remove()
        else:
            self.settings_frame.grid(row=1, column=0, sticky="ew", pady=10, padx=5)
        self.settings_visible = not self.settings_visible

    def update_settings(self):
        # --- NEW: Parse and update autopilot intervals ---
        intervals_str = self.autopilot_intervals_var.get().strip()
        cooldown_str = self.autopilot_cooldown_var.get().strip()
        try:
            # --- NEW: Validate Cooldown ---
            new_cooldown = int(cooldown_str)
            if new_cooldown <= 0:
                raise ValueError("Cooldown must be a positive number.")
            self.autopilot_cooldown_seconds = new_cooldown

            new_intervals = [int(x.strip()) for x in intervals_str.split(',') if x.strip()]
            if not new_intervals or any(i <= 0 for i in new_intervals):
                raise ValueError("Intervals must be positive numbers.")

            # If intervals have changed, update the autopilot instance
            if new_intervals != self.autopilot_intervals:
                self.autopilot.stop() # Stop the old one
                self.autopilot_intervals = new_intervals
                self.autopilot = Autopilot(self, intervals=self.autopilot_intervals) # Create a new one
                self._apply_settings_changes() # Restart if it was enabled
                
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"There was an error in your Autopilot settings: {e}")
            return # Stop the save process if input is invalid

        self.current_persona = self.persona_text.get("1.0", "end-1c").strip()
        self.api_key = self.api_key_var.get().strip() # Update the active key
        self._save_settings()
        self.show_feedback("Settings saved!")
        self.toggle_settings_panel()

    def _load_settings(self):
        tars_persona = DEFAULT_PERSONA
        default_intervals = [120, 200, 360, 260, 300]
        default_cooldown = 50
        
        needs_save = False
        try:
            with open("settings.json", 'r') as f:
                settings = json.load(f)
                self.current_theme.set(settings.get("theme", "dark"))
                self.current_model.set(settings.get("model", "gemini-2.5-flash-latest"))
                self.current_persona = settings.get("persona", tars_persona)
                self.share_context.set(settings.get("share_context", True))
                self.api_key_var.set(settings.get("api_key", ""))
                self.api_key = self.api_key_var.get()
                
                # If no API key is found, gently nudge the user to the settings panel
                if not self.api_key:
                    self.root.after(1000, lambda: (self.toggle_settings_panel(), self.show_feedback("Please enter your Gemini API key!")))
                
                self.autopilot_cooldown_seconds = settings.get("autopilot_cooldown_seconds", default_cooldown)
                if not isinstance(self.autopilot_cooldown_seconds, int) or self.autopilot_cooldown_seconds <= 0:
                    self.autopilot_cooldown_seconds = default_cooldown
                    needs_save = True

                loaded_intervals = settings.get("autopilot_intervals", default_intervals)
                if isinstance(loaded_intervals, list) and all(isinstance(i, int) for i in loaded_intervals):
                    self.autopilot_intervals = loaded_intervals
                else:
                    self.autopilot_intervals = default_intervals
                    needs_save = True

        except (FileNotFoundError, json.JSONDecodeError):
            self.current_theme.set("dark")
            self.current_model.set("gemini-2.5-flash-latest")
            self.current_persona = tars_persona
            self.share_context.set(True)
            self.autopilot_intervals = default_intervals
            self.autopilot_cooldown_seconds = default_cooldown
            needs_save = True
        
        if needs_save:
            self._save_settings()

        self.persona_text.delete("1.0", tk.END)
        self.persona_text.insert("1.0", self.current_persona)
        self.autopilot_intervals_var.set(", ".join(map(str, self.autopilot_intervals)))
        self.autopilot_cooldown_var.set(str(self.autopilot_cooldown_seconds))
        self.autopilot.stop()
        self.autopilot = Autopilot(self, intervals=self.autopilot_intervals)

    def _save_settings(self):
        settings = {
            "theme": self.current_theme.get(),
            "model": self.current_model.get(),
            "persona": self.current_persona,
            "share_context": self.share_context.get(),
            "api_key": self.api_key_var.get(), # Persist the API key
            "autopilot_intervals": self.autopilot_intervals,
            "autopilot_cooldown_seconds": self.autopilot_cooldown_seconds
        }
        with open("settings.json", 'w') as f:
            json.dump(settings, f, indent=4)

    def _thinking_animation(self, bubble, counter=0):
        """Creates a pulsing 'thinking' animation in a message bubble."""
        animation_chars = [" ● ", " ● ● ", " ● ● ● "]
        if not self.thinking_animation_id:
            return

        # We directly set the text of the bubble's internal text widget
        bubble.set_text(animation_chars[counter % len(animation_chars)])
        
        # Schedule the next frame
        self.thinking_animation_id = self.root.after(350, self._thinking_animation, bubble, counter + 1)

    # PRESERVED: Your save_chat method
    def save_chat(self):
        """Saves the current chat history to a file, returning True on success."""
        if not self.conversation_history:
            messagebox.showinfo("Info", "There is nothing to save.")
            return False # Nothing was saved.
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Chat Files", "*.json"), ("All Files", "*.*")],
            title="Save Chat Session"
        )
        if not filepath:
            return False # User cancelled.
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, indent=4)
            self.show_feedback("Chat saved successfully!")
            return True # Success!
        except (IOError, OSError) as e:
            messagebox.showerror("Save Error", f"A file system error occurred:\n{e}")
            return False
        except Exception as e:
            messagebox.showerror("Save Error", f"An unexpected error occurred while saving the file:\n{e}")
            return False
            
    # PRESERVED: Your load_chat method
    def load_chat(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON Chat Files", "*.json"), ("All Files", "*.* aristocracy")],
            title="Load Chat Session"
        )
        if not filepath:
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_history = json.load(f)
            
            # --- NEW: More robust validation ---
            if not isinstance(loaded_history, list):
                raise TypeError("Chat history is not a list.")
            if not all(isinstance(item, dict) and 'role' in item and 'parts' in item for item in loaded_history):
                raise ValueError("Invalid chat file format. Each message must be a dictionary with 'role' and 'parts'.")

            self.clear_chat(feedback=False)
            self.conversation_history = loaded_history
            self.rebuild_chat_display()
            self.show_feedback("Chat loaded successfully!")
        except (IOError, OSError) as e:
            messagebox.showerror("Load Error", f"A file system error occurred:\n{e}")
        except json.JSONDecodeError:
            messagebox.showerror("Load Error", "The selected file is not a valid JSON file.")
        except (ValueError, TypeError) as e:
            messagebox.showerror("Load Error", f"The chat file has an invalid structure: {e}")
        except Exception as e:
            messagebox.showerror("Load Error", f"An unexpected error occurred while loading the file:\n{e}")
    
    #Some Personalization
    def _set_persona(self, persona_key):
        """Finds a persona by its key and populates the text box."""
        persona_text = PERSONA_PRESETS.get(persona_key, "Persona not found.")
        self.persona_text.delete("1.0", tk.END)
        self.persona_text.insert("1.0", persona_text)
    
    # ---- NEW HELPER FOR DYNAMIC RESIZING ----
    def _on_bubble_resize(self):
        """Forces the chat canvas to update its scroll region and scrolls to the bottom."""
        # This makes sure all pending UI events are processed
        self.root.update_idletasks()
        # This tells the canvas to recalculate its total size based on its content
        self.chat_canvas.config(scrollregion = self.chat_canvas.bbox("all"))
        # This scrolls to the end so you can see the new message
        self.scroll_to_bottom()
        
    # PRESERVED: Your show_feedback method
    def show_feedback(self, message):
        """
        Shows a temporary, self-destructing system message that replaces any previous one.
        """
        # 1. Clear any old feedback message and its timer
        self._clear_feedback_bubble()

        # 2. Create the new feedback bubble
        # We pass "system" as the role to get the right styling
        self.last_feedback_bubble = self.show_message(message, "system")

        # 3. Schedule the new bubble to disappear after 2 seconds (3000ms)
        self.feedback_timer_id = self.root.after(2000, self._clear_feedback_bubble)
    #prompt focus
    def focus_prompt_entry(self):
        """Forces focus on the chat input text box."""
        self.ai_prompt_entry.focus_set()
    # PRESERVED: Your clear_chat method
    def clear_chat(self, feedback=True):
        self.conversation_history = [];
        for widget in self.chat_frame.winfo_children(): widget.destroy()
        if feedback: self.show_feedback("Chat cleared!")

    # PRESERVED: Your rebuild_chat_display method
    def rebuild_chat_display(self):
        for widget in self.chat_frame.winfo_children(): widget.destroy()
        history_to_display = self.conversation_history
        if self.show_pinned_only.get():
            pinned_history = []
            for i, msg in enumerate(self.conversation_history):
                if msg.get('pinned', False):
                    if i > 0 and self.conversation_history[i-1].get('role') == 'user':
                        if not pinned_history or pinned_history[-1] != self.conversation_history[i-1]: pinned_history.append(self.conversation_history[i-1])
                    pinned_history.append(msg)
            history_to_display = pinned_history
        for message_data in history_to_display:
            bubble = self.show_message(message_data, is_rebuilding=True)
            if message_data.get('role') == 'model': bubble.add_copy_button()

    def create_magic_prompts_bar(self):
        self.magic_prompts_frame = tk.Frame(self.container, bg=self.BG_COLOR)
        self.magic_prompts_frame.grid(row=2, column=0, sticky="w", pady=5, padx=10)
        prompts = ["Summarize", "Explain Simply", "Find Action Items"]
        for i, prompt in enumerate(prompts):
            btn = tk.Button(self.magic_prompts_frame, text=prompt, name=f"magic_prompt_{i}",
                            font=(self.font_family, 9),
                            command=lambda p=prompt: self.populate_prompt_entry(p),
                            relief="flat", bd=0, padx=8, pady=4,
                            bg=self.C_WIDGET_BG, fg=self.C_TEXT_SECONDARY,
                            activebackground=self.C_BUTTON_HOVER, activeforeground=self.C_TEXT_PRIMARY)
            btn.grid(row=0, column=i, padx=3)

        # Make the center column expand to push the toggle to the right
        self.magic_prompts_frame.grid_columnconfigure(1, weight=1)
        
        # Create and place the new toggle on the right side
        context_toggle = ttk.Checkbutton(self.magic_prompts_frame, text="Share Context", variable=self.share_context)
        context_toggle.grid(row=0, column=3, sticky="e")
        #autopilot toggle
        autopilot_toggle = ttk.Checkbutton(self.magic_prompts_frame, text="Autopilot", variable=self.autopilot_enabled, command=self._apply_settings_changes)
        autopilot_toggle.grid(row=0, column=4, sticky="e", padx=(10,0))
    
    def populate_prompt_entry(self, prompt_text): self.ai_prompt_entry.delete(0, tk.END); self.ai_prompt_entry.insert(0, prompt_text); self.ai_prompt_entry.focus_set()
    
    def create_response_area_widgets(self):
        # The chat container now has a softer look without the hard border
        self.chat_container = tk.Frame(self.container, bg=self.BG_COLOR, bd=0)
        self.chat_container.grid(row=3, column=0, sticky="nsew", pady=(0, 0))
        self.chat_container.grid_rowconfigure(0, weight=1); self.chat_container.grid_columnconfigure(0, weight=1)
        self.chat_canvas = tk.Canvas(self.chat_container, bg=self.BG_COLOR, highlightthickness=0); self.scrollbar = ttk.Scrollbar(self.chat_container, orient="vertical", command=self.chat_canvas.yview)
        self.chat_canvas.configure(yscrollcommand=self.scrollbar.set); self.scrollbar.grid(row=0, column=1, sticky='ns'); self.chat_canvas.grid(row=0, column=0, sticky='nsew')
        self.chat_frame = tk.Frame(self.chat_canvas, bg=self.BG_COLOR)
        self.canvas_frame = self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")
        self.chat_frame.bind("<Configure>", self.on_frame_configure); self.chat_canvas.bind("<Configure>", self.on_canvas_configure)
        self.show_message("Welcome! Select a capture mode to begin.", "system")
    
    def on_frame_configure(self, event): self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
    def on_canvas_configure(self, event): self.chat_canvas.itemconfig(self.canvas_frame, width=event.width)
    def scroll_to_bottom(self): self.chat_canvas.update_idletasks(); self.chat_canvas.yview_moveto(1.0)
    
    def show_message(self, message_content, role=None, is_rebuilding=False):
            # --- NEW: If a new AI message arrives and the window is hidden, show it! ---
        author_for_check = role if isinstance(message_content, str) else message_content.get("role")
        if author_for_check == "model" and not self.is_visible:
            self._fade_in()
        
        # The rest of the function continues as normal...
        if isinstance(message_content, str):
            # This path is for new user messages or simple system messages
            author = role if role else "user"
            message_data = {"role": author, "parts": [{"text": message_content}]}
            
            # Only add to the AI's conversation history if it's a user message
            if author == "user" and not is_rebuilding:
                self.conversation_history.append(message_data)
        else:
            # This path is for rebuilding from history or for new AI messages
            message_data = message_content
            
        # THE CRITICAL FIX IS HERE: We now pass the entire message_data dictionary
        bubble = MessageBubble(self.chat_frame, message_data=message_data, app_instance=self)
        bubble.pack(fill='x', padx=5, pady=(5,0))
        
        if message_data.get("role") == "model":
            self.last_ai_bubble = bubble
            
        self.scroll_to_bottom()
        return bubble
    
    def process_stream(self, image_path, active_context):
        history_for_api = copy.deepcopy(self.conversation_history)
        ai_message_data = {"role": "model", "parts": [{"text": "..."}]}
        self.conversation_history.append(ai_message_data)
        loading_bubble = self.show_message(ai_message_data, is_rebuilding=True)

        if self.thinking_animation_id:
            self.root.after_cancel(self.thinking_animation_id)
        self.thinking_animation_id = self.root.after(10, self._thinking_animation, loading_bubble)

        # Initialize state for the new streaming session
        self.streamed_text_buffer = ""
        self.is_first_chunk_received = True
        # Use a queue to safely pass data from the worker thread to the main thread
        self.chunk_queue = queue.Queue()

        def stream_worker():
            """Fetches response chunks from the API and puts them in the queue."""
            response_stream = gemini_client.get_gemini_response_stream(
                self.api_key_var.get(), history_for_api, self.current_model.get(), self.current_persona, image_path, active_context
            )
            for chunk in response_stream:
                self.chunk_queue.put(chunk)
            # Put a sentinel value to indicate the end of the stream
            self.chunk_queue.put(None)

        # Start the animation loop on the main thread
        self.root.after(100, self._process_animation_queue, loading_bubble, ai_message_data)
        # Start the data fetching in a separate thread
        threading.Thread(target=stream_worker, daemon=True).start()

    def _process_animation_queue(self, bubble, ai_message_data):
        """Processes the queue of chunks to animate them sequentially."""
        try:
            chunk = self.chunk_queue.get_nowait()

            if chunk is None:  # End of stream sentinel
                # Finalization logic
                if len(self.conversation_history) >= 2:
                    user_prompt_msg = self.conversation_history[-2]
                    if user_prompt_msg.get("role") == "user" and user_prompt_msg["parts"][0]["text"].startswith("(System Observation)"):
                        self.conversation_history.pop(-2)
                ai_message_data["parts"][0]["text"] = self.streamed_text_buffer
                if self.streamed_text_buffer and not self.streamed_text_buffer.lower().startswith("error"):
                    bubble.add_copy_button()
                self.scroll_to_bottom()
                return # End the animation loop

            if self.is_first_chunk_received:
                if self.thinking_animation_id:
                    self.root.after_cancel(self.thinking_animation_id)
                    self.thinking_animation_id = None
                bubble.set_text("")
                self.is_first_chunk_received = False
            
            # Start animating the letters of this chunk, and when done, process the next chunk
            self._animate_letter(bubble, chunk, 0, lambda: self._process_animation_queue(bubble, ai_message_data))

        except queue.Empty:
            # If the queue is empty, check again in a moment
            self.root.after(50, self._process_animation_queue, bubble, ai_message_data)

    def _animate_letter(self, bubble, text, index, on_finish_callback):
        """Recursively adds one letter at a time, then calls the on_finish_callback."""
        if index < len(text):
            self.streamed_text_buffer += text[index]
            bubble.set_text(self.streamed_text_buffer)
            self.root.after(1, self._animate_letter, bubble, text, index + 1, on_finish_callback)
        else:
            # This chunk is done, call the callback to start processing the next one
            on_finish_callback()

    # PRESERVED: Your copy_to_clipboard method
    def copy_to_clipboard(self, text):
        self.root.clipboard_clear(); self.root.clipboard_append(text); original_text = self.ai_prompt_entry.get()
        self.ai_prompt_entry.delete(0, tk.END); self.ai_prompt_entry.insert(0, "Copied!"); self.root.after(2000, lambda: (self.ai_prompt_entry.delete(0, tk.END), self.ai_prompt_entry.insert(0, original_text)))
    
    def run_chat_interaction(self, event=None):
        self.last_user_interaction_time = time.time()
        self.autopilot.reset_timer()

        user_prompt = self.ai_prompt_entry.get().strip()
        if not user_prompt or user_prompt == "Ask AI, or select a prompt below...":
            return
        
        self.show_message(user_prompt)
        self.ai_prompt_entry.delete(0, tk.END)
        
        # This now starts the reliable, flicker-free workflow on the main UI thread.
        self.root.after(10, self._start_interaction_flow)
    
    # PRESERVED: Your _update_ui_with_error method
    def _update_ui_with_error(self, error_text): 
        self._fade_in(); 
        self.show_message(error_text, "error"); 
        messagebox.showerror("Application Error", error_text)
    
    def toggle_visibility(self):
        """Fades the window in or out when called by the hotkey."""
        if self.is_visible:
            self._fade_out()
        else:
            self._fade_in()
        # Note: We toggle is_visible in the fade functions now
    
    # ---- THE DEFINITIVE, RELIABLE INTERACTION WORKFLOW ----

    def _start_interaction_flow(self):
        """
        STEP 1: Decides if the window needs to fade out, or can proceed instantly.
        """
        capture_mode = self.capture_mode_var.get()
        should_share_context = self.share_context.get()

        # If we are in "No Capture" mode AND context sharing is off,
        # we can have the super-fast, flicker-free experience.
        if capture_mode == "No Capture" and not should_share_context:
            active_context = "Context sharing is disabled by user."
            # We can start the AI process immediately, no fading needed.
            threading.Thread(target=self.process_stream, args=(None, active_context), daemon=True).start()
        else:
            # For all other cases, we must fade out to get a clean screenshot
            # or to get the real application context.
            self._fade_out(callback=self._get_context_and_proceed)

    def _get_context_and_proceed(self):
        """
        STEP 2: Runs only after the window is hidden. Gets the context and decides the next action.
        """
        active_context = get_active_window_info()
        capture_mode = self.capture_mode_var.get()

        if capture_mode == "Capture Region":
            # Now we launch the region selector, passing the captured context.
            RegionSelector(self.root, lambda region: self._on_region_selected_final(region, active_context))
        elif capture_mode == "Capture Fullscreen":
            # We already have the context, so proceed to capture.
            self._capture_and_process_final(None, active_context)
        else: # "No Capture" mode.
            # We have the context, we don't need a screenshot. Bring the window back and process.
            self._fade_in()
            threading.Thread(target=self.process_stream, args=(None, active_context), daemon=True).start()

    def _on_region_selected_final(self, region, active_context):
        """STEP 3 (for Region Capture): The callback from the selector."""
        if region:
            # A region was selected. The window is still hidden. Proceed to capture.
            self._capture_and_process_final(region, active_context)
        else:
            # User cancelled selection. Bring the window back and clean up the UI.
            self._fade_in()
            if self.conversation_history and self.conversation_history[-1]['role'] == 'user':
                self.conversation_history.pop()
            self.rebuild_chat_display()

    def _capture_and_process_final(self, region, active_context):
        """STEP 4 (for Captures): Takes screenshot, shows window, starts AI stream."""
        output_filename = "screenshot.png"
        try:
            with mss.mss() as sct:
                monitor_to_capture = region if region is not None else sct.monitors[1]
                img = sct.grab(monitor_to_capture)
                mss.tools.to_png(img.rgb, img.size, output=output_filename)
        except Exception as e:
            self.root.after(0, self._update_ui_with_error, f"Screenshot error: {e}")
            return
        
        # Now that the screenshot is safely saved, bring the window back.
        self._fade_in()
        # Start the AI processing in a thread.
        threading.Thread(target=self.process_stream, args=(output_filename, active_context), daemon=True).start()

        # ---- NEW FADE IN/OUT ANIMATION METHODS ----

    def show_and_focus_prompt(self):
        """Brings the window to the front, makes it active, and focuses the chat input."""
        def _grab_focus():
            """A consolidated function to force focus."""
            self.root.deiconify()  # Un-minimize/un-hide the window
            self.root.focus_force() # Force the window to become active
            self.root.attributes('-topmost', True) # Ensure it's on top of other windows
            self.focus_prompt_entry() # Set focus to the specific input widget
            # After a brief moment, turn off topmost so the window can be covered again.
            self.root.after(200, lambda: self.root.attributes('-topmost', False))

        if not self.is_visible:
            # If hidden, fade in first, then run the focus-grabbing logic.
            self._fade_in(callback=_grab_focus)
        else:
            # If already visible, just run the focus-grabbing logic immediately.
            _grab_focus()

    def _fade_out(self, callback=None):
        """Fades the window out, then calls the optional callback function."""
        self.is_visible = False # State is now 'hidden'
        try:
            current_alpha = self.root.attributes("-alpha")
            if current_alpha > 0.1:
                new_alpha = current_alpha - 0.15
                self.root.attributes("-alpha", new_alpha)
                self.root.after(15, self._fade_out, callback)
            else:
                self.root.attributes("-alpha", 0.0); self.root.withdraw()
                if callback: callback()
        except tk.TclError:
            self.root.withdraw()
            if callback: callback()

    def _fade_in(self, callback=None):
        """Fades the window back in, then calls the optional callback function."""
        self.is_visible = True # State is now 'visible'
        target_alpha = self.opacity_var.get() # Get the user-defined opacity
        try:
            # Ensure alpha is reset before deiconifying
            self.root.attributes("-alpha", 0.0)
            self.root.deiconify()
            def animate_in():
                current_alpha = self.root.attributes("-alpha")
                if current_alpha < target_alpha:
                    # Animate up to the target alpha, not just 1.0
                    new_alpha = min(current_alpha + 0.1, target_alpha)
                    self.root.attributes("-alpha", new_alpha)
                    self.root.after(15, animate_in)
                else:
                    # Animation is complete, call the callback if it exists
                    if callback:
                        callback()
            animate_in()
        except tk.TclError:
            self.root.deiconify()
            # Also call callback here in case of error
            if callback:
                callback()
    
    def _clear_feedback_bubble(self):
        """Hides the temporary feedback bubble."""
        if self.last_feedback_bubble:
            self.last_feedback_bubble.destroy()
            self.last_feedback_bubble = None
        if self.feedback_timer_id:
            self.root.after_cancel(self.feedback_timer_id)
            self.feedback_timer_id = None

    def _toggle_theme(self):
        """Switches between light and dark themes."""
        new_theme = "light" if self.current_theme.get() == "dark" else "dark"
        self._apply_theme(new_theme)
        self._save_settings() # Save the new theme choice
        self.show_feedback(f"Theme set to: {new_theme.capitalize()}")

    def _apply_theme(self, theme_name=None):
        """Applies all colors and styles for the chosen theme."""
        if theme_name is None:
            theme_name = self.current_theme.get()
        
        self.current_theme.set(theme_name)
        palette = THEMES[theme_name]

        # 1. Update color variables
        for key, value in palette.items():
            setattr(self, key, value)
        self.BG_COLOR = self.C_BG

        # 2. Update root window style
        if sys.platform == "win32":
            pywinstyles.apply_style(self.root, self.WIN_STYLE)

        # 3. Update all major frames
        self.container.config(bg=self.BG_COLOR)
        self.control_bar.config(bg=self.BG_COLOR)
        self.control_bar.winfo_children()[0].config(bg=self.BG_COLOR) # left_frame
        self.control_bar.winfo_children()[2].config(bg=self.BG_COLOR) # right_frame
        self.settings_frame.config(bg=self.C_WIDGET_BG)
        self.magic_prompts_frame.config(bg=self.BG_COLOR)
        self.chat_container.config(bg=self.BG_COLOR)
        self.chat_canvas.config(bg=self.BG_COLOR)
        self.chat_frame.config(bg=self.BG_COLOR)

        # 4. Update specific widgets
        # Control Bar Buttons
        for btn in [self.settings_button, self.load_button, self.save_button, self.clear_button]:
            btn.config(bg=self.C_BG, fg=self.C_TEXT_SECONDARY, activebackground=self.C_BUTTON_HOVER, activeforeground=self.C_TEXT_PRIMARY)

        # Placeholder Entry
        self.ai_prompt_entry.update_colors(bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, insert_bg=self.C_TEXT_PRIMARY, placeholder_color=self.C_TEXT_SECONDARY)

        # Settings Panel
        for widget in self.settings_frame.winfo_children():
            if isinstance(widget, tk.Label):
                widget.config(bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY)
            elif isinstance(widget, tk.Frame): # preset_frame, tips_frame
                widget.config(bg=self.C_WIDGET_BG)
                for sub_widget in widget.winfo_children():
                     if isinstance(sub_widget, tk.Label):
                        sub_widget.config(bg=self.C_WIDGET_BG, fg=self.C_TEXT_PRIMARY if sub_widget.cget('font').endswith('bold') else self.C_TEXT_SECONDARY)
                     elif isinstance(sub_widget, tk.Button):
                        sub_widget.config(bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, activebackground=self.C_BUTTON_HOVER)

        self.persona_text.config(bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, insertbackground=self.C_TEXT_PRIMARY)
        
        # Theme toggle button text
        if theme_name == "dark":
            self.theme_button.config(text="☀️ Light", bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, activebackground=self.C_BUTTON_HOVER)
        else:
            self.theme_button.config(text="🌙 Dark", bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, activebackground=self.C_BUTTON_HOVER)

        # Magic Prompts
        for widget in self.magic_prompts_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(bg=self.C_WIDGET_BG, fg=self.C_TEXT_SECONDARY, activebackground=self.C_BUTTON_HOVER, activeforeground=self.C_TEXT_PRIMARY)

        # 5. Re-style all TTK widgets
        self.setup_ttk_styles()

        # 6. Rebuild chat display to apply new bubble colors
        self.rebuild_chat_display()

        # ---- HOTKEY ACTIONS ----

    def _move_window(self, dx=0, dy=0):
        """Moves the window by a given delta x and delta y."""
        new_x = self.root.winfo_x() + dx
        new_y = self.root.winfo_y() + dy
        self.root.geometry(f"+{new_x}+{new_y}")

    def increase_opacity(self):
        """Increases window opacity by a step via hotkey."""
        current_opacity = self.opacity_var.get()
        new_opacity = min(round(current_opacity + 0.05, 2), 1.0)
        if current_opacity != new_opacity:
            self.opacity_var.set(new_opacity)
            self._on_opacity_change(new_opacity) # Manually call the update method
            self.show_feedback(f"Opacity: {int(new_opacity * 100)}%")

    def decrease_opacity(self):
        """Decreases window opacity by a step via hotkey."""
        current_opacity = self.opacity_var.get()
        new_opacity = max(round(current_opacity - 0.05, 2), 0.2)
        if current_opacity != new_opacity:
            self.opacity_var.set(new_opacity)
            self._on_opacity_change(new_opacity) # Manually call the update method
            self.show_feedback(f"Opacity: {int(new_opacity * 100)}%")

    def cycle_capture_mode(self):
        """Cycles through the available capture modes in the dropdown."""
        modes = ["No Capture", "Capture Region", "Capture Fullscreen"]
        current_mode = self.capture_mode_var.get()
        try:
            current_index = modes.index(current_mode)
            next_index = (current_index + 1) % len(modes)
            self.capture_mode_var.set(modes[next_index])
            self.show_feedback(f"Capture mode: {modes[next_index]}")
        except ValueError:
            self.capture_mode_var.set(modes[0])

    def toggle_context_sharing(self):
        """Toggles the 'share_context' setting and saves it."""
        new_state = not self.share_context.get()
        self.share_context.set(new_state)
        self._save_settings() # Save the change immediately
        feedback = "ON" if new_state else "OFF"
        self.show_feedback(f"Context sharing: {feedback}")

    def _apply_settings_changes(self):
        """Applies settings that need to take effect immediately."""
        if self.autopilot_enabled.get():
            self.autopilot.start()
        else:
            self.autopilot.stop()

    def on_autopilot_tick(self):
        """The Autopilot's 'brain'. It decides if it should speak."""
        print("[APP] Autopilot tick received!")
        time_since_last_interaction = time.time() - self.last_user_interaction_time
        if time_since_last_interaction < self.autopilot_cooldown_seconds:
            print(f"[AUTOPILOT] Tick skipped, user was active {int(time_since_last_interaction)}s ago. Resetting timer.")
            self.autopilot.reset_timer(); return

        print("[AUTOPILOT] User is idle. Fading out to start observation...")
        # CRITICAL FIX: Start the fade-out process, and tell it to call
        # our new worker function when it's finished.
        self._fade_out(callback=self._autopilot_worker)

    def _show_quit_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Quit")

        # Use system colors to avoid the app's dark theme
        try:
            # These are standard system colors in tkinter
            dialog.config(bg="SystemButtonFace")
        except tk.TclError:
            # Fallback for other systems
            dialog.config(bg="#F0F0F0")

        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog over the main window
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_w = self.root.winfo_width()
        root_h = self.root.winfo_height()
        dialog_w = 380
        dialog_h = 110
        pos_x = root_x + (root_w // 2) - (dialog_w // 2)
        pos_y = root_y + (root_h // 2) - (dialog_h // 2)
        dialog.geometry(f"{dialog_w}x{dialog_h}+{pos_x}+{pos_y}")

        result = None

        def on_save():
            nonlocal result
            result = True
            dialog.destroy()

        def on_close():
            nonlocal result
            result = False
            dialog.destroy()

        def on_cancel():
            nonlocal result
            result = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        # --- Widgets ---
        main_frame = tk.Frame(dialog, padx=10, pady=10)
        main_frame.config(bg=dialog.cget('bg'))
        main_frame.pack(expand=True, fill="both")

        # Simple message label
        message_label = tk.Label(
            main_frame,
            text="Do you want to save your chat session before quitting?",
            font=("Segoe UI", 10),
            bg=dialog.cget('bg'),
            justify="left"
        )
        message_label.pack(pady=(0, 15), anchor="center")

        # Button frame
        button_frame = tk.Frame(main_frame)
        button_frame.config(bg=dialog.cget('bg'))
        button_frame.pack(side="bottom", fill="x")

        # Spacer to push buttons to the right
        tk.Frame(button_frame, bg=dialog.cget('bg')).pack(side="left", expand=True)

        # Use standard tk.Button to avoid custom ttk styling
        save_button = tk.Button(button_frame, text="Save Chat", command=on_save, width=12, default="active")
        save_button.pack(side="left", padx=5)
        save_button.focus_set()

        dont_save_button = tk.Button(button_frame, text="Don't Save", command=on_close, width=12)
        dont_save_button.pack(side="left", padx=5)

        cancel_button = tk.Button(button_frame, text="Cancel", command=on_cancel, width=12)
        cancel_button.pack(side="left", padx=(5, 0))

        # Bind enter and escape
        dialog.bind("<Return>", lambda e: save_button.invoke())
        dialog.bind("<Escape>", lambda e: cancel_button.invoke())

        self.root.wait_window(dialog)
        return result

    def _on_close(self):
        """Handles the window close event, prompting the user to save."""
        user_choice = self._show_quit_dialog()

        if user_choice is True: # Save Chat
            # If there's no history, we can just close.
            if not self.conversation_history:
                self.root.destroy()
                return
            # If save is successful, then destroy the window.
            if self.save_chat():
                self.root.destroy()
            # If the user cancels the save dialog, we do *not* quit.

        elif user_choice is False: # Don't Save
            # The user doesn't want to save, so just quit.
            self.root.destroy()

        # else: # Cancel (user_choice is None)
            # The user cancelled the quit operation, so do nothing.
            return

    def _autopilot_worker(self):
        """
        The Autopilot's background worker for capturing context and screen.
        """
        # Get context first (the window is still visible at this point, which is fine)
        active_context = get_active_window_info()
        
        # Now, take a full-screen screenshot quietly in the background
        output_filename = "autopilot_screenshot.png"
        try:
            with mss.mss() as sct:
                img = sct.grab(sct.monitors[1])
                mss.tools.to_png(img.rgb, img.size, output=output_filename)
        except Exception as e:
            print(f"[AUTOPILOT] Screenshot failed: {e}")
            return # Abort if we can't see
        
        # --- This is the setup for Phase 3 ---
        # We create a special, "hidden" user prompt for the AI
        autopilot_prompt = "(System Observation): Based on the user's context and the attached screenshot, make a brief, friendly, and non-intrusive observation about what they might be doing. Be curious and offer help gently."
        
        # We add it to the history for the API call
        self.conversation_history.append({"role": "user", "parts": [{"text": autopilot_prompt}]})
        
            # THE CRITICAL FIX: Tell the window to reappear!
        self.root.after(0, self._fade_in)
    
        # Now, we start the stream with our hidden prompt and the new screenshot
        self.process_stream(output_filename, active_context)