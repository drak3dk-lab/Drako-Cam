"""Salida hacia OBS, sin un paso extra al pulsar EN VIVO.

Unity Capture es la opción principal: OBS la ve como una cámara más
(«Unity Video Capture»). La cámara virtual de OBS es la salida del
propio OBS; elegirla dentro de OBS no está soportado y puede hacer
un bucle. Si no hay ningún controlador, queda la ventana limpia.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

NOMBRE_UNITY = "Unity Video Capture"
NOMBRE_OBS = "OBS Virtual Camera"

_RUTAS_OBS = (
    r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    r"C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe",
)
_RUTAS_UNITY = (
    r"C:\Program Files\UnityCapture\UnityCaptureFilter64.dll",
    r"C:\Program Files (x86)\UnityCapture\UnityCaptureFilter64.dll",
)
_RUTAS_OBS_VIRTUAL = (
    r"C:\Program Files\obs-studio\data\obs-plugins\win-dshow\obs-virtualcam-module64.dll",
    r"C:\Program Files\obs-studio\bin\64bit\obs-virtualcam-module64.dll",
)


@dataclass(frozen=True)
class EleccionSalida:
    backend: str | None
    nombre: str
    modo: str  # camara | ventana
    motivo: str


@dataclass(frozen=True)
class EstadoObs:
    obs_instalado: bool
    unity: bool
    obs_virtual: bool
    obs_en_marcha: bool
    eleccion: EleccionSalida


def elegir(unity: bool, obs_virtual: bool) -> EleccionSalida:
    if unity:
        return EleccionSalida(
            "unitycapture",
            NOMBRE_UNITY,
            "camara",
            "Unity Capture es más estable para OBS: aparece como una cámara y no es la salida del propio OBS.",
        )
    if obs_virtual:
        return EleccionSalida(
            "obs",
            NOMBRE_OBS,
            "camara",
            "No está Unity Capture. Uso la cámara virtual de OBS. Si OBS no la lista, usa la ventana de salida.",
        )
    return EleccionSalida(
        None,
        "",
        "ventana",
        "No hay una cámara virtual instalada. La ventana de salida sirve para Captura de ventana.",
    )


def detectar(
    existe=None,
    procesos: list[str] | None = None,
) -> EstadoObs:
    """existe(ruta) permite probarlo sin un Windows real."""
    mirar = existe or (lambda ruta: Path(ruta).is_file())
    obs = any(mirar(ruta) for ruta in _RUTAS_OBS)
    unity = any(mirar(ruta) for ruta in _RUTAS_UNITY)
    virtual = any(mirar(ruta) for ruta in _RUTAS_OBS_VIRTUAL)
    nombres = {nombre.lower() for nombre in (procesos or [])}
    en_marcha = bool(nombres & {"obs64.exe", "obs.exe", "obs32.exe"})
    return EstadoObs(obs, unity, virtual, en_marcha, elegir(unity, virtual))


def procesos_windows() -> list[str]:
    if os.name != "nt":
        return []
    try:
        import subprocess

        texto = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True,
            timeout=2,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    nombres = []
    for linea in texto.splitlines():
        if not linea.startswith('"'):
            continue
        nombres.append(linea.split('"', 2)[1])
    return nombres


def texto_indicador(
    *,
    dispositivo_abierto: bool,
    obs_en_marcha: bool,
    ventana: bool,
) -> str:
    if dispositivo_abierto and obs_en_marcha:
        return "OBS recibiendo"
    if dispositivo_abierto or ventana:
        return "Salida activa"
    return "APAGADA"


def debe_cortar_salida(*, cara_perdida: bool, parar: bool, panel_cerrado: bool) -> bool:
    """La cara perdida y el panel no cortan. Parar el programa, sí."""
    if cara_perdida or panel_cerrado:
        return False
    return parar


def pasos_para_obs(nombre_camara: str) -> tuple[str, str, str]:
    destino = nombre_camara or "la ventana «Drako Cam — salida»"
    return (
        "En OBS, en Fuentes, pulsa +.",
        "Elige «Dispositivo de captura de vídeo». Si usas la ventana, elige «Captura de ventana».",
        f"En Dispositivo, elige «{destino}» y pulsa Aceptar.",
    )


def fotograma_prueba(ancho: int, alto: int):
    import numpy as np

    frame = np.zeros((max(1, alto), max(1, ancho), 3), dtype=np.uint8)
    frame[:, :] = (8, 6, 5)  # BGR, casi negro
    margen_x = max(1, ancho // 8)
    margen_y = max(1, alto // 3)
    frame[margen_y : alto - margen_y, margen_x : ancho - margen_x] = (240, 225, 92)
    return frame
