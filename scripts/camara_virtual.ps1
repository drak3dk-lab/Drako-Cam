# Registra y quita la camara virtual "Drako Cam" (Unity Capture).
# Lo cargan instalar.ps1 y desinstalar.ps1 con punto (dot-source).
# No hace nada si se ejecuta solo: no hay codigo fuera de las funciones.
# Windows PowerShell 5.1. Sin sintaxis de PowerShell 7.
#Requires -Version 5.1

$script:NombreCamaraDrako = "Drako Cam"
$script:Clsid64 = "{5C2CD55C-92AD-4999-8666-912BD3E70010}"
$script:Clsid32 = "{5C2CD55C-92AD-4999-8666-912BD3E70020}"

function Escribir-Camara([string]$Mensaje) {
    if (Get-Command Write-Log -ErrorAction SilentlyContinue) {
        Write-Log $Mensaje
        return
    }
    Write-Host $Mensaje
}

function Test-Administrador {
    try {
        $identidad = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identidad)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Leer-Registro([string]$Ruta, [string]$Nombre) {
    try {
        $valor = [Microsoft.Win32.Registry]::GetValue($Ruta, $Nombre, $null)
    } catch {
        return ""
    }
    if ($null -eq $valor) { return "" }
    return ([string]$valor).Trim()
}

function Ruta-DllCamara([string]$Raiz, [string]$Bits) {
    $nombre = "UnityCaptureFilter{0}.dll" -f $Bits
    return Join-Path (Join-Path (Join-Path $Raiz "vendor") "unitycapture") $nombre
}

function Rutas-Clsid([string]$Bits) {
    # La coma evita que PowerShell 5.1 desarme un array de un solo elemento.
    $lista = @()
    if ($Bits -eq "64") {
        $lista += "HKEY_LOCAL_MACHINE\SOFTWARE\Classes\CLSID\$($script:Clsid64)"
    } else {
        $lista += "HKEY_LOCAL_MACHINE\SOFTWARE\Classes\Wow6432Node\CLSID\$($script:Clsid32)"
        $lista += "HKEY_LOCAL_MACHINE\SOFTWARE\Classes\CLSID\$($script:Clsid32)"
    }
    return ,$lista
}

function Regsvr-De([string]$Bits) {
    if ($Bits -eq "32") {
        return Join-Path $env:SystemRoot "SysWOW64\regsvr32.exe"
    }
    return Join-Path $env:SystemRoot "System32\regsvr32.exe"
}

function Test-CamaraNuestra([string]$Raiz, [string]$Bits) {
    $dll = Ruta-DllCamara $Raiz $Bits
    if (-not (Test-Path -LiteralPath $dll)) { return $false }
    $dllFull = ""
    try { $dllFull = [System.IO.Path]::GetFullPath($dll) } catch { return $false }
    foreach ($base in (Rutas-Clsid $Bits)) {
        $nombre = Leer-Registro $base ""
        $servidor = Leer-Registro ($base + "\InprocServer32") ""
        if ($nombre -ne $script:NombreCamaraDrako) { continue }
        if (-not $servidor) { continue }
        $srvFull = $servidor
        try { $srvFull = [System.IO.Path]::GetFullPath($servidor) } catch { }
        if ($srvFull.ToLowerInvariant() -eq $dllFull.ToLowerInvariant()) {
            return $true
        }
    }
    return $false
}

function Test-ServidorNuestro([string]$Raiz, [string]$Bits) {
    $dll = Ruta-DllCamara $Raiz $Bits
    if (-not (Test-Path -LiteralPath $dll)) { return $false }
    $dllFull = ""
    try { $dllFull = [System.IO.Path]::GetFullPath($dll) } catch { return $false }
    foreach ($base in (Rutas-Clsid $Bits)) {
        $servidor = Leer-Registro ($base + "\InprocServer32") ""
        if (-not $servidor) { continue }
        $srvFull = $servidor
        try { $srvFull = [System.IO.Path]::GetFullPath($servidor) } catch { }
        if ($srvFull.ToLowerInvariant() -eq $dllFull.ToLowerInvariant()) {
            return $true
        }
    }
    return $false
}

function Invocar-Regsvr([string]$Regsvr, [string]$Argumentos, [string]$Directorio) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Regsvr
    $psi.Arguments = $Argumentos
    $psi.WorkingDirectory = $Directorio
    $psi.UseShellExecute = $false
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    try {
        [void]$proc.Start()
    } catch {
        Escribir-Camara ("No se pudo iniciar regsvr32: {0}" -f $_.Exception.Message)
        return -1
    }
    try { $proc.WaitForExit() } catch { }
    $codigo = -1
    try { $codigo = [int]$proc.ExitCode } catch { $codigo = -1 }
    try { $proc.Dispose() } catch { }
    return $codigo
}

