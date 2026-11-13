"""Logs rotativos de la aplicación y captura de excepciones no controladas."""

from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

NOMBRE_LOGGER = "drako"


def mensaje_para_usuario(exc: BaseException, ruta_log: Path | None = None) -> str:
    donde = f"\n\nDetalle guardado en:\n{ruta_log}" if ruta_log else ""
    return (
        "Drako Cam encontró un error y evitó cerrarse sin avisar.\n\n"
        f"{type(exc).__name__}: {exc}"
        f"{donde}\n\n"
        "Si vuelve a ocurrir, pasa ese archivo al administrador."
    )


def configurar_logs(
    directorio: Path,
    max_bytes: int = 2_000_000,
    copias: int = 5,
) -> logging.Logger:
    carpeta = Path(directorio) / "logs"
    carpeta.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(NOMBRE_LOGGER)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    destino = carpeta / "drako-cam.log"
    if not any(
        isinstance(handler, RotatingFileHandler)
        and Path(getattr(handler, "baseFilename", "")) == destino
        for handler in logger.handlers
    ):
        archivo = RotatingFileHandler(
            destino,
            maxBytes=max_bytes,
            backupCount=copias,
            encoding="utf-8",
        )
        archivo.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(archivo)
        consola = logging.StreamHandler()
        consola.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(consola)
    return logger


def ruta_log_actual(directorio: Path) -> Path:
    return Path(directorio) / "logs" / "drako-cam.log"


def instalar_captura_global(logger: logging.Logger, mostrar=None, ruta_log: Path | None = None) -> None:
    """Sustituye el cierre silencioso por un mensaje y una línea en el log."""

    def gancho(tipo, valor, traza):
        if tipo is KeyboardInterrupt:
            sys.__excepthook__(tipo, valor, traza)
            return
        logger.error("Excepción no capturada", exc_info=(tipo, valor, traza))
        texto = mensaje_para_usuario(valor, ruta_log)
        print(texto, file=sys.stderr)
        if mostrar is not None:
            try:
                mostrar(texto)
            except Exception:
                logger.exception("No se pudo mostrar el cuadro de error.")

    def gancho_hilo(args):
        logger.error(
            "Excepción en un hilo",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        texto = mensaje_para_usuario(args.exc_value, ruta_log)
        print(texto, file=sys.stderr)
        if mostrar is not None:
            try:
                mostrar(texto)
            except Exception:
                logger.exception("No se pudo mostrar el error del hilo.")

    sys.excepthook = gancho
    threading.excepthook = gancho_hilo
