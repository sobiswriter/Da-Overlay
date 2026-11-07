@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import webview, requests, mss, keyboard, win32gui, psutil, dotenv" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Cutex could not start. Check the error above and make sure Microsoft Edge WebView2 is installed.
pause
exit /b 1