function Registrar-UnaDll([string]$Raiz, [string]$Bits) {
    $dll = Ruta-DllCamara $Raiz $Bits
    if (-not (Test-Path -LiteralPath $dll)) {
        if ($Bits -eq "64") {
            Escribir-Camara "Falta vendor\unitycapture\UnityCaptureFilter64.dll."
            return $false
        }
        Escribir-Camara "No está el filtro de 32 bits. La cámara de 64 bits sigue valiendo para Meet, Zoom y Teams."
        return $true
    }
    if (Test-CamaraNuestra $Raiz $Bits) {
        Escribir-Camara ("La cámara «{0}» ({1} bits) ya está registrada. No se duplica." -f $script:NombreCamaraDrako, $Bits)
        return $true
    }
    try { Unblock-File -LiteralPath $dll -ErrorAction SilentlyContinue } catch { }
    $regsvr = Regsvr-De $Bits
    if (-not (Test-Path -LiteralPath $regsvr)) {
        Escribir-Camara ("No encuentro {0}." -f $regsvr)
        return $false
    }
    $dir = Split-Path -Parent $dll
    $argumentos = '/s "' + $dll + '" /i:UnityCaptureName="Drako Cam"'
    Escribir-Camara ("Registro {0} bits: {1}" -f $Bits, $dll)
    $codigo = Invocar-Regsvr $regsvr $argumentos $dir
    if ($codigo -ne 0) {
        Escribir-Camara ("regsvr32 devolvió {0} al registrar el filtro de {1} bits." -f $codigo, $Bits)
        return $false
    }
    if (-not (Test-CamaraNuestra $Raiz $Bits)) {
        Escribir-Camara ("regsvr32 terminó, pero el registro no muestra «{0}» en {1} bits." -f $script:NombreCamaraDrako, $Bits)
        return $false
    }
    Escribir-Camara ("Cámara «{0}» registrada ({1} bits)." -f $script:NombreCamaraDrako, $Bits)
    return $true
}

function Quitar-UnaDll([string]$Raiz, [string]$Bits) {
    $dll = Ruta-DllCamara $Raiz $Bits
    if (-not (Test-Path -LiteralPath $dll)) { return $true }
    if (-not (Test-ServidorNuestro $Raiz $Bits)) {
        Escribir-Camara ("El filtro de {0} bits no apunta a esta copia. No se desregistra." -f $Bits)
        return $true
    }
    $regsvr = Regsvr-De $Bits
    if (-not (Test-Path -LiteralPath $regsvr)) {
        Escribir-Camara ("No encuentro {0}." -f $regsvr)
        return $false
    }
    $dir = Split-Path -Parent $dll
    $argumentos = '/u /s "' + $dll + '"'
    Escribir-Camara ("Desregistro {0} bits: {1}" -f $Bits, $dll)
    $codigo = Invocar-Regsvr $regsvr $argumentos $dir
    if ($codigo -ne 0) {
        Escribir-Camara ("regsvr32 devolvió {0} al quitar el filtro de {1} bits." -f $codigo, $Bits)
        return $false
    }
    Escribir-Camara ("Cámara «{0}» desregistrada ({1} bits)." -f $script:NombreCamaraDrako, $Bits)
    return $true
}

function Invocar-Elevado([string]$ScriptPs1, [string]$Interruptor) {
    $ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    # Una sola cadena, con la ruta entre comillas: ArgumentList como array
    # no cita bien las rutas con espacios en Windows PowerShell 5.1.
    $lista = '-NoProfile -ExecutionPolicy Bypass -File "' + $ScriptPs1 + '" ' + $Interruptor
    try {
        $proc = Start-Process -FilePath $ps -ArgumentList $lista -Verb RunAs -Wait -PassThru
    } catch {
        Escribir-Camara ("No se concedió el permiso de administrador: {0}" -f $_.Exception.Message)
        return -1
    }
    if ($null -eq $proc) { return -1 }
    $codigo = -1
    try { $codigo = [int]$proc.ExitCode } catch { $codigo = -1 }
    return $codigo
}

function Mensaje-SinAdmin {
    return @(
        "No se pudo registrar la cámara virtual «Drako Cam» porque esta ventana no tiene permisos de administrador.",
        "",
        "Cierra esta ventana, haz clic derecho en Instalar.bat y elige «Ejecutar como administrador».",
        "Solo hace falta una vez. Sin eso, Meet, Zoom y Teams no verán la cámara «Drako Cam».",
        "OBS no es obligatorio: queda solo como respaldo si la cámara propia no está disponible."
    ) -join "`r`n"
}

