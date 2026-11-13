"""Canal de captura, inferencia y salida para la webcam.

La captura y la salida usan colas de tamaño 1. La inferencia usa la
cola de workers, acotada a 2 por quien arranca el directo. Si alguien
se retrasa, se tira el fotograma viejo.
"""

from __future__ import annotations

from app.drako.rendimiento.benchmark import CronometroEnVivo
from app.drako.rendimiento.colas import ColaLatencia


class CanalEnVivo:
    def __init__(self) -> None:
        self.captura = ColaLatencia(1)
        self.salida = ColaLatencia(1)
        self.cronometro = CronometroEnVivo()
