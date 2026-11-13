"""Salida a la cámara virtual de OBS.

El fotograma del pipeline ya es BGR. Se abre la cámara en BGR para no
hacer otra conversión. El fondo verde o transparente es opcional y
se compone en un buffer fijo del tamaño bloqueado.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfiguracionSalida:
    ancho: int
    alto: int
    fps: int
    fondo: str  # ninguno | verde | transparente
    formato: str  # bgr | rgba

    @classmethod
    def desde_control(
        cls,
        control: dict | None,
        fps_respaldo: float = 30,
        ancho_respaldo: int = 0,
        alto_respaldo: int = 0,
    ) -> "ConfiguracionSalida":
        control = control or {}
        ancho, alto = _parse_resolucion(
            str(control.get("WebcamMaxResSelection", "")),
            ancho_respaldo,
            alto_respaldo,
        )
        try:
            fps = int(control.get("WebCamMaxFPSSelection", 0) or 0)
        except (TypeError, ValueError):
            fps = 0
        if fps <= 0:
            fps = int(fps_respaldo) if fps_respaldo and fps_respaldo > 0 else 30
        fondo = str(control.get("FondoVirtualSelection", "Ninguno"))
        fondo_id = {"Verde": "verde", "Transparente": "transparente"}.get(
            fondo, "ninguno"
        )
        formato = "rgba" if fondo_id == "transparente" else "bgr"
        return cls(ancho=ancho, alto=alto, fps=fps, fondo=fondo_id, formato=formato)


def _parse_resolucion(texto: str, ancho: int, alto: int) -> tuple[int, int]:
    if "x" in texto.lower():
        try:
            a, b = texto.lower().split("x", 1)
            return max(1, int(a)), max(1, int(b))
        except ValueError:
            pass
    if ancho > 0 and alto > 0:
        return ancho, alto
    return 1280, 720


class PreparadorSalida:
    """Redimensiona y, si se pide, recorta el fondo. Reutiliza los buffers."""

    def __init__(self) -> None:
        self._bgr = None
        self._rgba = None
        self._mascara = None
        self._caja: tuple | None = None
        self.reservas = 0

    def preparar(self, frame, cfg: ConfiguracionSalida, bboxes=None):
        import numpy as np

        if frame is None:
            return None
        src = np.ascontiguousarray(frame)
        if src.ndim != 3 or src.shape[2] < 3:
            return src
        if cfg.formato == "rgba":
            destino = self._asegurar_rgba(cfg.alto, cfg.ancho)
        else:
            destino = self._asegurar_bgr(cfg.alto, cfg.ancho)
        self._copiar_redimension(
            src, destino[:, :, :3] if cfg.formato == "rgba" else destino
        )
        if cfg.fondo == "ninguno":
            return destino
        caja = _caja_principal(bboxes, destino.shape[1], destino.shape[0])
        if caja is None:
            return destino
        if cfg.fondo == "verde":
            _aplicar_verde(destino, caja, self)
            return destino
        _aplicar_alfa(destino, caja, self)
        return destino

    def _asegurar_bgr(self, alto: int, ancho: int):
        import numpy as np

        forma = (alto, ancho, 3)
        if self._bgr is None or self._bgr.shape != forma:
            self._bgr = np.empty(forma, dtype=np.uint8)
            self.reservas += 1
        return self._bgr

    def _asegurar_rgba(self, alto: int, ancho: int):
        import numpy as np

        forma = (alto, ancho, 4)
        if self._rgba is None or self._rgba.shape != forma:
            self._rgba = np.empty(forma, dtype=np.uint8)
            self.reservas += 1
        self._rgba[:, :, 3] = 255
        return self._rgba

    def _copiar_redimension(self, src, dst) -> None:
        import numpy as np

        if src.shape[0] == dst.shape[0] and src.shape[1] == dst.shape[1]:
            np.copyto(dst, src[:, :, :3])
            return
        try:
            import cv2

            cv2.resize(
                src[:, :, :3],
                (dst.shape[1], dst.shape[0]),
                dst=dst,
                interpolation=cv2.INTER_LINEAR,
            )
            return
        except Exception:
            pass
        ys = (np.linspace(0, src.shape[0] - 1, dst.shape[0])).astype(np.int32)
        xs = (np.linspace(0, src.shape[1] - 1, dst.shape[1])).astype(np.int32)
        np.copyto(dst, src[:, :, :3][ys][:, xs])


def _caja_principal(bboxes, ancho: int, alto: int) -> tuple[int, int, int, int] | None:
    if bboxes is None:
        return None
    try:
        if hasattr(bboxes, "size") and int(bboxes.size) == 0:
            return None
        if len(bboxes) == 0:
            return None
        fila = bboxes[0]
        x1, y1, x2, y2 = (
            float(fila[0]),
            float(fila[1]),
            float(fila[2]),
            float(fila[3]),
        )
    except Exception:
        return None
    margen_x = (x2 - x1) * 0.15
    margen_y = (y2 - y1) * 0.2
    ix1 = max(0, int(x1 - margen_x))
    iy1 = max(0, int(y1 - margen_y))
    ix2 = min(ancho, int(x2 + margen_x))
    iy2 = min(alto, int(y2 + margen_y))
    if ix2 <= ix1 or iy2 <= iy1:
        return None
    return ix1, iy1, ix2, iy2


def _mascara(
    preparador: PreparadorSalida, alto: int, ancho: int, caja: tuple[int, int, int, int]
):
    import numpy as np

    if (
        preparador._mascara is not None
        and preparador._caja == caja
        and preparador._mascara.shape
        == (
            alto,
            ancho,
        )
    ):
        return preparador._mascara
    mascara = np.zeros((alto, ancho), dtype=bool)
    x1, y1, x2, y2 = caja
    cy = (y1 + y2) * 0.5
    cx = (x1 + x2) * 0.5
    ry = max(1.0, (y2 - y1) * 0.5)
    rx = max(1.0, (x2 - x1) * 0.5)
    yy, xx = np.ogrid[0:alto, 0:ancho]
    mascara[((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0] = True
    preparador._mascara = mascara
    preparador._caja = caja
    preparador.reservas += 1
    return mascara


def _aplicar_verde(destino, caja, preparador: PreparadorSalida) -> None:
    mascara = _mascara(preparador, destino.shape[0], destino.shape[1], caja)
    fuera = ~mascara
    destino[fuera, 0] = 0
    destino[fuera, 1] = 255
    destino[fuera, 2] = 0


def _aplicar_alfa(destino, caja, preparador: PreparadorSalida) -> None:
    mascara = _mascara(preparador, destino.shape[0], destino.shape[1], caja)
    destino[:, :, 3] = 0
    destino[mascara, 3] = 255
