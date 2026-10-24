@echo off
title CRISS - MySQL Server (Port 3308)
echo ========================================================
echo Starting CRISS Local MySQL 8 Server on Port 3308...
echo Datadir: %~dp0mysql_dev_data
echo ========================================================

if not exist "%~dp0mysql_dev_data" (
    echo [ERROR] mysql_dev_data directory not found!
    pause
    exit /b 1
)

"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe" --datadir="%~dp0mysql_dev_data" --port=3308 --mysqlx=0 --console
