"""Ajustes > Modelos. Lista instalados y disponibles, y descarga el resto.

La ventana de progreso no es modal: la cámara sigue pintándose.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app.drako.catalogo_modelos import (
    MENSAJE_SIN_CONEXION,
    archivo_presente,
    fichas,
    suma_bytes,
    texto_progreso,
    texto_tamano,
)
from app.drako.descarga_modelos import gestor


class DialogoDescarga(QtWidgets.QDialog):
    """Progreso en español. Cancelar deja el parcial y no cierra el programa."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.setWindowTitle("Drako Cam — modelos")
        self.setMinimumWidth(480)
        self.setMinimumHeight(200)
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(20, 20, 20, 20)
        caja.setSpacing(12)
        self.texto = QtWidgets.QLabel("Preparando la descarga…", self)
        self.texto.setWordWrap(True)
        self.barra = QtWidgets.QProgressBar(self)
        self.barra.setTextVisible(False)
        self.barra.setMinimumHeight(8)
        self.boton = QtWidgets.QPushButton("Cancelar", self)
        self.boton.setMinimumHeight(44)
        self.boton.clicked.connect(self._al_pulsar)
        caja.addWidget(self.texto)
        caja.addWidget(self.barra)
        caja.addWidget(self.boton)
        self._cerrando = False
        self._terminado = False

    def preparar(self) -> None:
        self._terminado = False
        self.boton.setText("Cancelar")
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.texto.setText("Preparando la descarga…")

    def mostrar_progreso(self, datos) -> None:
        if self._terminado:
            return
        nombre, hechos, totales, eta, listos, archivos = datos
        self.texto.setText(
            texto_progreso(nombre, hechos, totales, eta, listos, archivos)
        )
        if totales > 0:
            self.barra.setValue(min(100, int(hechos * 100 / totales)))

    def mostrar_fin(self, resultado) -> None:
        self._terminado = True
        self.boton.setText("Cerrar")
        if resultado.cancelado:
            self.texto.setText(
                "Descarga cancelada. La salida en vivo sigue. "
                "Puedes retomarla en Ajustes > Modelos."
            )
            return
        if resultado.sin_conexion:
            self.texto.setText(MENSAJE_SIN_CONEXION)
            self.barra.setValue(0)
            return
        if resultado.correcto:
            self.barra.setValue(100)
            self.texto.setText(
                "Descarga terminada y comprobada. Ya puedes usar esos modelos."
            )
            return
        self.texto.setText(
            "Algún archivo no se pudo comprobar. La cámara sigue. "
            "Reintenta desde Ajustes > Modelos cuando haya red."
        )

    def _al_pulsar(self) -> None:
        if self._terminado:
            self.close()
            return
        gestor().cancelar()
        self.texto.setText("Cancelando… la salida en vivo sigue.")

    def closeEvent(self, event) -> None:
        if not self._terminado and not self._cerrando:
            self._cerrando = True
            gestor().cancelar()
        event.accept()


