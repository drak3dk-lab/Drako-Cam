"""Pantalla Halo: la cámara al centro, la foto a un clic y EN VIVO.

No conoce el motor de caras. Emite lo que la persona hace y pinta
el estado que le pasan.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.ui.estudio.ajuste_panel import PanelAjustes
from app.ui.estudio.estilo import ESTILO
from app.ui.estudio.logica import (
    CALIDADES,
    FONDOS,
    CaraVista,
    extension_admitida,
)

_FILTRO_FOTO = "Fotos (*.jpg *.jpeg *.png *.webp *.bmp)"


def _propiedad(widget: QtWidgets.QWidget, nombre: str, valor: object) -> None:
    widget.setProperty(nombre, valor)
    estilo = widget.style()
    estilo.unpolish(widget)
    estilo.polish(widget)
    widget.update()


class BotonPildora(QtWidgets.QPushButton):
    """El 95 % al pulsar: se nota, y vuelve en el mismo gesto."""

    def __init__(self, texto: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(texto, parent)
        self._pulsado = False
        self._pintando = False
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, evento: QtGui.QMouseEvent) -> None:
        self._pulsado = True
        self.update()
        super().mousePressEvent(evento)

    def mouseReleaseEvent(self, evento: QtGui.QMouseEvent) -> None:
        self._pulsado = False
        self.update()
        super().mouseReleaseEvent(evento)

    def paintEvent(self, evento: QtGui.QPaintEvent) -> None:
        if not self._pulsado or self._pintando:
            super().paintEvent(evento)
            return
        self._pintando = True
        base = QtGui.QPixmap(self.size())
        base.fill(QtCore.Qt.GlobalColor.transparent)
        self.render(base)
        self._pintando = False
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        margen_x = self.width() * 0.025
        margen_y = self.height() * 0.025
        pintor.drawPixmap(
            QtCore.QRectF(margen_x, margen_y, self.width() * 0.95, self.height() * 0.95),
            base,
            QtCore.QRectF(0, 0, base.width(), base.height()),
        )
        pintor.end()


class MarcoVista(QtWidgets.QWidget):
    """La luz azul respira solo mientras el directo está encendido."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._aliento = 0.0
        self._vivo = False
        self._animacion = QtCore.QVariantAnimation(self)
        self._animacion.setStartValue(0.18)
        self._animacion.setEndValue(0.46)
        self._animacion.setDuration(1700)
        self._animacion.setEasingCurve(QtCore.QEasingCurve.Type.InOutSine)
        self._animacion.setLoopCount(-1)
        self._animacion.valueChanged.connect(self._respirar)
        self.setMinimumSize(480, 270)

    def encender(self, activo: bool) -> None:
        self._vivo = activo
        if activo:
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
        pintor = QtGui.QPainter(self)
        pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(8, 8, -8, -8)
        if self._vivo:
            color = QtGui.QColor(92, 225, 240, int(70 + 90 * self._aliento))
            pintor.setPen(QtGui.QPen(color, 2))
            brillo = QtGui.QColor(80, 150, 255, int(40 + 80 * self._aliento))
            pintor.setBrush(brillo)
        else:
            pintor.setPen(QtGui.QPen(QtGui.QColor(160, 190, 255, 28), 1))
            pintor.setBrush(QtGui.QColor("#050608"))
        pintor.drawRoundedRect(rect, 16, 16)
        pintor.end()


