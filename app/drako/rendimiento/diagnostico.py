"""Una línea de FPS y latencia en el registro local.

No promete los FPS de la GPU: si el cronómetro aún no tiene
fotogramas reales, lo dice.
"""

from __future__ import annotations

from pathlib import Path


def linea(perfil: str, fps: float | None, latencia_ms: float | None, nota: str) -> str:
    fps_txt = "sin medida" if fps is None else f"{fps:.1f} FPS"
    lat_txt = "sin medida" if latencia_ms is None else f"{latencia_ms:.0f} ms"
    return f"{perfil}: {fps_txt}, latencia {lat_txt}. {nota}"


def anexar(directorio: Path, texto: str) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / "diagnostico.log"
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write(texto.rstrip() + "\n")
