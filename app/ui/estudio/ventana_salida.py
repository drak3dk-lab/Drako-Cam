"""Ventana aparte, solo con el vídeo, para Captura de ventana en OBS.

Sin botones ni paneles. El título es fijo para que OBS la encuentre.
El fotograma es el mismo que ya sale hacia la cámara virtual: una copia,
y el hilo de salida no espera al pintado.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.drako.rendimiento.obs_salida import TITULO_VENTANA, PasoFotograma, rect_con_relacion

_MARGEN = 8


class VentanaSalida(QtWidgets.QWidget):
    aviso = QtCore.Signal(str)
    geometria = QtCore.Signal(int, int, int, int)

    def __init__(self, ancho: int = 1280, alto: int = 720):
        super().__init__(None)
        self.entrega = PasoFotograma()
        self.setWindowTitle(TITULO_VENTANA)
        self.setMinimumSize(320, 180)
        self.resize(max(320, ancho), max(180, alto))
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self._frame = None
        self._arrastre = None
        self._reloj = QtCore.QTimer(self)
        self._reloj.setInterval(16)
        self._reloj.timeout.connect(self._pintar_si_hay)
        self._guardar = QtCore.QTimer(self)
        self._guardar.setSingleShot(True)
        self._guardar.setInterval(400)
        self._guardar.timeout.connect(self._emitir_geometria)
        atajo = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+O"), self)
        atajo.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        atajo.activated.connect(self.cerrar)

    def aplicar_geometria(self, datos: dict | None) -> None:
        if not isinstance(datos, dict):
            return
        try:
            x, y = int(datos["x"]), int(datos["y"])
            ancho, alto = int(datos["w"]), int(datos["h"])
        except (KeyError, TypeError, ValueError):
            return
        if ancho < 320 or alto < 180:
            return
        self.setGeometry(x, y, ancho, alto)

    def esta_abierta(self) -> bool:
        return self.isVisible() or self.isMinimized()

    def abrir(self) -> None:
        self.entrega.activa = True
        self.show()
        if self.isMinimized():
            self.showNormal()
        self._reloj.start()
        self._pedir_composicion()

    def cerrar(self) -> None:
        self._emitir_geometria()
        self.entrega.activa = False
        self._reloj.stop()
        self.hide()
        self.aviso.emit("Ventana de salida cerrada. La cámara virtual sigue.")

    def mostrar_frame(self, frame) -> None:
        self.entrega.activa = True
        self.entrega.publicar(frame)
        self._pintar_si_hay()

    def _pintar_si_hay(self) -> None:
        frame = self.entrega.tomar()
        if frame is None:
            return
        self._frame = frame
        self.repaint()
        self.entrega.soltar()
        if self.isMinimized():
            self._pedir_composicion()

    def _pedir_composicion(self) -> None:
        """Pide a Windows que no deje de componer la ventana si queda detrás."""
        try:
            import ctypes

            hwnd = int(self.winId())
            # RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN
            ctypes.windll.user32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0100 | 0x0080)
        except Exception:
            return

    def paintEvent(self, _evento: QtGui.QPaintEvent) -> None:
        pintor = QtGui.QPainter(self)
        pintor.fillRect(self.rect(), QtGui.QColor("#000000"))
        frame = self._frame
        if frame is not None:
            alto, ancho = frame.shape[0], frame.shape[1]
            x, y, destino_ancho, destino_alto = rect_con_relacion(
                self.width(), self.height(), ancho, alto
            )
            imagen = QtGui.QImage(
                frame.data,
                ancho,
                alto,
                int(frame.strides[0]),
                QtGui.QImage.Format.Format_BGR888,
            )
            pintor.drawImage(QtCore.QRect(x, y, destino_ancho, destino_alto), imagen)
        pintor.end()

    def mousePressEvent(self, evento: QtGui.QMouseEvent) -> None:
        if evento.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        self._arrastre = (
            self._bordes(evento.position().toPoint()),
            evento.globalPosition().toPoint(),
            self.geometry(),
        )

    def mouseMoveEvent(self, evento: QtGui.QMouseEvent) -> None:
        punto = evento.position().toPoint()
        if self._arrastre is None:
            self._cursor(self._bordes(punto))
            return
        bordes, origen, geom = self._arrastre
        delta = evento.globalPosition().toPoint() - origen
        if not any(bordes):
            self.move(geom.x() + delta.x(), geom.y() + delta.y())
            return
        rect = QtCore.QRect(geom)
        if bordes[0]:
            rect.setLeft(geom.left() + delta.x())
        if bordes[1]:
            rect.setRight(geom.right() + delta.x())
        if bordes[2]:
            rect.setTop(geom.top() + delta.y())
        if bordes[3]:
            rect.setBottom(geom.bottom() + delta.y())
        if rect.width() >= self.minimumWidth() and rect.height() >= self.minimumHeight():
            self.setGeometry(rect)

    def mouseReleaseEvent(self, _evento: QtGui.QMouseEvent) -> None:
        self._arrastre = None
        self._guardar.start()

    def resizeEvent(self, evento: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evento)
        self._guardar.start()

    def moveEvent(self, evento: QtGui.QMoveEvent) -> None:
        super().moveEvent(evento)
        self._guardar.start()

    def closeEvent(self, evento: QtGui.QCloseEvent) -> None:
        evento.ignore()
        self.cerrar()

    def _emitir_geometria(self) -> None:
        rect = self.geometry()
        self.geometria.emit(rect.x(), rect.y(), rect.width(), rect.height())

    def _bordes(self, punto: QtCore.QPoint) -> tuple[bool, bool, bool, bool]:
        return (
            punto.x() <= _MARGEN,
            punto.x() >= self.width() - _MARGEN,
            punto.y() <= _MARGEN,
            punto.y() >= self.height() - _MARGEN,
        )

    def _cursor(self, bordes: tuple[bool, bool, bool, bool]) -> None:
        izquierda, derecha, arriba, abajo = bordes
        if (izquierda and arriba) or (derecha and abajo):
            forma = QtCore.Qt.CursorShape.SizeFDiagCursor
        elif (derecha and arriba) or (izquierda and abajo):
            forma = QtCore.Qt.CursorShape.SizeBDiagCursor
        elif izquierda or derecha:
            forma = QtCore.Qt.CursorShape.SizeHorCursor
        elif arriba or abajo:
            forma = QtCore.Qt.CursorShape.SizeVerCursor
        else:
            forma = QtCore.Qt.CursorShape.ArrowCursor
        self.setCursor(forma)
