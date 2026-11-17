"""Logo de Drako Cam.

El símbolo oficial es el PNG que Drako aprobó
(`assets/drakocam/isotipo.png`): la D plateada con el ojo rojo
hecho lente. En la app se usa ese archivo, recortado, no un redibujo.

Para volver al logo de la marca, sin tocarlo, cambia una sola línea
en `app/ui/core/media/logo.usar`: escribe `marca` en vez de `producto`.
El original está en `assets/marca/`, sin modificar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

ROJO = "#F20A1C"

_MEDIA = Path(__file__).resolve().parents[1] / "core" / "media"
RUTA_USAR = _MEDIA / "logo.usar"
RUTA_ISOTIPO = _MEDIA / "isotipo-limpio.png"
RUTA_MINI = _MEDIA / "isotipo-mini.png"
RUTA_DRAKO = _MEDIA / "drako-plata.png"
RUTA_D_MARCA = _MEDIA / "d-plata.png"


def variante() -> str:
    try:
        texto = RUTA_USAR.read_text(encoding="utf-8").strip().lower()
    except OSError:
        texto = ""
    return "marca" if texto == "marca" else "producto"


def pixmap_simbolo(lado: int) -> QtGui.QPixmap:
    """La D del PNG aprobado. Solo por debajo de 40 px se usa la reducción de 64."""
    imagen = QtGui.QImage(lado, lado, QtGui.QImage.Format.Format_ARGB32)
    imagen.fill(QtGui.QColor("#000000"))
    pintor = QtGui.QPainter(imagen)
    pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    pintor.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    if variante() == "marca" and RUTA_D_MARCA.is_file():
        origen = RUTA_D_MARCA
    elif lado <= 32 and RUTA_MINI.is_file():
        origen = RUTA_MINI
    else:
        origen = RUTA_ISOTIPO
    simbolo = QtGui.QPixmap(str(origen))
    if not simbolo.isNull():
        escala = min(lado / simbolo.width(), lado / simbolo.height())
        ancho = max(1, int(round(simbolo.width() * escala)))
        alto = max(1, int(round(simbolo.height() * escala)))
        pintor.drawPixmap(
            (lado - ancho) // 2,
            (lado - alto) // 2,
            simbolo.scaled(
                ancho,
                alto,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            ),
        )
    pintor.end()
    return QtGui.QPixmap.fromImage(imagen)


def pixmap_lockup(ancho: int) -> QtGui.QPixmap:
    """Símbolo y, debajo, DRAKO. En producto, CAM más pequeño con el triángulo."""
    alto = int(ancho * (1.15 if variante() == "producto" else 0.95))
    imagen = QtGui.QImage(ancho, alto, QtGui.QImage.Format.Format_ARGB32)
    imagen.fill(0)
    pintor = QtGui.QPainter(imagen)
    pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    pintor.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    origen = RUTA_ISOTIPO if variante() == "producto" else RUTA_D_MARCA
    marca = QtGui.QPixmap(str(origen))
    alto_marca = int(ancho * 0.62)
    if not marca.isNull():
        ancho_marca = int(alto_marca * marca.width() / max(1, marca.height()))
        ancho_marca = min(ancho - 8, ancho_marca)
        alto_marca = int(ancho_marca * marca.height() / max(1, marca.width()))
        pintor.drawPixmap((ancho - ancho_marca) // 2, 0, marca.scaled(
            ancho_marca, alto_marca,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        ))
    y = alto_marca + int(ancho * 0.04)
    palabra = QtGui.QPixmap(str(RUTA_DRAKO))
    if not palabra.isNull():
        alto_palabra = max(18, int(ancho * 0.11))
        ancho_palabra = int(alto_palabra * palabra.width() / max(1, palabra.height()))
        ancho_palabra = min(ancho - 8, ancho_palabra)
        pintor.drawPixmap(
            (ancho - ancho_palabra) // 2,
            y,
            palabra.scaled(
                ancho_palabra,
                alto_palabra,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            ),
        )
        y += alto_palabra + int(ancho * 0.025)
    if variante() == "producto":
        _dibujar_cam(pintor, ancho, y, int(ancho * 0.075))
    pintor.end()
    return QtGui.QPixmap.fromImage(imagen)


def _barra(pintor: QtGui.QPainter, rect: QtCore.QRectF) -> None:
    pintor.drawRect(rect)


def _dibujar_cam(pintor: QtGui.QPainter, ancho: int, y: int, alto: int) -> None:
    """CAM geométrico, con aire entre letras y el triángulo rojo en la A."""
    t = max(4, int(alto * 0.22))
    hueco = int(alto * 0.72)
    ancho_letra = int(alto * 0.92)
    total = 3 * ancho_letra + 2 * hueco
    x = (ancho - total) // 2
    plata = QtGui.QColor("#C5CAD2")
    pintor.setPen(QtCore.Qt.PenStyle.NoPen)
    pintor.setBrush(plata)
    for letra in ("C", "A", "M"):
        left, top = x, y
        right, bottom = x + ancho_letra, y + alto
        if letra == "C":
            pintor.drawRect(QtCore.QRectF(left, top, t, alto))
            pintor.drawRect(QtCore.QRectF(left, top, ancho_letra * 0.72, t))
            pintor.drawRect(QtCore.QRectF(left, bottom - t, ancho_letra * 0.72, t))
        elif letra == "A":
            medio = left + ancho_letra / 2
            pintor.drawPolygon(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(medio, top),
                        QtCore.QPointF(medio + t * 0.7, top),
                        QtCore.QPointF(right, bottom),
                        QtCore.QPointF(right - t, bottom),
                    ]
                )
            )
            pintor.drawPolygon(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(medio, top),
                        QtCore.QPointF(medio - t * 0.7, top),
                        QtCore.QPointF(left, bottom),
                        QtCore.QPointF(left + t, bottom),
                    ]
                )
            )
            lado = t * 0.85
            pintor.setBrush(QtGui.QColor(ROJO))
            pintor.drawPolygon(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(medio, top + alto * 0.48),
                        QtCore.QPointF(medio - lado, top + alto * 0.78),
                        QtCore.QPointF(medio + lado, top + alto * 0.78),
                    ]
                )
            )
            pintor.setBrush(plata)
        else:
            pintor.drawRect(QtCore.QRectF(left, top, t, alto))
            pintor.drawRect(QtCore.QRectF(right - t, top, t, alto))
            pintor.drawPolygon(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(left, top),
                        QtCore.QPointF(left + t, top),
                        QtCore.QPointF(left + ancho_letra / 2 + t * 0.4, top + alto * 0.62),
                        QtCore.QPointF(left + ancho_letra / 2 - t * 0.4, top + alto * 0.62),
                    ]
                )
            )
            pintor.drawPolygon(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(right, top),
                        QtCore.QPointF(right - t, top),
                        QtCore.QPointF(left + ancho_letra / 2 - t * 0.4, top + alto * 0.62),
                        QtCore.QPointF(left + ancho_letra / 2 + t * 0.4, top + alto * 0.62),
                    ]
                )
            )
        x += ancho_letra + hueco


def icono(lado: int = 64) -> QtGui.QIcon:
    return QtGui.QIcon(pixmap_simbolo(lado))


class BotonIris(QtWidgets.QPushButton):
    """EN VIVO. El rojo del ojo solo mientras el directo está activo."""

    def __init__(self, texto: str = "EN VIVO", parent=None):
        super().__init__(texto, parent)
        self._aliento = 0.0
        self._activo = False
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(48)
        self._animacion = QtCore.QVariantAnimation(self)
        self._animacion.setStartValue(0.25)
        self._animacion.setEndValue(0.7)
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
        color = QtGui.QColor("#FFF6F6")
        color.setAlphaF(self._aliento * 0.55)
        pintor.setPen(QtGui.QPen(color, 1.25))
        pintor.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        rect = QtCore.QRectF(4, 4, self.width() - 8, self.height() - 8)
        pintor.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        pintor.end()


class MarcaOjo(QtWidgets.QWidget):
    """El símbolo, en la barra. Sin texto: a ese tamaño no se lee."""

    def __init__(self, lado: int = 36, parent=None):
        super().__init__(parent)
        self._lado = lado
        self.setFixedSize(lado, lado)

    def paintEvent(self, _evento: QtGui.QPaintEvent) -> None:
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        pintor.drawPixmap(self.rect(), pixmap_simbolo(self._lado))
        pintor.end()


class MarcaCompleta(QtWidgets.QWidget):
    def __init__(self, ancho: int = 280, parent=None):
        super().__init__(parent)
        self._pix = pixmap_lockup(ancho)
        self.setFixedSize(self._pix.size())

    def paintEvent(self, _evento: QtGui.QPaintEvent) -> None:
        pintor = QtGui.QPainter(self)
        pintor.drawPixmap(0, 0, self._pix)
        pintor.end()


class FondoCarga(QtWidgets.QWidget):
    """Fondo oscuro, apenas una tela, y el logo plateado con un brillo corto en el ojo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._marca = MarcaCompleta(300, self)
        self.setMinimumSize(460, 280)

    def resizeEvent(self, evento: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evento)
        self._marca.move(
            (self.width() - self._marca.width()) // 2,
            (self.height() - self._marca.height()) // 2 - 8,
        )

    def paintEvent(self, _evento: QtGui.QPaintEvent) -> None:
        pintor = QtGui.QPainter(self)
        pintor.fillRect(self.rect(), QtGui.QColor("#07080C"))
        pintor.setPen(QtGui.QColor(255, 255, 255, 10))
        for i in range(-self.height(), self.width(), 14):
            pintor.drawLine(i, 0, i + self.height(), self.height())
        centro = QtCore.QPointF(self.width() / 2, self.height() * 0.40)
        radio = min(self.width(), self.height()) * 0.22
        brillo = QtGui.QRadialGradient(centro, radio)
        brillo.setColorAt(0.0, QtGui.QColor(242, 10, 28, 70))
        brillo.setColorAt(0.45, QtGui.QColor(242, 10, 28, 18))
        brillo.setColorAt(1.0, QtGui.QColor(242, 10, 28, 0))
        pintor.setPen(QtCore.Qt.PenStyle.NoPen)
        pintor.setBrush(brillo)
        pintor.drawEllipse(centro, radio, radio * 0.72)
        pintor.end()
