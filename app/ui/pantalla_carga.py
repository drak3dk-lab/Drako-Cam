"""Pantalla de carga del directo. Sale al frente y no es un cuadro de la consola."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

_actual: PantallaCarga | None = None


class PantallaCarga(QtWidgets.QDialog):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowTitle("Drako Cam")
        self.setModal(False)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(480)
        self.setMinimumHeight(180)
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(24, 22, 24, 22)
        caja.setSpacing(14)
        titulo = QtWidgets.QLabel("Drako Cam", self)
        fuente = titulo.font()
        fuente.setPointSize(fuente.pointSize() + 4)
        fuente.setBold(True)
        titulo.setFont(fuente)
        self.texto = QtWidgets.QLabel("Abriendo el directo…", self)
        self.texto.setWordWrap(True)
        self.barra = QtWidgets.QProgressBar(self)
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setTextVisible(False)
        self.barra.setMinimumHeight(10)
        caja.addWidget(titulo)
        caja.addWidget(self.texto)
        caja.addWidget(self.barra)
        publicar(self)

    def poner(self, texto: str, valor: int | None) -> None:
        self.texto.setText(texto)
        if valor is None:
            self.barra.setRange(0, 0)
        else:
            if self.barra.maximum() == 0:
                self.barra.setRange(0, 100)
            self.barra.setValue(max(0, min(100, valor)))
        self.show()
        self.raise_()
        self.activateWindow()
        aplicacion = QtWidgets.QApplication.instance()
        if aplicacion is not None:
            aplicacion.processEvents()

    def cerrar(self) -> None:
        self.hide()
        self.close()


def publicar(pantalla: PantallaCarga) -> None:
    global _actual
    _actual = pantalla


def obtener() -> PantallaCarga | None:
    return _actual


def asegurar() -> PantallaCarga:
    if _actual is None:
        return PantallaCarga()
    return _actual
