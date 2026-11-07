@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Traducao PT-BR para o Soulbrandt (versao de teste)
echo.
python\python.exe -I -X utf8 pack\tools\ptbr_soulbrandt.py instalar
echo.
pause
