"""Nombres reales de las cámaras, sin abrirlas.

El índice de OpenCV se conserva. En pantalla se ve el nombre del dispositivo
(Integrated Webcam, NVIDIA Broadcast, OBS Virtual Camera). En Windows el orden
es el de DirectShow, el mismo que usa el backend DSHOW.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger("drako")
_ultimo_fallo = ""

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


def ultimo_fallo() -> str:
    return _ultimo_fallo


def backends_de_apertura() -> list[tuple[str, int]]:
    """En Windows solo DirectShow, igual que Deep-Live-Cam.

    MSMF y el backend por defecto se prueban únicamente si DirectShow ni siquiera
    llega a abrir el dispositivo. Si DirectShow ya lo abrió, no se cierra para
    reintentar con otro: eso deja la cámara como si estuviera en uso.
    """
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
    """Abre la webcam como Deep-Live-Cam: CAP_DSHOW y el formato nativo.

    No fuerza MJPG, ni resolución, ni FPS. Esos ajustes, antes del primer
    fotograma, encienden la luz y después dejan la captura muda. `ancho`,
    `alto` y `fps` se ignoran a propósito.
    """
    global _ultimo_fallo
    del ancho, alto, fps
    intentos = backends if backends is not None else backends_de_apertura()
    abrir = abrir or _abrir_cv
    leer = leer or _leer_cv
    esperar = esperar or time.sleep
    soltar = soltar or _soltar_cv
    informe: list[str] = []

    def anotar(linea: str, error: bool = False) -> None:
        informe.append(linea)
        if error:
            _log.error(linea)
        else:
            _log.info(linea)

    for nombre, backend_id in intentos:
        anotar(f"Cámara índice {indice}, backend {nombre} ({backend_id}): probando.")
        try:
            captura = abrir(indice, backend_id)
        except Exception as exc:
            anotar(
                f"Cámara índice {indice}, backend {nombre} ({backend_id}): "
                f"abierta=no, primer fotograma=no, error OpenCV: {exc}",
                error=True,
            )
            continue
        error_cv = _error_opencv(captura)
        if captura is None or not _esta_abierta(captura):
            detalle = error_cv or "OpenCV no abrió el dispositivo"
            anotar(
                f"Cámara índice {indice}, backend {nombre} ({backend_id}): "
                f"abierta=no, primer fotograma=no, error OpenCV: {detalle}",
                error=True,
            )
            soltar(captura)
            continue
        frame = _leer_varios(captura, leer, esperar, veces=8)
        if frame is None:
            anotar(
                f"Cámara índice {indice}, backend {nombre} ({backend_id}): "
                "abierta=sí, primer fotograma=no. No cierro para probar otro backend.",
                error=True,
            )
            soltar(captura)
            break
        ancho_real, alto_real, fps_real = _medidas(captura, frame)
        fps_texto = f"{fps_real:.1f}" if fps_real > 1 else "nativo"
        anotar(
            f"Cámara índice {indice}, backend {nombre} ({backend_id}): "
            f"abierta=sí, primer fotograma=sí, resolución {ancho_real}x{alto_real}, "
            f"fps {fps_texto}. Formato nativo, sin MJPG ni tamaño forzado."
        )
        texto = "\n".join(informe)
        _ultimo_fallo = ""
        return AperturaWebcam(
            captura, nombre, int(backend_id), ancho_real, alto_real, fps_real, frame, texto
        )

    anotar(
        f"Cámara índice {indice}: no se abrió. No se forzó MJPG, resolución ni FPS.",
        error=True,
    )
    _ultimo_fallo = "\n".join(informe)
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


def _esta_abierta(captura) -> bool:
    abierta = getattr(captura, "isOpened", None)
    if not callable(abierta):
        return captura is not None
    try:
        return bool(abierta())
    except Exception:
        return False


def _error_opencv(captura) -> str:
    texto = getattr(captura, "_drako_error_opencv", "") if captura is not None else ""
    return str(texto or "").strip()


def _abrir_cv(indice: int, backend_id: int):
    """Una sola apertura, la misma llamada que Deep-Live-Cam."""
    import cv2

    recogidos: list[str] = []

    def handler(*args):
        for pieza in args:
            if isinstance(pieza, bytes):
                texto = pieza.decode("utf-8", "replace").strip()
            elif isinstance(pieza, str):
                texto = pieza.strip()
            else:
                continue
            if len(texto) >= 4:
                recogidos.append(texto)
        return 0

    anterior = None
    redirigio = False
    if hasattr(cv2, "redirectError"):
        try:
            anterior = cv2.redirectError(handler)
            redirigio = True
        except Exception:
            redirigio = False
    try:
        captura = cv2.VideoCapture(int(indice), int(backend_id))
    finally:
        if redirigio:
            try:
                cv2.redirectError(anterior)
            except Exception:
                pass
    if recogidos:
        try:
            captura._drako_error_opencv = " | ".join(dict.fromkeys(recogidos))
        except Exception:
            pass
    return captura


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


def _medidas(captura, frame) -> tuple[int, int, float]:
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
    return ancho, alto, fps


_PISTAS_OCUPADA = (
    "busy",
    "in use",
    "occupied",
    "being used",
    "access is denied",
    "acceso denegado",
    "en uso",
    "ocupad",
    "sharing violation",
    "0x80070020",
    "0x800700aa",
    "device or resource busy",
    "error 32",
)


def es_error_de_ocupada(informe: str) -> bool:
    texto = (informe or "").lower()
    return any(pista in texto for pista in _PISTAS_OCUPADA)


def _detalle_visible(informe: str) -> str:
    lineas = [linea.strip() for linea in (informe or "").splitlines() if linea.strip()]
    utiles = [
        linea
        for linea in lineas
        if "error" in linea.lower() or "opencv" in linea.lower() or "abierta=no" in linea.lower()
    ]
    elegido = utiles[-1] if utiles else (lineas[-1] if lineas else "")
    if len(elegido) > 220:
        elegido = elegido[:217] + "..."
    return elegido


def mensaje_de_fallo(informe: str, habia_dispositivo: bool) -> str:
    """Solo dice que otro programa la usa si el error es de acceso."""
    if es_error_de_ocupada(informe):
        return MENSAJE_OCUPADA
    detalle = _detalle_visible(informe)
    if not habia_dispositivo and not detalle:
        return MENSAJE_AUSENTE
    if detalle:
        return f"No pude abrir la cámara: {detalle}"
    if not habia_dispositivo:
        return MENSAJE_AUSENTE
    return "No pude abrir la cámara. El detalle está en el registro."


def aviso_si_no_abre(habia_dispositivo: bool, informe: str = "") -> str:
    return mensaje_de_fallo(informe, habia_dispositivo)


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
