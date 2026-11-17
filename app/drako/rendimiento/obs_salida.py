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
TITULO_VENTANA = "Drako Cam - Salida OBS"

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
    destino = nombre_camara or TITULO_VENTANA
    return (
        "En OBS, en Fuentes, pulsa +.",
        "Elige «Dispositivo de captura de vídeo». Si usas la ventana, elige «Captura de ventana».",
        f"En Dispositivo, elige «{destino}» y pulsa Aceptar.",
    )


def rect_con_relacion(
    ancho_ventana: int, alto_ventana: int, ancho_frame: int, alto_frame: int
) -> tuple[int, int, int, int]:
    """El vídeo entra entero. Lo que sobra queda en negro, sin estirar."""
    if ancho_ventana <= 0 or alto_ventana <= 0 or ancho_frame <= 0 or alto_frame <= 0:
        return 0, 0, max(0, ancho_ventana), max(0, alto_ventana)
    escala = min(ancho_ventana / ancho_frame, alto_ventana / alto_frame)
    ancho = max(1, int(round(ancho_frame * escala)))
    alto = max(1, int(round(alto_frame * escala)))
    return (ancho_ventana - ancho) // 2, (alto_ventana - alto) // 2, ancho, alto


class PasoFotograma:
    """Una sola copia del fotograma que ya va a la cámara virtual.

    El hilo de salida no espera a que la ventana pinte, y no reutiliza
    el buffer que se está pintando.
    """

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self.activa = False
        self._listo = None
        self._libre: list = []
        self._pintando = None
        self._nuevo = False

    def publicar(self, frame) -> None:
        if not self.activa or frame is None:
            return
        import numpy as np

        src = np.asarray(frame)
        if src.ndim != 3 or src.shape[2] < 3:
            return
        if src.shape[2] > 3:
            src = np.ascontiguousarray(src[:, :, :3])
        elif not src.flags.c_contiguous:
            src = np.ascontiguousarray(src)
        with self._lock:
            destino = None
            for indice, buf in enumerate(self._libre):
                if buf.shape == src.shape and buf is not self._pintando:
                    destino = buf
                    del self._libre[indice]
                    break
            if destino is None:
                destino = np.empty(src.shape, dtype=np.uint8)
            np.copyto(destino, src)
            if (
                self._listo is not None
                and self._listo is not self._pintando
                and self._listo is not destino
            ):
                self._libre.append(self._listo)
            if len(self._libre) > 2:
                self._libre = self._libre[-2:]
            self._listo = destino
            self._nuevo = True

    def tomar(self):
        with self._lock:
            if not self._nuevo or self._listo is None or self._pintando is not None:
                return None
            self._pintando = self._listo
            self._nuevo = False
            return self._listo

    def soltar(self) -> None:
        with self._lock:
            self._pintando = None


def fotograma_prueba(ancho: int, alto: int):
    import numpy as np

    frame = np.zeros((max(1, alto), max(1, ancho), 3), dtype=np.uint8)
    frame[:, :] = (8, 6, 5)  # BGR, casi negro
    margen_x = max(1, ancho // 8)
    margen_y = max(1, alto // 3)
    frame[margen_y : alto - margen_y, margen_x : ancho - margen_x] = (240, 225, 92)
    return frame
