@echo off
cd /d "%~dp0"
runtime\python.exe -m unittest test_engine test_recent_engine test_hotkey test_spreadsheets test_images test_shell_menu test_compression -v
pause
