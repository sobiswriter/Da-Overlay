# --- utils/hotkey_manager.py ---
import keyboard

class HotkeyManager:
    def __init__(self, app_instance):
        self.app = app_instance

    def _add_hotkey_safely(self, hotkey, callback):
        """A wrapper to safely add hotkeys and handle potential registration errors."""
        try:
            keyboard.add_hotkey(hotkey, callback, suppress=True)
        except ValueError:
            print(f"Warning: Could not register hotkey '{hotkey}'. It may already be in use by another application.")

    def start_listener(self):
        """Sets up all the direct hotkeys for the application."""
        
        # --- The New, Simpler Hotkey System ---
        # The 'suppress=True' argument can prevent the original key press
        # (like typing '8') from going to the active window.
        
        # Window Movement
        # We use lambdas to call the new, consolidated _move_window method.
        self._add_hotkey_safely('alt+8', lambda: self.app._move_window(dy=-30)) # Up
        self._add_hotkey_safely('alt+4', lambda: self.app._move_window(dx=-30)) # Left
        self._add_hotkey_safely('alt+2', lambda: self.app._move_window(dy=30))  # Down
        self._add_hotkey_safely('alt+6', lambda: self.app._move_window(dx=30))  # Right
        
        # App Controls
        self._add_hotkey_safely('alt+0', self.app.cycle_capture_mode)
        self._add_hotkey_safely('alt+5', self.app.toggle_context_sharing)
        
        # Original Hotkey to Show/Hide
        # We can keep the old one or use your new suggestion. Let's use yours!
        self._add_hotkey_safely('alt+x', self.app.toggle_visibility)
        self._add_hotkey_safely('alt+a', self.app.show_and_focus_prompt)

        # --- NEW Hotkeys from user request ---
        self._add_hotkey_safely('alt+d', self.app._toggle_theme)
        # New Opacity Hotkeys
        self._add_hotkey_safely('alt+w', self.app.increase_opacity)
        self._add_hotkey_safely('alt+s', self.app.decrease_opacity)

        print("[HOTKEY] Direct hotkey listener started.")
        # The keyboard library's listener runs in the background automatically.
        
def setup_hotkey_listener(app_instance):
    """Global function to create and start the hotkey manager."""
    manager = HotkeyManager(app_instance)
    manager.start_listener()