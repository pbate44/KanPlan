@echo off
rem Double-click to install (if needed) and start KanPlan.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
