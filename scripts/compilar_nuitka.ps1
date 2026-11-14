# Compila Drako Cam a DrakoCam.exe con Nuitka y escribe el manifiesto de integridad.
# No publica un release. No guarda tokens.
# Ejecutar en Windows, en la carpeta del repositorio:
#   powershell -ExecutionPolicy Bypass -File scripts\compilar_nuitka.ps1
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$raiz = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
Set-Location $raiz

$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

Write-Host "Compruebo Nuitka. Si falta, se instala solo en este entorno."
& $python -m pip install --disable-pip-version-check "nuitka>=2.5"
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo instalar Nuitka. Alternativa: PyArmor, con 'pyarmor gen -O dist main.py'. Tampoco publiques el resultado sin el ok de Drako."
}

$icono = Join-Path $raiz "installer\logo.ico"
$argumentos = @(
    "-m", "nuitka",
    "--standalone",
    "--assume-yes-for-downloads",
    "--output-dir=dist",
    "--output-filename=DrakoCam.exe",
    "--windows-console-mode=disable",
    "--include-package=app",
    "--include-data-dir=app/ui/core/media=app/ui/core/media",
    "--include-data-dir=app/ui/styles=app/ui/styles"
)
if (Test-Path -LiteralPath $icono) {
    $argumentos += "--windows-icon-from-ico=$icono"
}
$argumentos += "main.py"
& $python @argumentos
if ($LASTEXITCODE -ne 0) {
    throw "Nuitka no terminó. No se ha publicado nada."
}

$salida = Join-Path $raiz "dist\main.dist"
if (-not (Test-Path -LiteralPath (Join-Path $salida "DrakoCam.exe"))) {
    $salida = Join-Path $raiz "dist\main.build"
}
$exe = Get-ChildItem -Path (Join-Path $raiz "dist") -Filter "DrakoCam.exe" -Recurse | Select-Object -First 1
if (-not $exe) {
    throw "Nuitka terminó pero no aparece DrakoCam.exe."
}

Copy-Item -LiteralPath $exe.FullName -Destination (Join-Path $raiz "DrakoCam.exe") -Force
& $python -c @"
from pathlib import Path
from app.drako.integridad import escribir_manifiesto
raiz = Path(r'$raiz')
escribir_manifiesto(raiz, ['DrakoCam.exe'])
"@
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo escribir integridad_manifiesto.json."
}
Write-Host "Listo: DrakoCam.exe y integridad_manifiesto.json en la carpeta del programa."
Write-Host "No se ha creado ningún release. Drako tiene que dar el ok antes de publicarlo."
