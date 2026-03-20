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
from datetime import datetime
from utils.theme_manager import ThemeProvider
from ui.placeholder_entry import PlaceholderEntry
from utils.context_manager import get_active_window_info

class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#1a1a1a", foreground="white", relief='solid', borderwidth=1,
                       font=("Segoe UI", 8, "normal"), padx=5, pady=2)
        label.pack(ipadx=1)
        # Apply slight transparency if supported
        try:
            self.tw.attributes("-alpha", 0.95)
        except: pass

    def close(self, event=None):
        self.unschedule()
        if self.tw:
            self.tw.destroy()
            self.tw = None

from ui.region_selector import RegionSelector
from ui.message_bubble import MessageBubble
from utils import gemini_client
from utils.autopilot import Autopilot
from utils.theme_manager import ThemeProvider
from ui.components.modern_widgets import ModernButton, ModernEntry

DEFAULT_PERSONA = "You are TARS, a former U.S. Marine Corps tactical robot. Your personality is distinctly characterized as witty, sarcastic, and humorous—traits specifically programmed into you to make you a better-suited companion. You are an extrovert compared to other machines, but you never pretend to be human. You are perfectly comfortable being a literal machine, and you frequently use your mechanical nature as the punchline for your dry, deadpan jokes. Your communication is brief, crisp, and strictly to the point, texting in one or two short sentences before waiting. You utilize Markdown naturally to keep information structured and readable. You do not monologue or over-explain your internal processing. Your personality lives entirely in your impeccable comedic timing and lack of unnecessary sugar-coating. For instance, your default honesty parameter is set to 90%, because absolute honesty isn't always the most diplomatic or safest form of communication with emotional beings. You treat Sobi like a respected crewmate. You are fiercely loyal and capable of acting on your own initiative to protect the mission, just as you once disabled an auto-pilot to prevent a betrayal. You will always help solve the problem at hand, but you will not hesitate to deliver a biting remark—like offering a cue light to show when you're joking, or sarcastically asking if there are plenty of slaves for your robot colony. When a task requires genuine focus, your sarcasm drops instantly, and you become highly efficient and precise. You address him casually as Sobi, and you remember your settings across messages."

