"""Encaja una ventana en la pantalla que hay, sin pasarse del monitor."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


def disponible_de(widget: QtWidgets.QWidget | None = None) -> QtCore.QRect:
    pantalla = widget.screen() if widget is not None else None
    if pantalla is None:
        aplicacion = QtWidgets.QApplication.instance()
        if aplicacion is not None:
            pantalla = aplicacion.primaryScreen()
    if pantalla is None:
        return QtCore.QRect(0, 0, 1280, 720)
    return pantalla.availableGeometry()


def medida_encajada(
    disponible: QtCore.QRect,
    ancho: int,
    alto: int,
    minimo_ancho: int = 0,
    minimo_alto: int = 0,
    margen: int = 16,
) -> tuple[int, int, int, int]:
    """Devuelve ancho, alto, mínimo ancho y mínimo alto, todos dentro de la pantalla."""
    ancho_max = max(320, disponible.width() - margen)
    alto_max = max(240, disponible.height() - margen)
    min_ancho = min(max(0, minimo_ancho), ancho_max)
    min_alto = min(max(0, minimo_alto), alto_max)
    ancho_final = min(max(ancho, min_ancho), ancho_max)
    alto_final = min(max(alto, min_alto), alto_max)
    return ancho_final, alto_final, min_ancho, min_alto


def encajar(
    widget: QtWidgets.QWidget,
    ancho: int,
    alto: int,
    minimo_ancho: int = 0,
    minimo_alto: int = 0,
    margen: int = 16,
    tope: bool = False,
) -> None:
    """La ventana queda dentro de la pantalla, centrada, y puede ser más pequeña."""
    rect = disponible_de(widget)
    ancho_final, alto_final, min_ancho, min_alto = medida_encajada(
        rect, ancho, alto, minimo_ancho, minimo_alto, margen
    )
    widget.setMinimumSize(min_ancho, min_alto)
    if tope:
        widget.setMaximumSize(
            max(320, rect.width() - margen),
            max(240, rect.height() - margen),
        )
    widget.resize(ancho_final, alto_final)
    marco = widget.frameGeometry()
    marco.moveCenter(rect.center())
    if marco.left() < rect.left():
        marco.moveLeft(rect.left())
    if marco.top() < rect.top():
        marco.moveTop(rect.top())
    if marco.right() > rect.right():
        marco.moveRight(rect.right())
    if marco.bottom() > rect.bottom():
        marco.moveBottom(rect.bottom())
    widget.move(marco.topLeft())


def asegurar_cabe(widget: QtWidgets.QWidget, margen: int = 8) -> None:
    """La ventana principal no abre más grande que el monitor, ni con un mínimo imposible."""
    encajar(
        widget,
        widget.width(),
        widget.height(),
        widget.minimumWidth(),
        widget.minimumHeight(),
        margen,
        tope=False,
    )
