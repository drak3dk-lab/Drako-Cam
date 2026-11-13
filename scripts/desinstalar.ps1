# Quita el entorno .venv y los accesos directos de Drako Cam.
# No borra %APPDATA%\DrakoCam salvo que la persona lo confirme
# o se pase -BorrarDatos junto con -Silencioso.
# Lo llama Desinstalar.bat. El desinstalador .exe lo llama con -Silencioso.
#Requires -Version 5.1
param(
    [switch]$Silencioso,
    [switch]$BorrarDatos
)

$ErrorActionPreference = "Stop"

$script:Utf8 = New-Object System.Text.UTF8Encoding $false
$script:Raiz = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$script:Venv = Join-Path $script:Raiz ".venv"

$baseLocal = $env:LOCALAPPDATA
if (-not $baseLocal) { $baseLocal = $env:TEMP }
$script:RutasLog = @(
    (Join-Path (Join-Path $baseLocal "DrakoCam\logs") "instalacion.log")
)

try { & "$env:SystemRoot\System32\chcp.com" 65001 | Out-Null } catch { }
try { [Console]::OutputEncoding = $script:Utf8 } catch { }
$OutputEncoding = $script:Utf8

function Write-Log([string]$Mensaje) {
    $linea = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Mensaje
    Write-Host $linea
    foreach ($ruta in $script:RutasLog) {
        try {
            $dir = Split-Path -Parent $ruta
            if (-not (Test-Path -LiteralPath $dir)) {
                New-Item -ItemType Directory -Path $dir -Force | Out-Null
            }
            [System.IO.File]::AppendAllText($ruta, $linea + "`r`n", $script:Utf8)
        } catch {
            # Si el registro no se puede escribir, la ventana sigue valiendo.
        }
    }
}

function Remove-Arbol([string]$Ruta) {
    if (-not (Test-Path -LiteralPath $Ruta)) { return }
    & cmd.exe /c "rmdir /s /q `"$Ruta`""
    if (Test-Path -LiteralPath $Ruta) {
        $vacio = Join-Path $env:TEMP ("drako-vacio-" + [guid]::NewGuid().ToString("n"))
        New-Item -ItemType Directory -Path $vacio -Force | Out-Null
        & robocopy.exe $vacio $Ruta /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null
        Remove-Item -LiteralPath $vacio -Force -Recurse -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $Ruta -Force -Recurse -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $Ruta) {
        throw "No se pudo borrar '$Ruta'. Cierra Drako Cam si está abierto y vuelve a intentarlo."
    }
}

function Confirma([string]$Pregunta) {
    Write-Host ""
    Write-Host $Pregunta
    $resp = Read-Host "Escribe SI para aceptar"
    if ($null -eq $resp) { return $false }
    $resp = $resp.Trim().ToUpperInvariant()
    return (($resp -eq "SI") -or ($resp -eq "SÍ") -or ($resp -eq "S"))
}

function Quitar-PreferenciaGpu {
    # Quita GpuPreference=2 escrito para python.exe, pythonw.exe y main.py.
    $clave = "HKCU:\Software\Microsoft\DirectX\UserGpuPreferences"
    if (-not (Test-Path $clave)) { return }
    $py = Join-Path (Join-Path $script:Venv "Scripts") "python.exe"
    $pyw = Join-Path (Join-Path $script:Venv "Scripts") "pythonw.exe"
    $main = Join-Path $script:Raiz "main.py"
    foreach ($ruta in @($py, $pyw, $main)) {
        Remove-ItemProperty -Path $clave -Name $ruta -ErrorAction SilentlyContinue
    }
    Write-Log "Preferencia de GPU dedicada retirada."
}

function Quitar-Acceso([string]$RutaLnk) {
    if (-not (Test-Path -LiteralPath $RutaLnk)) { return }
    Remove-Item -LiteralPath $RutaLnk -Force
    Write-Log ("Acceso directo borrado: {0}" -f $RutaLnk)
}

try {
    try { $Host.UI.RawUI.WindowTitle = "Drako Cam - desinstalación" } catch { }
    Write-Log "======== Drako Cam: desinstalación ========"
    Write-Log ("Carpeta: {0}" -f $script:Raiz)

    if (-not $Silencioso) {
        $texto = @(
            "Se va a borrar:",
            "  - el entorno de Python (.venv) de esta carpeta",
            "  - los accesos directos «Drako Cam» del escritorio y del menú Inicio",
            "",
            "No se borra la carpeta del programa ni los modelos ya descargados.",
            "La configuración de %APPDATA%\DrakoCam se pregunta después.",
            "",
            "Carpeta del programa:",
            "  $($script:Raiz)"
        ) -join "`r`n"
        if (-not (Confirma $texto)) {
            Write-Host ""
            Write-Host "No se ha borrado nada."
            Write-Log "La persona canceló la desinstalación. No se borró nada."
            exit 0
        }
    }

    if (Test-Path -LiteralPath $script:Venv) {
        Write-Log "Borrando el entorno .venv..."
        Remove-Arbol $script:Venv
        Write-Log "Entorno .venv borrado."
    } else {
        Write-Log "No había entorno .venv."
    }

    $escritorio = [Environment]::GetFolderPath("Desktop")
    $menu = [Environment]::GetFolderPath("Programs")
    if ($escritorio) { Quitar-Acceso (Join-Path $escritorio "Drako Cam.lnk") }
    if ($menu) { Quitar-Acceso (Join-Path $menu "Drako Cam.lnk") }
    Quitar-PreferenciaGpu

    $datos = Join-Path $env:APPDATA "DrakoCam"
    $borrarDatos = $false
    if ($Silencioso) {
        $borrarDatos = [bool]$BorrarDatos
    } elseif (Test-Path -LiteralPath $datos) {
        $preguntaDatos = @(
            "¿Borrar también la configuración, la contraseña y los registros?",
            "Carpeta:",
            "  $datos",
            "",
            "Si los borras, la próxima vez Drako Cam pedirá crear la contraseña de nuevo.",
            "Cualquier respuesta que no sea SI los conserva."
        ) -join "`r`n"
        $borrarDatos = Confirma $preguntaDatos
    } else {
        Write-Log "No hay datos en %APPDATA%\DrakoCam."
    }

    if ($borrarDatos) {
        if (Test-Path -LiteralPath $datos) {
            Write-Log ("Borrando datos de {0}" -f $datos)
            Remove-Arbol $datos
            Write-Log "Datos de Drako Cam borrados."
        }
    } else {
        Write-Log "Se conservan los datos de %APPDATA%\DrakoCam."
    }

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  Entorno y accesos directos quitados" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "La carpeta del programa sigue en:"
    Write-Host ("  " + $script:Raiz)
    Write-Host "Puedes borrarla a mano si ya no quieres Drako Cam."
    Write-Host "Si lo instalaste con el archivo .exe, también puedes quitarlo"
    Write-Host "desde Configuración de Windows, Aplicaciones, Drako Cam."
    if (-not $borrarDatos) {
        Write-Host ""
        Write-Host "La contraseña y los registros siguen en:"
        Write-Host ("  " + $datos)
    }
    Write-Log "Desinstalación del entorno terminada."
    exit 0
} catch {
    $detalle = $_.Exception.Message
    if (-not $detalle) { $detalle = "$_" }
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  No se pudo terminar la desinstalación" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host $detalle -ForegroundColor Red
    Write-Host ""
    Write-Host "Cierra Drako Cam y vuelve a ejecutar Desinstalar.bat."
    try { Write-Log ("ERROR: " + $detalle) } catch { }
    exit 1
}
