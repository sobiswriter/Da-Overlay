@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -B -m unittest discover -s tests -v
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --distpath release --workpath build/cutex-v2 "Cutex Overlay.spec"
if errorlevel 1 goto failed
echo.
echo Ready: release\Cutex.exe
echo Old builds, chats and settings have not been removed.
exit /b 0
:failed
echo Build failed. See the error above. Existing builds are unchanged.
pause
exit /b 1
