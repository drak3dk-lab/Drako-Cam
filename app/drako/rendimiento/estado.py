"""Copia barata del estado de la interfaz para el hilo de la webcam.

`fast_state_copy` recorre todo el árbol en cada fotograma. Aquí se
copian como mucho dos niveles de diccionarios y se comparten los
arrays: el worker escribe claves, no los píxeles del ajuste.
"""

from __future__ import annotations


def copia_estado(obj: object, nivel: int = 0, limite: int = 2):
    if isinstance(obj, dict):
        if nivel >= limite:
            return obj
        return {k: copia_estado(v, nivel + 1, limite) for k, v in obj.items()}
    if isinstance(obj, list):
        if nivel >= limite:
            return obj
        return [copia_estado(v, nivel + 1, limite) for v in obj]
    if isinstance(obj, tuple):
        if nivel >= limite:
            return obj
        return tuple(copia_estado(v, nivel + 1, limite) for v in obj)
    return obj