function Registrar-CamaraDrako {
    param(
        [Parameter(Mandatory = $true)][string]$Raiz,
        [switch]$YaElevado
    )
    $dll64 = Ruta-DllCamara $Raiz "64"
    if (-not (Test-Path -LiteralPath $dll64)) {
        $script:AvisoCamara = "No encuentro el controlador de la cámara «Drako Cam» (vendor\unitycapture\UnityCaptureFilter64.dll)."
        Escribir-Camara $script:AvisoCamara
        return $false
    }
    $ya64 = Test-CamaraNuestra $Raiz "64"
    $ya32 = Test-CamaraNuestra $Raiz "32"
    $hay32 = Test-Path -LiteralPath (Ruta-DllCamara $Raiz "32")
    if ($ya64 -and ((-not $hay32) -or $ya32)) {
        Escribir-Camara "La cámara virtual «Drako Cam» ya está registrada. No se duplica."
        $script:AvisoCamara = ""
        return $true
    }
    if (-not (Test-Administrador)) {
        if ($YaElevado) {
            $script:AvisoCamara = Mensaje-SinAdmin
            Escribir-Camara $script:AvisoCamara
            return $false
        }
        Escribir-Camara "Hace falta administrador una vez para registrar la cámara «Drako Cam». Windows pedirá permiso."
        Write-Host ""
        Write-Host "Se va a pedir permiso de administrador para registrar la cámara «Drako Cam»." -ForegroundColor Yellow
        Write-Host "Solo hace falta una vez. No instala ni abre OBS." -ForegroundColor Yellow
        Write-Host ""
        $scriptInstalar = Join-Path $PSScriptRoot "instalar.ps1"
        $codigo = Invocar-Elevado $scriptInstalar "-SoloCamara"
        if (($codigo -eq 0) -and (Test-CamaraNuestra $Raiz "64")) {
            Escribir-Camara "Cámara «Drako Cam» registrada."
            $script:AvisoCamara = ""
            return $true
        }
        $script:AvisoCamara = Mensaje-SinAdmin
        Escribir-Camara $script:AvisoCamara
        return $false
    }
    $ok64 = Registrar-UnaDll $Raiz "64"
    $ok32 = Registrar-UnaDll $Raiz "32"
    if ($ok64) {
        if (-not $ok32) {
            Escribir-Camara "La cámara de 64 bits quedó registrada. El filtro de 32 bits no. Meet, Zoom y Teams de 64 bits la verán igual."
        }
        $script:AvisoCamara = ""
        return $true
    }
    $script:AvisoCamara = Mensaje-SinAdmin
    return $false
}

function Quitar-CamaraDrako {
    param(
        [Parameter(Mandatory = $true)][string]$Raiz,
        [switch]$YaElevado,
        [switch]$Silencioso
    )
    $dll64 = Ruta-DllCamara $Raiz "64"
    $dll32 = Ruta-DllCamara $Raiz "32"
    $hayDll = (Test-Path -LiteralPath $dll64) -or (Test-Path -LiteralPath $dll32)
    if (-not $hayDll) {
        Escribir-Camara "No hay controlador de cámara virtual que quitar."
        return $true
    }
    $nuestra = (Test-ServidorNuestro $Raiz "64") -or (Test-ServidorNuestro $Raiz "32")
    if (-not $nuestra) {
        Escribir-Camara "La cámara «Drako Cam» de esta copia no está registrada. No se toca otra cámara."
        return $true
    }
    if (-not (Test-Administrador)) {
        if ($YaElevado) {
            $script:AvisoCamara = "Sin permisos de administrador no se pudo quitar la cámara «Drako Cam». Ejecuta Desinstalar.bat como administrador."
            Escribir-Camara $script:AvisoCamara
            return $false
        }
        if (-not $Silencioso) {
            Write-Host ""
            Write-Host "Se va a pedir permiso de administrador para quitar la cámara «Drako Cam»." -ForegroundColor Yellow
            Write-Host ""
        }
        $scriptQuitar = Join-Path $PSScriptRoot "desinstalar.ps1"
        $codigo = Invocar-Elevado $scriptQuitar "-SoloCamara"
        if ($codigo -eq 0) {
            Escribir-Camara "Cámara «Drako Cam» desregistrada."
            $script:AvisoCamara = ""
            return $true
        }
        $script:AvisoCamara = "No se pudo quitar la cámara «Drako Cam». Haz clic derecho en Desinstalar.bat y elige «Ejecutar como administrador»."
        Escribir-Camara $script:AvisoCamara
        return $false
    }
    $ok64 = Quitar-UnaDll $Raiz "64"
    $ok32 = Quitar-UnaDll $Raiz "32"
    if ($ok64 -and $ok32) {
        $script:AvisoCamara = ""
        return $true
    }
    $script:AvisoCamara = "No se pudo quitar del todo la cámara «Drako Cam». Vuelve a ejecutar Desinstalar.bat como administrador."
    Escribir-Camara $script:AvisoCamara
    return $false
}
