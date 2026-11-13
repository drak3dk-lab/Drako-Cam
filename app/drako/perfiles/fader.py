"""Paso entre dos caras sin cortar la cámara.

Mezcla los embeddings y los normaliza. El hilo de la webcam sigue
leyendo el resultado en el fotograma siguiente.
"""

from __future__ import annotations

import numpy as np


def pasos(cantidad: int = 8) -> list[float]:
    if cantidad < 2:
        return [1.0]
    return [indice / (cantidad - 1) for indice in range(cantidad)]


def mezclar(anterior: np.ndarray, nuevo: np.ndarray, avance: float) -> np.ndarray:
    peso = float(np.clip(avance, 0.0, 1.0))
    previo = np.asarray(anterior, dtype=np.float32).reshape(-1)
    destino = np.asarray(nuevo, dtype=np.float32).reshape(-1)
    if previo.shape != destino.shape:
        return destino
    mezcla = previo * (1.0 - peso) + destino * peso
    norma = float(np.linalg.norm(mezcla))
    if norma < 1e-8:
        return mezcla
    return mezcla / norma
