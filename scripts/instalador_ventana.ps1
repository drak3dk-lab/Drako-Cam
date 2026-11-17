# Ventana de instalación de Drako Cam.
# Por dentro llama a instalar.ps1 -ModoVentana: el mismo proceso que Instalar.bat.
# PowerShell 5.1. Sin secretos. Se abre sin consola desde Instalar.vbs.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

try {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class DrakoDpi {
    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@
    [DrakoDpi]::SetProcessDPIAware() | Out-Null
} catch { }

$raiz = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$scriptInstalar = Join-Path $PSScriptRoot "instalar.ps1"
$utf8 = New-Object System.Text.UTF8Encoding $false

$fondo = [System.Drawing.Color]::FromArgb(5, 6, 8)
$texto = [System.Drawing.Color]::FromArgb(244, 246, 248)
$suave = [System.Drawing.Color]::FromArgb(183, 192, 206)
$apagado = [System.Drawing.Color]::FromArgb(110, 119, 135)
$linea = [System.Drawing.Color]::FromArgb(26, 30, 36)
$rojo = [System.Drawing.Color]::FromArgb(242, 10, 28)
$rojoTexto = [System.Drawing.Color]::FromArgb(255, 246, 246)

$nombres = @(
    "Comprobando este PC",
    "Bajando lo necesario",
    "Preparando el programa",
    "Preparando el vídeo",
    "Instalando el cambio de cara",
    "Bajando los modelos de la cara",
    "Comprobando la tarjeta gráfica",
    "Creando el acceso directo",
    "Registrando la cámara Drako Cam"
)

$script:fase = "inicio"
$script:paso = 0
$script:porcentaje = -1
$script:listo = $false
$script:errorTexto = ""
$script:proceso = $null
$script:cola = [System.Collections.ArrayList]::Synchronized((New-Object System.Collections.ArrayList))
$global:DrakoCola = $script:cola

function Set-Redondo($control, [int]$radio) {
    $rect = New-Object System.Drawing.Rectangle 0, 0, $control.Width, $control.Height
    $camino = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = [Math]::Max(2, $radio * 2)
    $camino.AddArc($rect.X, $rect.Y, $d, $d, 180, 90)
    $camino.AddArc(($rect.Right - $d), $rect.Y, $d, $d, 270, 90)
    $camino.AddArc(($rect.Right - $d), ($rect.Bottom - $d), $d, $d, 0, 90)
    $camino.AddArc($rect.X, ($rect.Bottom - $d), $d, $d, 90, 90)
    $camino.CloseFigure()
    $control.Region = New-Object System.Drawing.Region $camino
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "Drako Cam"
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.BackColor = $fondo
$form.ForeColor = $texto
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$form.ClientSize = New-Object System.Drawing.Size(480, 640)
$form.MaximizeBox = $false
$form.ShowInTaskbar = $true
$icono = Join-Path $raiz "installer\logo.ico"
if (Test-Path -LiteralPath $icono) {
    $form.Icon = New-Object System.Drawing.Icon($icono)
}

$cerrar = New-Object System.Windows.Forms.Button
$cerrar.Text = "×"
$cerrar.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$cerrar.FlatAppearance.BorderSize = 0
$cerrar.BackColor = $fondo
$cerrar.ForeColor = $suave
$cerrar.Font = New-Object System.Drawing.Font("Segoe UI", 14)
$cerrar.Size = New-Object System.Drawing.Size(44, 36)
$cerrar.Location = New-Object System.Drawing.Point(430, 6)
$cerrar.Cursor = [System.Windows.Forms.Cursors]::Hand
$cerrar.TabStop = $false
$form.Controls.Add($cerrar)

$logo = New-Object System.Windows.Forms.PictureBox
$logo.Size = New-Object System.Drawing.Size(88, 88)
$logo.Location = New-Object System.Drawing.Point(196, 36)
$logo.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
$logo.BackColor = $fondo
$png = Join-Path $raiz "app\ui\core\media\isotipo-limpio.png"
if (Test-Path -LiteralPath $png) {
    $bytes = [System.IO.File]::ReadAllBytes($png)
    $memoria = New-Object System.IO.MemoryStream(,$bytes)
    $logo.Image = [System.Drawing.Image]::FromStream($memoria)
}
$form.Controls.Add($logo)

$titulo = New-Object System.Windows.Forms.Label
$titulo.Text = "Drako Cam"
$titulo.Font = New-Object System.Drawing.Font("Segoe UI", 20, [System.Drawing.FontStyle]::Regular)
$titulo.ForeColor = $texto
$titulo.AutoSize = $false
$titulo.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$titulo.Size = New-Object System.Drawing.Size(416, 40)
$titulo.Location = New-Object System.Drawing.Point(32, 132)
$form.Controls.Add($titulo)

$subtitulo = New-Object System.Windows.Forms.Label
$subtitulo.Text = "Instalar en este PC"
$subtitulo.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$subtitulo.ForeColor = $suave
$subtitulo.AutoSize = $false
$subtitulo.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$subtitulo.Size = New-Object System.Drawing.Size(416, 24)
$subtitulo.Location = New-Object System.Drawing.Point(32, 172)
$form.Controls.Add($subtitulo)

$estado = New-Object System.Windows.Forms.Label
$estado.Text = "Un clic. Puede tardar un rato."
$estado.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$estado.ForeColor = $suave
$estado.AutoSize = $false
$estado.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$estado.Size = New-Object System.Drawing.Size(416, 22)
$estado.Location = New-Object System.Drawing.Point(32, 200)
$form.Controls.Add($estado)

$script:marcas = @()
$script:etiquetas = @()
for ($i = 0; $i -lt $nombres.Count; $i++) {
    $marca = New-Object System.Windows.Forms.Label
    $marca.Text = ""
    $marca.Font = New-Object System.Drawing.Font("Segoe UI", 11)
    $marca.ForeColor = $apagado
    $marca.AutoSize = $false
    $marca.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
    $marca.Size = New-Object System.Drawing.Size(22, 22)
    $marca.Location = New-Object System.Drawing.Point(36, (216 + ($i * 24)))
    $form.Controls.Add($marca)
    $script:marcas += $marca

    $etiqueta = New-Object System.Windows.Forms.Label
    $etiqueta.Text = $nombres[$i]
    $etiqueta.Font = New-Object System.Drawing.Font("Segoe UI", 11)
    $etiqueta.ForeColor = $apagado
    $etiqueta.AutoSize = $false
    $etiqueta.TextAlign = [System.Drawing.ContentAlignment]::MiddleLeft
    $etiqueta.Size = New-Object System.Drawing.Size(380, 22)
    $etiqueta.Location = New-Object System.Drawing.Point(62, (216 + ($i * 24)))
    $form.Controls.Add($etiqueta)
    $script:etiquetas += $etiqueta
}

$aviso = New-Object System.Windows.Forms.Label
$aviso.Text = ""
$aviso.Font = New-Object System.Drawing.Font("Segoe UI", 8)
$aviso.ForeColor = $suave
$aviso.AutoSize = $false
$aviso.Size = New-Object System.Drawing.Size(416, 32)
$aviso.Location = New-Object System.Drawing.Point(32, 448)
$aviso.Visible = $false
$form.Controls.Add($aviso)
$script:aviso = $aviso

$barraFondo = New-Object System.Windows.Forms.Panel
$barraFondo.Size = New-Object System.Drawing.Size(416, 4)
$barraFondo.Location = New-Object System.Drawing.Point(32, 488)
$barraFondo.BackColor = $linea
$form.Controls.Add($barraFondo)
$barra = New-Object System.Windows.Forms.Panel
$barra.Size = New-Object System.Drawing.Size(0, 4)
$barra.Location = New-Object System.Drawing.Point(0, 0)
$barra.BackColor = $rojo
$barraFondo.Controls.Add($barra)
$script:barra = $barra
$script:barraFondo = $barraFondo

$boton = New-Object System.Windows.Forms.Button
$boton.Text = "Instalar"
$boton.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$boton.ForeColor = $rojoTexto
$boton.BackColor = $rojo
$boton.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$boton.FlatAppearance.BorderSize = 0
$boton.FlatAppearance.MouseOverBackColor = [System.Drawing.Color]::FromArgb(210, 8, 22)
$boton.FlatAppearance.MouseDownBackColor = [System.Drawing.Color]::FromArgb(176, 6, 18)
$boton.Size = New-Object System.Drawing.Size(416, 48)
$boton.Location = New-Object System.Drawing.Point(32, 508)
$boton.Cursor = [System.Windows.Forms.Cursors]::Hand
$form.Controls.Add($boton)
Set-Redondo $boton 24
$script:boton = $boton

$ver = New-Object System.Windows.Forms.Button
$ver.Text = "Ver detalles"
$ver.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$ver.ForeColor = $suave
$ver.BackColor = $fondo
$ver.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$ver.FlatAppearance.BorderSize = 0
$ver.FlatAppearance.MouseOverBackColor = $fondo
$ver.Size = New-Object System.Drawing.Size(160, 32)
$ver.Location = New-Object System.Drawing.Point(160, 564)
$ver.Cursor = [System.Windows.Forms.Cursors]::Hand
$form.Controls.Add($ver)

$detalle = New-Object System.Windows.Forms.TextBox
$detalle.Multiline = $true
$detalle.ReadOnly = $true
$detalle.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
$detalle.BorderStyle = [System.Windows.Forms.BorderStyle]::None
$detalle.BackColor = [System.Drawing.Color]::FromArgb(11, 14, 18)
$detalle.ForeColor = $apagado
$detalle.Font = New-Object System.Drawing.Font("Consolas", 8)
$detalle.Size = New-Object System.Drawing.Size(416, 120)
$detalle.Location = New-Object System.Drawing.Point(32, 600)
$detalle.Visible = $false
$detalle.WordWrap = $false
$form.Controls.Add($detalle)
$script:detalle = $detalle
$script:detallesAbiertos = $false

function Actualizar-Barra {
    $fraccion = 0.0
    if ($script:paso -gt 0) { $fraccion = ($script:paso - 1) / 9.0 }
    if ($script:porcentaje -ge 0) { $fraccion += ($script:porcentaje / 100.0) / 9.0 }
    if ($script:fase -eq "listo") { $fraccion = 1.0 }
    if ($fraccion -gt 1) { $fraccion = 1 }
    if ($fraccion -lt 0) { $fraccion = 0 }
    $ancho = [int]($script:barraFondo.Width * $fraccion)
    $script:barra.Width = $ancho
}

function Pintar-Pasos {
    for ($i = 0; $i -lt $nombres.Count; $i++) {
        $hecho = ($script:fase -eq "listo") -or ($script:paso -gt ($i + 1))
        $actual = ($script:fase -eq "instalando") -and ($script:paso -eq ($i + 1))
        if ($hecho) {
            $script:marcas[$i].Text = [string][char]0x2713
            $script:marcas[$i].ForeColor = $suave
            $script:etiquetas[$i].ForeColor = $suave
        } elseif ($actual) {
            $script:marcas[$i].Text = [string][char]0x25CF
            $script:marcas[$i].ForeColor = $rojo
            $script:etiquetas[$i].ForeColor = $texto
        } else {
            $script:marcas[$i].Text = [string][char]0x25CB
            $script:marcas[$i].ForeColor = $apagado
            $script:etiquetas[$i].ForeColor = $apagado
        }
    }
}

function Poner-Paso([int]$numero) {
    $script:paso = $numero
    $script:porcentaje = -1
    if ($numero -eq 5) {
        $estado.Text = "Esta parte es la larga. Deja la ventana abierta."
    } elseif ($numero -eq 6) {
        $estado.Text = "Si se corta internet, se reanuda. No cierres la ventana."
    } elseif ($numero -eq 9) {
        $estado.Text = "Windows puede pedir permiso una vez para la cámara."
    } else {
        $estado.Text = "No cierres esta ventana."
    }
    Pintar-Pasos
    Actualizar-Barra
}

function Aplicar-Linea([string]$linea) {
    if (-not $linea) { return }
    if ($linea.StartsWith("DRAKO_PASO ")) {
        $trozo = $linea.Substring(11).Trim()
        $numero = 0
        if ($trozo -match '^(\d+)') { $numero = [int]$Matches[1] }
        Poner-Paso $numero
        return
    }
    if ($linea.StartsWith("DRAKO_ESTADO ")) {
        $estado.Text = $linea.Substring(13).Trim()
        return
    }
    if ($linea.StartsWith("DRAKO_PORCIENTO ")) {
        $valor = 0
        [void][int]::TryParse($linea.Substring(16).Trim(), [ref]$valor)
        $script:porcentaje = $valor
        Actualizar-Barra
        return
    }
    if ($linea.StartsWith("DRAKO_AVISO ")) {
        $script:aviso.Text = $linea.Substring(12).Trim()
        $script:aviso.Visible = $true
        return
    }
    if ($linea.StartsWith("DRAKO_LISTO")) {
        $script:listo = $true
        return
    }
    if ($linea.StartsWith("DRAKO_ERROR ")) {
        $script:errorTexto = $linea.Substring(12).Trim()
    }
}

function Refrescar-Detalles {
    if (-not $script:detallesAbiertos) { return }
    $ruta = Join-Path $env:LOCALAPPDATA "DrakoCam\logs\instalacion.log"
    if (-not (Test-Path -LiteralPath $ruta)) { return }
    try {
        $lineas = Get-Content -LiteralPath $ruta -Tail 60 -ErrorAction SilentlyContinue
        if ($lineas) { $script:detalle.Text = ($lineas -join "`r`n") }
    } catch { }
}

function Mostrar-Listo {
    $script:fase = "listo"
    $script:paso = 10
    $estado.Text = "Ya está en este PC."
    $script:boton.Text = "Abrir Drako Cam"
    $script:boton.Enabled = $true
    Pintar-Pasos
    Actualizar-Barra
}

function Mostrar-Fallo {
    $script:fase = "fallo"
    $textoFallo = $script:errorTexto
    if (-not $textoFallo) { $textoFallo = "No se pudo terminar. Puedes volver a intentarlo." }
    if ($textoFallo.Length -gt 140) { $textoFallo = $textoFallo.Substring(0, 140) }
    $estado.Text = $textoFallo
    $script:boton.Text = "Reintentar"
    $script:boton.Enabled = $true
    Pintar-Pasos
}

function Empezar-Instalacion {
    if ($script:fase -eq "instalando") { return }
    try {
        Empezar-Proceso
    } catch {
        $script:errorTexto = $_.Exception.Message
        Mostrar-Fallo
    }
}

function Empezar-Proceso {
    $script:fase = "instalando"
    $script:paso = 0
    $script:porcentaje = -1
    $script:listo = $false
    $script:errorTexto = ""
    $script:cola.Clear()
    $estado.Text = "No cierres esta ventana."
    $script:boton.Text = "Instalando..."
    $script:boton.Enabled = $true
    Pintar-Pasos
    Actualizar-Barra

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptInstalar`" -ModoVentana"
    $psi.WorkingDirectory = $raiz
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.StandardOutputEncoding = $utf8
    $psi.StandardErrorEncoding = $utf8
    $proceso = New-Object System.Diagnostics.Process
    $proceso.StartInfo = $psi
    $proceso.EnableRaisingEvents = $true
    $proceso.add_OutputDataReceived({
        if ($null -ne $EventArgs.Data) { [void]$global:DrakoCola.Add($EventArgs.Data) }
    })
    $proceso.add_ErrorDataReceived({
        if ($null -ne $EventArgs.Data) { [void]$global:DrakoCola.Add($EventArgs.Data) }
    })
    $script:proceso = $proceso
    [void]$proceso.Start()
    $proceso.BeginOutputReadLine()
    $proceso.BeginErrorReadLine()
}

function Abrir-Programa {
    $compilado = Join-Path $raiz "DrakoCam.exe"
    $vbs = Join-Path $PSScriptRoot "Arrancar.vbs"
    if (Test-Path -LiteralPath $compilado) {
        Start-Process -FilePath $compilado -WorkingDirectory $raiz | Out-Null
    } elseif (Test-Path -LiteralPath $vbs) {
        Start-Process -FilePath (Join-Path $env:SystemRoot "System32\wscript.exe") -ArgumentList "`"$vbs`"" -WorkingDirectory $raiz | Out-Null
    }
    $form.Close()
}

function Parar-Proceso {
    if ($script:proceso -and -not $script:proceso.HasExited) {
        try {
            & "$env:SystemRoot\System32\taskkill.exe" /F /T /PID $script:proceso.Id 2>$null | Out-Null
        } catch { }
    }
}

$temporizador = New-Object System.Windows.Forms.Timer
$temporizador.Interval = 200
$temporizador.Add_Tick({
    try {
        while ($script:cola.Count -gt 0) {
            $linea = [string]$script:cola[0]
            $script:cola.RemoveAt(0)
            Aplicar-Linea $linea
        }
    } catch { }
    if ($script:fase -eq "instalando" -and $script:proceso -and $script:proceso.HasExited) {
        if ($script:listo -or $script:proceso.ExitCode -eq 0) { Mostrar-Listo } else { Mostrar-Fallo }
    }
    Refrescar-Detalles
})
$temporizador.Start()

$boton.Add_Click({
    if ($script:fase -eq "listo") { Abrir-Programa; return }
    if ($script:fase -eq "instalando") { return }
    Empezar-Instalacion
})

$ver.Add_Click({
    $script:detallesAbiertos = -not $script:detallesAbiertos
    $script:detalle.Visible = $script:detallesAbiertos
    if ($script:detallesAbiertos) {
        $form.ClientSize = New-Object System.Drawing.Size(480, 760)
        $ver.Text = "Ocultar detalles"
        Refrescar-Detalles
    } else {
        $form.ClientSize = New-Object System.Drawing.Size(480, 640)
        $ver.Text = "Ver detalles"
    }
})

$cerrar.Add_Click({ $form.Close() })
$form.Add_FormClosing({ Parar-Proceso; $temporizador.Stop() })

$script:arrastre = $false
$script:origenRaton = [System.Drawing.Point]::Empty
$form.Add_MouseDown({
    if ($EventArgs.Button -eq [System.Windows.Forms.MouseButtons]::Left -and $EventArgs.Y -lt 36) {
        $script:arrastre = $true
        $script:origenRaton = $EventArgs.Location
    }
})
$form.Add_MouseMove({
    if ($script:arrastre) {
        $pos = $form.PointToScreen($EventArgs.Location)
        $form.Location = New-Object System.Drawing.Point(($pos.X - $script:origenRaton.X), ($pos.Y - $script:origenRaton.Y))
    }
})
$form.Add_MouseUp({ $script:arrastre = $false })

Pintar-Pasos
Actualizar-Barra
$form.Add_Shown({
    try {
        [DrakoDpi]::ShowWindow($form.Handle, 1) | Out-Null
        [DrakoDpi]::SetForegroundWindow($form.Handle) | Out-Null
    } catch { }
})
[void]$form.ShowDialog()
