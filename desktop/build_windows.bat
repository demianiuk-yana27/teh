@echo off
setlocal
cd /d "%~dp0"
py -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1
py -m PyInstaller --noconfirm --clean --onefile --windowed --name "TehQuickRequests" quick_requests.py
if errorlevel 1 exit /b 1
echo Ready: dist\TehQuickRequests.exe
pause
