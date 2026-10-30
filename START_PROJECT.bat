@echo off
title SmartMES Launcher
echo ===================================================
echo    SMARTMES - SYSTEM LAUNCHER
echo ===================================================
echo.
echo [1/2] Checking if XAMPP MySQL is running...
echo MAKE SURE XAMPP MYSQL IS GREEN BEFORE CONTINUING!
echo.
pause
echo.
echo [2/2] Starting the Flask Application...
start http://localhost:5000
python app.py
pause