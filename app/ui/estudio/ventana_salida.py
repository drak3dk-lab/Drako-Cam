"""Ventana limpia para Captura de ventana en OBS.

Sin botones ni marcos de la interfaz. El tamaño no cambia.
Si se minimiza, OBS deja de verla: se devuelve detrás y se avisa.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


class VentanaSalida(QtWidgets.QWidget):
    aviso = QtCore.Signal(str)

    def __init__(self, ancho: int, alto: int):
        super().__init__(None)
        self.setWindowTitle("Drako Cam — salida")
        self.setFixedSize(max(160, ancho), max(120, alto))
        self.setStyleSheet("background: #050608;")
        self.setWindowFlag(QtCore.Qt.WindowType.Window, True)
        self._etiqueta = QtWidgets.QLabel(self)
        self._etiqueta.setGeometry(0, 0, self.width(), self.height())
        self._etiqueta.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._etiqueta.setStyleSheet("background: #050608; color: #7FEAF5;")
        self._etiqueta.setText("Salida")
        self._recuperando = False

    def fijar_tamano(self, ancho: int, alto: int) -> None:
        if self.width() == ancho and self.height() == alto:
            return
        self.setFixedSize(max(160, ancho), max(120, alto))
        self._etiqueta.setGeometry(0, 0, self.width(), self.height())

    def mostrar_frame(self, frame) -> None:
        if frame is None:
            return
        try:
            import numpy as np

            plano = np.ascontiguousarray(frame)
            if plano.ndim != 3 or plano.shape[2] < 3:
                return
            alto, ancho = plano.shape[0], plano.shape[1]
            self.fijar_tamano(ancho, alto)
            imagen = QtGui.QImage(
                plano.data,
                ancho,
                alto,
                plano.strides[0],
                QtGui.QImage.Format.Format_BGR888,
            ).copy()
            self._etiqueta.setPixmap(
                QtGui.QPixmap.fromImage(imagen).scaled(
                    self.size(),
                    QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )
        except Exception:
            return

    def changeEvent(self, evento: QtCore.QEvent) -> None:
        super().changeEvent(evento)
        if self._recuperando:
            return
        if (
            evento.type() == QtCore.QEvent.Type.WindowStateChange
            and self.isMinimized()
        ):
            self._recuperando = True
            self.showNormal()
            self.lower()
            self._recuperando = False
            self.aviso.emit(
                "No la minimices: OBS deja de verla. La dejé detrás de las otras ventanas."
            )

    def closeEvent(self, evento: QtGui.QCloseEvent) -> None:
        evento.ignore()
        self.hide()
        self.aviso.emit("Cerré la ventana de salida. La cámara virtual, si estaba, sigue.")
