@echo off
echo ========================================
echo Stopping AI Job Search Agent...
echo ========================================
REM Kills the python process running the continuous scheduler
taskkill /F /IM python.exe /T
echo.
echo Agent stopped successfully!
pause
