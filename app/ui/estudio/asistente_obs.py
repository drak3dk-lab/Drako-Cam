"""Asistente corto de OBS. Una sola pantalla, tres pasos dibujados.

Toma el checklist de un solo modal (Preply) y el botón único de
entrar (Whereby): no hay un recorrido de nueve pantallas.
El color vivo solo marca la salida que está activa.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.drako.rendimiento.obs_salida import EstadoObs, pasos_para_obs
from app.ui.estudio.panel import BotonPildora


class _Dibujo(QtWidgets.QWidget):
    """Tres tarjetas. No son capturas de OBS: son el orden de los clics."""

    def __init__(self, lineas: tuple[str, str, str]):
        super().__init__()
        self._lineas = lineas
        self.setMinimumHeight(168)

    def paintEvent(self, _evento: QtGui.QPaintEvent) -> None:
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        ancho = max(1, (self.width() - 16) // 3)
        for indice, texto in enumerate(self._lineas):
            x = indice * (ancho + 8)
            rect = QtCore.QRectF(x, 0, ancho, self.height() - 4)
            pintor.setPen(QtGui.QColor("#1C2430"))
            pintor.setBrush(QtGui.QColor("#121620"))
            pintor.drawRoundedRect(rect, 16, 16)
            pintor.setPen(QtGui.QColor("#5CE1F0"))
            fuente = pintor.font()
            fuente.setPixelSize(18)
            fuente.setBold(True)
            pintor.setFont(fuente)
            pintor.drawText(QtCore.QRectF(x + 12, 12, ancho - 24, 28), f"{indice + 1}")
            pintor.setPen(QtGui.QColor("#F4F7FB"))
            fuente.setPixelSize(13)
            fuente.setBold(False)
            pintor.setFont(fuente)
            pintor.drawText(
                QtCore.QRectF(x + 12, 46, ancho - 24, self.height() - 62),
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.TextFlag.TextWordWrap,
                texto,
            )
        pintor.end()


class AsistenteObs(QtWidgets.QDialog):
    probar = QtCore.Signal()
    pedir_ventana = QtCore.Signal()

    def __init__(self, estado: EstadoObs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OBS")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setStyleSheet(
            "QDialog { background: #050608; color: #F4F7FB; }"
            "QLabel { color: #F4F7FB; font-size: 16px; }"
            "QLabel#pista { color: #B7C0CE; font-size: 14px; }"
        )
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(24, 24, 24, 24)
        caja.setSpacing(14)
        titulo = QtWidgets.QLabel("OBS, en un momento")
        titulo.setStyleSheet("font-size: 22px; font-weight: 700;")
        caja.addWidget(titulo)
        estado_texto = QtWidgets.QLabel(self._resumen(estado))
        estado_texto.setWordWrap(True)
        estado_texto.setObjectName("pista")
        caja.addWidget(estado_texto)
        nombre = estado.eleccion.nombre or "Drako Cam — salida"
        self.dibujo = _Dibujo(pasos_para_obs(nombre))
        caja.addWidget(self.dibujo)
        motivo = QtWidgets.QLabel(estado.eleccion.motivo)
        motivo.setWordWrap(True)
        motivo.setObjectName("pista")
        caja.addWidget(motivo)
        self.resultado = QtWidgets.QLabel("")
        self.resultado.setWordWrap(True)
        caja.addWidget(self.resultado)
        fila = QtWidgets.QHBoxLayout()
        probar = BotonPildora("Probar salida")
        probar.setMinimumHeight(44)
        probar.clicked.connect(self.probar.emit)
        ventana = BotonPildora("Ventana de salida")
        ventana.setMinimumHeight(44)
        ventana.clicked.connect(self.pedir_ventana.emit)
        listo = BotonPildora("Ya está")
        listo.setMinimumHeight(44)
        listo.clicked.connect(self.accept)
        fila.addWidget(probar)
        fila.addWidget(ventana)
        fila.addWidget(listo)
        caja.addLayout(fila)

    def marcar_prueba(self, texto: str) -> None:
        self.resultado.setText(texto)

    @staticmethod
    def _resumen(estado: EstadoObs) -> str:
        obs = "OBS está instalado." if estado.obs_instalado else "No encuentro OBS. Instálalo desde obsproject.com."
        if estado.eleccion.backend == "unitycapture":
            camara = "La cámara que tienes que elegir es Unity Video Capture."
        elif estado.eleccion.backend == "obs":
            camara = "La cámara que tienes que elegir es OBS Virtual Camera."
        else:
            camara = "No hay cámara virtual. Usa la ventana de salida y Captura de ventana."
        return f"{obs} {camara}"
