"""Comprueba si un objeto de Qt sigue vivo antes de tocarlo.

Shiboken puede conservar el envoltorio de Python cuando el C++ ya se borró.
Llamar a un método entonces cierra el programa con RuntimeError.
"""

from __future__ import annotations


def qt_sigue(obj) -> bool:
    if obj is None:
        return False
    try:
        import shiboken6
    except ImportError:
        return True
    try:
        return bool(shiboken6.isValid(obj))
    except Exception:
        return False


def sincronizar_espaciado(layout, vista, centro, separadores, espaciado=12, margen=12) -> bool:
    """Ajusta el espaciado solo si el layout y los widgets siguen existiendo."""
    if not (qt_sigue(layout) and qt_sigue(vista) and qt_sigue(centro)):
        return False
    layout.setSpacing(espaciado)
    for separador in separadores:
        if not qt_sigue(separador):
            continue
        caja = separador.layout()
        if not qt_sigue(caja):
            continue
        caja.setContentsMargins(margen, 0, margen, 0)
    ancho = max(centro.sizeHint().width(), centro.minimumSizeHint().width())
    vista.setMinimumWidth(ancho)
    return True
