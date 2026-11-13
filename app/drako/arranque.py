"""Preparación del arranque que no depende de Qt."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.drako.auditoria import (
    ClavesAuditoria,
    RegistroAuditoria,
    guardar_claves,
    obtener_claves,
)
from app.drako.clave import AlmacenClave, ResultadoAcceso
from app.drako.configuracion import ConfiguracionLocal
from app.drako.registro import configurar_logs, instalar_captura_global, ruta_log_actual
from app.drako.rutas import directorio_datos
from app.drako.sesion import SesionUso, fijar_sesion
from app.drako.telegram_cliente import (
    ClienteTelegram,
    TransporteUrllib,
    credenciales_telegram,
)


@dataclass
class ContextoArranque:
    directorio: Path
    config: ConfiguracionLocal
    almacen: AlmacenClave
    telegram: ClienteTelegram
    logger: object


def preparar_contexto(entorno: dict | None = None) -> ContextoArranque:
    env = os.environ if entorno is None else entorno
    directorio = directorio_datos(env)
    directorio.mkdir(parents=True, exist_ok=True)
    config = ConfiguracionLocal(directorio)
    logger = configurar_logs(directorio)
    instalar_captura_global(logger, ruta_log=ruta_log_actual(directorio))
    almacen = AlmacenClave(config)
    token, chat = credenciales_telegram(config.datos, env)
    telegram = ClienteTelegram(
        token,
        chat,
        TransporteUrllib(),
        directorio / "cola_telegram.json",
    )
    return ContextoArranque(directorio, config, almacen, telegram, logger)


def activar_sesion(
    contexto: ContextoArranque,
    contrasena: str,
    pendientes: list | None = None,
) -> tuple[SesionUso, ClavesAuditoria]:
    claves = obtener_claves(contexto.config, contrasena)
    registro = RegistroAuditoria(contexto.directorio / "auditoria.log", claves)
    sesion = SesionUso(registro, contexto.telegram)
    fijar_sesion(sesion)
    if pendientes:
        sesion.volcar_pendientes(pendientes)
    sesion.abrir()
    contexto.telegram.iniciar_reintentos()
    return sesion, claves


def cambiar_contrasena(
    contexto: ContextoArranque,
    claves: ClavesAuditoria,
    actual: str,
    nueva: str,
    confirmacion: str,
) -> ResultadoAcceso:
    resultado = contexto.almacen.cambiar(actual, nueva, confirmacion)
    if resultado.ok:
        guardar_claves(contexto.config, claves, nueva)
    return resultado
