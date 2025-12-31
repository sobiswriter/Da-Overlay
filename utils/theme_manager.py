# --- utils/theme_manager.py ---
"""
Centralized theme management for Overlay Cutex.
Handles professional color palettes, icons, and font definitions.
"""

# Professional Obsidian Theme (Tech-focused)
OBSIDIAN_THEME = {
    "C_BG": "#0D1117",           # Deep dark background
    "C_SIDEBAR": "#010409",      # Even darker sidebar for depth
    "C_CARD": "#161B22",         # Widget/Card background
    "C_INPUT": "#1C2128",        # Lighter input background (Crucial for visibility)
    "C_BORDER": "#30363D",       # Professional subtle borders
    "C_ACCENT": "#58A6FF",       # Electric Blue accent
    "C_ACCENT_HOVER": "#79C0FF", # Brighter blue for hover
    "C_TEXT_PRIMARY": "#F0F6FC", # Super readable white
    "C_TEXT_SECONDARY": "#8B949E", # Muted/Description text
    "C_SUCCESS": "#3FB950",
    "C_ERROR": "#F85149",
    "C_BUTTON_HOVER": "#21262D",
    "WIN_STYLE": "mica"          # Preferred Windows style
}

# Soft Light Theme (Gentle on the eyes)
LIGHT_THEME = {
    "C_BG": "#EEF1F4",           # Soft grayish-white
    "C_SIDEBAR": "#E1E4E8",      # Subtle sidebar
    "C_CARD": "#FFFFFF",         # Pure white for cards/widgets
    "C_INPUT": "#F6F8FA",        # Very light input
    "C_BORDER": "#D1D5DA",       # Soft borders
    "C_ACCENT": "#0969DA",       # Professional Blue
    "C_ACCENT_HOVER": "#0A84FF",
    "C_TEXT_PRIMARY": "#24292E", # Deep gray (not pure black)
    "C_TEXT_SECONDARY": "#586069", # Muted gray
    "C_SUCCESS": "#28A745",
    "C_ERROR": "#D73A49",
    "C_BUTTON_HOVER": "#E1E4E8",
    "WIN_STYLE": "transparent"
}

THEMES = {
    "dark": OBSIDIAN_THEME,
    "light": LIGHT_THEME
}

class ThemeProvider:
    def __init__(self, current_theme="dark"):
        self.theme_name = current_theme
        self.palette = THEMES.get(current_theme, OBSIDIAN_THEME)
        
    def get_palette(self):
        return self.palette

    def switch_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.palette = THEMES[self.theme_name]
        return self.theme_name, self.palette

    # Font definitions
    DEFAULT_FONT_FAMILY = "Segoe UI"
    BOLD_FONT_FAMILY = "Segoe UI Semibold"
    MONO_FONT_FAMILY = "Consolas"