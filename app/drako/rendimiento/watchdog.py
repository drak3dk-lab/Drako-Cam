"""Recuperación si CUDA falla o el directo se queda sin fotogramas.

No cierra el proceso. Tras varios fallos seguidos sí pide parar el
directo, que es distinto de tumbar la aplicación.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Decision:
    detener: bool
    cambiar_proveedor: bool
    mensaje: str


@dataclass
class Vigilante:
    ventana_s: float = 8.0
    max_errores: int = 3
    atasco_s: float = 3.0
    pausa_entre_recuperaciones_s: float = 2.0
    errores: list[float] = field(default_factory=list)
    ultimo_fotograma: float = 0.0
    ultima_recuperacion: float = 0.0
    recuperaciones: int = 0
    proveedor_cambiado: bool = False

    def latido(self, ahora: float | None = None) -> None:
        self.ultimo_fotograma = ahora if ahora is not None else time.monotonic()

    def error_cuda(self, ahora: float | None = None) -> Decision:
        momento = ahora if ahora is not None else time.monotonic()
        self.errores = [t for t in self.errores if momento - t <= self.ventana_s]
        self.errores.append(momento)
        self.recuperaciones += 1
        if len(self.errores) >= self.max_errores and self.proveedor_cambiado:
            return Decision(
                True,
                False,
                "CUDA sigue fallando después de pasar a CUDA sin TensorRT. "
                "Se detiene el directo para no cerrar Drako Cam.",
            )
        if len(self.errores) >= self.max_errores:
            self.proveedor_cambiado = True
            return Decision(
                False,
                True,
                "Varios errores de CUDA. Se descarga TensorRT y se sigue con CUDA.",
            )
        return Decision(
            False,
            False,
            "Error de CUDA en un fotograma. Se suelta ese fotograma y se sigue.",
        )

    def atasco(self, ahora: float | None = None) -> Decision | None:
        momento = ahora if ahora is not None else time.monotonic()
        if self.ultimo_fotograma <= 0:
            self.ultimo_fotograma = momento
            return None
        if momento - self.ultimo_fotograma < self.atasco_s:
            return None
        if momento - self.ultima_recuperacion < self.pausa_entre_recuperaciones_s:
            return None
        self.ultima_recuperacion = momento
        self.ultimo_fotograma = momento
        self.recuperaciones += 1
        if self.recuperaciones >= 6:
            return Decision(
                True,
                False,
                "El directo no entrega fotogramas. Se detiene la webcam "
                "sin cerrar Drako Cam.",
            )
        return Decision(
            False,
            False,
            "El directo se atascó. Se vacían las colas y se redetecta la cara.",
        )


def _vaciar_cola_workers(video_processor: object) -> None:
    cola = getattr(video_processor, "frame_queue", None)
    if cola is None:
        return
    import queue

    from app.drako.rendimiento.colas import soltar_tarea

    while True:
        try:
            tarea = cola.get_nowait()
        except queue.Empty:
            break
        else:
            soltar_tarea(tarea)
            try:
                cola.task_done()
            except ValueError:
                pass


def _vaciar_cache_cuda() -> None:
    try:
        from app.processors.utils import platform_support

        platform_support.empty_cache("cuda")
    except Exception:
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            return


def recuperar(video_processor: object, decision: Decision) -> None:
    """Aplica una decisión. No lanza: un fallo de la recuperación no puede cerrar la app."""
    try:
        detector = getattr(video_processor, "sequential_detector", None)
        if detector is not None and hasattr(detector, "reset_state"):
            detector.reset_state()
        canal = getattr(
            getattr(video_processor, "media_pipeline", None), "_canal_en_vivo", None
        )
        if canal is not None:
            canal.captura.vaciar()
            canal.salida.vaciar()
        _vaciar_cola_workers(video_processor)
        _vaciar_cache_cuda()
        if decision.cambiar_proveedor:
            ventana = getattr(video_processor, "main_window", None)
            fw = (
                getattr(ventana, "function_worker", None)
                if ventana is not None
                else None
            )
            if fw is not None and hasattr(fw, "switch_providers_priority"):
                fw.switch_providers_priority("CUDA")
                if hasattr(ventana, "control") and isinstance(ventana.control, dict):
                    ventana.control["ProvidersPrioritySelection"] = "CUDA"
        if decision.detener:
            try:
                video_processor.fatal_processing_error_signal.emit(decision.mensaje)
            except Exception:
                if hasattr(video_processor, "stop_processing"):
                    video_processor.stop_processing()
        else:
            print(f"[AVISO] {decision.mensaje}")
    except Exception as exc:
        print(f"[AVISO] La recuperación no pudo completar: {exc}")


def observar_error(video_processor: object, _mensaje: str = "") -> bool:
    """True si el directo puede seguir. False si hay que pararlo como hasta ahora."""
    vigilante = getattr(video_processor, "vigilante", None)
    if not isinstance(vigilante, Vigilante):
        vigilante = Vigilante()
        video_processor.vigilante = vigilante
    decision = vigilante.error_cuda()
    if decision.detener:
        return False
    recuperar(video_processor, decision)
    return True


def observar_atasco(video_processor: object) -> None:
    vigilante = getattr(video_processor, "vigilante", None)
    if not isinstance(vigilante, Vigilante):
        return
    if not getattr(video_processor, "processing", False):
        return
    decision = vigilante.atasco()
    if decision is None:
        return
    recuperar(video_processor, decision)


def observar_latido(video_processor: object) -> None:
    vigilante = getattr(video_processor, "vigilante", None)
    if isinstance(vigilante, Vigilante):
        vigilante.latido()
