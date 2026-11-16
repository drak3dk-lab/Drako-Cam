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
from dataclasses import dataclass
from pathlib import Path

MENSAJE_OCUPADA = (
    "La cámara la está usando otro programa "
    "(cierra OBS, NVIDIA Broadcast, Teams/Meet/Zoom) e inténtalo otra vez."
)
MENSAJE_AUSENTE = "No hay cámara. Conéctala y pulsa actualizar."

_cache: tuple[float, list[str]] | None = None
_TTL_S = 20.0


@dataclass
class AperturaWebcam:
    captura: object
    backend: str
    backend_id: int
    ancho: int
    alto: int
    fps: float
    primer_frame: object
    informe: str


def backends_de_apertura() -> list[tuple[str, int]]:
    """En Windows, DirectShow primero: es el que usa Deep-Live-Cam y las webcams integradas."""
    import cv2

    if os.name == "nt":
        return [
            ("DirectShow", int(cv2.CAP_DSHOW)),
            ("MSMF", int(cv2.CAP_MSMF)),
            ("Default", int(cv2.CAP_ANY)),
        ]
    return [("Default", int(cv2.CAP_ANY))]


def abrir_webcam(
    indice: int,
    ancho: int = 0,
    alto: int = 0,
    fps: int = 0,
    *,
    abrir=None,
    leer=None,
    esperar=None,
    soltar=None,
    backends=None,
) -> AperturaWebcam | None:
    """Abre la webcam y espera un fotograma real.

    No fuerza MJPG ni una resolución antes del primer frame: eso enciende la luz
    y luego deja la captura muda en muchas webcams integradas.
    """
    intentos = backends if backends is not None else backends_de_apertura()
    abrir = abrir or _abrir_cv
    leer = leer or _leer_cv
    esperar = esperar or time.sleep
    soltar = soltar or _soltar_cv
    informe: list[str] = []

    def anotar(linea: str) -> None:
        informe.append(linea)
        print(linea)

    for nombre, backend_id in intentos:
        anotar(f"[INFO] Webcam índice {indice}, pruebo {nombre} ({backend_id}).")
        try:
            captura = abrir(indice, backend_id)
        except Exception as exc:
            anotar(f"[ERROR] Webcam índice {indice}, {nombre}: no se creó la captura: {exc}")
            continue
        if captura is None or not _esta_abierta(captura):
            anotar(f"[ERROR] Webcam índice {indice}, {nombre}: OpenCV no la abrió.")
            soltar(captura)
            continue
        frame = _leer_varios(captura, leer, esperar, veces=8)
        if frame is None:
            anotar(
                f"[ERROR] Webcam índice {indice}, {nombre}: abierta, pero sin fotograma tras 8 lecturas."
            )
            soltar(captura)
            continue
        if ancho > 0 and alto > 0:
            captura, frame, ajusto = _probar_tamano(
                captura, frame, indice, backend_id, ancho, alto, abrir, leer, esperar, soltar, anotar, nombre
            )
            if captura is None or frame is None:
                continue
        else:
            ajusto = False
        if fps > 0:
            try:
                captura.set(5, float(fps))
            except Exception as exc:
                anotar(f"[AVISO] Webcam índice {indice}, {nombre}: no aceptó {fps} fps ({exc}).")
        ancho_real, alto_real, fps_real = _medidas(captura, frame, fps)
        anotar(
            f"[INFO] Webcam índice {indice} abierta con {nombre}: "
            f"{ancho_real}x{alto_real} @ {fps_real:.1f} fps"
            + (" (resolución pedida no aceptada, se deja la nativa)." if ajusto else ".")
        )
        return AperturaWebcam(
            captura, nombre, int(backend_id), ancho_real, alto_real, fps_real, frame, "\n".join(informe)
        )

    anotar(f"[ERROR] No se pudo abrir la webcam índice {indice} con ningún backend.")
    return None


def _leer_varios(captura, leer, esperar, veces: int = 8):
    for numero in range(veces):
        try:
            frame = leer(captura)
        except Exception:
            frame = None
        if frame is not None:
            return frame
        if numero + 1 < veces:
            esperar(0.06)
    return None


def _probar_tamano(captura, frame, indice, backend_id, ancho, alto, abrir, leer, esperar, soltar, anotar, nombre):
    try:
        captura.set(3, float(ancho))
        captura.set(4, float(alto))
    except Exception as exc:
        anotar(f"[AVISO] Webcam índice {indice}, {nombre}: no pude pedir {ancho}x{alto} ({exc}).")
        return captura, frame, True
    siguiente = _leer_varios(captura, leer, esperar, veces=4)
    if siguiente is not None:
        return captura, siguiente, False
    anotar(
        f"[AVISO] Webcam índice {indice}, {nombre}: {ancho}x{alto} dejó de dar imagen. Vuelvo al tamaño nativo."
    )
    soltar(captura)
    try:
        captura = abrir(indice, backend_id)
    except Exception as exc:
        anotar(f"[ERROR] Webcam índice {indice}, {nombre}: no reabrió en nativo: {exc}")
        return None, None, True
    frame = _leer_varios(captura, leer, esperar, veces=8)
    if frame is None:
        anotar(f"[ERROR] Webcam índice {indice}, {nombre}: el tamaño nativo tampoco dio imagen.")
        soltar(captura)
        return None, None, True
    return captura, frame, True


def _esta_abierta(captura) -> bool:
    abierta = getattr(captura, "isOpened", None)
    if not callable(abierta):
        return captura is not None
    try:
        return bool(abierta())
    except Exception:
        return False


def _abrir_cv(indice: int, backend_id: int):
    import cv2

    return cv2.VideoCapture(int(indice), int(backend_id))


def _leer_cv(captura):
    ok, frame = captura.read()
    if not ok or frame is None:
        return None
    return frame


def _soltar_cv(captura) -> None:
    if captura is None:
        return
    try:
        captura.release()
    except Exception:
        pass


def _medidas(captura, frame, fps_pedido: int) -> tuple[int, int, float]:
    ancho = alto = 0
    fps = 0.0
    try:
        ancho = int(captura.get(3) or 0)
        alto = int(captura.get(4) or 0)
        fps = float(captura.get(5) or 0)
    except Exception:
        pass
    if ancho <= 0 or alto <= 0:
        forma = getattr(frame, "shape", None)
        if forma is not None and len(forma) >= 2:
            alto = int(forma[0])
            ancho = int(forma[1])
    if fps <= 1:
        fps = float(fps_pedido or 30)
    return ancho, alto, fps


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
