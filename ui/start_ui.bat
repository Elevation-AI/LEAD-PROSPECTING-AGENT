@echo off
echo.
echo ============================================================
echo   AGENT01 OUTPUT UI - Starting Server
echo ============================================================
echo.
echo Installing dependencies if needed...
pip install flask --quiet
echo.
echo Starting Flask server...
echo The UI will open at http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo ============================================================
echo.
python app.py
pause
