"""El fotograma llena el marco del estudio, sin estirar la imagen."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


def encajar_pixmap(vista, pixmap_item, scene_rect) -> None:
    vista.resetTransform()
    vista.setSceneRect(scene_rect)
    vista.fitInView(pixmap_item, QtCore.Qt.AspectRatioMode.KeepAspectRatio)


def encajar_si_hay_imagen(vista) -> bool:
    if vista is None or vista.width() < 8 or vista.height() < 8:
        return False
    escena = vista.scene()
    if escena is None:
        return False
    try:
        items = escena.items()
    except RuntimeError:
        return False
    pixmap_item = next(
        (item for item in items if isinstance(item, QtWidgets.QGraphicsPixmapItem)),
        None,
    )
    if pixmap_item is None:
        return False
    encajar_pixmap(vista, pixmap_item, pixmap_item.boundingRect())
    return True
