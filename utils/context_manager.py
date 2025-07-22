# --- utils/context_manager.py ---
import sys

def get_active_window_info():
    """
    Gets the title and executable name of the currently active window.
    """
    active_window_info = "No context detected." # Default message
    try:
        # ... (all the platform-specific code remains the same)
        if sys.platform == "win32":
            import win32gui, win32process, psutil
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                app_name = psutil.Process(pid).name().replace(".exe", "").capitalize()
                window_title = win32gui.GetWindowText(hwnd)
                if window_title: active_window_info = f"App: {app_name}, Title: {window_title}"
        # ... (macOS and Linux code is also the same)

    except Exception as e:
        active_window_info = f"Error detecting context: {e}"
    
    # A clearer debugging message
    print(f"--- [CONTEXT CHECK] --- Detected: {active_window_info}")
    return active_window_info