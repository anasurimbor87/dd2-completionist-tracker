@echo off
rem Starts DD2 Completionist Tracker from the source code and opens it in the browser. Close this window to stop it.
cd /d "%~dp0"
.venv\Scripts\python.exe dd2.py serve --open
pause
