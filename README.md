# Cutex Overlay

Cutex Overlay is a desktop application that allows you to capture a region of your screen and ask questions about it to the Gemini AI. It provides a seamless way to get information about anything on your screen.

## Features

*   **Screen Region Capture**: Select any part of your screen to capture.
*   **AI-Powered Analysis**: Uses the Gemini AI to understand and answer questions about the captured image.
*   **Chat Interface**: Interact with the AI in a user-friendly chat window.
*   **Global Hotkey**: Activate the screen capture from anywhere with a configurable hotkey.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/cutex-overlay.git
    cd cutex-overlay
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up your environment:**
    Create a `.env` file in the root directory of the project and add your Gemini API key:
    ```
    GEMINI_API_KEY=your_gemini_api_key
    ```

## Usage

1.  **Run the application:**
    ```bash
    python main.py
    ```

2.  **Activate the screen capture:**
    Press the configured hotkey (default is `Ctrl+Shift+X`) to activate the region selector.

3.  **Select a region:**
    Click and drag to select the area of the screen you want to capture.

4.  **Ask a question:**
    Type your question in the input box and press Enter. The AI's response will appear in the chat window.
