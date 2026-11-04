@echo off
rem Like "DD2 Completionist Tracker.cmd", but also reachable from phones and tablets on your home network.
rem Anyone on the same Wi-Fi can view the map while this window is open. Close it to stop.
cd /d "%~dp0"
.venv\Scripts\python.exe dd2.py serve --open --lan
pause
