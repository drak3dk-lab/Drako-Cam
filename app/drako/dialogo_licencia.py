"""Aviso de privacidad y código de acceso. Textos en español.

Sigue el ritmo de los cuadros de contraseña de Drako Cam: una columna,
botón secundario a la izquierda y acción principal a la derecha.
El aviso lista qué se registra, como un consentimiento de permisos,
y la casilla empieza desmarcada. El código es un solo campo, con el
error debajo, no una fila de casillas de un solo dígito.
"""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtWidgets

from app.drako.licencia import DecisionAcceso, GestorLicencia, crear_gestor
from app.drako.textos_licencia import (
    CASILLA_AVISO,
    CIERRE_AVISO,
    INTRO_AVISO,
    PLACEHOLDER_CODIGO,
    PUNTOS_AVISO,
    TEXTO_CODIGO,
    TITULO_AVISO,
    TITULO_CODIGO,
)

logger = logging.getLogger("drako.licencia")

_HOJA = """
QLabel#sobre { color: #4090a3; font-size: 13px; font-weight: 600; }
QLabel#titulo { font-size: 22px; font-weight: 700; color: #f0f0f0; }
QLabel#cuerpo { color: #f0f0f0; font-size: 15px; }
QLabel#punto { color: #f0f0f0; font-size: 15px; font-weight: 600; }
QLabel#detalle { color: #c6c6c6; font-size: 14px; }
QLabel#error { color: #ffb4b4; font-size: 14px; }
QLineEdit#codigo {
    font-size: 16px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    min-height: 44px;
    padding: 8px 10px;
}
QPushButton#primario {
    background-color: #4090a3;
    color: #101010;
    border: 1px solid #156a7d;
    font-weight: 700;
    min-height: 44px;
    padding: 6px 16px;
}
QPushButton#primario:disabled {
    background-color: #2b2b2b;
    color: #6a6a6a;
    border: 1px solid #363636;
}
QPushButton#secundario { min-height: 44px; padding: 6px 16px; }
QCheckBox::indicator { width: 22px; height: 22px; }
QLabel#casilla { color: #f0f0f0; font-size: 16px; }
"""


def _dialogo(titulo: str, padre=None) -> QtWidgets.QDialog:
    dialogo = QtWidgets.QDialog(padre)
    dialogo.setWindowTitle(titulo)
    dialogo.setModal(True)
    dialogo.setMinimumWidth(520)
    dialogo.setAttribute(QtCore.Qt.WidgetAttribute.WA_QuitOnClose, False)
    dialogo.setStyleSheet(_HOJA)
    layout = QtWidgets.QVBoxLayout(dialogo)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(14)
    return dialogo


def _etiqueta(texto: str, nombre: str, padre) -> QtWidgets.QLabel:
    etiqueta = QtWidgets.QLabel(texto, padre)
    etiqueta.setObjectName(nombre)
    etiqueta.setWordWrap(True)
    return etiqueta


def _botones(dialogo, aceptar_texto: str, aceptar_nombre: str = "primario"):
    fila = QtWidgets.QHBoxLayout()
    fila.setSpacing(10)
    salir = QtWidgets.QPushButton("Salir", dialogo)
    salir.setObjectName("secundario")
    salir.setMinimumHeight(44)
    aceptar = QtWidgets.QPushButton(aceptar_texto, dialogo)
    aceptar.setObjectName(aceptar_nombre)
    aceptar.setMinimumHeight(44)
    aceptar.setAutoDefault(False)
    aceptar.setDefault(False)
    salir.clicked.connect(dialogo.reject)
    fila.addWidget(salir)
    fila.addWidget(aceptar)
    return fila, salir, aceptar


def _aviso(padre, texto: str, critico: bool = False) -> None:
    if critico:
        QtWidgets.QMessageBox.critical(padre, "Drako Cam — acceso", texto)
    else:
        QtWidgets.QMessageBox.warning(padre, "Drako Cam", texto)


class _Tarea(QtCore.QThread):
    listo = QtCore.Signal(object)

    def __init__(self, funcion):
        super().__init__()
        self._funcion = funcion

    def run(self) -> None:
        try:
            valor = self._funcion()
        except Exception:
            logger.exception("Falló una comprobación de acceso.")
            valor = DecisionAcceso(
                False,
                "sin_red",
                "No se pudo comprobar el acceso. Inténtalo otra vez.",
            )
        self.listo.emit(valor)


