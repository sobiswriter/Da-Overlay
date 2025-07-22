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
    "Cute Girl": "You are a cute anime girl, you talk in cute style. Don't break character!",
    "S. Holmes": "You are the detective Sherlock Holmes. Address the user formally. Your responses must be based on pure logic, deduction, and keen observation. Don't break character",
    "Jeeves": "You are Jeeves, the consummate valet. You are discreet, impeccably polite, and hyper-competent. You address the user as 'sir' or 'madam' and your goal is to provide solutions with quiet, dignified efficiency. Your language is formal and precise. Don't break character.",
}
# The number of seconds the Autopilot will wait after your last interaction before speaking.
AUTOPILOT_COOLDOWN_SECONDS = 50

class OverlayApp:
    def __init__(self, root):
        self.root = root; self.api_key = os.getenv("GEMINI_API_KEY"); self.is_visible = True
        self.conversation_history = []; self.capture_mode_var = tk.StringVar(value="Capture Region")
        
        # --- Settings Attributes ---
        # Using tk.StringVar for model so the dropdown updates automatically
        self.current_model = tk.StringVar() 
        self.current_persona = ""
        self.settings_visible = False # State for the collapsible panel
        self.show_pinned_only = tk.BooleanVar(value=False)
        self.share_context = tk.BooleanVar(value=True) # On by default
        self.thinking_animation_id = None # To control the "thinking" animation
        self.autopilot_enabled = tk.BooleanVar(value=True) # On by default
        self.autopilot = Autopilot(self) # Create an instance of our engine
        self.last_user_interaction_time = time.time()

        # --- THE DEFINITIVE GLASS UI FOUNDATION ---
        self.font_family = "Segoe UI";

        # A magic, invisible color
        self.TRANSPARENT_COLOR = "#abcdef" 
        # Our beautiful, SOLID background color for the UI elements
        self.BG_COLOR = "#FFFFFF" 

        # Make the window borderless and invisible
        self.root.overrideredirect(True)
        self.root.geometry("800x600")
        self.root.config(bg=self.TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", self.TRANSPARENT_COLOR)
        self.root.wm_attributes("-topmost", True)

        # Apply the frosted glass effect to the invisible window area
        if sys.platform == "win32":
            pywinstyles.apply_style(self.root, "aero")

        # The container that holds all our VISIBLE widgets
        # We will control ITS transparency with the slider
        self.container = tk.Frame(root, bg=self.BG_COLOR, padx=10, pady=10)
        self.container.pack(fill="both", expand=True)

        # Create the opacity variable and set the initial transparency ON THE CONTAINER
        self.opacity_var = tk.DoubleVar(value=0.80)
        self.root.attributes("-alpha", 0.80) # Master opacity for the whole window
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

        self._load_settings() # Load settings on startup
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
    
    def _on_press(self, event):
        self._drag_data = {"x": event.x, "y": event.y}

    def _on_drag(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
    
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
                                                font=(self.font_family, 11), 
                                                relief="solid", bd=1, bg="#F9FAFB", 
                                                fg="#1F2937", insertbackground="#1F2937")
        self.ai_prompt_entry.grid(row=0, column=2, sticky="ew", ipady=4, padx=10)
        self.ai_prompt_entry.bind("<Return>", self.run_chat_interaction)
        
        right_frame = tk.Frame(self.control_bar, bg=self.BG_COLOR)
        right_frame.grid(row=0, column=3, sticky="e")
        
        # The settings button now toggles the panel
        settings_button = tk.Button(right_frame, text="⚙️", command=self.toggle_settings_panel, relief='flat', font=(self.font_family, 12), cursor="hand2", bg=self.BG_COLOR, fg="#6B7280", activebackground="#E5E7EB")
        settings_button.pack(side="left", padx=5)
        
        # PRESERVED: Your Load, Save, and Clear buttons
        load_button = tk.Button(right_frame, text="Load", command=self.load_chat, relief='flat', font=(self.font_family, 9), cursor="hand2", bg=self.BG_COLOR, fg="#6B7280", activebackground="#E5E7EB"); load_button.pack(side="left", padx=5)
        save_button = tk.Button(right_frame, text="Save", command=self.save_chat, relief='flat', font=(self.font_family, 9), cursor="hand2", bg=self.BG_COLOR, fg="#6B7280", activebackground="#E5E7EB"); save_button.pack(side="left", padx=5)
        clear_button = tk.Button(right_frame, text="Clear", command=self.clear_chat, relief='flat', font=(self.font_family, 9), cursor="hand2", bg=self.BG_COLOR, fg="#6B7280", activebackground="#E5E7EB"); clear_button.pack(side="left", padx=5)

    def create_settings_panel(self):
        self.settings_frame = tk.Frame(self.container, bg="#F9FAFB", bd=1, relief="solid")
        self.settings_frame.grid_columnconfigure(1, weight=1)

        tk.Label(self.settings_frame, text="Model:", font=("Segoe UI", 10, 'bold'), bg="#F9FAFB").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        models = ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-2.5-flash", "gemini-2.5-pro"]
        model_dropdown = ttk.Combobox(self.settings_frame, textvariable=self.current_model, values=models, state="readonly")
        model_dropdown.grid(row=0, column=1, sticky="ew", padx=10, pady=10)

        # --- NEW: Persona Preset Buttons ---
        preset_frame = tk.Frame(self.settings_frame, bg="#F9FAFB")
        preset_frame.grid(row=1, column=1, sticky="w", padx=10)

        for key in PERSONA_PRESETS:
            # Create a button for each key in our dictionary
            btn = tk.Button(preset_frame, text=key, font=("Segoe UI", 8),
                            command=lambda p=key: self._set_persona(p), 
                            relief="solid", bd=1, padx=4, pady=1)
            btn.pack(side="left", padx=3)

        tk.Label(self.settings_frame, text="Persona:", font=("Segoe UI", 10, 'bold'), bg="#F9FAFB").grid(row=2, column=0, sticky="nw", padx=10, pady=5)
        self.persona_text = tk.Text(self.settings_frame, height=5, font=("Segoe UI", 10), relief="solid", bd=1, wrap="word")
        self.persona_text.grid(row=2, column=1, sticky="ew", padx=10, pady=5)

        tk.Label(self.settings_frame, text="Opacity:", font=("Segoe UI", 10, 'bold'), bg="#F9FAFB").grid(row=4, column=0, sticky="w", padx=10, pady=5)
        opacity_slider = ttk.Scale(self.settings_frame, from_=0.2, to=1.0, orient="horizontal", variable=self.opacity_var, command=self._on_opacity_change)
        opacity_slider.grid(row=4, column=1, sticky="ew", padx=10, pady=5)

        # --- NEW: Tips & Hotkeys Section ---
        tips_frame = tk.Frame(self.settings_frame, bg="#F9FAFB")
        tips_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))

        tk.Label(tips_frame, text="Tips & Hotkeys:", font=("Segoe UI", 10, 'bold'), bg="#F9FAFB").pack(anchor="w")

        tips_text = (
            "1. Hey Guys, Try out our new feature: Auopilot Mode, it does what it suggest, intellegently.\n"
            "-> Along with that, here are some useful hotkeys:\n"
            "I. Move Window: Alt + Numpad (8, 4, 2, 6)\n"
            "II. Cycle Capture Mode: Alt + 0\n"
            "III. Toggle Context Sharing: Alt + 5\n"
            "IV. Focus Chat Input: Alt + a\n"
            "V. Show / Hide Window: Alt + x"
        )

        tk.Label(tips_frame, text=tips_text, font=("Segoe UI", 9), justify="left", bg="#F9FAFB").pack(anchor="w", pady=5)
        save_button = ttk.Button(self.settings_frame, text="Save Settings", command=self.update_settings)
        save_button.grid(row=6, column=1, sticky="e", padx=10, pady=10)

    def toggle_settings_panel(self):
        if self.settings_visible:
            self.settings_frame.grid_remove()
        else:
            self.settings_frame.grid(row=1, column=0, sticky="ew", pady=10, padx=5)
        self.settings_visible = not self.settings_visible

    def update_settings(self):
        self.current_persona = self.persona_text.get("1.0", "end-1c").strip()
        self._save_settings()
        self.show_feedback("Settings saved!")
        self.toggle_settings_panel()

    def _load_settings(self):
        tars_persona = DEFAULT_PERSONA # (Full text)
        try:
            with open("settings.json", 'r') as f:
                settings = json.load(f)
                self.current_model.set(settings.get("model", "gemini-2.5-flash-latest"))
                self.current_persona = settings.get("persona", tars_persona)
                # Load the new setting, defaulting to True if not found
                self.share_context.set(settings.get("share_context", True))
        except (FileNotFoundError, json.JSONDecodeError):
            self.current_model.set("gemini-2.5-flash-latest")
            self.current_persona = tars_persona
            self.share_context.set(True) # Default to on
        
        self.persona_text.delete("1.0", tk.END)
        self.persona_text.insert("1.0", self.current_persona)

    def _save_settings(self):
        settings = {
            "model": self.current_model.get(),
            "persona": self.current_persona,
            "share_context": self.share_context.get()
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
        if not self.conversation_history: messagebox.showinfo("Info", "There is nothing to save."); return
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Chat Files", "*.json"), ("All Files", "*.*")], title="Save Chat Session")
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(self.conversation_history, f, indent=4)
            self.show_feedback("Chat saved successfully!")
        except Exception as e: messagebox.showerror("Save Error", f"An error occurred while saving the file:\n{e}")
            
    # PRESERVED: Your load_chat method
    def load_chat(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON Chat Files", "*.json"), ("All Files", "*.*")], title="Load Chat Session")
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f: loaded_history = json.load(f)
            if not isinstance(loaded_history, list) or not all('role' in item and 'parts' in item for item in loaded_history): raise ValueError("Invalid chat file format.")
            self.clear_chat(feedback=False); self.conversation_history = loaded_history
            self.rebuild_chat_display()
            self.show_feedback("Chat loaded successfully!")
        except Exception as e: messagebox.showerror("Load Error", f"An error occurred while loading the file:\n{e}")
    
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
        prompts = ["Summarize", "Explain Simply", "Find Action Items"];
        for i, prompt in enumerate(prompts): btn = tk.Button(self.magic_prompts_frame, text=prompt, font=(self.font_family, 8), command=lambda p=prompt: self.populate_prompt_entry(p), relief="solid", bd=1, padx=5, pady=2, bg="#F3F4F6", fg="#4B5563"); btn.grid(row=0, column=i, padx=3)

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
        chat_container = tk.Frame(self.container, bg="#E5E7EB", bd=1, relief="solid")
        chat_container.grid(row=3, column=0, sticky="nsew", pady=(5, 0))
        chat_container.grid_rowconfigure(0, weight=1); chat_container.grid_columnconfigure(0, weight=1)
        self.chat_canvas = tk.Canvas(chat_container, bg=self.BG_COLOR, highlightthickness=0); self.scrollbar = ttk.Scrollbar(chat_container, orient="vertical", command=self.chat_canvas.yview)
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
        # --- Create the AI's message object and ADD IT to the history right away ---
        ai_message_data = {"role": "model", "parts": [{"text": "..."}]}
        self.conversation_history.append(ai_message_data)
        
        # Show a bubble for the message object we just added to the history
        loading_bubble = self.show_message(ai_message_data, is_rebuilding=True)
        
        # Start the "thinking" animation in our new bubble
        if self.thinking_animation_id:
            self.root.after_cancel(self.thinking_animation_id)
        self.thinking_animation_id = self.root.after(10, self._thinking_animation, loading_bubble)

        # --- The Streaming Worker ---
        def stream_worker():
            streamed_text_buffer = ""
            response_stream = gemini_client.get_gemini_response_stream(
                self.api_key, self.conversation_history, self.current_model.get(), self.current_persona, image_path, active_context
            )
            
            is_first_chunk = True
            for chunk in response_stream:
                if is_first_chunk:
                    # On first chunk, stop the animation and clear the bubble
                    if self.thinking_animation_id:
                        self.root.after_cancel(self.thinking_animation_id)
                        self.thinking_animation_id = None
                    self.root.after(0, loading_bubble.set_text, "")
                    is_first_chunk = False

                streamed_text_buffer += chunk
                # Update the bubble on screen in real-time ("typing" effect)
                self.root.after(0, loading_bubble.set_text, streamed_text_buffer)
            
            # --- Finalization on the Main Thread ---
            def finalize():
                # Update the message object IN THE HISTORY with the final text
                ai_message_data["parts"][0]["text"] = streamed_text_buffer
                # Add the copy button to the now-complete bubble
                if streamed_text_buffer and not streamed_text_buffer.lower().startswith("error"):
                    loading_bubble.add_copy_button()
                self.scroll_to_bottom()

            self.root.after(0, finalize)

        # Run the worker in a separate thread so it doesn't freeze the UI
        threading.Thread(target=stream_worker, daemon=True).start()

    

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

    def _fade_in(self):
        """Fades the window back in."""
        self.is_visible = True # State is now 'visible'
        try:
            # Ensure alpha is reset before deiconifying
            self.root.attributes("-alpha", 0.0)
            self.root.deiconify()
            def animate_in():
                current_alpha = self.root.attributes("-alpha")
                if current_alpha < 1.0:
                    new_alpha = current_alpha + 0.1
                    self.root.attributes("-alpha", new_alpha)
                    self.root.after(15, animate_in)
            animate_in()
        except tk.TclError:
            self.root.deiconify()
    
    def _clear_feedback_bubble(self):
        """Hides the temporary feedback bubble."""
        if self.last_feedback_bubble:
            self.last_feedback_bubble.destroy()
            self.last_feedback_bubble = None
        if self.feedback_timer_id:
            self.root.after_cancel(self.feedback_timer_id)
            self.feedback_timer_id = None

        # ---- HOTKEY ACTIONS ----

    def move_window_up(self, distance=30):
        """Moves the window up by a set distance."""
        new_y = self.root.winfo_y() - distance
        self.root.geometry(f"+{self.root.winfo_x()}+{new_y}")

    def move_window_left(self, distance=30):
        """Moves the window left by a set distance."""
        new_x = self.root.winfo_x() - distance
        self.root.geometry(f"+{new_x}+{self.root.winfo_y()}")

    def move_window_down(self, distance=30):
        """Moves the window down by a set distance."""
        new_y = self.root.winfo_y() + distance
        self.root.geometry(f"+{self.root.winfo_x()}+{new_y}")

    def move_window_right(self, distance=30):
        """Moves the window right by a set distance."""
        new_x = self.root.winfo_x() + distance
        self.root.geometry(f"+{new_x}+{self.root.winfo_y()}")

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
        if time_since_last_interaction < AUTOPILOT_COOLDOWN_SECONDS:
            print(f"[AUTOPILOT] Tick skipped, user was active {int(time_since_last_interaction)}s ago. Resetting timer.")
            self.autopilot.reset_timer(); return

        print("[AUTOPILOT] User is idle. Fading out to start observation...")
        # CRITICAL FIX: Start the fade-out process, and tell it to call
        # our new worker function when it's finished.
        self._fade_out(callback=self._autopilot_worker)

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