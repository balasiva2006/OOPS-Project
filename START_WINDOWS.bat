@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv
    if errorlevel 1 goto :failed
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failed
.venv\Scripts\python.exe seed.py
if errorlevel 1 goto :failed
echo Open http://127.0.0.1:5000 in your browser.
.venv\Scripts\python.exe app.py
pause
exit /b
:failed
echo Setup failed. Check that Python is installed and the internet is available.
pause
exit /b 1