class FichaCara(QtWidgets.QFrame):
    elegida = QtCore.Signal(str)
    favorita = QtCore.Signal(str, bool)

    def __init__(self, cara: CaraVista, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.cara_id = cara.id
        self.setFixedSize(96, 128)
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(4, 4, 4, 4)
        caja.setSpacing(4)
        self.foto = QtWidgets.QLabel()
        self.foto.setFixedSize(88, 88)
        self.foto.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._pintar(cara.ruta, False)
        self.nombre = QtWidgets.QLabel(cara.nombre)
        self.nombre.setObjectName("pista")
        self.nombre.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        fuente = self.nombre.font()
        fuente.setPixelSize(12)
        self.nombre.setFont(fuente)
        fila = QtWidgets.QHBoxLayout()
        fila.addWidget(self.nombre, 1)
        self.estrella = QtWidgets.QToolButton()
        self.estrella.setText("★" if cara.favorita else "☆")
        self.estrella.setFixedSize(28, 28)
        self.estrella.setAutoRaise(True)
        self.estrella.clicked.connect(self._alternar)
        self._favorita = cara.favorita
        fila.addWidget(self.estrella)
        caja.addWidget(self.foto)
        caja.addLayout(fila)
        self.atajo = QtWidgets.QLabel(cara.atajo, self.foto)
        self.atajo.setVisible(bool(cara.atajo))
        self.atajo.setStyleSheet(
            "background: rgba(0,0,0,0.66); color: #F1F4F9; border-radius: 6px; padding: 1px 5px;"
        )
        self.atajo.move(6, 6)

    def _pintar(self, ruta: str, seleccionada: bool) -> None:
        imagen = QtGui.QImage(ruta)
        if imagen.isNull():
            self.foto.setText(self.cara_id[:1].upper())
        else:
            pixmap = QtGui.QPixmap.fromImage(imagen).scaled(
                88,
                88,
                QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.foto.setPixmap(pixmap)
        borde = "#5CE1F0" if seleccionada else "rgba(160,190,255,0.16)"
        grosor = "2px" if seleccionada else "1px"
        self.foto.setStyleSheet(
            f"border: {grosor} solid {borde}; border-radius: 12px; background: #121620;"
        )

    def marcar(self, seleccionada: bool, cara: CaraVista) -> None:
        self._pintar(cara.ruta, seleccionada)
        self._favorita = cara.favorita
        self.estrella.setText("★" if cara.favorita else "☆")
        self.atajo.setText(cara.atajo)
        self.atajo.setVisible(bool(cara.atajo))
        self.nombre.setText(cara.nombre)

    def mousePressEvent(self, evento: QtGui.QMouseEvent) -> None:
        self.elegida.emit(self.cara_id)
        super().mousePressEvent(evento)

    def _alternar(self) -> None:
        self.favorita.emit(self.cara_id, not self._favorita)


class Segmento(QtWidgets.QWidget):
    """Varias opciones en una sola pastilla. Una está elegida."""

    def __init__(self, textos: list[str], parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.grupo = QtWidgets.QButtonGroup(self)
        self.grupo.setExclusive(True)
        caja = QtWidgets.QHBoxLayout(self)
        caja.setContentsMargins(3, 3, 3, 3)
        caja.setSpacing(2)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "Segmento { background: #0B0E14; border-radius: 18px; "
            "border: 1px solid rgba(160,190,255,0.08); }"
        )
        for texto in textos:
            boton = QtWidgets.QPushButton(texto)
            boton.setObjectName("segmento")
            boton.setCheckable(True)
            boton.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            self.grupo.addButton(boton)
            caja.addWidget(boton, 1)

    def button(self, indice: int) -> QtWidgets.QAbstractButton:
        botones = self.grupo.buttons()
        return botones[indice]


class Estudio(QtWidgets.QWidget):
    pedir_en_vivo = QtCore.Signal(bool)
    pedir_cara = QtCore.Signal(str)
    pedir_camara = QtCore.Signal(int)
    pedir_favorita = QtCore.Signal(str, bool)
    pedir_fotos = QtCore.Signal(list)
    pedir_original = QtCore.Signal(bool)
    pedir_virtual = QtCore.Signal(bool)
    pedir_calidad = QtCore.Signal(str)
    pedir_fuerza = QtCore.Signal(int)
    pedir_nitidez = QtCore.Signal(int)
    pedir_frente = QtCore.Signal(int)
    pedir_fps = QtCore.Signal(int)
    pedir_fondo = QtCore.Signal(str)
    pedir_toggle = QtCore.Signal(str, bool)
    pedir_ajuste = QtCore.Signal(str, object)
    pedir_control = QtCore.Signal(str, object)
    pedir_video = QtCore.Signal()
    pedir_compacto = QtCore.Signal(bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Estudio")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(ESTILO)
        self.setAcceptDrops(True)
        self._caras: dict[str, FichaCara] = {}
        self._cara_id = ""
        self._compacto = False
        self._animaciones: list[QtCore.QPropertyAnimation] = []
        self._entradas_hechas = False
        self._construir()
        self._atajos()

    def _construir(self) -> None:
        raiz = QtWidgets.QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self._cabecera())
        self.cuerpo = QtWidgets.QWidget()
        cuerpo = QtWidgets.QHBoxLayout(self.cuerpo)
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        self.rail = self._rail()
        cuerpo.addWidget(self.rail)
        cuerpo.addWidget(self._centro(), 1)
        self.columna = self._columna_obs()
        cuerpo.addWidget(self.columna)
        raiz.addWidget(self.cuerpo, 1)
        raiz.addWidget(self._estado())
        self._entradas = [
            self.marco,
            self.galeria,
            self.boton_vivo,
            self.columna,
        ]

    def _cabecera(self) -> QtWidgets.QWidget:
        barra = QtWidgets.QWidget()
        barra.setFixedHeight(52)
        fila = QtWidgets.QHBoxLayout(barra)
        fila.setContentsMargins(16, 0, 16, 0)
        marca = QtWidgets.QLabel("DRAKO")
        marca.setObjectName("marca")
        sub = QtWidgets.QLabel("CAM")
        sub.setObjectName("marcaSub")
        fila.addWidget(marca)
        fila.addWidget(sub)
        fila.addSpacing(18)
        self.paso = QtWidgets.QLabel("1  Elige una foto")
        self.paso.setObjectName("secundario")
        fila.addWidget(self.paso)
        fila.addStretch(1)
        self.licencia = QtWidgets.QLabel("Licencia activa")
        self.licencia.setObjectName("pista")
        fila.addWidget(self.licencia)
        fila.addSpacing(12)
        self.boton_compacto = BotonPildora("Modo compacto")
        self.boton_compacto.setObjectName("compacto")
        self.boton_compacto.clicked.connect(self._alternar_compacto)
        fila.addWidget(self.boton_compacto)
        return barra

    def _rail(self) -> QtWidgets.QWidget:
        rail = QtWidgets.QWidget()
        rail.setObjectName("railFavoritos")
        rail.setFixedWidth(112)
        caja = QtWidgets.QVBoxLayout(rail)
        caja.setContentsMargins(12, 14, 12, 14)
        caja.setSpacing(8)
        titulo = QtWidgets.QLabel("★  Favoritos")
        titulo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        titulo.setObjectName("pista")
        caja.addWidget(titulo)
        self.favoritos = QtWidgets.QVBoxLayout()
        self.favoritos.setSpacing(8)
        caja.addLayout(self.favoritos)
        caja.addStretch(1)
        self.cuenta = QtWidgets.QLabel("Biblioteca\n0 caras")
        self.cuenta.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.cuenta.setObjectName("pista")
        caja.addWidget(self.cuenta)
        return rail

    def _centro(self) -> QtWidgets.QWidget:
        centro = QtWidgets.QWidget()
        caja = QtWidgets.QVBoxLayout(centro)
        caja.setContentsMargins(22, 8, 22, 16)
        caja.setSpacing(14)
        self.marco = MarcoVista()
        self.marco.setMinimumHeight(260)
        marco_caja = QtWidgets.QVBoxLayout(self.marco)
        marco_caja.setContentsMargins(16, 16, 16, 16)
        self.hueco_vista = QtWidgets.QWidget()
        self.vista_caja = QtWidgets.QVBoxLayout(self.hueco_vista)
        self.vista_caja.setContentsMargins(0, 0, 0, 0)
        self.aviso_vacio = QtWidgets.QLabel("La cámara se verá aquí")
        self.aviso_vacio.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.aviso_vacio.setObjectName("secundario")
        self.vista_caja.addWidget(self.aviso_vacio)
        marco_caja.addWidget(self.hueco_vista, 1)
        self.banner = QtWidgets.QLabel(self.marco)
        self.banner.setWordWrap(True)
        self.banner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.banner.setStyleSheet(
            "background: #F1F4F9; color: #04060A; border-radius: 12px; "
            "padding: 12px 16px; font-size: 16px; font-weight: 650;"
        )
        self.banner.hide()
        self.chip_vivo = QtWidgets.QLabel("EN VIVO", self.marco)
        self.chip_vivo.setStyleSheet(
            "background: rgba(4,6,10,0.72); color: #7FEAF5; border-radius: 13px; "
            "padding: 4px 10px; font-weight: 700;"
        )
        self.chip_vivo.hide()
        self.chip_fps = QtWidgets.QLabel("", self.marco)
        self.chip_fps.setObjectName("numero")
        self.chip_fps.setStyleSheet(
            "background: rgba(4,6,10,0.72); color: #6FD9A3; border-radius: 13px; padding: 4px 10px;"
        )
        self.chip_fps.hide()
        caja.addWidget(self.marco, 1)
        self.galeria = self._galeria()
        caja.addWidget(self.galeria)
        vivos = QtWidgets.QHBoxLayout()
        self.boton_vivo = BotonPildora("EN VIVO")
        self.boton_vivo.setObjectName("enVivo")
        self.boton_vivo.setMinimumWidth(168)
        self.boton_vivo.clicked.connect(self._pulsar_en_vivo)
        vivos.addWidget(self.boton_vivo)
        self.antes = BotonPildora("Ver antes")
        self.antes.setToolTip("Mantén pulsado para ver tu cara, sin el cambio.")
        self.antes.pressed.connect(lambda: self.pedir_original.emit(True))
        self.antes.released.connect(self._soltar_antes)
        vivos.addWidget(self.antes)
        self.segmento_vista = Segmento(["Original", "Cambiada"])
        self.segmento_vista.grupo.buttonClicked.connect(
            lambda boton: self._pulsar_original(boton.text())
        )
        self.segmento_vista.button(1).setChecked(True)
        vivos.addWidget(self.segmento_vista)
        vivos.addStretch(1)
        self.camara = QtWidgets.QComboBox()
        self.camara.setMinimumWidth(220)
        self.camara.setMinimumHeight(44)
        self.camara.currentIndexChanged.connect(self._cambiar_camara)
        vivos.addWidget(self.camara)
        self.virtual_compacto = QtWidgets.QCheckBox("Cámara virtual")
        self.virtual_compacto.hide()
        self.virtual_compacto.toggled.connect(self.pedir_virtual.emit)
        vivos.addWidget(self.virtual_compacto)
        caja.addLayout(vivos)
        return centro

    def _galeria(self) -> QtWidgets.QWidget:
        bloque = QtWidgets.QWidget()
        caja = QtWidgets.QVBoxLayout(bloque)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(8)
        titulo = QtWidgets.QLabel("Elige la cara")
        titulo.setObjectName("tituloPanel")
        caja.addWidget(titulo)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(168)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tira = QtWidgets.QWidget()
        self.tira_caja = QtWidgets.QHBoxLayout(self.tira)
        self.tira_caja.setContentsMargins(0, 0, 0, 0)
        self.tira_caja.setSpacing(8)
        self.boton_anadir = BotonPildora("Añadir foto")
        self.boton_anadir.setObjectName("anadirFoto")
        self.boton_anadir.setFixedSize(120, 128)
        self.boton_anadir.clicked.connect(self._pedir_archivos)
        self.tira_caja.addWidget(self.boton_anadir)
        self.vacio = QtWidgets.QLabel("O suelta aquí una foto JPG, PNG, WEBP o BMP")
        self.vacio.setObjectName("pista")
        self.tira_caja.addWidget(self.vacio)
        self.tira_caja.addStretch(1)
        self.scroll.setWidget(self.tira)
        caja.addWidget(self.scroll)
        return bloque

    def _columna_obs(self) -> QtWidgets.QWidget:
        columna = QtWidgets.QWidget()
        columna.setObjectName("columnaObs")
        columna.setFixedWidth(400)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        interior = QtWidgets.QWidget()
        caja = QtWidgets.QVBoxLayout(interior)
        caja.setContentsMargins(18, 18, 18, 18)
        caja.setSpacing(14)
        fila = QtWidgets.QHBoxLayout()
        etiqueta = QtWidgets.QLabel("Salida a OBS")
        etiqueta.setObjectName("pista")
        fila.addWidget(etiqueta)
        fila.addStretch(1)
        self.pill_obs = QtWidgets.QLabel("APAGADA")
        self.pill_obs.setStyleSheet(
            "background: #121620; color: #B7C0CE; border-radius: 11px; padding: 3px 8px; font-weight: 700;"
        )
        fila.addWidget(self.pill_obs)
        caja.addLayout(fila)
        titulo = QtWidgets.QLabel("Cámara virtual")
        titulo.setObjectName("tituloPanel")
        caja.addWidget(titulo)
        pista = QtWidgets.QLabel("En OBS: Dispositivo de captura de vídeo → «Drako Cam»")
        pista.setWordWrap(True)
        pista.setObjectName("pista")
        caja.addWidget(pista)
        self.virtual = QtWidgets.QCheckBox("Enviar a la cámara virtual")
        self.virtual.toggled.connect(self.pedir_virtual.emit)
        caja.addWidget(self.virtual)
        self.copiar = BotonPildora("Copiar ajustes para OBS")
        self.copiar.setObjectName("copiarObs")
        self.copiar.clicked.connect(self._copiar_obs)
        caja.addWidget(self.copiar)
        self.nota_obs = QtWidgets.QLabel("")
        self.nota_obs.setWordWrap(True)
        self.nota_obs.setObjectName("pista")
        caja.addWidget(self.nota_obs)
        caja.addWidget(self._linea())
        caja.addWidget(QtWidgets.QLabel("Calidad"))
        self.calidad = QtWidgets.QComboBox()
        self.calidad.addItems(list(CALIDADES))
        self.calidad.setMinimumHeight(44)
        self.calidad.currentTextChanged.connect(self._pulsar_calidad)
        caja.addWidget(self.calidad)
        self.nota_calidad = QtWidgets.QLabel("Según la tarjeta que haya en el equipo.")
        self.nota_calidad.setWordWrap(True)
        self.nota_calidad.setObjectName("pista")
        caja.addWidget(self.nota_calidad)
        caja.addWidget(self._linea())
        self.ajustes = PanelAjustes()
        self.ajustes.cambiado.connect(self.pedir_control.emit)
        caja.addWidget(self.ajustes)
        caja.addWidget(self._linea())
        caja.addWidget(self._rotulo_valor("Fuerza", "fuerzaValor"))
        self.fuerza = self._slider(50, self.pedir_fuerza.emit)
        self.fuerza.valueChanged.connect(self.fijar_fuerza_texto)
        caja.addWidget(self.fuerza)
        extremos = QtWidgets.QHBoxLayout()
        suave = QtWidgets.QLabel("Suave")
        suave.setObjectName("pista")
        fuerte = QtWidgets.QLabel("Fuerte")
        fuerte.setObjectName("pista")
        extremos.addWidget(suave)
        extremos.addStretch(1)
        extremos.addWidget(fuerte)
        caja.addLayout(extremos)
        caja.addWidget(QtWidgets.QLabel("FPS de salida"))
        self.fps_salida = Segmento(["30", "60"])
        self.fps_salida.grupo.buttonClicked.connect(
            lambda boton: self._pulsar_fps(boton.text())
        )
        self.fps_salida.button(0).setChecked(True)
        caja.addWidget(self.fps_salida)
        caja.addWidget(QtWidgets.QLabel("Fondo"))
        self.fondo = Segmento(list(FONDOS))
        self.fondo.grupo.buttonClicked.connect(
            lambda boton: self._pulsar_fondo(boton.text())
        )
        self.fondo.button(0).setChecked(True)
        caja.addWidget(self.fondo)
        caja.addWidget(self._linea())
        self.toggles: dict[str, QtWidgets.QCheckBox] = {}
        for clave, texto in (
            ("fps", "Mostrar FPS"),
            ("varias", "Varias caras"),
        ):
            caja_toggle = QtWidgets.QCheckBox(texto)
            caja_toggle.toggled.connect(lambda activo, nombre=clave: self.pedir_toggle.emit(nombre, activo))
            self.toggles[clave] = caja_toggle
            caja.addWidget(caja_toggle)
        self.toggles["fps"].setChecked(True)
        caja.addWidget(self._linea())
        self.avanzado = QtWidgets.QToolButton()
        self.avanzado.setText("Avanzado")
        self.avanzado.setCheckable(True)
        self.avanzado.setChecked(False)
        self.avanzado.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.avanzado.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.avanzado.toggled.connect(self._abrir_avanzado)
        self.avanzado.setMinimumHeight(44)
        caja.addWidget(self.avanzado)
        self.panel_avanzado = QtWidgets.QWidget()
        self.panel_avanzado.hide()
        avanzado = QtWidgets.QVBoxLayout(self.panel_avanzado)
        avanzado.setContentsMargins(0, 0, 0, 0)
        avanzado.setSpacing(8)
        nota = QtWidgets.QLabel(
            "Resolución de la webcam, proveedor y un vídeo de prueba si no hay cámara. "
            "El ajuste de la cara está arriba."
        )
        nota.setWordWrap(True)
        nota.setObjectName("pista")
        avanzado.addWidget(nota)
        self.resolucion = self._combo(
            "Resolución",
            ["1280x720", "1920x1080", "2560x1440"],
            "resolucion",
        )
        self.proveedor = self._combo("Proveedor TensorRT", ["FP16", "FP32"], "proveedor")
        self.detector = self._combo(
            "Detector",
            ["RetinaFace", "SCRFD", "Yolov8"],
            "detector",
        )
        for combo in (self.resolucion, self.proveedor, self.detector):
            avanzado.addWidget(combo)
        self.boton_video = BotonPildora("Probar con un vídeo")
        self.boton_video.clicked.connect(self.pedir_video.emit)
        avanzado.addWidget(self.boton_video)
        self.boton_volver = BotonPildora("Volver a la cámara")
        self.boton_volver.clicked.connect(lambda: self.pedir_ajuste.emit("volver_camara", True))
        avanzado.addWidget(self.boton_volver)
        caja.addWidget(self.panel_avanzado)
        caja.addStretch(1)
        scroll.setWidget(interior)
        exterior = QtWidgets.QVBoxLayout(columna)
        exterior.setContentsMargins(0, 0, 0, 0)
        exterior.addWidget(scroll)
        return columna

    def _estado(self) -> QtWidgets.QWidget:
        barra = QtWidgets.QWidget()
        barra.setObjectName("barraEstado")
        barra.setFixedHeight(36)
        fila = QtWidgets.QHBoxLayout(barra)
        fila.setContentsMargins(16, 0, 16, 0)
        fila.setSpacing(18)
        self.txt_fps = self._medida("FPS")
        self.txt_latencia = self._medida("Latencia")
        self.txt_vram = self._medida("VRAM")
        self.txt_proveedor = self._medida("Proveedor")
        self.txt_vigilante = self._medida("Vigilante")
        self.txt_sesion = self._medida("Sesión")
        for pieza in (
            self.txt_fps,
            self.txt_latencia,
            self.txt_vram,
            self.txt_proveedor,
            self.txt_vigilante,
        ):
            fila.addWidget(pieza)
        fila.addStretch(1)
        fila.addWidget(self.txt_sesion)
        self._reloj = QtCore.QElapsedTimer()
        self._reloj.start()
        self._pulso = QtCore.QTimer(self)
        self._pulso.setInterval(500)
        self._pulso.timeout.connect(self._pintar_sesion)
        self._pulso.start()
        return barra

    def _medida(self, titulo: str) -> QtWidgets.QLabel:
        etiqueta = QtWidgets.QLabel(f"{titulo}  —")
        etiqueta.setObjectName("numero")
        return etiqueta

    def _slider(self, valor: int, slot) -> QtWidgets.QSlider:
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(valor)
        slider.setMinimumHeight(44)
        slider.valueChanged.connect(slot)
        return slider

    def _slider_rotulado(self, titulo: str, valor: int, slot) -> QtWidgets.QWidget:
        bloque = QtWidgets.QWidget()
        caja = QtWidgets.QVBoxLayout(bloque)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.addWidget(QtWidgets.QLabel(titulo))
        caja.addWidget(self._slider(valor, slot))
        return bloque

    def _rotulo_valor(self, titulo: str, nombre: str) -> QtWidgets.QWidget:
        fila = QtWidgets.QWidget()
        caja = QtWidgets.QHBoxLayout(fila)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.addWidget(QtWidgets.QLabel(titulo))
        caja.addStretch(1)
        valor = QtWidgets.QLabel("50")
        valor.setObjectName(nombre)
        caja.addWidget(valor)
        self.fuerza_valor = valor
        return fila

    def _combo(self, titulo: str, opciones: list[str], clave: str) -> QtWidgets.QWidget:
        bloque = QtWidgets.QWidget()
        caja = QtWidgets.QVBoxLayout(bloque)
        caja.setContentsMargins(0, 0, 0, 0)
        etiqueta = QtWidgets.QLabel(titulo)
        etiqueta.setObjectName("pista")
        combo = QtWidgets.QComboBox()
        combo.addItems(opciones)
        combo.setMinimumHeight(44)
        combo.currentTextChanged.connect(lambda texto, nombre=clave: self.pedir_ajuste.emit(nombre, texto))
        caja.addWidget(etiqueta)
        caja.addWidget(combo)
        bloque.combo = combo  # type: ignore[attr-defined]
        return bloque

    def _linea(self) -> QtWidgets.QFrame:
        linea = QtWidgets.QFrame()
        linea.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        linea.setStyleSheet("color: rgba(160,190,255,0.08);")
        return linea

    def _atajos(self) -> None:
        for indice in range(1, 9):
            atajo = QtGui.QShortcut(QtGui.QKeySequence(f"F{indice}"), self)
            atajo.activated.connect(lambda i=indice: self._favorito_por_tecla(i))
        espacio = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Space"), self)
        espacio.activated.connect(self._invertir_original)

    def mostrar_caras(self, caras: list[CaraVista], seleccion: str) -> None:
        firma = tuple((cara.id, cara.favorita, cara.atajo, cara.id == seleccion) for cara in caras)
        if firma == getattr(self, "_firma_caras", None):
            return
        self._firma_caras = firma
        self._cara_id = seleccion
        for indice in reversed(range(self.tira_caja.count())):
            pieza = self.tira_caja.itemAt(indice)
            widget = pieza.widget() if pieza is not None else None
            if isinstance(widget, FichaCara):
                self.tira_caja.takeAt(indice)
                widget.deleteLater()
        self._caras.clear()
        self._vaciar(self.favoritos)
        self.vacio.setVisible(not caras)
        favoritas = 0
        for cara in caras:
            ficha = FichaCara(cara)
            ficha.elegida.connect(self.pedir_cara.emit)
            ficha.favorita.connect(self.pedir_favorita.emit)
            ficha.marcar(cara.id == seleccion, cara)
            self._caras[cara.id] = ficha
            self.tira_caja.insertWidget(self.tira_caja.count() - 1, ficha)
            if cara.favorita:
                favoritas += 1
                boton = BotonPildora(cara.atajo or cara.nombre[:1])
                boton.setFixedSize(56, 56)
                boton.setToolTip(cara.nombre)
                boton.clicked.connect(lambda _=False, ident=cara.id: self.pedir_cara.emit(ident))
                if cara.id == seleccion:
                    _propiedad(boton, "vivo", True)
                    boton.setStyleSheet("background: #5CE1F0; color: #041014; border: none;")
                self.favoritos.addWidget(boton, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.cuenta.setText(f"Biblioteca\n{len(caras)} caras")
        if not favoritas:
            nota = QtWidgets.QLabel("Marca una\ncon la estrella")
            nota.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            nota.setObjectName("pista")
            nota.setWordWrap(True)
            self.favoritos.addWidget(nota)

    def mostrar_camaras(self, nombres: list[str], indice: int) -> None:
        firma = (tuple(nombres), indice)
        if firma == getattr(self, "_firma_camaras", None):
            return
        self._firma_camaras = firma
        self.camara.blockSignals(True)
        actual = self.camara.currentText()
        self.camara.clear()
        if not nombres:
            self.camara.addItem("No hay cámara")
            self.camara.setCurrentIndex(0)
        else:
            self.camara.addItems(nombres)
            if 0 <= indice < len(nombres):
                self.camara.setCurrentIndex(indice)
            elif actual in nombres:
                self.camara.setCurrentText(actual)
        self.camara.blockSignals(False)

    def mostrar_estado(
        self,
        *,
        sesion: bool,
        en_vivo: bool,
        original: bool,
        tiene_foto: bool,
        tiene_camara: bool,
        fps: float | None,
        latencia_ms: float | None,
        vram: str,
        proveedor: str,
        vigilante: str,
        mensaje: str,
        calidad_nota: str,
        virtual: bool,
        resolucion: str,
        fps_salida: str,
        fondo: str,
    ) -> None:
        self.marco.encender(sesion)
        _propiedad(self.boton_vivo, "vivo", en_vivo)
        self.boton_vivo.setText("PARAR" if sesion else "EN VIVO")
        self._marcar_original(original)
        self.chip_vivo.setVisible(en_vivo)
        if self.toggles["fps"].isChecked() and fps is not None and en_vivo:
            self.chip_fps.setText(f"{fps:.1f} FPS".replace(".", ","))
            self.chip_fps.show()
        else:
            self.chip_fps.hide()
        self._poner_medida(self.txt_fps, "FPS", None if fps is None else f"{fps:.1f}".replace(".", ","))
        self._poner_medida(
            self.txt_latencia,
            "Latencia",
            None if latencia_ms is None else f"{latencia_ms:.0f} ms",
        )
        self._poner_medida(self.txt_vram, "VRAM", vram or None)
        self._poner_medida(self.txt_proveedor, "Proveedor", proveedor or None)
        self._poner_medida(self.txt_vigilante, "Vigilante", vigilante or None)
        self.nota_calidad.setText(calidad_nota)
        self.pill_obs.setText("EMITIENDO" if virtual else "APAGADA")
        if virtual:
            self.pill_obs.setStyleSheet(
                "background: rgba(92,225,240,0.12); color: #7FEAF5; border-radius: 11px; "
                "padding: 3px 8px; font-weight: 700;"
            )
        else:
            self.pill_obs.setStyleSheet(
                "background: #121620; color: #B7C0CE; border-radius: 11px; padding: 3px 8px; font-weight: 700;"
            )
        if self.virtual.isChecked() != virtual:
            self.virtual.blockSignals(True)
            self.virtual.setChecked(virtual)
            self.virtual.blockSignals(False)
        if self.virtual_compacto.isChecked() != virtual:
            self.virtual_compacto.blockSignals(True)
            self.virtual_compacto.setChecked(virtual)
            self.virtual_compacto.blockSignals(False)
        self._texto_obs = self._texto_obs_de(resolucion, fps_salida, fondo)
        self.nota_obs.setText(self._texto_obs.replace("\n", " · "))
        if mensaje:
            self.banner.setText(mensaje)
            self.banner.show()
            self.banner.raise_()
        else:
            self.banner.hide()
        if sesion:
            self.paso.setText("En directo" if en_vivo else "Viendo el original")
        elif not tiene_foto:
            self.paso.setText("1  Elige una foto")
        elif not tiene_camara:
            self.paso.setText("2  Elige la cámara")
        else:
            self.paso.setText("3  Pulsa EN VIVO")
        self._colocar_capas()

    def adoptar_vista(self, vista: QtWidgets.QWidget) -> None:
        self.aviso_vacio.hide()
        vista.setParent(self.hueco_vista)
        self.vista_caja.addWidget(vista)
        vista.show()

    def resizeEvent(self, evento: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evento)
        self._colocar_capas()

    def showEvent(self, evento: QtGui.QShowEvent) -> None:
        super().showEvent(evento)
        self._colocar_capas()
        if self._entradas_hechas:
            return
        self._entradas_hechas = True
        for indice, pieza in enumerate(self._entradas):
            efecto = QtWidgets.QGraphicsOpacityEffect(pieza)
            efecto.setOpacity(0.0)
            pieza.setGraphicsEffect(efecto)
            animacion = QtCore.QPropertyAnimation(efecto, b"opacity", self)
            animacion.setDuration(220)
            animacion.setStartValue(0.0)
            animacion.setEndValue(1.0)
            animacion.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
            animacion.finished.connect(lambda pieza=pieza: pieza.setGraphicsEffect(None))
            self._animaciones.append(animacion)
            QtCore.QTimer.singleShot(40 * indice, animacion.start)

    def dragEnterEvent(self, evento: QtGui.QDragEnterEvent) -> None:
        if self._rutas_de_evento(evento):
            evento.acceptProposedAction()
        else:
            evento.ignore()

    def dropEvent(self, evento: QtGui.QDropEvent) -> None:
        rutas = self._rutas_de_evento(evento)
        if rutas:
            self.pedir_fotos.emit(rutas)
            evento.acceptProposedAction()

    def _colocar_capas(self) -> None:
        if self.banner.isVisible():
            self.banner.setGeometry(24, 24, max(80, self.marco.width() - 48), 72)
            self.banner.raise_()
        self.chip_vivo.move(28, self.marco.height() - 48)
        self.chip_fps.move(self.marco.width() - self.chip_fps.sizeHint().width() - 28, self.marco.height() - 48)
        self.chip_vivo.raise_()
        self.chip_fps.raise_()

    def _marcar_original(self, original: bool) -> None:
        boton = self.segmento_vista.button(0 if original else 1)
        if boton.isChecked():
            return
        self.segmento_vista.grupo.blockSignals(True)
        boton.setChecked(True)
        self.segmento_vista.grupo.blockSignals(False)

    def _pulsar_en_vivo(self) -> None:
        encender = self.boton_vivo.text() != "PARAR"
        self.pedir_en_vivo.emit(encender)

    def _pulsar_original(self, texto: str) -> None:
        self.pedir_original.emit(texto == "Original")

    def _soltar_antes(self) -> None:
        elegido = self.segmento_vista.grupo.checkedButton()
        self.pedir_original.emit(elegido is not None and elegido.text() == "Original")

    def _pulsar_calidad(self, texto: str) -> None:
        self.pedir_calidad.emit(texto)

    def _pulsar_fps(self, texto: str) -> None:
        self.pedir_fps.emit(int(texto))

    def _pulsar_fondo(self, texto: str) -> None:
        self.pedir_fondo.emit(texto)

    def _cambiar_camara(self, indice: int) -> None:
        if indice < 0 or self.camara.currentText() == "No hay cámara":
            return
        self.pedir_camara.emit(indice)

    def _pedir_archivos(self) -> None:
        rutas, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Añadir foto", "", _FILTRO_FOTO
        )
        if rutas:
            self.pedir_fotos.emit(rutas)

    def _copiar_obs(self) -> None:
        QtWidgets.QApplication.clipboard().setText(getattr(self, "_texto_obs", ""))
        self.nota_obs.setText("Copiado. Pégalo donde te haga falta y, en OBS, elige «Drako Cam».")

    def _texto_obs_de(self, resolucion: str, fps: str, fondo: str) -> str:
        from app.ui.estudio.logica import texto_para_obs

        return texto_para_obs(resolucion, fps, fondo)

    def _abrir_avanzado(self, abierto: bool) -> None:
        self.panel_avanzado.setVisible(abierto)
        self.avanzado.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if abierto else QtCore.Qt.ArrowType.RightArrow
        )

    def _alternar_compacto(self) -> None:
        self._compacto = not self._compacto
        self.rail.setVisible(not self._compacto)
        self.columna.setVisible(not self._compacto)
        self.virtual_compacto.setVisible(self._compacto)
        self.boton_compacto.setText("Ampliar" if self._compacto else "Modo compacto")
        ventana = self.window()
        if self._compacto:
            self._tamano_previo = ventana.size()
            ventana.resize(440, 720)
        elif getattr(self, "_tamano_previo", None) is not None:
            ventana.resize(self._tamano_previo)
        self.pedir_compacto.emit(self._compacto)

    def _favorito_por_tecla(self, numero: int) -> None:
        for cara_id, ficha in self._caras.items():
            if ficha.atajo.text() == f"F{numero}":
                self.pedir_cara.emit(cara_id)
                return

    def _invertir_original(self) -> None:
        actual = self.segmento_vista.checkedButton()
        if actual is not None and actual.text() == "Original":
            self.segmento_vista.button(1).setChecked(True)
            self.pedir_original.emit(False)
        else:
            self.segmento_vista.button(0).setChecked(True)
            self.pedir_original.emit(True)

    def _pintar_sesion(self) -> None:
        segundos = self._reloj.elapsed() // 1000
        horas, resto = divmod(segundos, 3600)
        minutos, seg = divmod(resto, 60)
        self.txt_sesion.setText(f"Sesión  {horas:02d}:{minutos:02d}:{seg:02d}")

    def _poner_medida(self, etiqueta: QtWidgets.QLabel, titulo: str, valor: str | None) -> None:
        etiqueta.setText(f"{titulo}  {valor or '—'}")

    def _rutas_de_evento(self, evento: QtGui.QDropEvent | QtGui.QDragEnterEvent) -> list[str]:
        mime = evento.mimeData()
        if mime is None or not mime.hasUrls():
            return []
        rutas = []
        for url in mime.urls():
            ruta = url.toLocalFile()
            if ruta and extension_admitida(ruta):
                rutas.append(ruta)
        return rutas

    def _vaciar(self, caja: QtWidgets.QLayout) -> None:
        while caja.count():
            pieza = caja.takeAt(0)
            if pieza is not None and pieza.widget() is not None:
                pieza.widget().deleteLater()

    def fijar_fuerza_texto(self, valor: int) -> None:
        self.fuerza_valor.setText(str(valor))
