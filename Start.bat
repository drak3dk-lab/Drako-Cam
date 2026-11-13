@echo off
cd /d "%~dp0"
REM Busca el entorno de Python
IF EXIST ".venv" (
    echo Entorno .venv encontrado. Activando...
    call ".venv\Scripts\activate"
) ELSE (
    echo No hay .venv. Activando el entorno conda "drakocam"...
    call conda activate drakocam
)

echo Iniciando Drako Cam...
python main.py
SET EXIT_CODE=%ERRORLEVEL%

REM Si falla, la consola se queda abierta para leer el error.
IF %EXIT_CODE% NEQ 0 (
    echo.
    echo [ERROR] Drako Cam terminó con el código %EXIT_CODE%.
    echo         Revisa el texto de arriba y el registro en %%APPDATA%%\DrakoCam\logs
    echo         Pulsa una tecla para cerrar.
    pause >nul
)