class PanelModelos(QtWidgets.QGroupBox):
    """Lista del catálogo. El botón baja todo lo que aún no está en disco."""

    def __init__(self, parent=None):
        super().__init__("Modelos", parent)
        caja = QtWidgets.QVBoxLayout(self)
        caja.setContentsMargins(12, 16, 12, 12)
        caja.setSpacing(10)
        intro = QtWidgets.QLabel(
            "Estos son los modelos del cambio de cara en vivo. "
            "Si ya están y no han cambiado, el arranque no los vuelve a comprobar.",
            self,
        )
        intro.setWordWrap(True)
        caja.addWidget(intro)
        self.resumen = QtWidgets.QLabel(self)
        self.resumen.setWordWrap(True)
        caja.addWidget(self.resumen)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setMinimumHeight(220)
        contenido = QtWidgets.QWidget()
        self._lista = QtWidgets.QVBoxLayout(contenido)
        self._lista.setContentsMargins(0, 0, 0, 0)
        self._lista.setSpacing(4)
        scroll.setWidget(contenido)
        caja.addWidget(scroll)

        self.boton = QtWidgets.QPushButton("Descargar todos", self)
        self.boton.setMinimumHeight(44)
        self.boton.clicked.connect(self._descargar_todos)
        caja.addWidget(self.boton)
        self._filas: list[tuple[str, QtWidgets.QLabel]] = []
        self.refrescar()

    def refrescar(self) -> None:
        while self._lista.count():
            item = self._lista.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._filas.clear()
        grupos: dict[str, list] = {}
        for ficha in fichas():
            grupos.setdefault(ficha.grupo, []).append(ficha)
        for grupo, items in grupos.items():
            titulo = QtWidgets.QLabel(
                f"{grupo} · {texto_tamano(suma_bytes(items))}", self
            )
            fuente = titulo.font()
            fuente.setBold(True)
            titulo.setFont(fuente)
            self._lista.addWidget(titulo)
            for ficha in items:
                self._lista.addWidget(self._fila(ficha))
        self._lista.addStretch(1)
        self._actualizar_resumen()

    def _fila(self, ficha) -> QtWidgets.QWidget:
        fila = QtWidgets.QWidget(self)
        linea = QtWidgets.QHBoxLayout(fila)
        linea.setContentsMargins(0, 2, 0, 2)
        linea.setSpacing(8)
        nombre = QtWidgets.QLabel(ficha.nombre, fila)
        nombre.setToolTip(ficha.porque)
        nombre.setMinimumHeight(28)
        tamano = QtWidgets.QLabel(texto_tamano(ficha.bytes), fila)
        tamano.setMinimumWidth(72)
        tamano.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        estado = QtWidgets.QLabel(fila)
        estado.setMinimumWidth(120)
        estado.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self._pintar_estado(estado, archivo_presente(ficha.nombre), ficha.esencial)
        linea.addWidget(nombre, 1)
        linea.addWidget(tamano)
        linea.addWidget(estado)
        self._filas.append((ficha.nombre, estado))
        return fila

    @staticmethod
    def _pintar_estado(
        etiqueta: QtWidgets.QLabel, instalado: bool, esencial: bool
    ) -> None:
        if instalado:
            etiqueta.setText("Instalado")
            etiqueta.setStyleSheet("color: #8fd0c6;")
            return
        etiqueta.setText("No descargado")
        etiqueta.setStyleSheet("color: #f0f0f0;" if esencial else "color: #bdbdbd;")

    def _actualizar_resumen(self) -> None:
        todas = fichas()
        esenciales = [item for item in todas if item.esencial]
        opcionales = [item for item in todas if not item.esencial]
        instalados = sum(1 for item in todas if archivo_presente(item.nombre))
        self.resumen.setText(
            f"Esenciales {texto_tamano(suma_bytes(esenciales))} · "
            f"opcionales {texto_tamano(suma_bytes(opcionales))} · "
            f"instalados {instalados} de {len(todas)}."
        )
        faltan = instalados < len(todas)
        self.boton.setEnabled(True)
        self.boton.setText("Descargar todos" if faltan else "Ya están todos")

    def _descargar_todos(self) -> None:
        faltan = [item.nombre for item in fichas() if not archivo_presente(item.nombre)]
        if not faltan:
            self.resumen.setText(
                self.resumen.text() + " No hay nada pendiente de descargar."
            )
            return
        dialogo = _dialogo(self.window())
        dialogo.preparar()
        dialogo.show()
        gestor().reintentar(faltan)


class _Puente(QtCore.QObject):
    progreso = QtCore.Signal(object)
    terminado = QtCore.Signal(object)
    pedido = QtCore.Signal(str)


_puente: _Puente | None = None
_dialogo_abierto: DialogoDescarga | None = None
_panel: PanelModelos | None = None


def _dialogo(padre) -> DialogoDescarga:
    global _dialogo_abierto
    if _dialogo_abierto is None:
        _dialogo_abierto = DialogoDescarga(padre)
    return _dialogo_abierto


def instalar_panel_modelos(ventana) -> PanelModelos:
    """Inserta el panel al inicio de Ajustes y escucha las peticiones de descarga."""
    global _puente, _panel
    ventana.tabWidget.setTabText(
        ventana.tabWidget.indexOf(ventana.settings_tab), "Ajustes"
    )
    panel = PanelModelos(ventana)
    ventana.settingsWidgetsLayout.insertWidget(0, panel)
    ventana.panel_modelos = panel
    _panel = panel

    if _puente is None:
        _puente = _Puente()
        descarga = gestor()
        descarga.al_progresar(_puente.progreso.emit)
        descarga.al_terminar(_puente.terminado.emit)
        descarga.al_pedir(_puente.pedido.emit)
        _puente.progreso.connect(_al_progreso)
        _puente.terminado.connect(_al_fin)
        _puente.pedido.connect(_al_pedido)
    return panel


def _al_pedido(_nombre: str) -> None:
    padre = _panel.window() if _panel is not None else None
    dialogo = _dialogo(padre)
    if not dialogo.isVisible():
        dialogo.preparar()
        dialogo.show()


def _al_progreso(datos) -> None:
    if _dialogo_abierto is not None:
        _dialogo_abierto.mostrar_progreso(datos)


def _al_fin(resultado) -> None:
    if _dialogo_abierto is not None:
        visible = _dialogo_abierto.isVisible()
        _dialogo_abierto.mostrar_fin(resultado)
        if visible or resultado.sin_conexion or resultado.correcto:
            _dialogo_abierto.show()
    if _panel is not None:
        _panel.refrescar()
