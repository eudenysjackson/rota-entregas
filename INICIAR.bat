@echo off
chcp 65001 > nul
title Rota de Entregas

echo.
echo  ==========================================
echo   Instalando dependencias (so na 1a vez)...
echo  ==========================================
pip install -r requirements.txt -q

echo.
echo  ==========================================
echo   Iniciando sistema...
echo   Abrindo navegador em http://localhost:5000
echo  ==========================================
echo.

start "" "http://localhost:5000"
python app.py

pause
