@echo off
title CRISS Platform Launcher
echo ========================================================
echo Campus Resource Intelligence ^& Sharing System (CRISS)
echo ========================================================
cd /d "%~dp0"

echo [1/3] Checking MySQL Server on port 3308...
powershell -Command "if (!(Get-NetTCPConnection -LocalPort 3308 -ErrorAction SilentlyContinue)) { exit 1 } else { exit 0 }"
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Starting local MySQL Server in background window...
    start "CRISS MySQL Daemon (Port 3308)" cmd /k "%~dp0start_mysql.bat"
    echo [INFO] Waiting 3 seconds for MySQL to be ready...
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] MySQL Server is already active on port 3308!
)

echo [2/3] Verifying database connectivity...
python -c "from database.connection import execute_query; res = execute_query('SELECT count(*) as c FROM users;', fetchone=True); print('[OK] Connected to database! Registered users:', res['c'])"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Could not connect to MySQL. Please check start_mysql.bat.
    pause
    exit /b 1
)

echo [3/3] Starting CRISS Flask Application...
echo ========================================================
echo Open your browser at: http://127.0.0.1:5000
echo Press CTRL+C to stop the application.
echo ========================================================
python app.py
