"""Sesión de uso: qué se anota y qué se avisa.

De cada cara solo se guarda el nombre del archivo y un hash.
No se guardan imágenes, embeddings ni la contraseña.
"""

from __future__ import annotations

import hashlib
import os
import socket
import time
import uuid
from typing import Any

from app.drako.telegram_cliente import ClienteTelegram

_sesion_activa: "SesionUso | None" = None


def fijar_sesion(sesion: "SesionUso | None") -> None:
    global _sesion_activa
    _sesion_activa = sesion


def sesion_activa() -> "SesionUso | None":
    return _sesion_activa


def _bytes_de(valor: Any) -> bytes:
    if valor is None:
        return b""
    if isinstance(valor, (bytes, bytearray)):
        return bytes(valor)
    tobytes = getattr(valor, "tobytes", None)
    if callable(tobytes):
        return tobytes()
    return str(valor).encode("utf-8", errors="replace")


def resumir_cara(ruta: str, embedding_store: Any) -> tuple[str, str]:
    """Nombre visible y SHA-256. El embedding no sale de esta función."""
    nombre = os.path.basename(str(ruta or "")) or "sin-nombre"
    resumen = hashlib.sha256()
    resumen.update(nombre.encode("utf-8"))
    if isinstance(embedding_store, dict):
        for clave in sorted(embedding_store, key=str):
            resumen.update(str(clave).encode("utf-8"))
            resumen.update(_bytes_de(embedding_store[clave]))
    return nombre, resumen.hexdigest()


def registrar_cara_activa(ruta: str, embedding_store: Any) -> None:
    sesion = _sesion_activa
    if sesion is None:
        return
    nombre, huella = resumir_cara(ruta, embedding_store)
    sesion.registrar_cara(nombre, huella)


def texto_aviso(evento: dict) -> str:
    lineas = [
        "Drako Cam",
        f"Equipo: {evento.get('equipo') or 'desconocido'}",
        f"Evento: {evento.get('tipo') or 'aviso'}",
    ]
    if evento.get("sesion"):
        lineas.append(f"Sesión: {evento['sesion']}")
    if evento.get("duracion_segundos") is not None:
        lineas.append(f"Duración: {float(evento['duracion_segundos']):.1f} s")
    if evento.get("cara_nombre"):
        lineas.append(f"Cara: {evento['cara_nombre']}")
    if evento.get("cara_hash"):
        lineas.append(f"Hash: {evento['cara_hash']}")
    if evento.get("detalle"):
        lineas.append(str(evento["detalle"]))
    return "\n".join(lineas)


class SesionUso:
    def __init__(
        self,
        registro,
        telegram: ClienteTelegram,
        equipo: str | None = None,
        reloj=None,
    ):
        self.registro = registro
        self.telegram = telegram
        self.equipo = equipo or socket.gethostname()
        self.reloj = reloj or time.time
        self.identificador = uuid.uuid4().hex
        self.inicio = float(self.reloj())
        self._cerrada = False

    def abrir(self) -> None:
        self.inicio = float(self.reloj())
        self._emitir("apertura", detalle="programa abierto")

    def cerrar(self) -> None:
        if self._cerrada:
            return
        self._cerrada = True
        duracion = max(0.0, float(self.reloj()) - self.inicio)
        self._emitir("cierre", duracion_segundos=duracion, detalle="programa cerrado")

    def registrar_cara(self, nombre: str, huella: str) -> None:
        self._emitir(
            "cara_usada",
            cara_nombre=nombre,
            cara_hash=huella,
            detalle="cara seleccionada",
        )

    def anotar(self, tipo: str, detalle: str = "") -> None:
        self._emitir(tipo, detalle=detalle)

    def volcar_pendientes(self, pendientes: list) -> None:
        for item in pendientes:
            if not isinstance(item, dict):
                continue
            evento = {
                "tipo": item.get("tipo") or "intento_fallido",
                "equipo": item.get("equipo") or self.equipo,
                "marca_unix": item.get("marca_unix"),
                "detalle": item.get("detalle") or "",
                "sesion": self.identificador,
            }
            self._escribir_y_avisar(evento, avisar=False)

    def _emitir(self, tipo: str, **extra) -> None:
        evento = {
            "tipo": tipo,
            "equipo": self.equipo,
            "sesion": self.identificador,
            "marca_unix": float(self.reloj()),
            "duracion_segundos": extra.get("duracion_segundos"),
            "cara_nombre": extra.get("cara_nombre"),
            "cara_hash": extra.get("cara_hash"),
            "detalle": extra.get("detalle") or "",
        }
        self._escribir_y_avisar(evento, avisar=True)

    def _escribir_y_avisar(self, evento: dict, avisar: bool) -> None:
        try:
            self.registro.registrar(evento)
        except Exception:
            # El aviso no debe impedir que el otro canal intente salir.
            pass
        if not avisar:
            return
        try:
            self.telegram.avisar(texto_aviso(evento))
        except Exception:
            pass
