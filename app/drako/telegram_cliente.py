"""Avisos al bot de Telegram del administrador, con cola si no hay red.

El token y el chat id llegan por variables de entorno o por la
configuración local. Si no están, los avisos se omiten y el programa sigue.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("drako.telegram")


class ErrorDeRed(Exception):
    """No hubo conexión o el servicio respondió con un fallo temporal."""


class ErrorConfiguracion(Exception):
    """Telegram rechazó el aviso (token o chat incorrectos). No se reintenta."""


class TransporteUrllib:
    """Cliente HTTP mínimo. El token no se incluye en los mensajes de error."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def enviar(self, token: str, chat_id: str, texto: str) -> None:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        cuerpo = json.dumps(
            {"chat_id": chat_id, "text": texto}, ensure_ascii=False
        ).encode("utf-8")
        peticion = urllib.request.Request(
            url,
            data=cuerpo,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(peticion, timeout=self.timeout) as respuesta:
                respuesta.read()
        except urllib.error.HTTPError as exc:
            if exc.code >= 500:
                raise ErrorDeRed("Telegram no respondió correctamente.") from exc
            raise ErrorConfiguracion(
                f"Telegram rechazó el aviso (HTTP {exc.code})."
            ) from exc
        except urllib.error.URLError as exc:
            raise ErrorDeRed("Sin conexión con Telegram.") from exc
        except TimeoutError as exc:
            raise ErrorDeRed("Tiempo de espera agotado al avisar por Telegram.") from exc


class ClienteTelegram:
    def __init__(self, token: str, chat_id: str, transporte, ruta_cola: Path):
        self.token = (token or "").strip()
        self.chat_id = (chat_id or "").strip()
        self.transporte = transporte
        self.ruta_cola = Path(ruta_cola)
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    def configurado(self) -> bool:
        return bool(self.token and self.chat_id)

    def actualizar(self, token: str, chat_id: str) -> None:
        self.token = (token or "").strip()
        self.chat_id = (chat_id or "").strip()

    def avisar(self, texto: str) -> str:
        if not self.configurado():
            return "omitido"
        try:
            self.transporte.enviar(self.token, self.chat_id, texto)
            return "enviado"
        except ErrorDeRed:
            self._encolar(texto)
            logger.warning("Sin red: el aviso de Telegram quedó en la cola local.")
            return "encolado"
        except ErrorConfiguracion:
            logger.error(
                "Telegram rechazó el aviso. Revisa el token y el chat id "
                "en la configuración local o en las variables de entorno."
            )
            return "error_configuracion"

    def reintentar(self) -> int:
        if not self.configurado():
            return 0
        pendientes = self._leer_cola()
        if not pendientes:
            return 0
        enviados = 0
        restantes = list(pendientes)
        for texto in pendientes:
            try:
                self.transporte.enviar(self.token, self.chat_id, texto)
            except ErrorDeRed:
                break
            except ErrorConfiguracion:
                logger.error("Telegram sigue rechazando los avisos encolados.")
                break
            enviados += 1
            restantes.pop(0)
        self._escribir_cola(restantes)
        return enviados

    def iniciar_reintentos(self, intervalo_s: float = 30.0) -> None:
        if self._hilo is not None:
            return

        def ciclo() -> None:
            while not self._parar.wait(intervalo_s):
                try:
                    self.reintentar()
                except Exception:
                    logger.exception("Falló un reintento de la cola de Telegram.")

        self._hilo = threading.Thread(
            target=ciclo, name="drako-telegram", daemon=True
        )
        self._hilo.start()

    def detener_reintentos(self) -> None:
        self._parar.set()

    def _encolar(self, texto: str) -> None:
        pendientes = self._leer_cola()
        pendientes.append(texto)
        self._escribir_cola(pendientes[-200:])

    def _leer_cola(self) -> list[str]:
        if not self.ruta_cola.is_file():
            return []
        try:
            cargado = json.loads(self.ruta_cola.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        pendientes = cargado.get("pendientes", []) if isinstance(cargado, dict) else []
        return [str(item) for item in pendientes]

    def _escribir_cola(self, pendientes: list[str]) -> None:
        self.ruta_cola.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta_cola.with_suffix(".json.tmp")
        temporal.write_text(
            json.dumps({"pendientes": pendientes}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            os.chmod(temporal, 0o600)
        except OSError:
            pass
        os.replace(temporal, self.ruta_cola)


def credenciales_telegram(config: dict, entorno: dict | None = None) -> tuple[str, str]:
    """El entorno manda si la variable tiene valor. Si no, se usa el archivo."""
    env = {} if entorno is None else entorno
    telegram = config.get("telegram") if isinstance(config, dict) else {}
    if not isinstance(telegram, dict):
        telegram = {}

    def elegir(nombre_env: str, nombre_archivo: str) -> str:
        valor_env = str(env.get(nombre_env, "")).strip()
        if valor_env:
            return valor_env
        return str(telegram.get(nombre_archivo, "")).strip()

    return (
        elegir("DRAKO_CAM_TELEGRAM_BOT_TOKEN", "bot_token"),
        elegir("DRAKO_CAM_TELEGRAM_CHAT_ID", "chat_id"),
    )
