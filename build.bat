@echo off
echo Ensuring all dependencies are installed...
pip install -r requirements.txt

echo.
echo Ensuring PyInstaller is installed...
pip install pyinstaller

echo.
echo Starting the build process with PyInstaller...
pyinstaller --noconsole --onefile --name "Cutex Overlay" --icon="flower.ico" main.py

echo.
echo Build complete! The executable can be found in the 'dist' folder.
