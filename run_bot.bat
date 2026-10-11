@echo off
title Maktab Test Boti
cd /d "%~dp0"
echo Bot ishga tushirilmoqda...
call .\venv\Scripts\activate.bat
python main.py
pause
