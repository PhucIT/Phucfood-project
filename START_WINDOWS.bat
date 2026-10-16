@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Chua co moi truong Python. Hay lam buoc 2 trong HUONG_DAN.md.
    pause
    exit /b 1
)
echo Mo trinh duyet: http://127.0.0.1:5000
".venv\Scripts\python.exe" server.py
pause
