"""Nombres reales de las cámaras, sin abrirlas.

El índice de OpenCV se conserva. En pantalla se ve el nombre del dispositivo
(Integrated Webcam, NVIDIA Broadcast, OBS Virtual Camera). En Windows el orden
es el de DirectShow, el mismo que usa el backend DSHOW.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

MENSAJE_OCUPADA = (
    "La cámara la está usando otro programa "
    "(cierra OBS, NVIDIA Broadcast, Teams/Meet/Zoom) e inténtalo otra vez."
)
MENSAJE_AUSENTE = "No hay cámara. Conéctala y pulsa actualizar."

_cache: tuple[float, list[str]] | None = None
_TTL_S = 20.0


def aviso_si_no_abre(habia_dispositivo: bool) -> str:
    """Si el dispositivo estaba en la lista y no abre, otro programa lo tiene."""
    if habia_dispositivo:
        return MENSAJE_OCUPADA
    return MENSAJE_AUSENTE


def olvidar_cache() -> None:
    global _cache
    _cache = None


def nombres_de_camaras(lector=None, forzar: bool = False) -> list[str]:
    global _cache
    if lector is not None:
        return _limpiar(lector())
    ahora = time.monotonic()
    if not forzar and _cache is not None and ahora - _cache[0] < _TTL_S:
        return list(_cache[1])
    if os.name == "nt":
        nombres = _windows()
    else:
        nombres = _linux()
    nombres = _limpiar(nombres)
    _cache = (ahora, nombres)
    return list(nombres)


def nombres_desde_ffmpeg(texto: str) -> list[str]:
    """Lee la lista de vídeo de `ffmpeg -f dshow -list_devices`."""
    encontrados = []
    for linea in texto.splitlines():
        if "(video)" not in linea.lower():
            continue
        coincidencia = re.search(r'"([^"]+)"', linea)
        if coincidencia:
            encontrados.append(coincidencia.group(1).strip())
    return _limpiar(encontrados)


def _limpiar(nombres) -> list[str]:
    vistos = []
    for nombre in nombres or []:
        texto = " ".join(str(nombre).split()).strip()
        if texto and texto not in vistos:
            vistos.append(texto[:80])
    return vistos


def _windows() -> list[str]:
    try:
        from pygrabber.dshow_graph import FilterGraph

        return list(FilterGraph().get_input_devices() or [])
    except Exception:
        pass
    texto = _ffmpeg_dshow()
    if texto:
        nombres = nombres_desde_ffmpeg(texto)
        if nombres:
            return nombres
    return _powershell()


def _ffmpeg_dshow() -> str:
    ejecutables = ["ffmpeg"]
    local = Path("dependencies/ffmpeg/ffmpeg-7.1.1-essentials_build/bin/ffmpeg.exe")
    if local.is_file():
        ejecutables.insert(0, str(local))
    for ejecutable in ejecutables:
        try:
            resultado = subprocess.run(
                [ejecutable, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        texto = (resultado.stderr or "") + "\n" + (resultado.stdout or "")
        if "(video)" in texto.lower():
            return texto
    return ""


def _powershell() -> list[str]:
    orden = (
        "Get-CimInstance Win32_PnPEntity | "
        "Where-Object { $_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image' } | "
        "Select-Object -ExpandProperty Name"
    )
    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", orden],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [linea.strip() for linea in (resultado.stdout or "").splitlines() if linea.strip()]


def _linux() -> list[str]:
    raiz = Path("/sys/class/video4linux")
    if not raiz.is_dir():
        return []
    dispositivos = []
    for carpeta in raiz.glob("video*"):
        numero = carpeta.name.removeprefix("video")
        if not numero.isdigit():
            continue
        try:
            nombre = (carpeta / "name").read_text(encoding="utf-8").strip()
        except OSError:
            nombre = ""
        dispositivos.append((int(numero), nombre or f"Cámara {int(numero) + 1}"))
    dispositivos.sort()
    return [nombre for _numero, nombre in dispositivos]
