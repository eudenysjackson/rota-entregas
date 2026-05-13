@echo off
chcp 65001 > nul
title Rota de Entregas

echo.
echo  ==========================================
echo   Instalando dependencias (so na 1a vez)...
echo  ==========================================
pip install -r requirements_desktop.txt -q

echo.
echo  ==========================================
echo   Iniciando sistema...
echo   O navegador abrira automaticamente.
echo  ==========================================
echo.

python app_desktop.py

pause
