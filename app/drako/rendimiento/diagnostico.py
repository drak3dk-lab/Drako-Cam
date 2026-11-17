"""Una línea de FPS y latencia en el registro local.

No promete los FPS de la GPU: si el cronómetro aún no tiene
fotogramas reales, lo dice.
"""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger("drako")


def linea(perfil: str, fps: float | None, latencia_ms: float | None, nota: str) -> str:
    fps_txt = "sin medida" if fps is None else f"{fps:.1f} FPS"
    lat_txt = "sin medida" if latencia_ms is None else f"{latencia_ms:.0f} ms"
    return f"{perfil}: {fps_txt}, latencia {lat_txt}. {nota}"


def anotar_swap_en_directo(worker, cara) -> None:
    """Una línea en drako-cam.log la primera vez que el swap entra en un directo."""
    ventana = getattr(worker, "main_window", None)
    procesador = getattr(ventana, "video_processor", None)
    if procesador is None or getattr(procesador, "file_type", "") != "webcam":
        return
    ident = str(getattr(cara, "face_id", "") or "principal")
    if getattr(procesador, "_cara_swap_anotada", None) == ident:
        return
    procesador._cara_swap_anotada = ident
    _log.info("Cara aplicada en el directo: %s", ident)


def anexar(directorio: Path, texto: str) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / "diagnostico.log"
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write(texto.rstrip() + "\n")
