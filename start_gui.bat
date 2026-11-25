@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" desktop_app.py
) else (
    py -3 desktop_app.py
)
if errorlevel 1 pause
