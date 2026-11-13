"""Buffers fijos para no reservar memoria en cada fotograma.

La subida a la GPU reutiliza un tensor y una zona anclada (pinned).
La bajada escribe en un anillo de arrays ya creados. El primer fotograma
de cada tamaño sí reserva; los siguientes no.
"""

from __future__ import annotations

import queue


class AnilloAnfitrion:
    """Anillo de arrays uint8 del mismo tamaño que el fotograma."""

    def __init__(self, n: int = 4) -> None:
        if n < 1:
            raise ValueError("el anillo necesita al menos un hueco")
        self.n = n
        self._i = 0
        self._bgr: list = []
        self._rgb = None
        self._forma = None
        self.reservas = 0

    def copiar(self, src):
        import numpy as np

        src = np.ascontiguousarray(src)
        if self._forma != src.shape or len(self._bgr) != self.n:
            self._forma = src.shape
            self._bgr = [np.empty(src.shape, dtype=src.dtype) for _ in range(self.n)]
            self._i = 0
            self.reservas += 1
        dst = self._bgr[self._i]
        self._i = (self._i + 1) % self.n
        np.copyto(dst, src)
        return dst

    def rgb(self, alto: int, ancho: int):
        import numpy as np

        forma = (alto, ancho, 3)
        if self._rgb is None or getattr(self._rgb, "shape", None) != forma:
            self._rgb = np.empty(forma, dtype=np.uint8)
            self.reservas += 1
        return self._rgb

    def bgr_slot(self, alto: int, ancho: int):
        import numpy as np

        forma = (alto, ancho, 3)
        if len(self._bgr) != self.n or (
            self._bgr and getattr(self._bgr[0], "shape", None) != forma
        ):
            self._bgr = [np.empty(forma, dtype=np.uint8) for _ in range(self.n)]
            self._i = 0
            self.reservas += 1
        dst = self._bgr[self._i]
        self._i = (self._i + 1) % self.n
        return dst


class ReservaGpu:
    """Dos (o más) tensores CHW reutilizables. Si no hay CUDA, `subir` da None."""

    def __init__(self, cupos: int = 2) -> None:
        if cupos < 1:
            raise ValueError("hace falta al menos un cupo")
        self._libres: queue.Queue[int] = queue.Queue()
        for indice in range(cupos):
            self._libres.put(indice)
        self._tensores: dict[int, object] = {}
        self._pinned: dict[int, object] = {}
        self._formas: dict[int, tuple] = {}

    def tomar(self) -> int | None:
        try:
            return self._libres.get_nowait()
        except queue.Empty:
            return None

    def devolver(self, indice: int) -> None:
        self._libres.put(indice)

    def subir_chw(self, indice: int, hwc):
        """Copia HWC uint8 al tensor CHW del cupo. None si no hay CUDA."""
        import numpy as np

        try:
            import torch
        except Exception:
            return None
        try:
            if not torch.cuda.is_available():
                return None
        except Exception:
            return None
        arr = np.ascontiguousarray(hwc)
        forma = tuple(arr.shape)
        if len(forma) != 3:
            return None
        pin = self._pinned.get(indice)
        if pin is None or self._formas.get(indice) != forma:
            pinned_t = torch.empty(forma, dtype=torch.uint8, pin_memory=True)
            self._pinned[indice] = pinned_t.numpy()
            self._tensores[indice] = torch.empty(
                (forma[2], forma[0], forma[1]),
                dtype=torch.uint8,
                device="cuda",
            )
            self._formas[indice] = forma
        np.copyto(self._pinned[indice], arr)
        origen = torch.from_numpy(self._pinned[indice]).permute(2, 0, 1)
        self._tensores[indice].copy_(origen, non_blocking=True)
        torch.cuda.current_stream().synchronize()
        return self._tensores[indice]


def bajar_bgr(tensor, anillo: AnilloAnfitrion):
    """Un solo viaje GPU→CPU hacia el anillo, en BGR, sin arrays nuevos."""
    import numpy as np

    try:
        import torch
    except Exception:
        return None
    t = tensor.detach()
    if t.dim() == 4:
        t = t[0]
    if t.dim() != 3:
        return None
    if t.shape[0] not in (3, 4) and t.shape[-1] in (3, 4):
        t = t.permute(2, 0, 1)
    if t.dtype != torch.uint8:
        t = t.clamp(0, 255).to(dtype=torch.uint8)
    alto, ancho = int(t.shape[1]), int(t.shape[2])
    rgb = anillo.rgb(alto, ancho)
    vista = torch.from_numpy(rgb)
    vista[..., 0].copy_(t[0])
    vista[..., 1].copy_(t[1])
    vista[..., 2].copy_(t[2])
    bgr = anillo.bgr_slot(alto, ancho)
    try:
        import cv2

        cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR, dst=bgr)
    except Exception:
        np.copyto(bgr[..., 0], rgb[..., 2])
        np.copyto(bgr[..., 1], rgb[..., 1])
        np.copyto(bgr[..., 2], rgb[..., 0])
    return bgr
