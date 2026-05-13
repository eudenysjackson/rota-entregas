@echo off
chcp 65001 > nul
title Build Desktop - Rota de Entregas

echo.
echo  ==========================================
echo   [1/2] Instalando dependencias...
echo  ==========================================
pip install -r requirements_desktop.txt -q

echo.
echo  ==========================================
echo   [2/2] Compilando executavel...
echo   Aguarde alguns minutos...
echo  ==========================================
echo.

if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"
if exist "RotaEntregas.spec" del "RotaEntregas.spec"

pyinstaller --onefile --noconsole ^
  --name "RotaEntregas" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --icon "static\favicon.png" ^
  app_desktop.py

echo.
if exist "dist\RotaEntregas.exe" (
    echo  ==========================================
    echo   PRONTO!
    echo.
    echo   Arquivo gerado:
    echo     dist\RotaEntregas.exe
    echo.
    echo   Para instalar em qualquer computador:
    echo   basta copiar esse .exe e dar duplo-clique.
    echo   Nao precisa de instalador, Python ou nada.
    echo  ==========================================
) else (
    echo  ERRO: A compilacao falhou. Veja o log acima.
)
echo.
pause
