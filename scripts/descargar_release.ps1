# Descarga Drako Cam desde un release o un enlace.
# La dirección sale de DRAKO_CAM_URL_RELEASE o de installer\descarga.url.
# Ese archivo no se sube al repositorio. Aquí no hay tokens.
# En un repo privado, la persona tiene que haber hecho antes `gh auth login` en ese PC.
#Requires -Version 5.1
param(
    [string]$Destino
)
$ErrorActionPreference = "Stop"
$raiz = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if (-not $Destino) { $Destino = Join-Path $raiz "descarga" }
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

$url = ""
if ($env:DRAKO_CAM_URL_RELEASE) { $url = $env:DRAKO_CAM_URL_RELEASE.Trim() }
$archivoUrl = Join-Path $raiz "installer\descarga.url"
if (-not $url -and (Test-Path -LiteralPath $archivoUrl)) {
    $url = (Get-Content -LiteralPath $archivoUrl -TotalCount 1).Trim()
}
if (-not $url -or $url.StartsWith("#")) {
    throw "No hay enlace de descarga. Crea installer\descarga.url con una sola línea, la URL del release, o define DRAKO_CAM_URL_RELEASE. No pongas tokens."
}

$nombre = "DrakoCam-descarga"
$partes = $url.Split("/")
if ($partes.Length -gt 0 -and $partes[-1]) { $nombre = $partes[-1] }
$salida = Join-Path $Destino $nombre

if ($url -match "^https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/(.+)$") {
    $repo = $Matches[1] + "/" + $Matches[2]
    $tag = $Matches[3]
    $asset = $Matches[4]
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $gh) {
        throw "Este enlace es de GitHub. Instala GitHub CLI y ejecuta 'gh auth login' en este PC. No copies un token dentro de Drako Cam."
    }
    & gh release download $tag --repo $repo --pattern $asset --dir $Destino --clobber
    if ($LASTEXITCODE -ne 0) {
        throw "gh no pudo descargar el release. Si el repositorio es privado, ejecuta 'gh auth login' con la cuenta que tiene acceso. No pegues el token en ningún archivo del programa."
    }
    Write-Host ("Descargado en {0}" -f $Destino)
    return
}

Invoke-WebRequest -Uri $url -OutFile $salida -UseBasicParsing
Write-Host ("Descargado: {0}" -f $salida)
