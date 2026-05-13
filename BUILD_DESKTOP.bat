@echo off
chcp 65001 > nul
title Build Desktop - Rota de Entregas

echo.
echo  ==========================================
echo   [1/3] Instalando dependencias...
echo  ==========================================
pip install -r requirements_desktop.txt -q

echo.
echo  ==========================================
echo   [2/3] Compilando executavel...
echo   Aguarde alguns minutos...
echo  ==========================================
echo.

pyinstaller --onefile --noconsole ^
  --name "RotaEntregas" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  app_desktop.py

echo.
if not exist "dist\RotaEntregas.exe" (
    echo  ERRO: A compilacao falhou. Veja o log acima.
    pause
    exit /b 1
)

echo  ==========================================
echo   [3/3] Gerando instalador Windows...
echo  ==========================================
echo.

set INNO1=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
set INNO2=C:\Program Files\Inno Setup 6\ISCC.exe

if exist "%INNO1%" (
    "%INNO1%" installer.iss
) else if exist "%INNO2%" (
    "%INNO2%" installer.iss
) else (
    echo  AVISO: Inno Setup nao encontrado.
    echo  Baixe gratuitamente em: https://jrsoftware.org/isdl.php
    echo  Depois abra o arquivo installer.iss e compile.
    echo.
    echo  O executavel portatil ja esta pronto em:
    echo    dist\RotaEntregas.exe
    pause
    exit /b 0
)

echo.
if exist "RotaEntregas_Setup.exe" (
    echo  ==========================================
    echo   PRONTO!
    echo   Instalador: RotaEntregas_Setup.exe
    echo   Portatil:   dist\RotaEntregas.exe
    echo  ==========================================
) else (
    echo  ERRO ao gerar instalador. Veja o log acima.
)
echo.
pause
