@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if exist "%~dp0dependencies\ffmpeg\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe" set "PATH=%~dp0dependencies\ffmpeg\ffmpeg-7.1.1-essentials_build\bin;%PATH%"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo No esta el entorno de Python.
    echo Ejecuta Instalar.bat en esta carpeta y vuelve a intentarlo.
    echo.
    echo Pulsa una tecla para cerrar.
    pause >nul
    exit /b 1
)

echo Iniciando Drako Cam...
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Drako Cam termino con el codigo %EXIT_CODE%.
    echo         Revisa el registro en %%APPDATA%%\DrakoCam\logs
    echo         Pulsa una tecla para cerrar.
    pause >nul
)
exit /b %EXIT_CODE%
