# --- utils/autopilot.py ---
import threading
import time

class Autopilot:
    def __init__(self, app_instance):
        self.app = app_instance
        self.running = False
        self.thread = None
        # NEW: The "reset" signal for our super-sensitive hearing!
        self._reset_event = threading.Event()
        
        # The sequence of intervals in seconds, as you designed!
        self.intervals = [120, 100, 160, 200, 300]
        self.current_interval_index = 0
        
        # An Event to allow us to stop the timer gracefully
        self._stop_event = threading.Event()

    def _run(self):
        """The main loop for the Autopilot thread, now with reset capability."""
        while not self._stop_event.is_set():
            # Clear any previous reset signal before we start waiting
            self._reset_event.clear()
            interval = self.intervals[self.current_interval_index]
            print(f"[AUTOPILOT] Waiting for {interval} seconds...")

            # We now wait in 1-second chunks, which allows us to be interrupted.
            # We do this for the number of seconds in the interval.
            awoke = self._reset_event.wait(timeout=interval)
            
            # After waiting, we check if we were told to reset.
            if self._reset_event.is_set():
                # If we were told to reset, just loop again from the start of the while loop.
                print("[AUTOPILOT] Cooldown reset during wait. Restarting timer.")
                continue

            if self._stop_event.is_set():
                # If we were told to stop completely during the wait
                break
            
            # If the wait finished naturally without a reset or stop, it's time to trigger!
            print("[AUTOPILOT] Timer fired! Triggering proactive tick.")
            self.app.root.after(0, self.app.on_autopilot_tick)

            if self.current_interval_index < len(self.intervals) - 1:
                self.current_interval_index += 1

    def start(self):
        """Starts the Autopilot thread."""
        if self.running:
            return
        
        print("[AUTOPILOT] Starting...")
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the Autopilot thread."""
        if not self.running:
            return
            
        print("[AUTOPILOT] Stopping...")
        self._stop_event.set() # Signal the loop to stop
        self.thread.join(timeout=2) # Wait briefly for the thread to finish
        self.running = False
        self.current_interval_index = 0 # Reset for next time
    
    def reset_timer(self):
        """Resets the timer back to the first interval and interrupts the wait."""
        if self.running:
            print("[AUTOPILOT] Cooldown reset by user activity.")
            self.current_interval_index = 0
            # Set the reset flag to interrupt the wait() in the _run loop
            self._reset_event.set()