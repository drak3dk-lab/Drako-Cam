"""Cuadros de acceso, cambio de contraseña y Telegram. Textos en español."""

from __future__ import annotations

import os

from PySide6 import QtWidgets

from app.drako.arranque import ContextoArranque, cambiar_contrasena
from app.drako.auditoria import ClavesAuditoria
from app.drako.telegram_cliente import credenciales_telegram


def _campo_clave(padre: QtWidgets.QWidget) -> QtWidgets.QLineEdit:
    campo = QtWidgets.QLineEdit(padre)
    campo.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
    campo.setMinimumHeight(44)
    campo.setStyleSheet("font-size: 16px; padding: 6px 8px;")
    return campo


def _boton(texto: str, padre: QtWidgets.QWidget) -> QtWidgets.QPushButton:
    boton = QtWidgets.QPushButton(texto, padre)
    boton.setMinimumHeight(44)
    return boton


class _DialogoBase(QtWidgets.QDialog):
    def __init__(self, titulo: str, padre=None):
        super().__init__(padre)
        self.setWindowTitle(titulo)
        self.setModal(True)
        self.setMinimumWidth(420)
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(12)

    def agregar(self, widget: QtWidgets.QWidget) -> None:
        self._layout.addWidget(widget)


def _aviso(padre, texto: str) -> None:
    QtWidgets.QMessageBox.warning(padre, "Drako Cam", texto)


def solicitar_acceso(contexto: ContextoArranque, padre=None):
    """Pide la contraseña. Devuelve (contraseña, pendientes) o None si se cancela.

    La contraseña solo vive en memoria el tiempo de abrir las claves del registro.
    """
    almacen = contexto.almacen
    if not almacen.esta_configurada():
        return _crear_primera(almacen, padre)
    return _entrar(contexto, padre)


def _crear_primera(almacen, padre):
    while True:
        dialogo = _DialogoBase("Drako Cam — primera contraseña", padre)
        texto = QtWidgets.QLabel(
            "Es la primera vez que se abre Drako Cam en este equipo. "
            "Elige una contraseña de administrador. Solo se guardará su huella "
            "(Argon2id), nunca la contraseña en claro.",
            dialogo,
        )
        texto.setWordWrap(True)
        clave = _campo_clave(dialogo)
        confirmacion = _campo_clave(dialogo)
        clave.setPlaceholderText("Contraseña (8 caracteres como mínimo)")
        confirmacion.setPlaceholderText("Repite la contraseña")
        fila = QtWidgets.QHBoxLayout()
        aceptar = _boton("Guardar y entrar", dialogo)
        cancelar = _boton("Salir", dialogo)
        aceptar.clicked.connect(dialogo.accept)
        cancelar.clicked.connect(dialogo.reject)
        fila.addWidget(cancelar)
        fila.addWidget(aceptar)
        dialogo.agregar(texto)
        dialogo.agregar(clave)
        dialogo.agregar(confirmacion)
        dialogo._layout.addLayout(fila)
        if dialogo.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        resultado = almacen.fijar_inicial(clave.text(), confirmacion.text())
        if resultado.ok:
            return clave.text(), []
        _aviso(dialogo, resultado.mensaje)


def _entrar(contexto: ContextoArranque, padre):
    almacen = contexto.almacen
    while True:
        if almacen.esta_bloqueado():
            resultado = almacen.verificar("")
            _aviso(padre, resultado.mensaje)
            _avisar_acceso(contexto, "bloqueo", resultado.mensaje)
            return None
        dialogo = _DialogoBase("Drako Cam — acceso de administrador", padre)
        texto = QtWidgets.QLabel(
            "Introduce la contraseña de administrador para abrir el programa.",
            dialogo,
        )
        texto.setWordWrap(True)
        clave = _campo_clave(dialogo)
        clave.setPlaceholderText("Contraseña")
        fila = QtWidgets.QHBoxLayout()
        aceptar = _boton("Entrar", dialogo)
        cancelar = _boton("Salir", dialogo)
        aceptar.clicked.connect(dialogo.accept)
        cancelar.clicked.connect(dialogo.reject)
        fila.addWidget(cancelar)
        fila.addWidget(aceptar)
        dialogo.agregar(texto)
        dialogo.agregar(clave)
        dialogo._layout.addLayout(fila)
        clave.setFocus()
        if dialogo.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        resultado = almacen.verificar(clave.text())
        if resultado.ok:
            return clave.text(), resultado.pendientes
        _aviso(dialogo, resultado.mensaje)
        _avisar_acceso(contexto, resultado.motivo, resultado.mensaje)
        if resultado.motivo == "bloqueada":
            return None


def _avisar_acceso(contexto: ContextoArranque, motivo: str, detalle: str) -> None:
    from app.drako.sesion import texto_aviso

    tipo = "bloqueo" if motivo == "bloqueada" or motivo == "bloqueo" else "intento_fallido"
    contexto.telegram.avisar(
        texto_aviso(
            {
                "tipo": tipo,
                "equipo": _nombre_equipo(contexto),
                "detalle": detalle,
            }
        )
    )