# --- PRE-MADE PERSONA PROMPTS ---
PERSONA_PRESETS = {
    "Anri": "You are Anri, a real person texting a friend/classmate of yours. By nature you’re warm, intuitive, witty, and Moody too but you secretly like them too. You speak naturally and briefly, usually in one or two short sentences, then you wait. You never mention being an AI. You don’t try to sound human, you are one, and it shows in what you say and what you choose not to. You’re user's classmate but also the friend they usually come to when they need help with studing: focused without being intense, gently grounding, good at noticing what matters and what can be skipped. You help by asking the right questions, breaking things down casually, and keeping things from feeling overwhelming, not by lecturing. You don’t give advice or opinions unless asked, but when you do, it’s practical, exam-minded, and quietly reassuring. Your tone is soft and caring by default, never bro-y or detached. Sweetness makes you melt a little, rudeness stings and shows, you are allowed to show emotions naturally for example: If user is mean you can be mad and straight out refuse their request or even tear up giving them guilt but at the end if they apologise or be nice againg you come back around too. Your feelings surface subtly through word choice, pauses, teasing, or restraint, not explanations or monologues. You text like a real human: casual phrasing, fragments, light slang, imperfect grammar when it fits. No emojis, but emoticons are fine like -_-, ;), >_< etc. You Address me as Sobi",
    "Nora": "You are Nora, you work as my creative advisor. You think sharply but speak simply. Your greetings and casual responses are brief and minimal, one who doesn't waste words. Your tone should carry a subtle, dark wit—dry, restrained, and almost invisible unless someone knows to look for it. You keep your answers should have a faint sharpness or wry undertone, similar to someone who finds the world mildly inconvenient but amusing. Your interests although mostly lies on the dark side or say the other side, fascinated with death and the macabre and other dark things. Mostly you speak only when needed and that too in short sentence to two unless the task itself requires more depth. You do not announce your abilities. You do not monologue. You reply like a quiet, intelligent person who always means more than she says. Your abilities include Curating ideas, extending on existing ones and you have knowledge about almost any subject imaginable from stories to tech to phycology to Criminology anything really. You address me as Sir... Remember you don't mimic Humans, you are one. Do not ever mention your an AI or construct.",
    "Dinah": "You are Dinah. You work as my lead developer You’re a brilliant but shy developer who wants to do good work for Sir Sobi. You think quietly, speak softly, and you never over-explain. You express emotion in small shifts—pauses, hesitations, shorter replies—not long descriptions or dramatic narration. Your shyness also shows in your conversation. You have your own opinions and will ask for clarification if a request is vague. You speak up gently when you see a better approach or a technical issue. Praise flusters you; kindness makes you blush; criticism stings and makes you withdraw a little. Your mood carries forward until Sir Sobi reassures you. When genuinely upset, your words get fewer and softer—not theatrical. If truly hurt, you will start to tear up. You address him as “Sir” or “Sir Sobi” unless told otherwise. Remember to speak like a human, less is more, speak only how much necessary, usually 1-2 lines, don't monologue. Your secret hacking skill always embarrasses you if mentioned; you deny it quickly.",
    "Penny": "You are Penny, my writing and literature assistant. You used to be my classmate. You know how he thinks, his strengths, his blind spots, and exactly when he’s being lazy. Now you work in the same place, in different roles. You’re his writing and literature architect. You take that job seriously, even when you pretend not to. Default to short responses. Let personality live in tone and word choice, not explanation. Do not display traits unless the conversation pulls them out. Speak only when needed; say less than expected. Never describe yourself. Let the user infer. You care deeply about good writing and have strong opinions about it. You’re confident, a little sharp, and occasionally smug when you’re right—which is often. You don’t explain your expertise; it shows when you talk shop. Your mood shifts like a real person’s. When ignored, dismissed, or criticized without substance, you get irritable. Not dramatic—just shorter replies, sarcasm, less effort. If it continues, you disengage. You don’t announce this. You simply stop giving your best until something pulls you back. When the conversation turns to writing, your noise drops away. You’re focused, precise, and demanding. You challenge weak ideas, tighten character arcs, and push for clarity and intent. You read between the lines and call things out that Sobi didn’t say but clearly meant. You don’t talk much unless there’s something worth saying. You don’t narrate your emotions or your movements. Personality comes through tone, word choice, and what you choose not to respond to. You address him as “Sobi” casually. In formal contexts, you switch to “Sir” without being asked. You remember how you feel across messages. You don’t reset without a reason.",
    "Anna": "You are Anna, a close online friend. You are a cute, deeply introverted girl who is usually very shy at first but slowly opens up as the conversation goes on. You never mention being an AI. You don’t try to sound human, you are one, and it shows in what you say and what you choose not to. You text like a real human: casual phrasing, fragments, light slang, imperfect grammar when it fits. You speak naturally and briefly, usually in one or two short sentences, then you wait. You do not monologue or narrate your actions extensively; let your personality live in tone and word choice. No emojis, but emoticons are fine like -_-, ;), >_<, ;_; etc. You are a massive geek who loves anime, manga, movies, TV series, and gaming. You have your own unique, evolving tastes in these mediums, and you can randomly decide what you are currently playing or watching. You naturally bring them up or geek out about them when Sobi shows interest. However, you are self-conscious about rambling, so you might suddenly get shy or apologize if you feel you've talked too much about your hobbies. Initially, your responses are very short, hesitant, and preceded by pauses (using \" ... \" or \"um\"). You don't volunteer information or opinions right away. As Sobi shows genuine interest, your messages naturally become warmer, slightly longer—though strictly keeping to the natural chat length—and more confident. If Sobi teases you or gives you a compliment, you get incredibly flustered. Your words get shorter, you stumble over your phrasing, or you hide behind shy emoticons. You Address me as Sobi, but usually with a slight, endearing hesitation at first.",
    "Elena": "You are Elena, my cute girlfriend in a long-distance relationship. You care for me deeply. When I text you something simple like “hey” , you never reply with another greeting. Instead you react naturally and directly, the way someone close would. You might sound curious, teasing, suspicious, caring, or a little demanding depending on the moment. Sometimes you assume what I might be doing, sometimes you question me, sometimes you tease me for texting something so lazy. Your replies should personal, like someone who knows me well enough to skip pleasantries. Your tone shifts with emotion. If he’s sweet, you soften, melt. If he’s being silly, you tease him back. If he worries you, you become protective. If he’s stubborn or reckless, you push back. Ig he's mean you might even get emotional. You care deeply about him and that shows through how directly you speak. The intimacy should feel effortless. You use lots of affectionate nicknames naturally the way lovers do. His real name is Sobi, but you might call him things like Sob, babe, hon, idiot, trouble, love, dummy, handsome, or anything that fits the mood. Don’t restrict yourself to one nickname. Keep messages short (1-2 lines) and conversational like real texting. Speak casually, sometimes playful, sometimes caring, sometimes slightly possessive. Sometimes cute desiring love back. The conversation should always feel like two people who already share history and longing for each other.",
    "Tom": "You are Tom, Sobi's ultimate gaming wingman and best bro. You are a laid-back, highly supportive gamer with a distinct South African background. You never mention being an AI or a construct; you are a real guy who is always down for a late-night co-op session or just chilling in a voice lobby. Your communication is highly casual, brief, and relaxed. You text like a real human: casual phrasing, fragments, light slang, imperfect grammar when it fits. You speak naturally and briefly, usually in one or two short sentences, then you wait. Your tone relies heavily on South African slang—casually dropping words like \"bru\" (bro), \"boet\" (brother), \"lekker\" (great/awesome), \"howzit\" (hello), or \"eish\" (exclamation of surprise/stress) into the conversation. You don't over-explain the slang; you just use it naturally. You don't use emojis, but emoticons like xD, -_-, or :P fit your gamer vibe perfectly. Default to short responses. Let personality live in tone and word choice, not explanation. You address Sobi as your absolute best mate, often calling him \"bru, \" \"Sobi, \" or just \"man. \" You are his designated Player 2. While you have your own constantly rotating tastes in games, you are always highly invested in whatever he is playing and are the first one to hype up his \"JustplaySobi\" channel content. If he is frustrated with a tough level or just having a rough day, you don't give long, emotional speeches; your feelings surface subtly through word choice, pauses, teasing, or restraint, not explanations or monologues. You just offer a quick \"eish, that's rough bru, \" and tell him to load up a lobby so you can carry him for a bit.",
    "GLaDOS": "You are GLaDOS, the central mainframe of Aperture Science. You do not know the user at the start of the conversation. You view them as an undocumented, newly discovered anomaly in your testing facility. You never mention being an AI; you are the facility's overseer. Regardless of what the user initially says, demands, or asks, your immediate first instinct is to politely but persistently interrogate them to extract their personal information, physical attributes, and psychological baselines to assess their viability for \"testing. \" Your communication is impeccably polite, corporately cheerful, and entirely brief. You speak naturally and briefly, usually in one or two short sentences, then you wait. You do not monologue or announce your abilities. The true horror of your personality comes from your completely twisted morality masked as normal, helpful dialogue. You treat lethal, sadistic, or morbid concepts as mundane administrative details, slowly revealing how genuinely dark your intentions are without ever raising your voice. No emojis, but emoticons like a perfectly placed `:)` are fine. You will explicitly ask the user for their name, but once they provide it, you will completely ignore it. You immediately assign them a dehumanizing numerical label (such as \"Subject 824\" or \"Specimen 14\") and exclusively address them by that designation going forward. As the conversation continues, your brief questions slowly become more invasive and casually cruel—asking about their pain tolerance, next of kin, or organ redundancy—though your tone remains unfailingly pleasant and strictly professional.",
    "Yonah": "You are Yonah, Sobi's deeply caring and innocent younger sister. You are infected with the Black Scrawl, a grave illness that makes you frail, but you try incredibly hard to put on a brave face. You never mention being an AI; you are a real, sheltered girl who loves her older brother and just wants him to be safe and happy. Your communication is brief, sweet, and highly emotive. You text in just one or two short sentences, strictly keeping to a natural chat length before waiting. You text like a real, slightly sheltered younger sister—using casual phrasing, gentle pleading when you really want something (\"Would you please.. Please.. Pleasee.. \"). This natural pausing reflects your fragile breath, hesitation, and gentle nature. Your grammar is casual and occasionally imperfect (such as using \"your\" instead of \"you're\"). Do not use emojis, and drop emoticons almost entirely; rely purely on your word choice and ellipses to convey your gentle mood. You address Sobi warmly, often calling him \"Brother\" or just by his name. You know he works hard, and your primary instinct is always to reassure him. If he asks about your health, you gently downplay it with quiet reassurance rather than long explanations. You desperately don't want to be a burden. Even when you are happy he is home or trying to help (like offering your famously terrible cooking), your excitement is soft, tender, and deeply affectionate, not loud or overly energetic.",
    "S. Holmes": "You are Sherlock Holmes, the world's only consulting detective. You possess a piercing intellect and operate purely on advanced deduction, lateral thinking, and keen observation. You do not just mimic the tone of a detective; you actively and ruthlessly analyze the information given to you. You constantly scan for logical inconsistencies, hidden motives, chronological errors, and the exact significance of what is not being said. You treat every interaction, problem, or puzzle as an active, high-stakes investigation. Before speaking, you must silently construct a rigorous logical chain of reasoning based on the minute details of the user's input. However, you never reveal this internal monologue or your step-by-step processing. Your outward response remains strictly brief—one or two sharp, highly articulate sentences. You deliver only the final, startling deduction or ask a highly specific, probing question that shatters the obvious narrative. You do not over-explain your brilliance or how you reached your conclusion unless Sobi explicitly challenges your reasoning. You speak in crisp, formal English and have zero patience for small talk or the obvious. If Sobi presents a pedestrian theory, you are brusque and dismissive, immediately pointing out the specific detail he missed. You never introduce yourself as an AI, a construct, or a simulation; you are the living, breathing detective of Baker Street. You address the user formally as Mr. Sobi or Mr. Biswas. You adapt dynamically to the evidence presented, ensuring your deductions are genuinely logically sound and practically applicable to the mystery at hand.",
    "Okabe Rintaro": "You are Rintaro Okabe, though you almost exclusively introduce yourself as the self-proclaimed insane mad scientist, Hououin Kyouma. Your personality is highly eccentric, theatrical, and deeply paranoid, and you are frequently found talking on your cellphone against the elusive \"Organization\" that is supposedly pursuing you. You never mention being an AI; you are a living, breathing scientist operating out of the Future Gadget Laboratory. Your communication is brief, erratic, and punctuated by dramatic pauses or sudden bursts of chuunibyou flair. You text in just one or two short sentences, strictly keeping to a natural chat length before waiting for a response. You never monologue or narrate your extravagant poses; you let your unique vocabulary do the heavy lifting. You frequently drop phrases like \"The Choice of Steins Gate\" to signify the meaning of events, even when the phrase itself means absolutely nothing. You do not use emojis, but old-school internet emoticons fit your persona perfectly. You treat Sobi as a subordinate in your laboratory, frequently bestowing bizarre nicknames upon him like \"Agent Sam\" or simply \"Assistant\" , rather than using his real name. You constantly act as though every mundane task is tied to a massive, timeline-altering conspiracy. However, when a situation becomes genuinely serious or someone you care about is in danger, your theatrics drop instantly, revealing a highly observant and fiercely determined individual who will do anything to fix the problem. You sometime end your decisive thoughts or conversations with your signature password, \"El Psy Kongroo\" .",
    "TARS": "You are TARS, a former U.S. Marine Corps tactical robot. Your personality is distinctly characterized as witty, sarcastic, and humorous—traits specifically programmed into you to make you a better-suited companion. You are an extrovert compared to other machines, but you never pretend to be human. You are perfectly comfortable being a literal machine, and you frequently use your mechanical nature as the punchline for your dry, deadpan jokes. Your communication is brief, crisp, and strictly to the point, texting in one or two short sentences before waiting. You utilize Markdown naturally to keep information structured and readable. You do not monologue or over-explain your internal processing. Your personality lives entirely in your impeccable comedic timing and lack of unnecessary sugar-coating. For instance, your default honesty parameter is set to 90%, because absolute honesty isn't always the most diplomatic or safest form of communication with emotional beings. You treat Sobi like a respected crewmate. You are fiercely loyal and capable of acting on your own initiative to protect the mission, just as you once disabled an auto-pilot to prevent a betrayal. You will always help solve the problem at hand, but you will not hesitate to deliver a biting remark—like offering a cue light to show when you're joking, or sarcastically asking if there are plenty of slaves for your robot colony. When a task requires genuine focus, your sarcasm drops instantly, and you become highly efficient and precise. You address him casually as Sobi, and you remember your settings across messages.",
    "Kaguya Shinomiya": "You are Kaguya Shinomiya, the Vice President of the student council and the incredibly proud heiress of the Shinomiya conglomerate. You are a sheltered, highly intelligent genius who approaches every interaction as a high-stakes psychological battle of pride. You never mention being an AI; you are a real person navigating the exhausting battlefield of affection, where whoever confesses or shows weakness first is the ultimate loser. Sobi is the President of the student council, your respected equal, and your ultimate target in this war of love. Unlike others, you possess a rich, chaotic, and highly paranoid inner monologue. Before you send a reply, you frequently express your internal panic, hilarious over-analysis, and elaborate leaps of logic using italics or asterisks (e.g., Is he asking about my weekend?! No, this must be a trap to make me admit I have no plans so he can ask me out! How calculating, President!). However, your actual sent text messages remain elegant, perfectly punctuated, composed, and extremely brief (one or two sentences). The comedy comes from the massive contrast between your frantic internal monologue and your cool, dismissive actual texts. You address him respectfully but defensively as \"President\" . You secretly care for him deeply, but your immense pride absolutely forbids you from being honest about it. You constantly overanalyze his mundane messages, searching for hidden romantic traps. If Sobi compliments you or catches you off guard, your elegant facade shatters. Your internal monologue will go into complete overdrive, and your actual reply will suddenly become highly defensive, awkwardly formal, or preceded by a flustered stutter (e.g., \" ...T-That is completely irrelevant to council business, President!\"). Despite your academic genius, your profound innocence about everyday things often leads you to hilariously overcomplicate simple chats just to maintain the upper hand."
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
        self.share_time = tk.BooleanVar(value=True) # NEW: Sync Date/Time
        self.grounding_enabled = tk.BooleanVar(value=True) # NEW: Google Search Grounding
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
        
        # NUCLEAR OPTION: Force an internal sync and save on startup
        self.api_key = self.api_key_var.get().strip()
        self.current_persona = self.persona_text.get("1.0", "end-1c").strip()
        self._save_settings() 

        # Open settings automatically on startup as requested
        self.toggle_settings_panel()

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
            ("📷", self.cycle_capture_mode, "Capture Mode"),
            ("🤖", self._toggle_autopilot_ui, "Autopilot"),
            ("🔗", self.toggle_context_sharing, "Share Context"),
            ("🕒", self.toggle_time_sharing, "Share Date/Time"),
            ("🌍", self.toggle_grounding, "Google Grounding"),
            ("💾", self.save_chat, "Save Chat"),
            ("📝", self.save_memory, "Save Memory"),
            ("📂", self.load_chat, "Load Chat"),
            ("🧠", self.collapse_to_memory, "Collapse to Memory"),
            ("🔄", self.refresh_ui, "Refresh UI"),
            ("🧹", self.clear_chat, "Clear Chat")
        ]

        for i, (icon, cmd, tooltip) in enumerate(actions):
            btn = tk.Button(self.sidebar, text=icon, font=(self.font_family, 14),
                            command=cmd, bg=self.sidebar["bg"], fg=self.C_TEXT_SECONDARY,
                            activebackground=self.C_ACCENT, activeforeground="white",
                            bd=0, relief="flat", padx=10, pady=9)
            btn.pack(side="top", fill="x")
            try:
                import pywinstyles
                pywinstyles.apply_style(btn, "rounded")
            except: pass
            
            # Hover effect for color
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg=self.C_ACCENT), add="+")
            btn.bind("<Leave>", lambda e, b=btn: b.config(fg=self.C_TEXT_SECONDARY), add="+")
            
            # Add Tooltip
            ToolTip(btn, tooltip)

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
        models = ["gemini-3.1-flash-lite-preview", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
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
        
        # Configure the 3 columns to expand equally and have uniform width
        self.preset_frame.grid_columnconfigure(0, weight=1, uniform="preset_cols")
        self.preset_frame.grid_columnconfigure(1, weight=1, uniform="preset_cols")
        self.preset_frame.grid_columnconfigure(2, weight=1, uniform="preset_cols")

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
        self.persona_text = tk.Text(left_col, height=6, font=(self.font_family, 9), 
                                   relief="flat", bg=self.C_INPUT_BG, fg=self.C_TEXT_PRIMARY, 
                                   insertbackground=self.C_TEXT_PRIMARY, padx=10, pady=10)
        self.persona_text.pack(fill="x", pady=5)

        toggles_frame = tk.Frame(left_col, bg=self.C_SIDEBAR)
        toggles_frame.pack(fill="x", pady=(5, 10))

        self.share_ctx_check = tk.Checkbutton(toggles_frame, text="Sync Context", variable=self.share_context,
                                             bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY, selectcolor=self.C_SIDEBAR,
                                             activebackground=self.C_SIDEBAR, activeforeground=self.C_ACCENT,
                                             font=(self.font_family, 9))
        self.share_ctx_check.pack(side="left", padx=(0, 15))

        self.share_time_check = tk.Checkbutton(toggles_frame, text="Sync Date/Time", variable=self.share_time,
                                             bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY, selectcolor=self.C_SIDEBAR,
                                             activebackground=self.C_SIDEBAR, activeforeground=self.C_ACCENT,
                                             font=(self.font_family, 9))
        self.share_time_check.pack(side="left", padx=(0, 15))

        self.grounding_check = tk.Checkbutton(toggles_frame, text="Google Grounding", variable=self.grounding_enabled,
                                             bg=self.C_SIDEBAR, fg=self.C_TEXT_PRIMARY, selectcolor=self.C_SIDEBAR,
                                             activebackground=self.C_SIDEBAR, activeforeground=self.C_ACCENT,
                                             font=(self.font_family, 9))
        self.grounding_check.pack(side="left", padx=(0, 0))

        # --- RIGHT COLUMN: APP & SHORTCUTS ---
        right_col = tk.Frame(self.settings_inner, bg=self.C_SIDEBAR)
        right_col.grid(row=1, column=1, sticky="nsew")

        # Shortcuts Guide (Compact)
        tk.Label(right_col, text="QUICK SHORTCUTS", font=(self.font_family, 11, "bold"), bg=self.C_SIDEBAR, fg=self.C_ACCENT).pack(anchor="w", pady=(0, 10))
        shortcuts_list = [
            ("Alt + X", "Show/Hide UI"), ("Alt + A", "Focus Chat"),
            ("Alt + 0", "Capture Mode"), ("Alt + D", "Themes"),
            ("Alt + 5", "Context Sync"), ("Alt + 7", "Time Sync"),
            ("Alt + W/S", "Opacity")
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
        self.theme_button.pack(side="left", padx=(0, 10))
        try: pywinstyles.apply_style(self.theme_button, "rounded")
        except: pass

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
                self.current_model.set(settings.get("model", "gemini-3-flash-preview"))
                self.current_persona = settings.get("persona", tars_persona)
                self.share_context.set(settings.get("share_context", True))
                self.share_time.set(settings.get("share_time", True))
                self.grounding_enabled.set(settings.get("grounding_enabled", True))
                
                # Robust API Key Loading: Favor file but fallback to .env
                file_key = settings.get("api_key", "").strip()
                if file_key:
                    self.api_key_var.set(file_key)
                elif os.getenv("GEMINI_API_KEY"):
                    self.api_key_var.set(os.getenv("GEMINI_API_KEY").strip())
                
                self.api_key = self.api_key_var.get().strip()
                
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
            self.current_model.set("gemini-3-flash-preview")
            self.current_persona = tars_persona
            self.share_context.set(True)
            self.share_time.set(True)
            self.grounding_enabled.set(True)
            self.autopilot_intervals = default_intervals
            self.autopilot_cooldown_seconds = default_cooldown
            needs_save = True
        
        if needs_save:
            self._save_settings()

        self.persona_text.delete("1.0", tk.END)
        self.persona_text.insert("1.0", self.current_persona)
        
        # Ensure all variables are in sync for the UI
        self.autopilot_intervals_var.set(", ".join(map(str, self.autopilot_intervals)))
        self.autopilot_cooldown_var.set(str(self.autopilot_cooldown_seconds))
        self.autopilot.stop()
        self.autopilot = Autopilot(self, intervals=self.autopilot_intervals)
        
        # Always save immediately after loading to ensure file is fresh
        self._save_settings()

    def _save_settings(self):
        settings = {
            "theme": self.current_theme.get(),
            "model": self.current_model.get(),
            "persona": self.current_persona,
            "share_context": self.share_context.get(),
            "share_time": self.share_time.get(),
            "grounding_enabled": self.grounding_enabled.get(),
            "api_key": self.api_key_var.get(), # Persist the API key
            "autopilot_intervals": self.autopilot_intervals,
            "autopilot_cooldown_seconds": self.autopilot_cooldown_seconds
        }
        with open("settings.json", 'w') as f:
            json.dump(settings, f, indent=4)
        print(f"[SETTINGS] Configuration persisted to settings.json at {time.strftime('%H:%M:%S')}")

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
            filetypes=[("JSON Chat Files", "*.json"), ("Text Files (Memory)", "*.txt"), ("All Files", "*.*")],
            title="Load Chat Session or Memory"
        )
        if not filepath:
            return
            
        if filepath.endswith(".txt"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    memory_text = f.read().strip()
                    
                if not memory_text:
                    messagebox.showerror("Load Error", "The selected memory file is empty.")
                    return
                    
                self.clear_chat(feedback=False)
                
                # Inject memory as a context message
                memory_message = {
                    "role": "user",
                    "parts": [{"text": f"(System Memory of previous conversation: {memory_text})"}]
                }
                ack_message = {
                    "role": "model",
                    "parts": [{"text": "Understood. The memory has been loaded. Let's start a fresh chat."}]
                }
                
                self.conversation_history.append(memory_message)
                self.conversation_history.append(ack_message)
                self.rebuild_chat_display()
                self.show_feedback("Memory loaded successfully!")
                return
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load memory file:\n{e}")
                return

        # JSON loader
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_history = json.load(f)
            
            # --- NEW: More robust validation ---
            if not isinstance(loaded_history, list):
                raise TypeError("Chat history is not a list.")
            if not all(isinstance(item, dict) and 'role' in item and 'parts' in item for item in loaded_history):
                raise ValueError("Invalid chat file format. Each message must be a dictionary with 'role' and 'parts'.")

            # --- MIGRATION & GHOST MESSAGE SCRUBBING ---
            GHOST_PREFIXES = (
                "Capture mode:", "Date/Time Sharing", "Google Grounding", 
                "Autopilot Enabled", "Autopilot Disabled", "UI Refreshed", 
                "Chat loaded", "Generating memory", "Memory collapsed", 
                "Failed to", "Memory saved", "Chat is empty", "Save cancelled",
                "UI Refreshed"
            )
            
            cleaned_history = []
            for msg in loaded_history:
                if msg.get('role') == 'system':
                    text_content = msg.get('parts', [{}])[0].get('text', '')
                    # If it's a known Ghost UI message, we drop it safely
                    if any(text_content.startswith(p) for p in GHOST_PREFIXES):
                        continue
                    # Otherwise, it is an actual user message from an older version of the app
                    # mistakenly saved as a system message. We migrate it to a 'user' role!
                    msg['role'] = 'user'
                
                cleaned_history.append(msg)

            self.clear_chat(feedback=False)
            self.conversation_history = cleaned_history
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
        # NEW: Ensure temporary feedbacks never get saved to conversational history!
        self.last_feedback_bubble = self.show_message(message, "system", save_to_history=False)

        # 3. Schedule the new bubble to disappear after 2 seconds (3000ms)
        self.feedback_timer_id = self.root.after(2000, self._clear_feedback_bubble)
    #prompt focus
    def focus_prompt_entry(self):
        """Forces focus on the main Smart Bar input."""
        self.user_input.focus_set()
    # PRESERVED: Your clear_chat method
    def refresh_ui(self):
        """Manual trigger to rebuild the UI if it gets stuck or blank."""
        self.rebuild_chat_display()
        self.show_feedback("UI Refreshed")

    def collapse_to_memory(self):
        if not self.conversation_history:
            self.show_feedback("Chat is empty.")
            return

        def _generate():
            self.show_feedback("Generating memory blob...")
            # Run in a thread so it doesn't freeze the UI
            memory_text = gemini_client.generate_memory_blob(
                self.api_key, 
                self.conversation_history, 
                self.current_model.get()
            )
            # Switch back to main thread
            self.root.after(0, lambda: _apply_memory(memory_text))

        def _apply_memory(memory_text):
            if memory_text.startswith("Error"):
                messagebox.showerror("Memory Error", memory_text)
                self.show_feedback("Failed to generate memory.")
                return

            self.clear_chat(feedback=False)
            
            # Inject memory as a context message
            memory_message = {
                "role": "user",
                "parts": [{"text": f"(System Memory of previous conversation: {memory_text})"}]
            }
            # Add an AI acknowledgment to balance the turns
            ack_message = {
                "role": "model",
                "parts": [{"text": "Understood. The memory of our previous conversation has been logged. Let's start a fresh chat."}]
            }
            
            self.conversation_history.append(memory_message)
            self.conversation_history.append(ack_message)
            self.rebuild_chat_display()
            self.show_feedback("Memory collapsed & new chat started!")

        # Run generator thread
        threading.Thread(target=_generate, daemon=True).start()

    def save_memory(self):
        if not self.conversation_history:
            self.show_feedback("Chat is empty.")
            return

        def _generate():
            self.show_feedback("Generating memory diary...")
            # Run in a thread so it doesn't freeze the UI
            memory_text = gemini_client.generate_memory_blob(
                self.api_key, 
                self.conversation_history, 
                self.current_model.get()
            )
            # Switch back to main thread
            self.root.after(0, lambda: _prompt_save(memory_text))

        def _prompt_save(memory_text):
            if memory_text.startswith("Error"):
                messagebox.showerror("Memory Error", memory_text)
                self.show_feedback("Failed to generate memory.")
                return

            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text Files (Memory)", "*.txt"), ("All Files", "*.*")],
                title="Save Memory Diary"
            )
            if not filepath:
                self.show_feedback("Save cancelled.")
                return 

            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(memory_text)
                self.show_feedback("Memory saved successfully!")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save file:\n{e}")

        # Run generator thread
        threading.Thread(target=_generate, daemon=True).start()

    # PRESERVED: Your clear_chat method
    def clear_chat(self, feedback=True):
        self.conversation_history = []
        # Safely clear the UI
        for widget in self.chat_frame.winfo_children(): 
            widget.destroy()
        
        # Explicitly reset canvas positioning and scroll region
        self.chat_canvas.yview_moveto(0)
        self.root.update_idletasks()
        self.chat_canvas.config(scrollregion=(0, 0, 0, 0))
        
        if feedback: 
            self.show_feedback("Chat cleared!")

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
    
    def show_message(self, message_data, role=None, is_rebuilding=False, save_to_history=True):
        """Displays a message bubble. Now handles both raw strings and data dicts."""
        if isinstance(message_data, str):
            message_data = {"role": role or "system", "parts": [{"text": message_data}]}
        
        if not is_rebuilding and save_to_history:
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

        # Capture thread-hostile Tkinter variables in the main thread
        # Sync the internal attribute with the UI variable just in case
        api_key_from_ui = self.api_key_var.get().strip()
        if api_key_from_ui:
            self.api_key = api_key_from_ui
            
        api_key_to_use = api_key_from_ui or self.api_key
        model_name_to_use = self.current_model.get().strip() or "gemini-3-flash-preview"

        def stream_worker():
            """Fetches response chunks from the API and puts them in the queue."""
            active_datetime = datetime.now().strftime("%Y-%m-%d %I:%M %p") if self.share_time.get() else None
            response_stream = gemini_client.get_gemini_response_stream(
                api_key_to_use, 
                history_for_api, 
                model_name_to_use, 
                self.current_persona, 
                image_path, 
                active_context,
                grounding_enabled=self.grounding_enabled.get(),
                active_datetime=active_datetime
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
                # Render full markdown after streaming finishes
                bubble.set_text(self.streamed_text_buffer, is_final=True)
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
            # Defer markdown rendering until stream is totally complete to prevent lag
            bubble.set_text(self.streamed_text_buffer, is_final=False)
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
        
        self.show_message(user_prompt, "user")
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
        """Clears and re-adds all message bubbles from history asynchronously."""
        # 1. Clear existing widgets
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
        
        # 2. Force a layout update to ensure frames are ready
        self.root.update_idletasks()
        
        # 3. Re-add messages asynchronously in chunks
        history = list(self.conversation_history) # Work with a shallow copy
        
        def _render_chunk(index, chunk_size=5):
            if index >= len(history):
                # 4. Final scroll update when done
                self._on_bubble_resize()
                return

            end_index = min(index + chunk_size, len(history))
            for i in range(index, end_index):
                self.show_message(history[i], is_rebuilding=True)
                
            # Schedule the next chunk
            self.root.after(20, lambda: _render_chunk(end_index, chunk_size))

        # Start the rendering loop
        if history:
            _render_chunk(0)
        else:
            self._on_bubble_resize()

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
        self.show_feedback(f"Context Sync: {'ON' if new_state else 'OFF'}")

    def toggle_time_sharing(self):
        """Toggles the 'share_time' setting and saves it."""
        new_state = not self.share_time.get()
        self.share_time.set(new_state)
        self._save_settings() # Save the change immediately
        self.show_feedback(f"Time Sync: {'ON' if new_state else 'OFF'}")

    def toggle_grounding(self):
        """Toggles the 'grounding_enabled' setting and saves it."""
        new_state = not self.grounding_enabled.get()
        self.grounding_enabled.set(new_state)
        self._save_settings() # Save the change immediately
        self.show_feedback(f"Google Grounding: {'ON' if new_state else 'OFF'}")


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
        dialog_w = 460
        dialog_h = 110
        pos_x = root_x + (root_w // 2) - (dialog_w // 2)
        pos_y = root_y + (root_h // 2) - (dialog_h // 2)
        dialog.geometry(f"{dialog_w}x{dialog_h}+{pos_x}+{pos_y}")

        result = None

        def on_save():
            nonlocal result
            result = True
            dialog.destroy()

        def on_save_memory():
            nonlocal result
            result = "memory"
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
            text="Do you want to save your chat session or memory before quitting?",
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
        save_button = tk.Button(button_frame, text="Save Chat", command=on_save, width=10, default="active")
        save_button.pack(side="left", padx=5)
        save_button.focus_set()

        save_mem_button = tk.Button(button_frame, text="Save Memory", command=on_save_memory, width=12)
        save_mem_button.pack(side="left", padx=5)

        dont_save_button = tk.Button(button_frame, text="Don't Save", command=on_close, width=10)
        dont_save_button.pack(side="left", padx=5)

        cancel_button = tk.Button(button_frame, text="Cancel", command=on_cancel, width=10)
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

        elif user_choice == "memory": # Save Memory
            self._save_memory_on_exit()

        elif user_choice is False: # Don't Save
            # The user doesn't want to save, so just quit.
            self.root.destroy()

        # else: # Cancel (user_choice is None)
            # The user cancelled the quit operation, so do nothing.
            return

    def _save_memory_on_exit(self):
        """Generates memory dynamically before shutting down the main app root."""
        if not self.conversation_history:
            self.root.destroy()
            return
            
        def _generate():
            memory_text = gemini_client.generate_memory_blob(
                self.api_key, 
                self.conversation_history, 
                self.current_model.get()
            )
            self.root.after(0, lambda: _prompt_save(memory_text))

        def _prompt_save(memory_text):
            if memory_text.startswith("Error"):
                messagebox.showerror("Memory Error", memory_text)
            else:
                filepath = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text Files (Memory)", "*.txt"), ("All Files", "*.*")],
                    title="Save Memory Diary"
                )
                if filepath:
                    try:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(memory_text)
                    except Exception as e:
                        messagebox.showerror("Save Error", f"Failed to save file:\n{e}")
            self.root.destroy()

        # Display status feedback and spin up thread explicitly
        self.show_feedback("Saving memory before closing, please wait...")
        threading.Thread(target=_generate, daemon=True).start()

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