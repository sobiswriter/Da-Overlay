if __name__ == "__main__":
    try:
        from desktop import run
        run()
    except Exception as error:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Cutex could not start", str(error) + "\n\nIf this is a dependency issue, run run.bat. Saved conversations are not changed.")
        root.destroy()
        raise
