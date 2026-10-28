@echo off
cd /d "%~dp0"
py -3.12 -m venv .build-venv
if errorlevel 1 goto error
.build-venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.16.0
if errorlevel 1 goto error
.build-venv\Scripts\python.exe build_metadata.py
if errorlevel 1 goto error
.build-venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --noupx --windowed --onedir --name BakuriFileConverter --icon assets/app.ico --version-file version-resource.txt --add-data "assets;assets" --add-data "USER-GUIDE.md;." --add-binary "FilePathCheckerModuleExample.dll;." --hidden-import win32timezone --hidden-import win32com.shell.shell --exclude-module PIL.AvifImagePlugin --exclude-module PIL._avif --collect-submodules pynput --collect-all velopack app.py
if errorlevel 1 goto error
echo Built: dist\BakuriFileConverter\BakuriFileConverter.exe
pause
exit /b 0
:error
echo Build failed. Install Python 3.12 x64 and check the error above.
pause
exit /b 1
