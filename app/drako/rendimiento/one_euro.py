"""Suavizado de puntos con One Euro.

En reposo el corte es bajo (el ajuste 25 son 2,5 Hz). Si la cabeza
se mueve, el corte sube y el punto sigue el fotograma, sin quedarse
atrás como la media fija de 35.
"""

from __future__ import annotations

import math


def alpha(corte_hz: float, fps: float) -> float:
    if corte_hz <= 0 or fps <= 0:
        return 1.0
    tau = 1.0 / (2.0 * math.pi * corte_hz)
    paso = 1.0 / fps
    return 1.0 / (1.0 + tau / paso)


def alpha_por_velocidad(
    velocidad_px: float,
    ajuste: float = 25.0,
    beta: float = 0.5,
    fps: float = 30.0,
) -> float:
    """`ajuste` 25 es el corte en reposo. 35 era la media fija anterior."""
    corte = max(0.1, float(ajuste) / 10.0) + float(beta) * abs(float(velocidad_px))
    return alpha(corte, fps)
