# dev.nix
{ pkgs, ... }: {

  # Using a stable channel is a great choice for consistency.
  channel = "stable-23.11";

  # This is the "magic recipe" for our Python app.
  # It tells Nix to get Python and all the libraries we need to run our app.
  packages = [
    (pkgs.python311.withPackages (ps: [
      # Core UI library
      ps.tkinter
      
      # For our hotkeys and keyboard magic
      ps.pynput
      ps.keyboard
      
      # For screenshots
      ps.mss
      ps.pillow
      
      # For talking to the Gemini API
      ps.requests
      
      # For reading our .env file with the API key
      ps.python-dotenv
      
      # For syntax highlighting in code blocks
      ps.pygments
      
      # --- Windows-Specific (for context awareness) ---
      # This will be available if you're on a Windows machine
      ps.pywin32
      
      # --- macOS-Specific (for context awareness) ---
      # Not in standard nixpkgs, would require an overlay if needed on Mac
      # but this setup is for Firebase Studio (Linux)
      
      # --- Linux-Specific (for context awareness) ---
      ps.python-xlib
    ]))
    
    # We'll also add a code formatter to keep our files looking neat!
    pkgs.black
  ];

  # Sets the environment variables for your project.
  # This is a perfect place for placeholders, but remember to
  # use your real key from a .env file or a secret manager in production.
  env = {
    GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_GOES_HERE";
  };

  # Essential VS Code extensions for Python development.
  # You can find more on https://open-vsx.org/
  idx.extensions = [
    "ms-python.python"          # The official Python extension
    "ms-python.vscode-pylance"  # Super smart auto-complete and code analysis
    "njpwerner.autodocstring"     # Helps you write helpful comments
  ];

  # Since our app is a graphical desktop application and not a web server,
  # the standard 'previews' section for web apps doesn't really apply.
  # Instead, we will define a 'start' script.
  idx.previews = {
    enable = false; # We are not running a web preview
  };

  # This section defines the commands that will be available in your workspace.
  idx.scripts = {
    # The 'start' command will be the main way to run our app
    start.exec = "python main.py";
  };

  # This is the main entrypoint when your workspace starts up.
  # It will automatically install our Python packages.
  idx.main = {
    install = ''
      # No extra installation needed, nix does the magic!
      echo "Welcome to your AI Overlay dev environment!"
      echo "All Python packages are ready."
      echo "To run the app, type: start"
    '';
    run = "start";
  };

}