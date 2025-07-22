# --- main.py ---
import tkinter as tk
from dotenv import load_dotenv

# Import from the new structure
from ui.main_window import OverlayApp
from utils.hotkey_manager import setup_hotkey_listener

if __name__ == "__main__":
    load_dotenv()
    root = tk.Tk()
    app = OverlayApp(root)
    setup_hotkey_listener(app)
    root.mainloop()