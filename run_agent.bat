@echo off
REM ============================================================
REM  AI Job Search Agent — One-Click Pipeline Runner
REM ============================================================
REM  Double-click this file to run the full pipeline:
REM    Collect Jobs → Match → Rank → Filter Duplicates → Email
REM ============================================================

cd /d "%~dp0"

echo.
echo  ============================================================
echo   AI Job Search Agent — Full Pipeline
echo   %DATE% %TIME%
echo  ============================================================
echo.

.\venv\Scripts\python.exe cli.py run-all

echo.
echo  ============================================================
echo   Pipeline finished! Check your email inbox.
echo  ============================================================
echo.
pause
