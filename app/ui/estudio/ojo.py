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
    """Ojo abierto, o un parpadeo lento si `parpadea` es verdadero."""

    def __init__(self, lado: int = 36, parpadea: bool = False, parent=None):
        super().__init__(parent)
        self._lado = lado
        self._cerrado = False
        self.setFixedSize(lado, lado)
        if parpadea:
            self._reloj = QtCore.QTimer(self)
            self._reloj.setInterval(2400)
            self._reloj.timeout.connect(self._parpadear)
            self._reloj.start()

    def _parpadear(self) -> None:
        self._cerrado = True
        self.update()
        QtCore.QTimer.singleShot(110, self._abrir)

    def _abrir(self) -> None:
        self._cerrado = False
        self.update()

    def paintEvent(self, _evento: QtGui.QPaintEvent) -> None:
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        renderer(self._cerrado).render(pintor, QtCore.QRectF(self.rect()))
        pintor.end()


class BotonIris(QtWidgets.QPushButton):
    """EN VIVO. La pupila respira en #5CE1F0 solo cuando el directo está activo."""

    def __init__(self, texto: str = "EN VIVO", parent=None):
        super().__init__(texto, parent)
        self._aliento = 0.35
        self._activo = False
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(48)
        self._animacion = QtCore.QVariantAnimation(self)
        self._animacion.setStartValue(0.35)
        self._animacion.setEndValue(1.0)
        self._animacion.setDuration(1400)
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
            self._aliento = 0.35
        self.update()

    def _respirar(self, valor: object) -> None:
        self._aliento = float(valor)
        self.update()

    def paintEvent(self, evento: QtGui.QPaintEvent) -> None:
        super().paintEvent(evento)
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        centro = QtCore.QPointF(26, self.height() / 2)
        radio = 9
        anillo = QtGui.QColor("#041014" if self._activo else "#5CE1F0")
        anillo.setAlphaF(0.9 if self._activo else 0.45)
        pintor.setPen(QtGui.QPen(anillo, 1.6))
        pintor.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        pintor.drawEllipse(centro, radio, radio)
        pupila = QtGui.QColor("#041014" if self._activo else "#5CE1F0")
        pupila.setAlphaF(self._aliento if self._activo else 0.7)
        pintor.setBrush(pupila)
        pintor.setPen(QtCore.Qt.PenStyle.NoPen)
        pintor.drawEllipse(centro, 3.2 + (1.4 * self._aliento if self._activo else 0), 3.2 + (1.4 * self._aliento if self._activo else 0))
        pintor.end()


class HaloCara(QtWidgets.QWidget):
    """Un anillo suave sobre la cara principal. No tapa los clics."""

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self._caja: tuple[float, float, float, float] | None = None

    def colocar(self, caja: tuple[float, float, float, float] | None) -> None:
        self._caja = caja
        if self.parent() is not None:
            self.setGeometry(self.parent().rect())
        self.setVisible(caja is not None)
        self.update()

    def paintEvent(self, _evento: QtGui.QPaintEvent) -> None:
        if not self._caja:
            return
        x, y, ancho, alto = self._caja
        rect = QtCore.QRectF(
            (x - 0.04) * self.width(),
            (y - 0.06) * self.height(),
            (ancho + 0.08) * self.width(),
            (alto + 0.12) * self.height(),
        )
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        color = QtGui.QColor("#5CE1F0")
        color.setAlpha(72)
        pintor.setPen(QtGui.QPen(color, 1.5))
        pintor.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        pintor.drawEllipse(rect)
        pintor.end()