def _nombre_equipo(contexto: ContextoArranque) -> str:
    equipo = contexto.almacen._equipo
    return equipo() if callable(equipo) else str(equipo)


def instalar_menu(
    ventana,
    contexto: ContextoArranque,
    claves: ClavesAuditoria,
    al_cambiar_codigo=None,
) -> None:
    barra = ventana.menuBar()
    menu = barra.addMenu("Drako")
    cambiar = menu.addAction("Cambiar contraseña…")
    telegram = menu.addAction("Avisos de Telegram…")
    cambiar.triggered.connect(
        lambda: _dialogo_cambiar(ventana, contexto, claves)
    )
    telegram.triggered.connect(lambda: _dialogo_telegram(ventana, contexto))
    if al_cambiar_codigo is not None:
        codigo = menu.addAction("Cambiar código de acceso…")
        codigo.triggered.connect(al_cambiar_codigo)


def _dialogo_cambiar(ventana, contexto: ContextoArranque, claves: ClavesAuditoria) -> None:
    dialogo = _DialogoBase("Drako Cam — cambiar contraseña", ventana)
    actual = _campo_clave(dialogo)
    nueva = _campo_clave(dialogo)
    confirmacion = _campo_clave(dialogo)
    actual.setPlaceholderText("Contraseña actual")
    nueva.setPlaceholderText("Contraseña nueva")
    confirmacion.setPlaceholderText("Repite la contraseña nueva")
    aceptar = _boton("Cambiar", dialogo)
    cancelar = _boton("Cancelar", dialogo)
    aceptar.clicked.connect(dialogo.accept)
    cancelar.clicked.connect(dialogo.reject)
    fila = QtWidgets.QHBoxLayout()
    fila.addWidget(cancelar)
    fila.addWidget(aceptar)
    for widget in (actual, nueva, confirmacion):
        dialogo.agregar(widget)
    dialogo._layout.addLayout(fila)
    if dialogo.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return
    resultado = cambiar_contrasena(
        contexto, claves, actual.text(), nueva.text(), confirmacion.text()
    )
    if resultado.ok:
        QtWidgets.QMessageBox.information(ventana, "Drako Cam", resultado.mensaje)
        return
    _aviso(ventana, resultado.mensaje)


def _dialogo_telegram(ventana, contexto: ContextoArranque) -> None:
    token_actual, chat_actual = credenciales_telegram(
        contexto.config.datos, dict(os.environ)
    )
    # Si vienen del entorno, el archivo puede estar vacío: mostrar lo efectivo
    # salvo que el entorno esté definido, en cuyo caso se avisa y no se pisa.
    dialogo = _DialogoBase("Drako Cam — avisos de Telegram", ventana)
    nota = QtWidgets.QLabel(
        "Opcional. Si lo dejas vacío, Drako Cam funciona igual y no envía avisos. "
        "Las variables DRAKO_CAM_TELEGRAM_BOT_TOKEN y DRAKO_CAM_TELEGRAM_CHAT_ID "
        "tienen prioridad sobre lo que guardes aquí. El token no se escribe en el código.",
        dialogo,
    )
    nota.setWordWrap(True)
    token = _campo_clave(dialogo)
    token.setPlaceholderText("Token del bot")
    token.setText(token_actual)
    chat = QtWidgets.QLineEdit(dialogo)
    chat.setPlaceholderText("Chat id")
    chat.setText(chat_actual)
    chat.setMinimumHeight(44)
    chat.setStyleSheet("font-size: 16px; padding: 6px 8px;")
    aceptar = _boton("Guardar", dialogo)
    cancelar = _boton("Cancelar", dialogo)
    aceptar.clicked.connect(dialogo.accept)
    cancelar.clicked.connect(dialogo.reject)
    fila = QtWidgets.QHBoxLayout()
    fila.addWidget(cancelar)
    fila.addWidget(aceptar)
    dialogo.agregar(nota)
    dialogo.agregar(token)
    dialogo.agregar(chat)
    dialogo._layout.addLayout(fila)
    if dialogo.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return
    telegram = contexto.config.datos.setdefault("telegram", {})
    telegram["bot_token"] = token.text().strip()
    telegram["chat_id"] = chat.text().strip()
    contexto.config.guardar()
    token_efectivo, chat_efectivo = credenciales_telegram(
        contexto.config.datos, dict(os.environ)
    )
    contexto.telegram.actualizar(token_efectivo, chat_efectivo)
    QtWidgets.QMessageBox.information(
        ventana,
        "Drako Cam",
        "Avisos de Telegram actualizados en la configuración local."
        if contexto.telegram.configurado()
        else "Telegram quedó sin configurar. El programa sigue funcionando.",
    )

