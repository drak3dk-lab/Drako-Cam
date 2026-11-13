# Instala Drako Cam en Windows: uv, Python 3.12, FFmpeg 7.1.1,
# el entorno .venv, los componentes y los accesos directos.
# Lo llama Instalar.bat con ExecutionPolicy Bypass, solo para este proceso.
# Compatible con Windows PowerShell 5.1. No uses sintaxis de PowerShell 7.
#Requires -Version 5.1
param(
    [switch]$DesdeInstalador,
    [switch]$SoloComprobar
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$script:Utf8 = New-Object System.Text.UTF8Encoding $false
$script:Raiz = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$script:Venv = Join-Path $script:Raiz ".venv"
$script:Vbs = Join-Path $PSScriptRoot "Arrancar.vbs"
$script:FfmpegBuild = Join-Path (Join-Path $script:Raiz "dependencies\ffmpeg") "ffmpeg-7.1.1-essentials_build"
$script:FfmpegLocal = Join-Path $script:FfmpegBuild "bin\ffmpeg.exe"
$script:HayRed = $false
$script:AvisoGpu = $false
$script:TextoAvisoGpu = ""
$script:ResumenNvidia = ""
$script:UvExe = ""

$baseLocal = $env:LOCALAPPDATA
if (-not $baseLocal) { $baseLocal = $env:TEMP }
if ($env:USERPROFILE) {
    $script:UvDir = Join-Path (Join-Path $env:USERPROFILE ".local") "bin"
} else {
    $script:UvDir = Join-Path (Join-Path $baseLocal "DrakoCam") "uv"
}
$script:RutasLog = @(
    (Join-Path (Join-Path $baseLocal "DrakoCam\logs") "instalacion.log"),
    (Join-Path (Join-Path $script:Raiz "logs") "instalacion.log")
)

try { & "$env:SystemRoot\System32\chcp.com" 65001 | Out-Null } catch { }
try { [Console]::OutputEncoding = $script:Utf8 } catch { }
$OutputEncoding = $script:Utf8
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
}

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
            # Si un registro no se puede escribir, la ventana sigue valiendo.
        }
    }
}

function Paso([string]$Numero, [string]$Texto) {
    Write-Log ""
    Write-Log ("[{0}] {1}" -f $Numero, $Texto)
}

function Asegurar-Directorio([string]$Ruta) {
    if (-not (Test-Path -LiteralPath $Ruta)) {
        New-Item -ItemType Directory -Path $Ruta -Force | Out-Null
    }
}

function Desbloquear([string]$Ruta) {
    if (Test-Path -LiteralPath $Ruta) {
        try { Unblock-File -LiteralPath $Ruta -ErrorAction SilentlyContinue } catch { }
    }
}

function Formatear-Argumentos([string[]]$Argumentos) {
    $partes = @()
    foreach ($arg in $Argumentos) {
        if ($null -eq $arg) { continue }
        if ($arg -match '[\s"]') {
            $partes += ('"' + ($arg -replace '"', '\"') + '"')
        } else {
            $partes += $arg
        }
    }
    return ($partes -join " ")
}

function Invocar-Proceso {
    param(
        [Parameter(Mandatory = $true)][string]$Archivo,
        [string[]]$Argumentos = @(),
        [string]$Directorio = "",
        [int]$TiempoSegundos = 0,
        [hashtable]$EntornoExtra = $null
    )
    if (-not $Directorio) { $Directorio = $script:Raiz }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Archivo
    $psi.Arguments = (Formatear-Argumentos $Argumentos)
    $psi.WorkingDirectory = $Directorio
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $false
    if ($EntornoExtra) {
        foreach ($clave in @($EntornoExtra.Keys)) {
            $psi.EnvironmentVariables[$clave] = [string]$EntornoExtra[$clave]
        }
    }
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    Write-Log ("Ejecuto: {0} {1}" -f (Split-Path -Leaf $Archivo), ($Argumentos -join " "))
    try {
        [void]$proc.Start()
    } catch {
        throw ("No se pudo iniciar {0}: {1}" -f $Archivo, $_.Exception.Message)
    }
    $termino = $true
    if ($TiempoSegundos -gt 0) {
        $termino = $proc.WaitForExit($TiempoSegundos * 1000)
        if (-not $termino) {
            try { $proc.Kill() } catch { }
            try { $proc.WaitForExit() } catch { }
            $proc.Dispose()
            Write-Log ("Se agotó el tiempo ({0} s) al ejecutar {1}." -f $TiempoSegundos, (Split-Path -Leaf $Archivo))
            return -1
        }
    }
    try { $proc.WaitForExit() } catch { }
    $codigo = $proc.ExitCode
    $proc.Dispose()
    return $codigo
}

function Invocar-Captura {
    param(
        [Parameter(Mandatory = $true)][string]$Archivo,
        [string[]]$Argumentos = @(),
        [string]$Directorio = "",
        [int]$TiempoSegundos = 40
    )
    if (-not $Directorio) { $Directorio = $script:Raiz }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Archivo
    $psi.Arguments = (Formatear-Argumentos $Argumentos)
    $psi.WorkingDirectory = $Directorio
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = $script:Utf8
    $psi.StandardErrorEncoding = $script:Utf8
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $codigo = -1
    $texto = ""
    try {
        [void]$proc.Start()
        $tareaOut = $null
        $tareaErr = $null
        $sync = $false
        try {
            $tareaOut = $proc.StandardOutput.ReadToEndAsync()
            $tareaErr = $proc.StandardError.ReadToEndAsync()
        } catch {
            $sync = $true
        }
        if ($sync) {
            $texto = $proc.StandardOutput.ReadToEnd()
            try { $texto = $texto + "`n" + $proc.StandardError.ReadToEnd() } catch { }
            try { $proc.WaitForExit($TiempoSegundos * 1000) | Out-Null } catch { }
            try { $codigo = $proc.ExitCode } catch { $codigo = -1 }
        } else {
            $termino = $proc.WaitForExit($TiempoSegundos * 1000)
            if (-not $termino) {
                try { $proc.Kill() } catch { }
            }
            try { $proc.WaitForExit() } catch { }
            if ($termino) {
                try { $codigo = $proc.ExitCode } catch { $codigo = -1 }
            }
            try { $texto = [string]$tareaOut.Result } catch { $texto = "" }
            try { $texto = $texto + "`n" + [string]$tareaErr.Result } catch { }
        }
    } catch {
        $texto = $_.Exception.Message
        $codigo = -1
    } finally {
        try { $proc.Dispose() } catch { }
    }
    return @{ Codigo = $codigo; Texto = $texto }
}

