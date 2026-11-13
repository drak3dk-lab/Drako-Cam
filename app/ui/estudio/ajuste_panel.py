"""Panel «Ajustar cara»: un grupo, un interruptor, los sliders debajo."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app.ui.estudio.controles import GRUPOS, Control, Grupo, por_clave


class _Fila(QtWidgets.QWidget):
    def __init__(self, control: Control, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.control = control
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(0, 4, 0, 4)
        caja.setSpacing(2)
        cabeza = QtWidgets.QHBoxLayout()
        self.titulo = QtWidgets.QLabel(control.nombre)
        self.titulo.setToolTip(self._ayuda())
        cabeza.addWidget(self.titulo, 1)
        self.valor = QtWidgets.QLabel(self._texto(control.predeterminado))
        self.valor.setObjectName("numero")
        cabeza.addWidget(self.valor)
        self.reset = QtWidgets.QToolButton()
        self.reset.setText("Restablecer")
        self.reset.setToolTip(f"Vuelve a {self._texto(control.recomendado)}, el valor recomendado.")
        self.reset.setMinimumHeight(32)
        cabeza.addWidget(self.reset)
        caja.addLayout(cabeza)
        pista = QtWidgets.QLabel(control.ayuda)
        pista.setWordWrap(True)
        pista.setObjectName("pista")
        caja.addWidget(pista)
        if control.tipo == "eleccion":
            self.editor: QtWidgets.QWidget = QtWidgets.QComboBox()
            self.editor.addItems(list(control.opciones))
            self.editor.setCurrentText(str(control.predeterminado))
            self.editor.setMinimumHeight(40)
        elif control.tipo == "toggle":
            self.editor = QtWidgets.QCheckBox("Activado")
            self.editor.setChecked(bool(control.predeterminado))
        else:
            escala = 10**control.decimales
            self._escala = escala
            slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setRange(int(round(control.minimo * escala)), int(round(control.maximo * escala)))
            slider.setValue(int(round(float(control.predeterminado) * escala)))
            slider.setSingleStep(max(1, int(round(control.paso * escala))))
            slider.setMinimumHeight(36)
            self.editor = slider
        self.editor.setToolTip(self._ayuda())
        caja.addWidget(self.editor)

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
        self._filas: dict[str, _Fila] = {}
        self._cuerpos: dict[str, QtWidgets.QWidget] = {}
        self._maestros: dict[str, QtWidgets.QCheckBox] = {}
        self._silencio = False
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(8)
        titulo = QtWidgets.QLabel("Ajustar cara")
        titulo.setObjectName("tituloPanel")
        caja.addWidget(titulo)
        nota = QtWidgets.QLabel("Se guarda con la cara elegida. Los cambios se ven en el directo.")
        nota.setWordWrap(True)
        nota.setObjectName("pista")
        caja.addWidget(nota)
        for grupo in GRUPOS:
            caja.addWidget(self._grupo(grupo))
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
        caja = QtWidgets.QVBoxLayout(bloque)
        caja.setContentsMargins(0, 8, 0, 0)
        caja.setSpacing(4)
        cabeza = QtWidgets.QHBoxLayout()
        texto_interruptor = "Mejorar cara" if grupo.ident == "nitidez" else grupo.nombre
        interruptor = QtWidgets.QCheckBox(texto_interruptor)
        interruptor.setChecked(grupo.maestro == "BordermaskEnableToggle")
        interruptor.setToolTip(grupo.frase)
        interruptor.toggled.connect(lambda activo, clave=grupo.maestro: self._emitir(clave, activo))
        self._maestros[grupo.maestro] = interruptor
        cabeza.addWidget(interruptor, 1)
        coste = QtWidgets.QLabel(grupo.coste)
        coste.setObjectName("pista")
        coste.setToolTip("No está medido en FPS en esta máquina. Pesado suele bajar los fotogramas.")
        cabeza.addWidget(coste)
        caja.addLayout(cabeza)
        frase = QtWidgets.QLabel(grupo.frase)
        frase.setWordWrap(True)
        frase.setObjectName("pista")
        caja.addWidget(frase)
        cuerpo = QtWidgets.QWidget()
        interior = QtWidgets.QVBoxLayout(cuerpo)
        interior.setContentsMargins(8, 0, 0, 0)
        interior.setSpacing(0)
        for control in grupo.controles:
            fila = _Fila(control)
            self._filas[control.clave] = fila
            self._conectar(fila)
            interior.addWidget(fila)
        self._cuerpos[grupo.ident] = cuerpo
        interruptor.toggled.connect(lambda _activo, ident=grupo.ident: self._refrescar())
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
            cuerpo = self._cuerpos[grupo.ident]
            cuerpo.setVisible(
                self._maestros[grupo.maestro].isChecked()
                or grupo.ident in ("nitidez", "estabilidad")
            )
        for clave, fila in self._filas.items():
            depende = fila.control.muestra_si
            if depende is None:
                fila.show()
            else:
                fila.setVisible(bool(activos.get(depende, False)))
