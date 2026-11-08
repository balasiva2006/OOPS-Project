@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv
    if errorlevel 1 goto :failed
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failed
if not exist .env (
    echo Create .env from .env.example and fill in DATABASE_URL and HMC_SECRET_KEY.
    echo See README.md for PostgreSQL setup and account creation.
    pause
    exit /b 1
)
echo Open http://127.0.0.1:5000 in your browser.
.venv\Scripts\python.exe app.py
if errorlevel 1 goto :failed
pause
exit /b
:failed
echo Startup failed. Check Python, your .env settings, and database setup in README.md.
pause
exit /b 1
