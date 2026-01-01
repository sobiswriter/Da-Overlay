@echo off
echo ========================================
echo   BUILDING OVERLAY CUTEX (ANNA)
echo ========================================
echo.
echo [1/3] Updating dependencies...
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

echo [2/3] Cleaning previous builds...
if exist build rd /s /q build
if exist dist rd /s /q dist

echo [3/3] Running PyInstaller...
if exist "Cutex Overlay.spec" (
    echo [INFO] Building from spec file...
    pyinstaller --clean "Cutex Overlay.spec"
) else (
    echo [INFO] Generating new build...
    pyinstaller --noconsole --onefile --clean --name "Cutex Overlay" --icon="flower.ico" main.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PyInstaller failed with exit code %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ========================================
echo   BUILD COMPLETE! Check 'dist' folder.
echo ========================================
if not exist dist (
    echo [WARNING] 'dist' folder was not created as expected!
)
pause
