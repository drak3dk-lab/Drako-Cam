@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Drako Cam - instalacion

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar.ps1" %*
set "CODIGO=%ERRORLEVEL%"

if not "%CODIGO%"=="0" goto :fallo

echo.
echo Pulsa una tecla para cerrar esta ventana.
pause >nul
exit /b 0

:fallo
echo.
echo No se pudo terminar la instalación.
echo Lee el mensaje de arriba. El registro está en:
echo   %LOCALAPPDATA%\DrakoCam\logs\instalacion.log
echo.
echo Pulsa una tecla para cerrar esta ventana.
pause >nul
exit /b %CODIGO%
