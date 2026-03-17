@echo off
echo.
echo  ===================================
echo   F1 Dashboard starten...
echo  ===================================
echo.
cd /d "%~dp0"
start http://localhost:5000
python app.py
pause
