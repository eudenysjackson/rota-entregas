@echo off
chcp 65001 > nul
title Build Desktop - Rota de Entregas

echo.
echo  ==========================================
echo   Instalando dependencias...
echo  ==========================================
pip install -r requirements_desktop.txt -q

echo.
echo  ==========================================
echo   Compilando executavel...
echo   Isso pode levar alguns minutos...
echo  ==========================================
echo.

pyinstaller --onefile --noconsole ^
  --name "RotaEntregas" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  app_desktop.py

echo.
if exist "dist\RotaEntregas.exe" (
    echo  ==========================================
    echo   PRONTO! Executavel gerado em:
    echo   dist\RotaEntregas.exe
    echo.
    echo   Copie esses arquivos para onde quiser:
    echo     dist\RotaEntregas.exe
    echo     .env  (com sua GOOGLE_API_KEY)
    echo  ==========================================
) else (
    echo  ERRO: A compilacao falhou. Veja o log acima.
)
echo.
pause
