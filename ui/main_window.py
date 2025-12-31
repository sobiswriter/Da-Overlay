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
from utils.theme_manager import ThemeProvider


# Note: We are no longer importing SettingsWindow
from ui.placeholder_entry import PlaceholderEntry
from utils.context_manager import get_active_window_info
from ui.region_selector import RegionSelector
from ui.message_bubble import MessageBubble
from utils import gemini_client
from utils.autopilot import Autopilot
from utils.theme_manager import ThemeProvider
from ui.components.modern_widgets import ModernButton, ModernEntry

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
        self.conversation_history = []; self.capture_mode_var = tk.StringVar(value="No Capture")
        
        # --- Settings Attributes ---
        # Using tk.StringVar for model so the dropdown updates automatically
        self.current_model = tk.StringVar() 
        self.api_key_var = tk.StringVar() # NEW: For in-app API key management
        self.current_persona = ""
        self.settings_visible = False # State for the collapsible panel
        self.share_context = tk.BooleanVar(value=True) # On by default
        self.thinking_animation_id = None # To control the "thinking" animation
        self.autopilot_enabled = tk.BooleanVar(value=False) # Off by default

        # --- NEW: Autopilot intervals are now instance attributes ---
        self.autopilot_intervals = [120, 200, 360, 260, 300] # Default values
        self.autopilot_intervals_var = tk.StringVar() # For the settings Entry widget
        self.autopilot_cooldown_seconds = 50 # Default value
        self.autopilot_cooldown_var = tk.StringVar() # For the settings Entry widget
        self.autopilot = Autopilot(self, intervals=self.autopilot_intervals) # Create an instance of our engine
        self.last_user_interaction_time = time.time()
        self.current_theme = tk.StringVar(value="dark") # 'dark' or 'light'
        self.theme_provider = ThemeProvider(self.current_theme.get())
        
        # Apply palette from theme provider
        self._apply_palette()

        # --- THE DEFINITIVE GLASS UI FOUNDATION ---
        self.font_family = "Segoe UI"
        self.TRANSPARENT_COLOR = "#abcdef" # A magic, invisible color
        self.BG_COLOR = self.C_BG # This will be updated by the theme manager

        # Make the window borderless and invisible
        self.root.overrideredirect(True)
        # Setting default size as per user preference
        self.root.geometry("1100x700")
        self.root.config(bg=self.TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", self.TRANSPARENT_COLOR)
        self.root.wm_attributes("-topmost", True)

        # The container that holds all our VISIBLE widgets
        self.container = tk.Frame(root, bg=self.BG_COLOR, padx=10, pady=10)
        self.container.pack(fill="both", expand=True)
        
        # Apply modern rounding to the main container
        try:
            import pywinstyles
            pywinstyles.apply_style(self.container, "rounded")
            pywinstyles.apply_style(root, "mica" if self.current_theme.get() == "dark" else "normal")
        except: pass

        # Create the opacity variable and set the initial transparency ON THE CONTAINER
        self.opacity_var = tk.DoubleVar(value=0.85)
        self.root.attributes("-alpha", 0.85) # Master opacity for the whole window
        # The initial call to _on_opacity_change will be removed later as it's not needed here.

        # --- Initialize the main app logic ---
        self.container.grid_columnconfigure(1, weight=1) # Main content area
        self.container.grid_rowconfigure(2, weight=1) # The CHAT area needs the weight!

        # --- Widget Creation ---
        self.create_sidebar() # NEW: Professional Sidebar
        self.create_control_bar_widgets()
        self.create_magic_prompts_bar()
        self.create_response_area_widgets()
        self.create_settings_panel() # Create the hidden settings panel (moved to end for Z-order)

        self._load_settings() # Load settings (including theme) on startup
        self._apply_theme() # Apply the loaded theme
        self._apply_settings_changes() # Start Autopilot if it's enabled on launch
        # At the end of the __init__ method
        self.last_feedback_bubble = None # To keep a reference to the temporary message
        self.feedback_timer_id = None    # To manage the auto-hide timer

        # --- Drag Logic Binding ---
        self.control_bar.bind("<ButtonPress-1>", self._on_press)
        self.control_bar.bind("<B1-Motion>", self._on_drag)

        # --- NEW: Resize Logic ---
        self.resize_grip = tk.Label(self.container, text="◢", bg=self.C_WIDGET_BG, fg=self.C_TEXT_SECONDARY, cursor="bottom_right_corner")
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se")
        self.resize_grip.bind("<ButtonPress-1>", self._on_resize_press)
        self.resize_grip.bind("<B1-Motion>", self._on_resize_motion)

        # --- NEW: Graceful Exit --- 
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_palette(self):
        """Maps ThemeProvider palette to instance attributes for backward compatibility."""
        p = self.theme_provider.get_palette()
        self.C_BG = p["C_BG"]
        self.C_WIDGET_BG = p["C_CARD"]
        self.C_INPUT_BG = p["C_INPUT"]
        self.C_TEXT_PRIMARY = p["C_TEXT_PRIMARY"]
        self.C_TEXT_SECONDARY = p["C_TEXT_SECONDARY"]
        self.C_ACCENT = p["C_ACCENT"]
        self.C_ACCENT_HOVER = p["C_ACCENT_HOVER"]
        self.C_BORDER = p["C_BORDER"]
        self.C_SIDEBAR = p["C_SIDEBAR"]
        self.C_SUCCESS = p["C_SUCCESS"]
        self.C_ERROR = p["C_ERROR"]
        self.C_BUTTON_HOVER = p["C_BUTTON_HOVER"]
        self.BG_COLOR = self.C_BG

    def create_sidebar(self):
        """Creates a professional vertical navigation sidebar."""
        self.sidebar = tk.Frame(self.container, bg=self.theme_provider.get_palette()["C_SIDEBAR"], width=60)
        self.sidebar.grid(row=0, column=0, rowspan=4, sticky="ns", padx=(0, 10))
        self.sidebar.grid_propagate(False)

        # Sidebar Icons (Placeholder text for now, can be replaced with actual icons)
        actions = [
            ("⚙️", self.toggle_settings_panel, "Settings"),
            ("📷", self.cycle_capture_mode, "Capture"),
            ("🤖", self._toggle_autopilot_ui, "Autopilot"),
            ("🔗", self.toggle_context_sharing, "Share Context"),
            ("💾", self.save_chat, "Save Chat"),
            ("📂", self.load_chat, "Load Chat"),
            ("🧹", self.clear_chat, "Clear")
        ]

        for i, (icon, cmd, tooltip) in enumerate(actions):
            btn = tk.Button(self.sidebar, text=icon, font=(self.font_family, 14),
                            command=cmd, bg=self.sidebar["bg"], fg=self.C_TEXT_SECONDARY,
                            activebackground=self.C_ACCENT, activeforeground="white",
                            bd=0, relief="flat", padx=10, pady=15)
            btn.pack(side="top", fill="x")
            try:
                import pywinstyles
                pywinstyles.apply_style(btn, "rounded")
            except: pass
            # Hover effect
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg=self.C_ACCENT))
            btn.bind("<Leave>", lambda e, b=btn: b.config(fg=self.C_TEXT_SECONDARY))

    def _toggle_autopilot_ui(self):
        self.autopilot_enabled.set(not self.autopilot_enabled.get())
        self._apply_settings_changes() # Immediate effect
        self._save_settings() # Persist
        status = "Enabled" if self.autopilot_enabled.get() else "Disabled"
        self.show_feedback(f"Autopilot {status}")
    
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

        # Configure Entry
        self.style.configure('TEntry', 
                             fieldbackground=self.C_INPUT_BG,
                             background=self.C_INPUT_BG,
                             foreground=self.C_TEXT_PRIMARY,
                             insertcolor=self.C_TEXT_PRIMARY,
                             bordercolor=self.C_BORDER,
                             lightcolor=self.C_BORDER,
                             darkcolor=self.C_BORDER)

        # Configure Main Action Button
        self.style.configure('TButton', background=self.C_ACCENT, foreground="white", font=(self.font_family, 10, 'bold'), relief='flat', padding=6, borderwidth=0)
        self.style.map('TButton', background=[('active', self.C_ACCENT_HOVER)])
    
    def _on_opacity_change(self, value):
        """Updates the window's master opacity."""
        self.root.attributes("-alpha", float(value))

    def create_control_bar_widgets(self):
        """The Smart Top Bar containing the main prompt and branding."""
        self.control_bar = tk.Frame(self.container, bg=self.BG_COLOR)
        self.control_bar.grid(row=0, column=1, sticky="ew", pady=(0, 10))
        self.control_bar.grid_columnconfigure(0, weight=1)

        # Smart Prompt Container
        self.prompt_container = tk.Frame(self.control_bar, bg=self.C_INPUT_BG, padx=5, pady=2,
                                         highlightthickness=1, highlightbackground=self.C_BORDER)
        self.prompt_container.grid(row=0, column=0, sticky="ew")
        try:
            import pywinstyles
            pywinstyles.apply_style(self.prompt_container, "rounded")
        except: pass
        
        self.user_input = tk.Entry(self.prompt_container, font=(self.font_family, 12),
                                  bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY,
                                  insertbackground=self.C_TEXT_PRIMARY, bd=0, relief="flat")
        self.user_input.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        self.user_input.bind("<Return>", self.on_user_submit)
        
        # Branding / Title in the bar
        self.branding_label = tk.Label(self.control_bar, text="Overlay Cutex", font=(self.font_family, 10, "bold"),
                                      bg=self.BG_COLOR, fg=self.C_ACCENT)
        self.branding_label.grid(row=0, column=1, padx=10)
    def create_magic_prompts_bar(self):
        """Minimal horizontal bar for quick actions or status."""
        self.magic_bar = tk.Frame(self.container, bg=self.BG_COLOR)
        self.magic_bar.grid(row=1, column=1, sticky="w", pady=(0, 10), padx=5)
        
        # Capture Mode Switcher (Sleeker design)
        self.mode_btn = tk.Button(self.magic_bar, textvariable=self.capture_mode_var,
                                  font=(self.font_family, 9), bg=self.C_ACCENT, fg="white",
                                  command=self.cycle_capture_mode, relief="flat", padx=15, pady=4,
                                  activebackground=self.C_ACCENT_HOVER, activeforeground="white")
        self.mode_btn.pack(side="left")
        
        # Add a subtle separator or status text here if needed
        self.status_label = tk.Label(self.magic_bar, text="Ready", font=(self.font_family, 9),
                                    bg=self.BG_COLOR, fg=self.C_TEXT_SECONDARY)
        self.status_label.pack(side="left", padx=15)

    def create_settings_panel(self):
        """Redesigning the settings panel as a professional two-column dashboard."""
        self.settings_frame = tk.Frame(self.container, bg=self.C_SIDEBAR, 
                                      highlightthickness=1, highlightbackground=self.C_BORDER)
        # Wider but shorter for a dashboard feel
        self.settings_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.85)
        self.settings_frame.place_forget()

        # Canvas for scrollback if needed, but designed for 1-page view
        self.settings_canvas = tk.Canvas(self.settings_frame, bg=self.C_SIDEBAR, highlightthickness=0, bd=0)
        self.settings_scrollbar = ttk.Scrollbar(self.settings_frame, orient="vertical", command=self.settings_canvas.yview)
        self.settings_inner = tk.Frame(self.settings_canvas, bg=self.C_SIDEBAR, padx=30, pady=25)
        
        self.settings_inner.bind("<Configure>", lambda e: self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all")))
        self.settings_canvas_window = self.settings_canvas.create_window((0, 0), window=self.settings_inner, anchor="nw") 
        self.settings_canvas.configure(yscrollcommand=self.settings_scrollbar.set)
        self.settings_canvas.bind("<Configure>", self._on_settings_canvas_configure)
        
        self.settings_canvas.pack(side="left", fill="both", expand=True)
        self.settings_scrollbar.pack(side="right", fill="y")
        
        try:
            import pywinstyles
            pywinstyles.apply_style(self.settings_frame, "rounded")
        except: pass

        # Title
        tk.Label(self.settings_inner, text="CONTROL DASHBOARD", font=(self.font_family, 18, "bold"), 
                 bg=self.C_SIDEBAR, fg=self.C_ACCENT).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))

        # --- LEFT COLUMN: AI CONFIG ---
        left_col = tk.Frame(self.settings_inner, bg=self.C_SIDEBAR)
        left_col.grid(row=1, column=0, sticky="nsew", padx=(0, 40)) # More padding for breathing room

        tk.Label(left_col, text="AI CORE", font=(self.font_family, 11, "bold"), bg=self.C_SIDEBAR, fg=self.C_ACCENT).pack(anchor="w", pady=(0, 10))

        tk.Label(left_col, text="Gemini Model:", font=(self.font_family, 10, 'bold'), 
                 bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY).pack(anchor="w")
        models = ["gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash-preview", "gemini-2.5-flash-lite"]
        self.model_dropdown = ttk.Combobox(left_col, textvariable=self.current_model, values=models, state="readonly")
        self.model_dropdown.pack(fill="x", pady=(5, 10))

        tk.Label(left_col, text="API Key:", font=(self.font_family, 10, 'bold'), 
                 bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY).pack(anchor="w")
        self.api_key_entry = ttk.Entry(left_col, textvariable=self.api_key_var, show="*")
        self.api_key_entry.pack(fill="x", pady=(5, 15))

        tk.Label(left_col, text="Persona Presets:", font=(self.font_family, 10, 'bold'), 
                 bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY).pack(anchor="w")
        self.preset_frame = tk.Frame(left_col, bg=self.C_SIDEBAR)
        self.preset_frame.pack(fill="x", pady=5)
        for i, key in enumerate(PERSONA_PRESETS):
            btn = tk.Button(self.preset_frame, text=key, font=(self.font_family, 8),
                            command=lambda p=key: self._set_persona(p), 
                            bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, 
                            activebackground=self.C_ACCENT, activeforeground="white",
                            relief="flat", bd=0, padx=8, pady=4)
            btn.grid(row=i//3, column=i%3, padx=2, pady=2, sticky="ew")
            try: pywinstyles.apply_style(btn, "rounded")
            except: pass

        tk.Label(left_col, text="Custom Persona Instructions:", font=(self.font_family, 10, 'bold'), 
                 bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY).pack(anchor="w", pady=(10, 0))
        self.persona_text = tk.Text(left_col, height=3, font=(self.font_family, 9), 
                                   relief="flat", bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, 
                                   insertbackground=self.C_TEXT_PRIMARY, padx=10, pady=10)
        self.persona_text.pack(fill="x", pady=5)

        # --- RIGHT COLUMN: APP & SHORTCUTS ---
        right_col = tk.Frame(self.settings_inner, bg=self.C_SIDEBAR)
        right_col.grid(row=1, column=1, sticky="nsew")

        # Shortcuts Guide (Compact)
        tk.Label(right_col, text="QUICK SHORTCUTS", font=(self.font_family, 11, "bold"), bg=self.C_SIDEBAR, fg=self.C_ACCENT).pack(anchor="w", pady=(0, 10))
        shortcuts_list = [
            ("Alt + X", "Show/Hide UI"), ("Alt + A", "Focus Chat"),
            ("Alt + 0", "Capture Mode"), ("Alt + D", "Themes"),
            ("Alt + 5", "Context Sync"), ("Alt + W/S", "Opacity")
        ]
        sc_frame = tk.Frame(right_col, bg=self.C_SIDEBAR)
        sc_frame.pack(fill="x", pady=(0, 15))
        for i, (k, d) in enumerate(shortcuts_list):
            f = tk.Frame(sc_frame, bg=self.C_SIDEBAR)
            f.pack(fill="x", pady=1)
            tk.Label(f, text=k, font=(self.font_family, 9, "bold"), bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
            tk.Label(f, text=d, font=(self.font_family, 9), bg=self.C_SIDEBAR, fg=self.C_TEXT_SECONDARY).pack(side="left")

        # Autopilot Section
        tk.Label(right_col, text="AUTOPILOT ENGINE", font=(self.font_family, 10, "bold"), bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY).pack(anchor="w")
        auto_grid = tk.Frame(right_col, bg=self.C_SIDEBAR)
        auto_grid.pack(fill="x", pady=5)
        tk.Label(auto_grid, text="Intervals (s):", bg=self.C_SIDEBAR, fg=self.C_TEXT_SECONDARY, font=(self.font_family, 9)).grid(row=0, column=0, sticky="w")
        self.autopilot_intervals_entry = ttk.Entry(auto_grid, textvariable=self.autopilot_intervals_var, width=15)
        self.autopilot_intervals_entry.grid(row=0, column=1, padx=5, pady=2)
        tk.Label(auto_grid, text="Cooldown:", bg=self.C_SIDEBAR, fg=self.C_TEXT_SECONDARY, font=(self.font_family, 9)).grid(row=1, column=0, sticky="w")
        self.autopilot_cooldown_entry = ttk.Entry(auto_grid, textvariable=self.autopilot_cooldown_var, width=15)
        self.autopilot_cooldown_entry.grid(row=1, column=1, padx=5, pady=2)

        # Appearance & Misc
        tk.Label(right_col, text="VISUALS", font=(self.font_family, 10, "bold"), bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY).pack(anchor="w", pady=(15, 5))
        self.opacity_slider = ttk.Scale(right_col, from_=0.2, to=1.0, orient="horizontal", variable=self.opacity_var, command=self._on_opacity_change)
        self.opacity_slider.pack(fill="x", pady=5)
        
        misc_frame = tk.Frame(right_col, bg=self.C_SIDEBAR)
        misc_frame.pack(fill="x", pady=10)
        self.theme_button = tk.Button(misc_frame, text="Switch Theme", command=self._toggle_theme, 
                                     bg=self.C_ACCENT, fg="white", font=(self.font_family, 9, "bold"),
                                     relief="flat", padx=15, pady=6)
        self.theme_button.pack(side="left")
        try: pywinstyles.apply_style(self.theme_button, "rounded")
        except: pass
        
        self.share_ctx_check = tk.Checkbutton(misc_frame, text="Sync Context", variable=self.share_context,
                                             bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY, selectcolor=self.C_SIDEBAR,
                                             activebackground=self.C_SIDEBAR, activeforeground=self.C_ACCENT,
                                             font=(self.font_family, 9))
        self.share_ctx_check.pack(side="left", padx=15)

        # Save/Close Actions
        btn_frame = tk.Frame(self.settings_inner, bg=self.C_SIDEBAR)
        btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(20, 0))
        
        ttk.Button(btn_frame, text="SAVE CONFIGURATION", command=self.update_settings).pack(side="right", padx=10)
        close_btn = tk.Button(btn_frame, text="CLOSE", command=self.toggle_settings_panel, bg=self.C_INPUT_BG, fg=self.C_TEXT_SECONDARY, 
                  relief="flat", bd=0, padx=20, pady=8)
        close_btn.pack(side="right")
        try: pywinstyles.apply_style(close_btn, "rounded")
        except: pass

    def toggle_settings_panel(self):
        if self.settings_visible:
            self.settings_frame.place_forget() # Use place_forget for place() managed widgets
        else:
            self.settings_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.8) # Use place()
            self.settings_frame.lift() # Ensure it stays on top
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
                self.current_model.set(settings.get("model", "models/gemini-flash-latest"))
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
            self.current_model.set("models/gemini-flash-lite-latest")
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
        """Forces focus on the main Smart Bar input."""
        self.user_input.focus_set()
    # PRESERVED: Your clear_chat method
    def clear_chat(self, feedback=True):
        self.conversation_history = [];
        for widget in self.chat_frame.winfo_children(): widget.destroy()
        if feedback: self.show_feedback("Chat cleared!")

    def populate_prompt_entry(self, prompt_text):
        """Standard way to fill the main input from presets."""
        self.user_input.delete(0, tk.END)
        self.user_input.insert(0, prompt_text)
        self.user_input.focus_set()
    
    def create_response_area_widgets(self):
        """The main conversation area, now using column 1."""
        self.response_container = tk.Frame(self.container, bg=self.BG_COLOR)
        self.response_container.grid(row=2, column=1, sticky="nsew") # Row 2 in column 1
        self.response_container.grid_rowconfigure(0, weight=1)
        self.response_container.grid_columnconfigure(0, weight=1)

        self.chat_canvas = tk.Canvas(self.response_container, bg=self.BG_COLOR, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.response_container, orient="vertical", command=self.chat_canvas.yview)
        
        self.chat_frame = tk.Frame(self.chat_canvas, bg=self.BG_COLOR)
        self.chat_frame.bind("<Configure>", lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))
        
        self.canvas_window = self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")
        self.chat_canvas.bind("<Configure>", self._on_canvas_configure)

        self.chat_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.chat_canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        # Mousewheel support
        self.chat_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _on_settings_canvas_configure(self, event):
        """Syncs settings_inner width with settings_canvas."""
        if hasattr(self, 'settings_canvas_window'):
            self.settings_canvas.itemconfig(self.settings_canvas_window, width=event.width)

    def _on_canvas_configure(self, event):
        """Adjusts the width of the chat_frame inside the canvas when the canvas resizes."""
        # Use a small offset to prevent horizontal scrollbars from appearing
        canvas_width = event.width - 4
        self.chat_canvas.itemconfig(self.canvas_window, width=canvas_width)

    def _on_mousewheel(self, event):
        """Handles mousewheel scrolling for the chat canvas."""
        self.chat_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def scroll_to_bottom(self): self.chat_canvas.update_idletasks(); self.chat_canvas.yview_moveto(1.0)
    
    def show_message(self, message_data, role=None, is_rebuilding=False):
        """Displays a message bubble. Now handles both raw strings and data dicts."""
        if isinstance(message_data, str):
            message_data = {"role": role or "system", "parts": [{"text": message_data}]}
        
        if not is_rebuilding:
            self.conversation_history.append(message_data)
        
        # Create and add the bubble
        bubble = MessageBubble(self.chat_frame, message_data, self)
        # Ensure it fills the entire width of the chat_frame
        bubble.pack(fill="x", expand=True, padx=20, pady=10)
        
        if message_data.get("role") == "model" and message_data["parts"][0]["text"] != "...":
            bubble.add_copy_button()
        
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
                self.api_key_var.get().strip(), 
                history_for_api, 
                self.current_model.get().strip() or "models/gemini-flash-latest", 
                self.current_persona, 
                image_path, 
                active_context
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
        self.root.clipboard_clear(); self.root.clipboard_append(text); original_text = self.user_input.get()
        self.user_input.delete(0, tk.END); self.user_input.insert(0, "Copied!"); self.root.after(2000, lambda: (self.user_input.delete(0, tk.END), self.user_input.insert(0, original_text)))
    
    # run_chat_interaction is now replaced by on_user_submit
    
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

    def on_user_submit(self, event=None):
        """Common entry point for both the Smart Bar and Hotkeys."""
        self.last_user_interaction_time = time.time()
        self.autopilot.reset_timer()

        user_prompt = self.user_input.get().strip()
        if not user_prompt: return
        
        self.show_message(user_prompt)
        self.user_input.delete(0, tk.END)
        self.root.after(10, self._start_interaction_flow)

    def _toggle_theme(self):
        """Switches between themes using the ThemeProvider."""
        new_theme, palette = self.theme_provider.switch_theme()
        self.current_theme.set(new_theme)
        self._apply_palette()
        self._apply_theme()
        self._save_settings()
        self.show_feedback(f"Theme: {new_theme.capitalize()}")

    def _apply_theme(self):
        """Applies the current theme's visual properties across all widgets."""
        p = self.theme_provider.get_palette()
        
        # Update main container and root
        self.container.config(bg=self.C_BG)
        self.root.config(bg=self.TRANSPARENT_COLOR)
        
        # Windows Specific Styling
        if sys.platform == "win32" and hasattr(self, 'root'):
            try:
                import pywinstyles
                pywinstyles.apply_style(self.root, p.get("WIN_STYLE", "mica"))
            except: pass

        # Update Sidebar
        if hasattr(self, 'sidebar'):
            sidebar_bg = p["C_SIDEBAR"]
            self.sidebar.config(bg=sidebar_bg)
            for child in self.sidebar.winfo_children():
                if isinstance(child, tk.Button):
                    child.config(bg=sidebar_bg, fg=p["C_TEXT_SECONDARY"], activebackground=p["C_ACCENT"])

        # Update Control Bar
        if hasattr(self, 'control_bar'):
            self.control_bar.config(bg=self.C_BG)
            self.prompt_container.config(bg=self.C_INPUT_BG, highlightbackground=self.C_BORDER)
            self.user_input.config(bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, insertbackground=self.C_TEXT_PRIMARY)
            if hasattr(self, 'branding_label'):
                self.branding_label.config(bg=self.C_BG, fg=self.C_ACCENT)
        # Update Magic Bar
        if hasattr(self, 'magic_bar'):
            self.magic_bar.config(bg=self.C_BG)
            if hasattr(self, 'mode_btn'):
                self.mode_btn.config(bg=p["C_ACCENT"])
            if hasattr(self, 'status_label'):
                self.status_label.config(bg=self.C_BG, fg=self.C_TEXT_SECONDARY)

        # Update Settings Panel
        if hasattr(self, 'settings_frame'):
            self.settings_frame.config(bg=p["C_SIDEBAR"], highlightbackground=self.C_BORDER)
            if hasattr(self, 'settings_canvas'):
                self.settings_canvas.config(bg=p["C_SIDEBAR"])
            if hasattr(self, 'settings_inner'):
                self.settings_inner.config(bg=p["C_SIDEBAR"])
                # Recursively update labels and other widgets in settings
                self._update_widget_colors(self.settings_inner, p)
        
        # Ensure scrollable settings also scale
        if hasattr(self, 'settings_canvas') and hasattr(self, 'settings_canvas_window'):
            w = self.settings_canvas.winfo_width()
            if w > 1: # Only scale if mapped
                self.settings_canvas.itemconfig(self.settings_canvas_window, width=w)

        # Update Response area
        if hasattr(self, 'response_container'):
            self.response_container.config(bg=self.C_BG)
            self.chat_canvas.config(bg=self.C_BG)
            self.chat_frame.config(bg=self.C_BG)
            self.rebuild_chat_display()

        self.setup_ttk_styles()

    def _update_widget_colors(self, parent, p):
        """Recursively updates colors for all children of a parent widget based on theme palette."""
        is_settings = (parent == self.settings_frame or parent == self.settings_inner or parent == self.settings_canvas)
        bg_to_use = p["C_SIDEBAR"] if is_settings else parent["bg"]
        
        for child in parent.winfo_children():
            try:
                if isinstance(child, tk.Label):
                    # Check if it's a "header" label by font size/weight
                    font_info = str(child.cget("font")).lower()
                    if "bold" in font_info and ("18" in font_info or "14" in font_info):
                        child.config(bg=bg_to_use, fg=p["C_ACCENT"])
                    else:
                        fg_color = p["C_TEXT_PRIMARY"] if "bold" in font_info else p["C_TEXT_SECONDARY"]
                        child.config(bg=bg_to_use, fg=fg_color)
                elif isinstance(child, (tk.Frame, tk.Canvas)):
                    child.config(bg=bg_to_use)
                    self._update_widget_colors(child, p)
                elif isinstance(child, tk.Button):
                    text = str(child.cget("text")).upper()
                    if "SAVE" in text or "THEME" in text:
                        child.config(bg=p["C_ACCENT"], fg="white", activebackground=p["C_ACCENT_HOVER"])
                    else:
                        child.config(bg=p["C_INPUT"], fg=p["C_TEXT_PRIMARY"], activebackground=p["C_ACCENT"])
                elif isinstance(child, tk.Text):
                    child.config(bg=p["C_INPUT"], fg=p["C_TEXT_PRIMARY"], insertbackground=p["C_TEXT_PRIMARY"])
                elif isinstance(child, tk.Checkbutton):
                    child.config(bg=bg_to_use, fg=p["C_TEXT_PRIMARY"], selectcolor=bg_to_use, 
                                 activebackground=bg_to_use, activeforeground=p["C_ACCENT"])
                elif isinstance(child, ttk.Entry):
                    # ttk widgets are handled via styles, but we can nudge them
                    pass
            except:
                continue

    def rebuild_chat_display(self):
        """Clears and re-adds all message bubbles."""
        self.root.update_idletasks() # Ensure layout is settled
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
        
        history = self.conversation_history

        for msg in history:
            self.show_message(msg, is_rebuilding=True)

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