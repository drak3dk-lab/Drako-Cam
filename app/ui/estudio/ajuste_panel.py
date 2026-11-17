"""Panel «Ajustar cara»: un grupo, un interruptor, los sliders debajo.

El título y el número van juntos. «Restablecer» baja a otra línea
si no cabe al lado, y el deslizador ocupa todo el ancho. Nada se sale
por la derecha: el panel vive en un área con scroll vertical.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from app.ui.estudio.controles import GRUPOS, Control, Grupo, por_clave


def _marcar(widget: QtWidgets.QWidget, activo: bool) -> None:
    widget.setProperty("activo", "true" if activo else "false")
    estilo = widget.style()
    estilo.unpolish(widget)
    estilo.polish(widget)
    widget.update()


class _TextoQueCabe(QtWidgets.QLabel):
    """Parte el texto en varias líneas y no ensancha el panel."""

    def __init__(self, texto: str = "", parent: QtWidgets.QWidget | None = None):
        super().__init__(texto, parent)
        self.setWordWrap(True)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )

    def minimumSizeHint(self) -> QtCore.QSize:
        alto = max(self.fontMetrics().lineSpacing(), 1)
        return QtCore.QSize(0, alto)

    def hasHeightForWidth(self) -> bool:
        return True


class FiltroRueda(QtCore.QObject):
    """La rueda desplaza el panel. El control solo cambia si se enfocó con un clic."""

    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self._con_clic: set[int] = set()

    def _marcados(self) -> set[int]:
        clic = getattr(self, "_con_clic", None)
        if clic is None:
            clic = set()
            self._con_clic = clic
        return clic

    def eventFilter(self, obj, evento) -> bool:
        if not isinstance(
            obj,
            (QtWidgets.QSlider, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QComboBox),
        ):
            return False
        if evento.type() == QtCore.QEvent.Type.MouseButtonPress:
            self._marcados().add(id(obj))
            return False
        if evento.type() == QtCore.QEvent.Type.FocusIn:
            if evento.reason() == QtCore.Qt.FocusReason.MouseFocusReason:
                self._marcados().add(id(obj))
            return False
        if evento.type() != QtCore.QEvent.Type.Wheel:
            return False
        if obj.hasFocus() and id(obj) in self._marcados():
            return False
        area = obj.parentWidget()
        elegido = None
        while area is not None:
            if isinstance(area, QtWidgets.QScrollArea) and area.verticalScrollBar().maximum() > 0:
                elegido = area
                break
            area = area.parentWidget()
        if elegido is None:
            return True
        QtWidgets.QApplication.sendEvent(elegido.viewport(), evento)
        return True


def preparar_rueda(control: QtWidgets.QWidget, filtro: FiltroRueda) -> None:
    control.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
    control.installEventFilter(filtro)


class _Fila(QtWidgets.QWidget):
    """Un control: título con su número, deslizador a todo el ancho y Restablecer."""

    def __init__(self, control: Control, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.control = control
        self._apilado: bool | None = None
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(0, 6, 0, 6)
        caja.setSpacing(4)
        self._rejilla = QtWidgets.QGridLayout()
        self._rejilla.setContentsMargins(0, 0, 0, 0)
        self._rejilla.setHorizontalSpacing(8)
        self._rejilla.setVerticalSpacing(4)
        self._rejilla.setColumnStretch(0, 1)
        self.titulo = _TextoQueCabe(control.nombre)
        self.titulo.setToolTip(self._ayuda())
        self._rejilla.addWidget(self.titulo, 0, 0, 1, 3, QtCore.Qt.AlignmentFlag.AlignTop)
        self.valor = QtWidgets.QLabel(self._texto(control.predeterminado))
        self.valor.setObjectName("numero")
        self.valor.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop
        )
        ancho_valor = self.valor.fontMetrics().horizontalAdvance("-000,00") + 6
        self.valor.setMinimumWidth(ancho_valor)
        self.valor.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.reset = QtWidgets.QToolButton()
        self.reset.setObjectName("restablecer")
        self.reset.setText("Restablecer")
        self.reset.setToolTip(f"Restablecer a {self._texto(control.recomendado)}, el valor recomendado.")
        self.reset.setAccessibleName("Restablecer")
        self.reset.setAccessibleDescription(self.reset.toolTip())
        self.reset.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.reset.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.reset.setAutoRaise(False)
        self.reset.setMinimumHeight(36)
        self.reset.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Maximum,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self._rejilla.addWidget(
            self.reset,
            1,
            2,
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter,
        )
        self._apilado = False
        pista = _TextoQueCabe(control.ayuda)
        pista.setObjectName("pista")
        if control.tipo == "eleccion":
            self.editor: QtWidgets.QWidget = QtWidgets.QComboBox()
            editor = self.editor
            assert isinstance(editor, QtWidgets.QComboBox)
            editor.addItems(list(control.opciones))
            editor.setCurrentText(str(control.predeterminado))
            editor.setMinimumHeight(40)
            editor.setMinimumContentsLength(8)
            editor.setSizeAdjustPolicy(
                QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            editor.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            editor.setMinimumWidth(0)
        elif control.tipo == "toggle":
            self.editor = QtWidgets.QCheckBox("Activado")
            self.editor.setToolTip("Enciende o apaga este ajuste.")
            self.editor.setChecked(bool(control.predeterminado))
        else:
            escala = 10**control.decimales
            self._escala = escala
            slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setRange(int(round(control.minimo * escala)), int(round(control.maximo * escala)))
            slider.setValue(int(round(float(control.predeterminado) * escala)))
            slider.setSingleStep(max(1, int(round(control.paso * escala))))
            slider.setMinimumHeight(36)
            slider.setMinimumWidth(0)
            slider.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
            self.editor = slider
        self.editor.setToolTip(self._ayuda())
        self._rejilla.addWidget(self.editor, 1, 0)
        self._rejilla.addWidget(self.valor, 1, 1, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._rejilla.addWidget(pista, 2, 0, 1, 3)
        caja.addLayout(self._rejilla)

    def resizeEvent(self, evento: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evento)
        self._revisar_ancho()

    def showEvent(self, evento: QtGui.QShowEvent) -> None:
        super().showEvent(evento)
        self._revisar_ancho()

    def _revisar_ancho(self) -> None:
        return

    def _ayuda(self) -> str:
        return f"{self.control.ayuda} Recomendado: {self._texto(self.control.recomendado)}."

    def _texto(self, valor: object) -> str:
        if isinstance(valor, bool):
            return "sí" if valor else "no"
        if self.control.decimales:
            return f"{float(valor):.{self.control.decimales}f}".replace(".", ",")
        if isinstance(valor, float) and valor.is_integer():
            return str(int(valor))
        return str(valor)

    def leer(self) -> object:
        if isinstance(self.editor, QtWidgets.QComboBox):
            return self.editor.currentText()
        if isinstance(self.editor, QtWidgets.QCheckBox):
            return self.editor.isChecked()
        crudo = self.editor.value() / self._escala
        if self.control.decimales:
            return round(crudo, self.control.decimales)
        return int(round(crudo))

    def escribir(self, valor: object) -> None:
        if isinstance(self.editor, QtWidgets.QComboBox):
            self.editor.setCurrentText(str(valor))
        elif isinstance(self.editor, QtWidgets.QCheckBox):
            self.editor.setChecked(bool(valor))
        else:
            self.editor.setValue(int(round(float(valor) * self._escala)))
        self.valor.setText(self._texto(valor))


class PanelAjustes(QtWidgets.QWidget):
    cambiado = QtCore.Signal(str, object)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self._filtro_rueda = FiltroRueda(self)
        self._filas: dict[str, _Fila] = {}
        self._cuerpos: dict[str, QtWidgets.QWidget] = {}
        self._maestros: dict[str, QtWidgets.QCheckBox] = {}
        self._bloques: dict[str, QtWidgets.QWidget] = {}
        self._estados: dict[str, QtWidgets.QLabel] = {}
        self._grupos: dict[str, Grupo] = {}
        self._silencio = False
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(2, 4, 8, 12)
        caja.setSpacing(14)
        nota = _TextoQueCabe("Se guarda con la cara elegida. Los cambios se ven en el directo.")
        nota.setObjectName("pista")
        caja.addWidget(nota)
        for grupo in GRUPOS:
            caja.addWidget(self._grupo(grupo))
        caja.addStretch(1)
        self._refrescar()

    def fijar(self, valores: dict[str, object]) -> None:
        self._silencio = True
        try:
            for clave, valor in valores.items():
                if clave in self._maestros:
                    self._maestros[clave].setChecked(bool(valor))
                fila = self._filas.get(clave)
                if fila is not None:
                    fila.escribir(valor)
        finally:
            self._silencio = False
        self._refrescar()

    def _grupo(self, grupo: Grupo) -> QtWidgets.QWidget:
        bloque = QtWidgets.QWidget()
        bloque.setObjectName("grupoAjuste")
        bloque.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        bloque.setMinimumWidth(0)
        caja = QtWidgets.QVBoxLayout(bloque)
        caja.setContentsMargins(0, 16, 0, 8)
        caja.setSpacing(8)
        titulos = {
            "boca": "Boca",
            "ojos": "Ojos",
            "bordes": "Bordes y fusión",
            "nitidez": "Nitidez",
            "color": "Color y luz",
            "oclusion": "Oclusión",
            "estabilidad": "Estabilidad",
        }
        cabecera = QtWidgets.QHBoxLayout()
        plegar = QtWidgets.QToolButton()
        plegar.setObjectName("plegar")
        plegar.setText(titulos.get(grupo.ident, grupo.nombre))
        plegar.setCheckable(True)
        plegar.setChecked(True)
        plegar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        plegar.setArrowType(QtCore.Qt.ArrowType.DownArrow)
        plegar.setMinimumHeight(44)
        plegar.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        cabecera.addWidget(plegar, 1)
        texto_interruptor = "Mejorar cara" if grupo.ident == "nitidez" else "Encendido"
        interruptor = QtWidgets.QCheckBox(texto_interruptor)
        interruptor.setObjectName("interruptorGrupo")
        interruptor.setChecked(grupo.maestro == "BordermaskEnableToggle")
        interruptor.setToolTip(grupo.frase)
        interruptor.setAccessibleName(texto_interruptor)
        interruptor.setAccessibleDescription(grupo.frase)
        interruptor.setMinimumWidth(0)
        interruptor.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        interruptor.toggled.connect(lambda activo, clave=grupo.maestro: self._emitir(clave, activo))
        self._maestros[grupo.maestro] = interruptor
        self._bloques[grupo.ident] = bloque
        self._grupos[grupo.ident] = grupo
        cabecera.addWidget(interruptor)
        caja.addLayout(cabecera)
        plegar.toggled.connect(
            lambda abierto, boton=plegar: boton.setArrowType(
                QtCore.Qt.ArrowType.DownArrow if abierto else QtCore.Qt.ArrowType.RightArrow
            )
        )
        estado = _TextoQueCabe()
        estado.setObjectName("pista")
        self._estados[grupo.ident] = estado
        caja.addWidget(estado)
        cuerpo = QtWidgets.QWidget()
        cuerpo.setMinimumWidth(0)
        interior = QtWidgets.QVBoxLayout(cuerpo)
        interior.setContentsMargins(12, 4, 0, 0)
        interior.setSpacing(2)
        for control in grupo.controles:
            fila = _Fila(control)
            preparar_rueda(fila.editor, self._filtro_rueda)
            self._filas[control.clave] = fila
            self._conectar(fila)
            interior.addWidget(fila)
        self._cuerpos[grupo.ident] = cuerpo
        interruptor.toggled.connect(lambda _activo, ident=grupo.ident: self._refrescar())
        plegar.toggled.connect(cuerpo.setVisible)
        caja.addWidget(cuerpo)
        return bloque

    def _conectar(self, fila: _Fila) -> None:
        editor = fila.editor
        if isinstance(editor, QtWidgets.QComboBox):
            editor.currentTextChanged.connect(lambda _texto, clave=fila.control.clave: self._desde_fila(clave))
        elif isinstance(editor, QtWidgets.QCheckBox):
            editor.toggled.connect(lambda _activo, clave=fila.control.clave: self._desde_fila(clave))
        else:
            editor.valueChanged.connect(lambda _valor, clave=fila.control.clave: self._desde_fila(clave))
        fila.reset.clicked.connect(lambda _=False, clave=fila.control.clave: self._restablecer(clave))

    def _desde_fila(self, clave: str) -> None:
        if self._silencio:
            return
        fila = self._filas[clave]
        valor = fila.leer()
        fila.valor.setText(fila._texto(valor))
        self._emitir(clave, valor)
        self._refrescar()

    def _restablecer(self, clave: str) -> None:
        control = por_clave()[clave]
        self._silencio = True
        try:
            self._filas[clave].escribir(control.recomendado)
        finally:
            self._silencio = False
        self._emitir(clave, control.recomendado)
        self._refrescar()

    def _emitir(self, clave: str, valor: object) -> None:
        if self._silencio:
            return
        self.cambiado.emit(clave, valor)

    def _refrescar(self) -> None:
        activos = {clave: caja.isChecked() for clave, caja in self._maestros.items()}
        for clave, fila in self._filas.items():
            if isinstance(fila.editor, QtWidgets.QCheckBox):
                activos[clave] = fila.editor.isChecked()
        for grupo in GRUPOS:
            activo = self._maestros[grupo.maestro].isChecked()
            cuerpo = self._cuerpos[grupo.ident]
            cuerpo.setVisible(activo or grupo.ident in ("nitidez", "estabilidad", "boca"))
            _marcar(self._bloques[grupo.ident], activo)
            _marcar(self._maestros[grupo.maestro], activo)
            estado = "Encendido" if activo else "Apagado"
            self._estados[grupo.ident].setText(
                f"{estado} · {grupo.coste.capitalize()}. {grupo.frase}"
            )
        for clave, fila in self._filas.items():
            depende = fila.control.muestra_si
            if depende is None:
                fila.show()
            else:
                fila.setVisible(bool(activos.get(depende, False)))
