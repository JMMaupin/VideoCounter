@echo off
setlocal
cd /d "%~dp0"

echo Installation des dependances...
python -m pip install --quiet -r requirements.txt pyinstaller
if errorlevel 1 goto :error

echo.
echo Compilation de l'executable...
python -m PyInstaller --noconfirm --onefile --windowed --name VideoCounter --collect-all imageio_ffmpeg video_counter.py
if errorlevel 1 goto :error

echo.
echo Termine : dist\VideoCounter.exe
pause
exit /b 0

:error
echo.
echo La compilation a echoue.
pause
exit /b 1
