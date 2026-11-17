"""Construye los motores TensorRT del directo antes de abrir la ventana.

La primera vez cada motor tarda minutos. Si eso ocurre al elegir la foto,
el directo cree que la foto no se pudo leer.
"""

from __future__ import annotations

import logging
import time

from app.ui.estudio.caras import MOTORES_DIRECTO, texto_motor

_log = logging.getLogger("drako")


def precalentar(ventana, al_estado=None) -> None:
    procesador = getattr(ventana, "models_processor", None)
    if procesador is None or not hasattr(procesador, "load_model"):
        _log.info("TensorRT: no hay procesador de modelos. No precaliento.")
        return
    proveedor = str(getattr(procesador, "provider_name", "") or "")
    total = len(MOTORES_DIRECTO)
    for indice, (nombre, etiqueta) in enumerate(MOTORES_DIRECTO, start=1):
        if "tensor" in proveedor.lower() or not proveedor:
            texto = texto_motor(indice, total, etiqueta)
        else:
            texto = f"Preparando el modelo ({indice}/{total}): {etiqueta}…"
        if al_estado is not None:
            try:
                al_estado(texto, int((indice - 1) * 100 / total))
            except Exception:
                _log.exception("No pude actualizar la pantalla de carga")
        inicio = time.perf_counter()
        _log.info(
            "TensorRT: inicio de la preparación %s (%s/%s) %s",
            nombre,
            indice,
            total,
            etiqueta,
        )
        try:
            sesion = procesador.load_model(nombre)
        except Exception:
            _log.exception("TensorRT: no se pudo preparar %s", nombre)
            continue
        duracion = time.perf_counter() - inicio
        if sesion is None:
            _log.warning(
                "TensorRT: %s no quedó cargado (%.1f s). El directo sigue.",
                nombre,
                duracion,
            )
        else:
            _log.info("TensorRT: fin de %s en %.1f s", nombre, duracion)
    if al_estado is not None:
        try:
            al_estado("Motores del directo listos.", 100)
        except Exception:
            _log.exception("No pude cerrar el aviso de los motores")
