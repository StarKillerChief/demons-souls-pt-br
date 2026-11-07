@echo off
chcp 65001 >nul
cd /d "%~dp0"
python\python.exe -I -X utf8 pack\tools\ptbr_soulbrandt.py desinstalar
echo.
pause
