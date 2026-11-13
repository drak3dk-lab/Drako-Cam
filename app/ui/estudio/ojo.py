"""El ojo provisional. El archivo que hay que sustituir es uno solo.

`app/ui/core/media/logo.svg`

Tiene dos grupos: `abierto` y `cerrado`. El logo final de Drako
reemplaza ese SVG y se vuelve a generar el icono del instalador
con `python scripts/generar_icono.py`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtSvg, QtWidgets

RUTA_LOGO = Path(__file__).resolve().parents[1] / "core" / "media" / "logo.svg"


def _xml(cerrado: bool) -> bytes:
    texto = RUTA_LOGO.read_text(encoding="utf-8")
    if cerrado:
        texto = texto.replace('id="abierto"', 'id="abierto" visibility="hidden"', 1)
        texto = texto.replace('id="cerrado" visibility="hidden"', 'id="cerrado"', 1)
    return texto.encode("utf-8")


def renderer(cerrado: bool = False) -> QtSvg.QSvgRenderer:
    dibujo = QtSvg.QSvgRenderer()
    dibujo.load(_xml(cerrado))
    return dibujo


def icono(lado: int = 64) -> QtGui.QIcon:
    imagen = QtGui.QImage(lado, lado, QtGui.QImage.Format.Format_ARGB32)
    imagen.fill(QtGui.QColor("#050608"))
    pintor = QtGui.QPainter(imagen)
    renderer(False).render(pintor)
    pintor.end()
    return QtGui.QIcon(QtGui.QPixmap.fromImage(imagen))


class MarcaOjo(QtWidgets.QWidget):
    """El logo, quieto. Solo va en el título y en la espera del acceso."""

    def __init__(self, lado: int = 36, parent=None):
        super().__init__(parent)
        self.setFixedSize(lado, lado)

    def paintEvent(self, _evento: QtGui.QPaintEvent) -> None:
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        renderer(False).render(pintor, QtCore.QRectF(self.rect()))
        pintor.end()


class BotonIris(QtWidgets.QPushButton):
    """EN VIVO. Solo un borde que respira, y únicamente mientras está activo."""

    def __init__(self, texto: str = "EN VIVO", parent=None):
        super().__init__(texto, parent)
        self._aliento = 0.0
        self._activo = False
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(48)
        self._animacion = QtCore.QVariantAnimation(self)
        self._animacion.setStartValue(0.22)
        self._animacion.setEndValue(0.55)
        self._animacion.setDuration(1600)
        self._animacion.setLoopCount(-1)
        self._animacion.setEasingCurve(QtCore.QEasingCurve.Type.InOutSine)
        self._animacion.valueChanged.connect(self._respirar)

    def respirar(self, activo: bool) -> None:
        self._activo = bool(activo)
        if self._activo:
            if self._animacion.state() != QtCore.QAbstractAnimation.State.Running:
                self._animacion.start()
        else:
            self._animacion.stop()
            self._aliento = 0.0
        self.update()

    def _respirar(self, valor: object) -> None:
        self._aliento = float(valor)
        self.update()

    def paintEvent(self, evento: QtGui.QPaintEvent) -> None:
        super().paintEvent(evento)
        if not self._activo:
            return
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        color = QtGui.QColor("#041014")
        color.setAlphaF(self._aliento)
        pintor.setPen(QtGui.QPen(color, 1.5))
        pintor.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        rect = QtCore.QRectF(3, 3, self.width() - 6, self.height() - 6)
        pintor.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        pintor.end()