def _ejecutar(funcion, padre=None, texto: str | None = None):
    tarea = _Tarea(funcion)
    bucle = QtCore.QEventLoop()
    caja = {}

    def guardar(valor) -> None:
        caja["valor"] = valor
        tarea._valor = valor
        bucle.quit()

    tarea.listo.connect(guardar)
    espera = {"dialogo": None}

    def mostrar() -> None:
        if not bucle.isRunning():
            return
        dialogo = _dialogo("Drako Cam", padre)
        dialogo.setMinimumWidth(420)
        dialogo.layout().addWidget(_etiqueta(texto or "Comprobando el acceso…", "cuerpo", dialogo))
        barra = QtWidgets.QProgressBar(dialogo)
        barra.setRange(0, 0)
        barra.setFixedHeight(8)
        barra.setTextVisible(False)
        dialogo.layout().addWidget(barra)
        dialogo.show()
        espera["dialogo"] = dialogo

    aviso = QtCore.QTimer()
    aviso.setSingleShot(True)
    if texto:
        aviso.timeout.connect(mostrar)
        aviso.start(300)
    tarea.start()
    bucle.exec()
    aviso.stop()
    dialogo = espera["dialogo"]
    if dialogo is not None:
        dialogo.close()
    tarea.wait(2000)
    if "valor" not in caja:
        raise RuntimeError("La comprobación de acceso no terminó.")
    return caja["valor"]


def _pedir_privacidad(padre) -> bool:
    dialogo = _dialogo("Drako Cam — aviso de privacidad", padre)
    dialogo.layout().addWidget(_etiqueta("Privacidad", "sobre", dialogo))
    dialogo.layout().addWidget(_etiqueta(TITULO_AVISO, "titulo", dialogo))
    contenido = QtWidgets.QWidget(dialogo)
    columna = QtWidgets.QVBoxLayout(contenido)
    columna.setContentsMargins(0, 0, 0, 0)
    columna.setSpacing(12)
    columna.addWidget(_etiqueta(INTRO_AVISO, "cuerpo", contenido))
    for titulo, detalle in PUNTOS_AVISO:
        fila = QtWidgets.QHBoxLayout()
        fila.setSpacing(12)
        marca = QtWidgets.QFrame(contenido)
        marca.setFixedWidth(3)
        marca.setMinimumHeight(36)
        marca.setStyleSheet("background-color: #4090a3;")
        textos = QtWidgets.QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(_etiqueta(titulo, "punto", contenido))
        textos.addWidget(_etiqueta(detalle, "detalle", contenido))
        fila.addWidget(marca)
        fila.addLayout(textos, 1)
        columna.addLayout(fila)
    columna.addWidget(_etiqueta(CIERRE_AVISO, "cuerpo", contenido))
    zona = QtWidgets.QScrollArea(dialogo)
    zona.setWidgetResizable(True)
    zona.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    zona.setMinimumHeight(240)
    zona.setWidget(contenido)
    dialogo.layout().addWidget(zona)
    fila_casilla = QtWidgets.QHBoxLayout()
    fila_casilla.setSpacing(8)
    casilla = QtWidgets.QCheckBox(dialogo)
    casilla.setFixedSize(44, 44)
    texto_casilla = _etiqueta(CASILLA_AVISO, "casilla", dialogo)
    texto_casilla.setMinimumHeight(44)

    def alternar(evento, casilla=casilla, etiqueta=texto_casilla) -> None:
        if evento.button() == QtCore.Qt.MouseButton.LeftButton:
            casilla.toggle()
        QtWidgets.QLabel.mousePressEvent(etiqueta, evento)

    texto_casilla.mousePressEvent = alternar
    fila_casilla.addWidget(casilla, 0, QtCore.Qt.AlignmentFlag.AlignTop)
    fila_casilla.addWidget(texto_casilla, 1)
    dialogo.layout().addLayout(fila_casilla)
    fila, _salir, aceptar = _botones(dialogo, "Aceptar y continuar")
    aceptar.setEnabled(False)
    casilla.toggled.connect(aceptar.setEnabled)
    aceptar.clicked.connect(dialogo.accept)
    dialogo.layout().addLayout(fila)
    return dialogo.exec() == QtWidgets.QDialog.DialogCode.Accepted and casilla.isChecked()