function Primera-Linea([string]$Texto) {
    if (-not $Texto) { return "" }
    foreach ($linea in ($Texto -split "`r?`n")) {
        if ($linea.Trim() -ne "") { return $linea.Trim() }
    }
    return ""
}

function Espacio-LibreGB([string]$Ruta) {
    try {
        $completo = [System.IO.Path]::GetFullPath($Ruta)
        $raizUnidad = [System.IO.Path]::GetPathRoot($completo)
        $unidad = New-Object System.IO.DriveInfo($raizUnidad)
        if (-not $unidad.IsReady) { return -1 }
        return [math]::Round(($unidad.AvailableFreeSpace / 1GB), 1)
    } catch {
        return -1
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

function Assert-AppCerrada {
    $procesos = @()
    try {
        $procesos = @(Get-Process -Name python, pythonw -ErrorAction SilentlyContinue)
    } catch {
        return
    }
    $prefijo = $script:Raiz.TrimEnd('\') + '\'
    foreach ($proc in $procesos) {
        $rutaProc = $null
        try { $rutaProc = $proc.Path } catch { continue }
        if (-not $rutaProc) { continue }
        if ($rutaProc.StartsWith($prefijo, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Drako Cam está abierto. Ciérralo y vuelve a ejecutar Instalar.bat."
        }
    }
}

function Test-Red {
    $urls = @("https://pypi.org", "https://github.com")
    foreach ($url in $urls) {
        try {
            $cliente = New-Object System.Net.WebClient
            $cliente.Headers.Add("User-Agent", "DrakoCam-Instalador")
            $null = $cliente.DownloadString($url)
            return $true
        } catch {
            Write-Log ("Sin respuesta de {0}." -f $url)
        }
    }
    return $false
}

function Test-Zip([string]$Ruta) {
    if (-not (Test-Path -LiteralPath $Ruta)) { return $false }
    $fs = [System.IO.File]::OpenRead($Ruta)
    try {
        $b0 = $fs.ReadByte()
        $b1 = $fs.ReadByte()
        return ($b0 -eq 0x50 -and $b1 -eq 0x4B)
    } finally {
        $fs.Close()
    }
}

function Recibir-Archivo([string]$Url, [string]$Destino) {
    $dir = Split-Path -Parent $Destino
    Asegurar-Directorio $dir
    $intento = 0
    $ultimo = ""
    while ($intento -lt 3) {
        $intento++
        if (Test-Path -LiteralPath $Destino) {
            Remove-Item -LiteralPath $Destino -Force
        }
        Write-Log ("Descargando ({0}/3): {1}" -f $intento, $Url)
        $respuesta = $null
        $entrada = $null
        $salida = $null
        try {
            $peticion = [System.Net.HttpWebRequest]::Create($Url)
            $peticion.UserAgent = "DrakoCam-Instalador"
            $peticion.Timeout = 60000
            $peticion.ReadWriteTimeout = 120000
            $peticion.AllowAutoRedirect = $true
            $respuesta = $peticion.GetResponse()
            $total = $respuesta.ContentLength
            $entrada = $respuesta.GetResponseStream()
            $salida = [System.IO.File]::Create($Destino)
            $buffer = New-Object byte[] 65536
            $leidoTotal = [int64]0
            $ultimoAviso = [DateTime]::MinValue
            while ($true) {
                $n = $entrada.Read($buffer, 0, $buffer.Length)
                if ($n -le 0) { break }
                $salida.Write($buffer, 0, $n)
                $leidoTotal += $n
                $ahora = [DateTime]::UtcNow
                if (($ahora - $ultimoAviso).TotalSeconds -ge 2) {
                    $ultimoAviso = $ahora
                    if ($total -gt 0) {
                        $porcentaje = [math]::Floor(100.0 * $leidoTotal / $total)
                        Write-Host ("  {0}%  ({1} MB)" -f $porcentaje, [math]::Round($leidoTotal / 1MB, 1))
                    } else {
                        Write-Host ("  {0} MB" -f [math]::Round($leidoTotal / 1MB, 1))
                    }
                }
            }
            $salida.Close()
            $salida = $null
            $entrada.Close()
            $entrada = $null
            $respuesta.Close()
            $respuesta = $null
            if (-not (Test-Zip $Destino)) {
                throw "la descarga no es un archivo zip"
            }
            Write-Log ("Descarga lista ({0} MB)." -f [math]::Round(((Get-Item -LiteralPath $Destino).Length / 1MB), 1))
            return
        } catch {
            $ultimo = $_.Exception.Message
            Write-Log ("Intento {0} fallido: {1}" -f $intento, $ultimo)
            Start-Sleep -Seconds (5 * $intento)
        } finally {
            if ($salida) { try { $salida.Close() } catch { } }
            if ($entrada) { try { $entrada.Close() } catch { } }
            if ($respuesta) { try { $respuesta.Close() } catch { } }
        }
    }
    throw "No se pudo descargar $Url. $ultimo"
}

function Actualizar-Path {
    $maquina = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $usuario = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $maquina) { $maquina = "" }
    if (-not $usuario) { $usuario = "" }
    $env:Path = "$maquina;$usuario"
}

function Add-PathDeSesion([string]$Directorio) {
    if (-not $Directorio) { return }
    $limpio = $Directorio.TrimEnd('\')
    $resto = @()
    foreach ($parte in ($env:Path -split ';')) {
        if (-not $parte) { continue }
        if ($parte.TrimEnd('\').Equals($limpio, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
        $resto += $parte
    }
    $env:Path = $limpio + ';' + ($resto -join ';')
}

function Notificar-CambioDeEntorno {
    try {
        if (-not ("DrakoCam.Entorno" -as [type])) {
            Add-Type -Namespace DrakoCam -Name Entorno -MemberDefinition '[DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);'
        }
        $resultado = [UIntPtr]::Zero
        [void][DrakoCam.Entorno]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, "Environment", 2, 5000, [ref]$resultado)
    } catch {
        Write-Log "No pude avisar a Windows del PATH nuevo. Esta instalación ya lo usa, sin reiniciar."
    }
}

function Add-PathDeUsuario([string]$Directorio) {
    if (-not $Directorio) { return }
    if (-not (Test-Path -LiteralPath $Directorio)) { return }
    $limpio = $Directorio.TrimEnd('\')
    $usuario = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $usuario) { $usuario = "" }
    $ya = $false
    foreach ($parte in ($usuario -split ';')) {
        if (-not $parte) { continue }
        if ($parte.TrimEnd('\').Equals($limpio, [System.StringComparison]::OrdinalIgnoreCase)) {
            $ya = $true
            break
        }
    }
    if (-not $ya) {
        if ($usuario) {
            $nuevo = $limpio + ';' + $usuario
        } else {
            $nuevo = $limpio
        }
        [Environment]::SetEnvironmentVariable("Path", $nuevo, "User")
        Notificar-CambioDeEntorno
    }
    Add-PathDeSesion $limpio
}

function Buscar-FfmpegEnPath {
    $cmd = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Es-Ffmpeg711([string]$Version) {
    return ($Version -match '^7\.1\.1($|[^0-9])')
}

function Version-De-Ffmpeg([string]$Exe) {
    if (-not $Exe) { return "" }
    if (-not (Test-Path -LiteralPath $Exe)) { return "" }
    $cap = Invocar-Captura -Archivo $Exe -Argumentos @("-version") -TiempoSegundos 20
    if ($cap.Codigo -ne 0) { return "" }
    $linea = Primera-Linea $cap.Texto
    if ($linea -match 'ffmpeg version\s+(\S+)') { return $Matches[1] }
    return ""
}

function Buscar-NvidiaSmi {
    $candidatos = @()
    $cmd = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($cmd) { $candidatos += $cmd.Source }
    $candidatos += (Join-Path $env:SystemRoot "System32\nvidia-smi.exe")
    $candidatos += (Join-Path $env:ProgramFiles "NVIDIA Corporation\NVSMI\nvidia-smi.exe")
    foreach ($ruta in $candidatos) {
        if ($ruta -and (Test-Path -LiteralPath $ruta)) { return $ruta }
    }
    return $null
}

function Test-UvExe([string]$Exe) {
    if (-not (Test-Path -LiteralPath $Exe)) { return $false }
    $cap = Invocar-Captura -Archivo $Exe -Argumentos @("--version") -TiempoSegundos 30
    if ($cap.Codigo -ne 0) { return $false }
    $linea = Primera-Linea $cap.Texto
    if ($linea) { Write-Log ("uv: {0}" -f $linea) }
    return $true
}

function Instalar-UvDescarga {
    $zip = Join-Path $env:TEMP "drako-uv.zip"
    $tmp = Join-Path $env:TEMP ("drako-uv-" + [guid]::NewGuid().ToString("n"))
    $url = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
    try {
        Recibir-Archivo $url $zip
        Asegurar-Directorio $tmp
        Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
        $encontrado = Get-ChildItem -LiteralPath $tmp -Filter uv.exe -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $encontrado) { throw "El archivo de uv no trae uv.exe." }
        Asegurar-Directorio $script:UvDir
        Copy-Item -LiteralPath $encontrado.FullName -Destination (Join-Path $script:UvDir "uv.exe") -Force
        Desbloquear (Join-Path $script:UvDir "uv.exe")
    } finally {
        if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue }
        if (Test-Path -LiteralPath $tmp) {
            try { Remove-Arbol $tmp } catch { }
        }
    }
}

function Asegurar-Uv {
    $uv = Join-Path $script:UvDir "uv.exe"
    $cargo = Join-Path (Join-Path $env:USERPROFILE ".cargo") "bin\uv.exe"
    Add-PathDeSesion $script:UvDir
    if (Test-UvExe $uv) {
        $script:UvExe = $uv
        Add-PathDeUsuario $script:UvDir
        Write-Log ("uv está en el PATH de esta sesión: {0}" -f $script:UvDir)
        if ($script:HayRed) {
            Write-Log "Busco si hay una versión más nueva de uv..."
            $codigo = Invocar-Proceso -Archivo $script:UvExe -Argumentos @("self", "update") -TiempoSegundos 120
            if ($codigo -ne 0) {
                Write-Log "No se actualizó uv. Sigo con la copia que ya funciona."
            }
            if (-not (Test-UvExe $script:UvExe)) {
                Write-Log "uv dejó de responder. Lo vuelvo a instalar."
                Instalar-UvOficial
            }
        }
        return
    }
    if (-not $script:HayRed) {
        if (Test-UvExe $cargo) {
            $script:UvExe = $cargo
            Add-PathDeSesion (Split-Path -Parent $cargo)
            Write-Log "Sin internet. Uso el uv que ya está en la carpeta del usuario."
            return
        }
        $delPath = Get-Command uv.exe -ErrorAction SilentlyContinue
        if ($delPath -and (Test-UvExe $delPath.Source)) {
            $script:UvExe = $delPath.Source
            Add-PathDeSesion (Split-Path -Parent $delPath.Source)
            Write-Log "Sin internet. Uso el uv que ya está en el PATH."
            return
        }
        throw "Falta uv y no hay internet. Conéctate y vuelve a ejecutar Instalar.bat."
    }
    Instalar-UvOficial
}

function Instalar-UvOficial {
    Write-Log "Instalo uv con el instalador oficial. No hace falta reiniciar."
    $orden = "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; irm https://astral.sh/uv/install.ps1 | iex"
    $powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $null = Invocar-Proceso -Archivo $powershell -Argumentos @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command", $orden
    ) -TiempoSegundos 180
    Add-PathDeSesion $script:UvDir
    $uv = Join-Path $script:UvDir "uv.exe"
    if (Test-UvExe $uv) {
        $script:UvExe = $uv
        Add-PathDeUsuario $script:UvDir
        Write-Log ("uv quedó disponible sin reiniciar: {0}" -f $uv)
        return
    }
    $cargoDir = Join-Path (Join-Path $env:USERPROFILE ".cargo") "bin"
    $cargo = Join-Path $cargoDir "uv.exe"
    Add-PathDeSesion $cargoDir
    if (Test-UvExe $cargo) {
        $script:UvExe = $cargo
        Add-PathDeUsuario $cargoDir
        Write-Log ("uv quedó disponible sin reiniciar: {0}" -f $cargo)
        return
    }
    Write-Log "El instalador oficial no dejó uv en el PATH. Lo descargo en la carpeta del usuario."
    Instalar-UvDescarga
    Add-PathDeSesion $script:UvDir
    Add-PathDeUsuario $script:UvDir
    $script:UvExe = Join-Path $script:UvDir "uv.exe"
    if (-not (Test-UvExe $script:UvExe)) {
        throw "uv se instaló pero no arranca. Vuelve a ejecutar Instalar.bat."
    }
}

function Python-DelVenv {
    return (Join-Path (Join-Path $script:Venv "Scripts") "python.exe")
}

function Pedir-Acceso {
    try {
        $python = Python-DelVenv
        if (-not (Test-Path -LiteralPath $python)) {
            Write-Host "No pude pedir el código de acceso porque falta Python. Podrás hacerlo al abrir Drako Cam."
            return
        }
        & $python -m app.drako.solicitud_instalador --estado
        if ($LASTEXITCODE -eq 10) {
            Write-Host ""
            Write-Host "Falta la configuración del servidor de acceso."
            Write-Host "La instalación ha terminado igual. Cuando esté configurado, pide el código al abrir Drako Cam."
            return
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "No pude comprobar el servidor de acceso. Podrás pedir el código al abrir Drako Cam."
            return
        }
        Write-Host ""
        Write-Host "Puedes pedir el código de acceso. Drako lo recibirá y, si lo aprueba, te lo pasará."
        $nombre = Read-Host "Nombre de la persona (vacío para hacerlo luego)"
        if (-not $nombre -or -not $nombre.Trim()) {
            Write-Host "De acuerdo. Podrás pedirlo al abrir Drako Cam."
            return
        }
        $oficina = Read-Host "Nombre de la oficina donde se instala"
        if (-not $oficina -or -not $oficina.Trim()) {
            Write-Host "Sin la oficina no envío la solicitud. Podrás hacerlo al abrir Drako Cam."
            return
        }
        & $python -m app.drako.solicitud_instalador --nombre $nombre --oficina $oficina
        if ($LASTEXITCODE -ne 0) {
            Write-Host "No se pudo enviar la solicitud. La instalación está lista. Podrás pedirla al abrir el programa."
        }
    } catch {
        Write-Host "No se pudo pedir el código de acceso. La instalación está lista."
        try { Write-Log ("Aviso de acceso: " + $_.Exception.Message) } catch { }
    }
}

function Pythonw-DelVenv {
    return (Join-Path (Join-Path $script:Venv "Scripts") "pythonw.exe")
}

function Test-Python312([string]$Exe) {
    if (-not (Test-Path -LiteralPath $Exe)) { return $false }
    $codigo = Invocar-Proceso -Archivo $Exe -Argumentos @(
        "-c",
        "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    ) -TiempoSegundos 60
    return ($codigo -eq 0)
}

function Asegurar-Python {
    Write-Log "No uso el Python de Windows ni el alias de la Microsoft Store. Instalo Python 3.12 con uv, sin activar el entorno."
    if ($script:HayRed) {
        $codigo = Invocar-Proceso -Archivo $script:UvExe -Argumentos @("python", "install", "3.12") -TiempoSegundos 600
        if ($codigo -ne 0) {
            throw "No se pudo instalar Python 3.12 (código $codigo)."
        }
        $hallado = Invocar-Captura -Archivo $script:UvExe -Argumentos @("python", "find", "3.12") -TiempoSegundos 60
        $rutaPy = Primera-Linea $hallado.Texto
        if ($rutaPy) { Write-Log ("Python de uv: {0}" -f $rutaPy) }
    }
    $py = Python-DelVenv
    $pyw = Pythonw-DelVenv
    if (Test-Python312 $py) {
        Write-Log "Ya hay un .venv con Python 3.12. Lo reutilizo. Si faltan componentes, los completo."
        if (-not (Test-Path -LiteralPath $pyw)) {
            Write-Log "Falta pythonw.exe. Reparo el entorno sin borrar lo que ya se hubiera instalado."
            $null = Invocar-Proceso -Archivo $script:UvExe -Argumentos @("venv", "--python", "3.12", "--allow-existing", $script:Venv) -TiempoSegundos 180
            if (-not (Test-Path -LiteralPath $pyw)) {
                Write-Log "No pude recuperar pythonw.exe. Recreo el entorno y vuelvo a instalar los componentes."
                $codigo = Invocar-Proceso -Archivo $script:UvExe -Argumentos @("venv", "--python", "3.12", "--clear", $script:Venv) -TiempoSegundos 180
                if ($codigo -ne 0) {
                    throw "No se pudo reparar el entorno .venv (código $codigo)."
                }
            }
        }
        if (-not (Test-Python312 (Python-DelVenv))) {
            throw "El entorno .venv no responde con Python 3.12."
        }
        return
    }
    if (-not $script:HayRed) {
        throw "Falta el entorno de Python 3.12 y no hay internet."
    }
    if (Test-Path -LiteralPath $script:Venv) {
        Write-Log "Hay un entorno .venv a medias. Lo reparo con Python 3.12."
        $argumentos = @("venv", "--python", "3.12", "--clear", $script:Venv)
    } else {
        Write-Log "Creo el entorno .venv con Python 3.12."
        $argumentos = @("venv", "--python", "3.12", $script:Venv)
    }
    $codigo = Invocar-Proceso -Archivo $script:UvExe -Argumentos $argumentos -TiempoSegundos 180
    if ($codigo -ne 0) {
        throw "No se pudo crear el entorno .venv (código $codigo)."
    }
    if (-not (Test-Python312 (Python-DelVenv))) {
        throw "El entorno .venv no responde con Python 3.12."
    }
    if (-not (Test-Path -LiteralPath (Pythonw-DelVenv))) {
        throw "No aparece pythonw.exe. Sin él, el acceso directo no puede abrir Drako Cam."
    }
}

function Intentar-WingetFfmpeg {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Log "winget no está en este Windows. Descargo FFmpeg directamente."
        return $false
    }
    Write-Log "Intento instalar FFmpeg 7.1.1 con winget. Si tarda demasiado, lo dejo y lo descargo yo."
    $null = Invocar-Proceso -Archivo $winget.Source -Argumentos @(
        "install", "--exact", "--id", "Gyan.FFmpeg", "--version", "7.1.1",
        "--scope", "user",
        "--accept-package-agreements", "--accept-source-agreements",
        "--disable-interactivity"
    ) -TiempoSegundos 300
    Actualizar-Path
    $enPath = Buscar-FfmpegEnPath
    if (-not $enPath) {
        Write-Log "winget no dejó ffmpeg en el PATH."
        return $false
    }
    $ver = Version-De-Ffmpeg $enPath
    if (Es-Ffmpeg711 $ver) {
        Write-Log ("FFmpeg {0} quedó disponible con winget." -f $ver)
        Notificar-CambioDeEntorno
        return $true
    }
    Write-Log ("winget dejó FFmpeg {0}, que no es la 7.1.1. Descargo esa versión." -f $ver)
    return $false
}

function Instalar-FfmpegDescarga {
    $zip = Join-Path $env:TEMP "drako-ffmpeg-7.1.1.zip"
    $urls = @(
        "https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip",
        "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-7.1.1-essentials_build.zip"
    )
    $bajo = $false
    $ultimo = ""
    foreach ($url in $urls) {
        try {
            if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
            Recibir-Archivo $url $zip
            $bajo = $true
            break
        } catch {
            $ultimo = $_.Exception.Message
            Write-Log "Pruebo otra dirección para FFmpeg..."
        }
    }
    if (-not $bajo) {
        if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue }
        throw "No se pudo descargar FFmpeg 7.1.1. $ultimo"
    }
    $tmp = Join-Path $env:TEMP ("drako-ffmpeg-" + [guid]::NewGuid().ToString("n"))
    try {
        Asegurar-Directorio $tmp
        Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
        $exe = Get-ChildItem -LiteralPath $tmp -Filter ffmpeg.exe -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $exe -or $null -eq $exe.Directory -or $null -eq $exe.Directory.Parent) {
            throw "El zip de FFmpeg no tiene la carpeta bin que esperaba."
        }
        if (Test-Path -LiteralPath $script:FfmpegBuild) { Remove-Arbol $script:FfmpegBuild }
        Asegurar-Directorio (Split-Path -Parent $script:FfmpegBuild)
        $origen = $exe.Directory.Parent.FullName
        if ($origen.TrimEnd('\') -eq $tmp.TrimEnd('\')) {
            Asegurar-Directorio $script:FfmpegBuild
            Get-ChildItem -LiteralPath $tmp -Force | ForEach-Object {
                Move-Item -LiteralPath $_.FullName -Destination $script:FfmpegBuild
            }
        } else {
            Move-Item -LiteralPath $origen -Destination $script:FfmpegBuild
        }
    } finally {
        if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue }
        if (Test-Path -LiteralPath $tmp) {
            try { Remove-Arbol $tmp } catch { }
        }
    }
    if (-not (Test-Path -LiteralPath $script:FfmpegLocal)) {
        throw "No quedó ffmpeg.exe después de descomprimir."
    }
    $bin = Split-Path -Parent $script:FfmpegLocal
    Get-ChildItem -LiteralPath $bin -File -ErrorAction SilentlyContinue | ForEach-Object { Desbloquear $_.FullName }
    $ver = Version-De-Ffmpeg $script:FfmpegLocal
    if (-not (Es-Ffmpeg711 $ver)) {
        throw "El FFmpeg descargado no es la versión 7.1.1 (dice '$ver')."
    }
    Write-Log ("FFmpeg local listo: {0}" -f $ver)
}

function Publicar-FfmpegEnPath {
    if (-not (Test-Path -LiteralPath $script:FfmpegLocal)) { return }
    $bin = Split-Path -Parent $script:FfmpegLocal
    Add-PathDeUsuario $bin
    Write-Log ("FFmpeg 7.1.1 está en el PATH de esta sesión: {0}" -f $bin)
}

function Asegurar-Ffmpeg {
    if (Test-Path -LiteralPath $script:FfmpegLocal) {
        $ver = Version-De-Ffmpeg $script:FfmpegLocal
        if (Es-Ffmpeg711 $ver) {
            Write-Log ("FFmpeg local ya está: {0}" -f $ver)
            Desbloquear $script:FfmpegLocal
            Publicar-FfmpegEnPath
            return
        }
        Write-Log ("El FFmpeg de la carpeta es '{0}' y no es el 7.1.1. Lo reemplazo." -f $ver)
    }
    Actualizar-Path
    $enPath = Buscar-FfmpegEnPath
    if ($enPath) {
        $verPath = Version-De-Ffmpeg $enPath
        if (Es-Ffmpeg711 $verPath) {
            Write-Log ("FFmpeg {0} ya está en el PATH." -f $verPath)
            Notificar-CambioDeEntorno
            return
        }
        if ($verPath) {
            Write-Log ("Hay otro FFmpeg en el PATH ({0}). Hace falta el 7.1.1 para Drako Cam." -f $verPath)
        }
    }
    if (-not $script:HayRed) {
        throw "Falta FFmpeg 7.1.1 y no hay internet."
    }
    if (Intentar-WingetFfmpeg) { return }
    Write-Log "Descargo FFmpeg 7.1.1 (el paquete essentials, unos 90 MB)."
    Instalar-FfmpegDescarga
    Publicar-FfmpegEnPath
}

function Leer-ConfigUv {
    $toml = Join-Path $script:Raiz "pyproject.toml"
    if (-not (Test-Path -LiteralPath $toml)) {
        throw "Falta pyproject.toml. La carpeta de Drako Cam está incompleta."
    }
    $texto = [System.IO.File]::ReadAllText($toml, $script:Utf8)
    $estrategia = "unsafe-best-match"
    if ($texto -match 'index-strategy\s*=\s*"([^"]+)"') {
        $estrategia = $Matches[1]
    }
    $urls = New-Object System.Collections.Generic.List[string]
    $dentro = $false
    foreach ($linea in ($texto -split "`r?`n")) {
        $limpia = $linea.Trim()
        if ($limpia -match '^extra-index-url\s*=') { $dentro = $true; continue }
        if ($dentro) {
            if ($limpia.StartsWith("]")) { break }
            if ($limpia -match '"([^"]+)"') { [void]$urls.Add($Matches[1]) }
        }
    }
    if ($urls.Count -eq 0) {
        throw "No leo los índices de paquetes en pyproject.toml."
    }
    return @{ Estrategia = $estrategia; Urls = @($urls.ToArray()) }
}

function Test-PaquetesMinimos {
    $site = Join-Path $script:Venv "Lib\site-packages"
    $torch = Join-Path (Join-Path $site "torch") "__init__.py"
    $pyside = Join-Path (Join-Path $site "PySide6") "__init__.py"
    return ((Test-Path -LiteralPath $torch) -and (Test-Path -LiteralPath $pyside))
}

function Instalar-Componentes {
    $req = Join-Path $script:Raiz "requirements_cu13.txt"
    if (-not (Test-Path -LiteralPath $req)) {
        throw "Falta requirements_cu13.txt."
    }
    $pythonExe = Python-DelVenv
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw "No encuentro el Python del entorno. Vuelve a ejecutar Instalar.bat."
    }
    if (-not $script:HayRed) {
        if (Test-PaquetesMinimos) {
            Write-Log "Sin internet. No actualizo los componentes: los que hay sirven para abrir el programa."
            return
        }
        throw "Faltan componentes y no hay internet."
    }
    $libre = Espacio-LibreGB $script:Raiz
    $minimo = 25
    if (Test-PaquetesMinimos) { $minimo = 10 }
    Write-Host ""
    Write-Host "Ahora se descargan los componentes grandes: PyTorch (torch) y TensorRT (tensorrt-cu13)." -ForegroundColor Cyan
    Write-Host "Son varios gigabytes. Según la red, puede tardar bastante: a veces más de media hora." -ForegroundColor Cyan
    if ($libre -ge 0) {
        Write-Host ("Espacio libre ahora: {0} GB. Hacen falta unos {1} GB." -f $libre, $minimo) -ForegroundColor Cyan
    }
    Write-Host "Si el entorno estaba a medias, esto completa lo que falte. No cierres la ventana." -ForegroundColor Cyan
    Write-Host ""
    if ($libre -ge 0 -and $libre -lt $minimo) {
        throw ("No hay espacio suficiente para torch y tensorrt-cu13. Hacen falta unos {0} GB libres y hay {1} GB. Libera espacio y vuelve a ejecutar Instalar.bat." -f $minimo, $libre)
    }
    $cfg = Leer-ConfigUv
    $argumentos = @(
        "pip", "install",
        "--python", $pythonExe,
        "--link-mode", "copy",
        "--index-strategy", [string]$cfg.Estrategia,
        "-r", $req
    )
    foreach ($url in @($cfg.Urls)) {
        $argumentos += @("--extra-index-url", [string]$url)
    }
    $codigo = Invocar-Proceso -Archivo $script:UvExe -Argumentos $argumentos -EntornoExtra @{
        UV_LINK_MODE = "copy"
        UV_NO_CONFIG = "1"
    }
    if ($codigo -ne 0) {
        throw "No se pudieron instalar los componentes (código $codigo). Si fue un corte de red, vuelve a ejecutar Instalar.bat: continúa donde lo dejó."
    }
    if (-not (Test-PaquetesMinimos)) {
        throw "La instalación terminó sin dejar PyTorch o PySide. Vuelve a ejecutar Instalar.bat."
    }
}

function Probar-Cuda {
    $pythonExe = Join-Path (Join-Path $script:Venv "Scripts") "python.exe"
    $comprobar = Join-Path $PSScriptRoot "comprobar_cuda.py"
    if (-not (Test-Path -LiteralPath $comprobar)) {
        throw "Falta scripts\comprobar_cuda.py."
    }
    Write-Log "Compruebo si PyTorch ve la tarjeta. La primera vez puede tardar un momento."
    $codigo = Invocar-Proceso -Archivo $pythonExe -Argumentos @($comprobar) -TiempoSegundos 180 -EntornoExtra @{
        PYTHONUTF8 = "1"
        PYTHONIOENCODING = "utf-8"
    }
    if ($codigo -eq 0) {
        $script:AvisoGpu = $false
        if ($script:ResumenNvidia) {
            Write-Log ("CUDA está visible. {0}" -f $script:ResumenNvidia)
        } else {
            Write-Log "CUDA está visible."
        }
        return
    }
    $script:AvisoGpu = $true
    if ($codigo -eq 2) {
        throw "PyTorch no arranca. Los componentes no quedaron bien. Vuelve a ejecutar Instalar.bat. Si se repite, cierra el programa, borra la carpeta .venv y ejecútalo otra vez."
    }
    if ($codigo -eq -1) {
        $script:TextoAvisoGpu = "La comprobación de la tarjeta tardó demasiado. Drako Cam se ha instalado, pero no he podido confirmar CUDA."
        return
    }
    if ($script:ResumenNvidia) {
        $script:TextoAvisoGpu = "La tarjeta está instalada ($($script:ResumenNvidia)), pero PyTorch no puede usar CUDA. Suele hacer falta un controlador NVIDIA más reciente. Drako Cam se ha instalado igual. Cuando actualices el controlador, vuelve a ejecutar Instalar.bat."
    } else {
        $script:TextoAvisoGpu = "No se ve una GPU NVIDIA con CUDA. Drako Cam se ha instalado, pero el cambio de cara en directo irá muy lento o no funcionará. Instala el controlador más reciente de NVIDIA y vuelve a ejecutar Instalar.bat."
    }
    Write-Log $script:TextoAvisoGpu
}

function Nuevo-Acceso([string]$RutaLnk) {
    $pyw = Pythonw-DelVenv
    $main = Join-Path $script:Raiz "main.py"
    if (-not (Test-Path -LiteralPath $pyw)) {
        throw "No encuentro pythonw.exe. Sin él, el acceso directo no puede abrir Drako Cam."
    }
    $dir = Split-Path -Parent $RutaLnk
    Asegurar-Directorio $dir
    $wsh = New-Object -ComObject WScript.Shell
    $lnk = $wsh.CreateShortcut($RutaLnk)
    $lnk.TargetPath = $pyw
    $lnk.Arguments = '"' + $main + '"'
    $lnk.WorkingDirectory = $script:Raiz
    $lnk.WindowStyle = 1
    $lnk.Description = "Abrir Drako Cam"
    $lnk.IconLocation = "$pyw,0"
    $lnk.Save()
    Write-Log ("Acceso directo: {0}" -f $RutaLnk)
    Write-Log ("Abre con: {0} {1}" -f $pyw, $main)
}

function Crear-Accesos {
    $escritorio = [Environment]::GetFolderPath("Desktop")
    $menu = [Environment]::GetFolderPath("Programs")
    if (-not $escritorio) {
        throw "No encuentro la carpeta del escritorio. No puedo crear el acceso directo."
    }
    if (-not $menu) {
        throw "No encuentro el menú Inicio. No puedo crear el acceso directo."
    }
    Nuevo-Acceso (Join-Path $escritorio "Drako Cam.lnk")
    Nuevo-Acceso (Join-Path $menu "Drako Cam.lnk")
}

function Mirar-Nvidia {
    $smi = Buscar-NvidiaSmi
    if (-not $smi) {
        Write-Log "No encuentro nvidia-smi. Es normal si no hay una GPU NVIDIA o falta el controlador."
        return
    }
    try {
        $cap = Invocar-Captura -Archivo $smi -Argumentos @(
            "--query-gpu=name,driver_version,memory.total",
            "--format=csv,noheader"
        ) -TiempoSegundos 25
    } catch {
        Write-Log ("No pude leer nvidia-smi: {0}" -f $_.Exception.Message)
        return
    }
    if ($cap.Codigo -ne 0) {
        Write-Log "nvidia-smi no respondió. Puede que el controlador esté mal o que no haya tarjeta."
        return
    }
    $linea = Primera-Linea $cap.Texto
    if ($linea) {
        $script:ResumenNvidia = $linea
        Write-Log ("Tarjeta vista por el controlador: {0}" -f $linea)
    }
}

try {
    try {
        $Host.UI.RawUI.WindowTitle = "Drako Cam - instalación"
    } catch { }

    Write-Log "======== Drako Cam: instalación ========"
    Write-Log ("Carpeta: {0}" -f $script:Raiz)
    Set-Location -LiteralPath $script:Raiz

    if (-not [Environment]::Is64BitOperatingSystem) {
        throw "Hace falta Windows de 64 bits."
    }
    if (-not [Environment]::Is64BitProcess) {
        throw "PowerShell se está ejecutando en 32 bits. Vuelve a abrir Instalar.bat con un doble clic."
    }
    $cv = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    $buildTexto = [string]$cv.CurrentBuild
    if ($cv.CurrentBuildNumber) { $buildTexto = [string]$cv.CurrentBuildNumber }
    if ($buildTexto -notmatch '(\d+)$') {
        throw "No puedo leer la versión de Windows."
    }
    $build = [int]$Matches[1]
    Write-Log ("Windows build {0}." -f $build)
    if ($build -lt 10240) {
        throw "Hace falta Windows 10 o Windows 11. Esta versión de Windows no sirve."
    }
    if ($script:Raiz.StartsWith("\\")) {
        throw "La carpeta está en una ruta de red. Cópiala a un disco local, por ejemplo el Escritorio, y vuelve a intentarlo."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $script:Raiz "main.py"))) {
        throw "No encuentro main.py. Ejecuta Instalar.bat dentro de la carpeta completa de Drako Cam."
    }

    if ($SoloComprobar) {
        Write-Log "Comprobación de arranque: Windows vale y el script ha llegado hasta aquí."
        Write-Log "No se ha instalado ni borrado nada."
        exit 0
    }

    Paso "1/7" "Comprobando el equipo"
    Assert-AppCerrada
    $prueba = Join-Path $script:Raiz (".drako-escritura-" + [guid]::NewGuid().ToString("n"))
    try {
        [System.IO.File]::WriteAllText($prueba, "ok", $script:Utf8)
        Remove-Item -LiteralPath $prueba -Force
    } catch {
        throw "No puedo escribir en esta carpeta. Cópiala a un sitio tuyo, por ejemplo el Escritorio, y vuelve a ejecutar Instalar.bat.`nCarpeta: $($script:Raiz)"
    }
    $libre = Espacio-LibreGB $script:Raiz
    $yaHayTorch = Test-PaquetesMinimos
    if ($libre -ge 0) {
        Write-Log ("Espacio libre en el disco: {0} GB" -f $libre)
        $minimo = 25
        if ($yaHayTorch) { $minimo = 10 }
        if ($libre -lt $minimo) {
            throw ("No hay espacio para torch y tensorrt-cu13. Hacen falta unos {0} GB libres y solo hay {1} GB. Libera espacio y vuelve a ejecutar Instalar.bat." -f $minimo, $libre)
        }
        if (-not $yaHayTorch -and $libre -lt 30) {
            Write-Log "Aviso: torch y tensorrt-cu13 ocupan varios gigabytes. Es más cómodo tener 30 GB libres. Hay sitio para intentarlo."
        }
    }
    Write-Log "Comprobando la conexión..."
    $script:HayRed = Test-Red
    if ($script:HayRed) {
        Write-Log "Hay internet."
    } else {
        Write-Log "No hay internet. Solo puedo reparar lo que ya esté descargado."
    }
    Mirar-Nvidia
    if (-not $script:ResumenNvidia) {
        Write-Host ""
        Write-Host "AVISO: de momento no veo una tarjeta NVIDIA. La instalación sigue." -ForegroundColor Yellow
        Write-Host "Al final te diré si el programa podrá usarla." -ForegroundColor Yellow
        Write-Host ""
    }

    Paso "2/7" "Preparando uv"
    Asegurar-Uv

    Paso "3/7" "Preparando Python 3.12"
    Asegurar-Python

    Paso "4/7" "Preparando FFmpeg 7.1.1"
    Asegurar-Ffmpeg

    Paso "5/7" "Instalando los componentes"
    Instalar-Componentes

    Paso "6/7" "Comprobando la tarjeta NVIDIA"
    Probar-Cuda

    Paso "7/7" "Creando los accesos directos"
    Crear-Accesos

    Write-Host ""
    if ($script:AvisoGpu) {
        Write-Host "============================================================" -ForegroundColor Yellow
        Write-Host "  AVISO: no se ve CUDA" -ForegroundColor Yellow
        Write-Host "============================================================" -ForegroundColor Yellow
        Write-Host $script:TextoAvisoGpu -ForegroundColor Yellow
        Write-Host ""
    }
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  Drako Cam está listo" -ForegroundColor Green
    Write-Host "  Abre el acceso directo «Drako Cam» del escritorio" -ForegroundColor Green
    Write-Host "  o del menú Inicio. No se abre una ventana de consola." -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Si algo se rompe más adelante, vuelve a ejecutar Instalar.bat."
    Write-Host "Repara o actualiza lo que falte."
    Write-Host ""
    Write-Host "Registro:"
    foreach ($rutaLog in $script:RutasLog) {
        Write-Host ("  " + $rutaLog)
    }
    Pedir-Acceso
    if ($DesdeInstalador) {
        Write-Host ""
        Write-Host "Cuando pulses una tecla se cerrará esta ventana y el instalador terminará."
    }
    Write-Log "Instalación terminada."
    exit 0
} catch {
    $detalle = $_.Exception.Message
    if (-not $detalle) { $detalle = "$_" }
    if ($detalle -match "too long|MAX_PATH|ruta de acceso|206") {
        $detalle = $detalle + " Prueba a copiar Drako Cam a una carpeta más corta, por ejemplo C:\DrakoCam, y ejecuta Instalar.bat allí."
    }
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  No se pudo terminar la instalación" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host $detalle -ForegroundColor Red
    Write-Host ""
    Write-Host "El registro está en:"
    foreach ($rutaLog in $script:RutasLog) {
        Write-Host ("  " + $rutaLog)
    }
    Write-Host ""
    Write-Host "Puedes volver a ejecutar Instalar.bat. Si ya había avanzado, continúa y repara lo que falte."
    try { Write-Log ("ERROR: " + $detalle) } catch { }
    exit 1
}
