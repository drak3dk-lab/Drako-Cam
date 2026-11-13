"""Colas cortas que prefieren el fotograma nuevo al antiguo.

En directo importa la latencia: si la inferencia va detrás, se tira
el fotograma viejo en vez de hacer crecer la cola.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class ColaLatencia:
    """Cola acotada. `poner_fresco` descarta lo más viejo si no cabe."""

    def __init__(self, capacidad: int = 1) -> None:
        if capacidad < 1:
            raise ValueError("la capacidad tiene que ser al menos 1")
        self.capacidad = capacidad
        self._items: deque[Any] = deque()
        self._cv = threading.Condition()
        self.descartados = 0

    def poner_fresco(
        self,
        item: T,
        al_descartar: Callable[[], None] | None = None,
    ) -> int:
        """Mete `item` y devuelve cuántos fotogramas viejos tiró."""
        with self._cv:
            tirados = 0
            while len(self._items) >= self.capacidad:
                self._items.popleft()
                tirados += 1
                self.descartados += 1
                if al_descartar is not None:
                    al_descartar()
            self._items.append(item)
            self._cv.notify()
            return tirados

    def tomar(self, timeout: float | None = None) -> T | None:
        """Espera un elemento. None si vence el tiempo."""
        with self._cv:
            if timeout is None:
                while not self._items:
                    self._cv.wait()
            else:
                limite = time.monotonic() + timeout
                while not self._items:
                    resto = limite - time.monotonic()
                    if resto <= 0:
                        return None
                    self._cv.wait(resto)
            return self._items.popleft()

    def vaciar(self) -> int:
        with self._cv:
            n = len(self._items)
            self._items.clear()
            self._cv.notify_all()
            return n

    def __len__(self) -> int:
        with self._cv:
            return len(self._items)


def soltar_tarea(tarea: Any) -> None:
    """Suelta la reserva de GPU de una tarea que no va a procesarse."""
    if not isinstance(tarea, tuple) or len(tarea) < 9:
        return
    extra = tarea[8]
    if not isinstance(extra, dict):
        return
    liberar = extra.get("liberar")
    if not callable(liberar):
        return
    try:
        liberar()
    except Exception:
        return


def poner_descartando(cola: Any, tarea: Any) -> bool:
    """Mete `tarea` en una `queue.Queue`. Si está llena, tira la más vieja.

    La cola de workers de vídeo usa `task_done`. Al descartar un elemento
    que nadie va a procesar hay que compensar esa cuenta y soltar su reserva.
    """
    import queue

    try:
        cola.put(tarea, block=False)
        return True
    except queue.Full:
        pass
    vieja = None
    try:
        vieja = cola.get_nowait()
    except queue.Empty:
        vieja = None
    else:
        try:
            cola.task_done()
        except ValueError:
            pass
        soltar_tarea(vieja)
    try:
        cola.put(tarea, block=False)
        return True
    except queue.Full:
        soltar_tarea(tarea)
        return False