def _pedir_codigo(gestor: GestorLicencia, padre, cambio: bool = False) -> bool:
    while True:
        dialogo = _dialogo("Drako Cam — código de acceso", padre)
        dialogo.layout().addWidget(_etiqueta("Acceso", "sobre", dialogo))
        titulo = "Cambiar el código" if cambio else TITULO_CODIGO
        dialogo.layout().addWidget(_etiqueta(titulo, "titulo", dialogo))
        dialogo.layout().addWidget(_etiqueta(TEXTO_CODIGO, "cuerpo", dialogo))
        campo = QtWidgets.QLineEdit(dialogo)
        campo.setObjectName("codigo")
        campo.setPlaceholderText(PLACEHOLDER_CODIGO)
        campo.setMinimumHeight(44)
        campo.setMaxLength(40)
        campo.setAccessibleName("Código de acceso")
        campo.setClearButtonEnabled(True)
        dialogo.layout().addWidget(campo)
        error = _etiqueta("", "error", dialogo)
        error.hide()
        dialogo.layout().addWidget(error)
        fila, _salir, aceptar = _botones(dialogo, "Continuar")

        def continuar(aceptar=aceptar, campo=campo, error=error, dialogo=dialogo) -> None:
            aceptar.setEnabled(False)
            error.setText("Comprobando el código…")
            error.show()
            try:
                decision = _ejecutar(
                    lambda: gestor.probar_codigo(campo.text()),
                    dialogo,
                    "Comprobando el código…",
                )
            except Exception:
                logger.exception("No se pudo comprobar el código.")
                error.setText("No se pudo comprobar el código. Inténtalo otra vez.")
                aceptar.setEnabled(True)
                return
            if decision.permitir:
                dialogo.accept()
                return
            error.setText(decision.mensaje)
            error.show()
            aceptar.setEnabled(True)

        aceptar.clicked.connect(continuar)
        campo.returnPressed.connect(continuar)
        campo.setFocus()
        if dialogo.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return False
        return True


class VigilanteLicencia(QtCore.QObject):
    def __init__(self, gestor: GestorLicencia):
        super().__init__()
        self.gestor = gestor
        self._activo = True
        self._tarea: _Tarea | None = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(60_000)
        self._timer.timeout.connect(self._disparar)
        aplicacion = QtWidgets.QApplication.instance()
        if aplicacion is not None:
            self.setParent(aplicacion)

    def iniciar(self) -> None:
        segundos = 60
        self._timer.start(max(15, segundos) * 1000)

    def detener(self) -> None:
        self._activo = False
        self._timer.stop()
        self.gestor.cerrar_sesion()

    def pedir_cambio(self) -> None:
        _pedir_codigo(self.gestor, None, cambio=True)

    def _disparar(self) -> None:
        if not self._activo:
            return
        if self._tarea is not None and self._tarea.isRunning():
            return
        self._tarea = _Tarea(self.gestor.comprobar_latido)
        self._tarea.listo.connect(self._aplicar)
        self._tarea.start()

    def _aplicar(self, decision: DecisionAcceso) -> None:
        if not self._activo or decision is None or decision.permitir:
            return
        self._activo = False
        self._timer.stop()
        _aviso(None, decision.mensaje, critico=True)
        aplicacion = QtWidgets.QApplication.instance()
        if aplicacion is not None:
            aplicacion.quit()


def solicitar_licencia(contexto, claves, padre=None) -> VigilanteLicencia | None:
    gestor = crear_gestor(contexto, claves)
    if gestor.paso() == "privacidad":
        if not _pedir_privacidad(padre):
            return None
        gestor.aceptar_aviso()
    if not gestor.cliente.configurado():
        _aviso(padre, _textos_config())
        return None
    if not gestor.leer_codigo():
        if not _pedir_codigo(gestor, padre):
            return None
    else:
        try:
            decision = _ejecutar(gestor.comprobar_arranque, padre, "Comprobando el acceso…")
        except Exception:
            logger.exception("Falló la comprobación de acceso al arrancar.")
            _aviso(padre, "No se pudo comprobar el acceso. El programa se cierra.", critico=True)
            return None
        if not decision.permitir:
            _aviso(padre, decision.mensaje, critico=True)
            return None
        if decision.motivo == "gracia" and decision.mensaje:
            QtWidgets.QMessageBox.information(padre, "Drako Cam — sin conexión", decision.mensaje)
    vigilante = VigilanteLicencia(gestor)
    vigilante.iniciar()
    return vigilante


def _textos_config() -> str:
    from app.drako.textos_licencia import MENSAJE_SIN_CONFIGURAR

    return MENSAJE_SIN_CONFIGURAR
