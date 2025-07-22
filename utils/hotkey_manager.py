# --- utils/hotkey_manager.py ---
import keyboard

class HotkeyManager:
    def __init__(self, app_instance):
        self.app = app_instance

    def start_listener(self):
        """Sets up all the direct hotkeys for the application."""
        
        # --- The New, Simpler Hotkey System ---
        # The 'suppress=True' argument can prevent the original key press
        # (like typing '8') from going to the active window.
        
        # Window Movement
        keyboard.add_hotkey('alt+8', self.app.move_window_up, suppress=True)
        keyboard.add_hotkey('alt+4', self.app.move_window_left, suppress=True)
        keyboard.add_hotkey('alt+2', self.app.move_window_down, suppress=True)
        keyboard.add_hotkey('alt+6', self.app.move_window_right, suppress=True)
        
        # App Controls
        keyboard.add_hotkey('alt+0', self.app.cycle_capture_mode, suppress=True)
        keyboard.add_hotkey('alt+5', self.app.toggle_context_sharing, suppress=True)
        
        # Original Hotkey to Show/Hide
        # We can keep the old one or use your new suggestion. Let's use yours!
        keyboard.add_hotkey('alt+x', self.app.toggle_visibility, suppress=True)
        keyboard.add_hotkey('alt+a', self.app.focus_prompt_entry, suppress=True)

        print("[HOTKEY] Direct hotkey listener started.")
        # The keyboard library's listener runs in the background automatically.
        
def setup_hotkey_listener(app_instance):
    """Global function to create and start the hotkey manager."""
    manager = HotkeyManager(app_instance)
    manager.start_listener()