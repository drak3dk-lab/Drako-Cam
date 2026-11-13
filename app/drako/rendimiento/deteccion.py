"""Detección cada N fotogramas y seguimiento entre medias.

Cuando el detector no corre, se mueven la caja y los puntos con la
velocidad del último fotograma. Si la cara sale del encuadre o se
pierde el rastro, el siguiente fotograma vuelve a detectar.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PoliticaDeteccion:
    """Decide si este fotograma paga el detector completo."""

    cada_n: int = 2
    _contador: int = 0
    forzar: bool = True

    def debe_detectar(self, perdido: bool) -> bool:
        cada = max(1, int(self.cada_n))
        if perdido or self.forzar or cada <= 1:
            self.forzar = False
            self._contador = 0
            return True
        self._contador += 1
        if self._contador >= cada:
            self._contador = 0
            return True
        return False

    def anotar(self, hubo_cara: bool) -> None:
        if not hubo_cara:
            self.forzar = True


def _iou(a: list[float], b: list[float]) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


@dataclass
class _Pista:
    bbox: list[float]
    kps5: object | None
    kps: object | None
    kps203: object | None
    vx: float = 0.0
    vy: float = 0.0
    sin_correccion: int = 0
    perdida: bool = False
    ancho: int = 0
    alto: int = 0


def _como_filas(arr: object) -> list:
    if arr is None:
        return []
    if hasattr(arr, "shape"):
        forma = getattr(arr, "shape", None)
        if not forma or forma[0] == 0:
            return []
        return [arr[i] for i in range(int(forma[0]))]
    if isinstance(arr, (list, tuple)):
        return list(arr)
    return []


def _copiar_puntos(arr: object):
    if arr is None:
        return None
    try:
        import numpy as np

        return np.array(arr, dtype=np.float32, copy=True)
    except Exception:
        return arr


def _desplazar_puntos(arr: object, vx: float, vy: float) -> None:
    if arr is None or not hasattr(arr, "shape"):
        return
    if vx == 0 and vy == 0:
        return
    arr[..., 0] += vx
    arr[..., 1] += vy


@dataclass
class RastreadorRostros:
    """Sigue cajas y puntos entre detecciones completas."""

    max_sin_correccion: int = 8
    margen: float = 8.0
    pistas: list[_Pista] = field(default_factory=list)
    ancho: int = 0
    alto: int = 0

    def perdido(self) -> bool:
        if not self.pistas:
            return True
        return any(
            p.perdida or p.sin_correccion >= self.max_sin_correccion
            for p in self.pistas
        )

    def corregir(
        self,
        bboxes: object,
        kps5: object,
        kps: object,
        kps203: object,
        ancho: int,
        alto: int,
    ) -> None:
        self.ancho = int(ancho)
        self.alto = int(alto)
        filas = _como_filas(bboxes)
        puntos5 = _como_filas(kps5)
        puntos = _como_filas(kps)
        puntos203 = _como_filas(kps203)
        if not filas:
            self.pistas.clear()
            return
        nuevas: list[_Pista] = []
        usadas: set[int] = set()
        for i, fila in enumerate(filas):
            caja = [float(fila[0]), float(fila[1]), float(fila[2]), float(fila[3])]
            mejor = -1
            mejor_iou = 0.3
            for j, previa in enumerate(self.pistas):
                if j in usadas:
                    continue
                solape = _iou(caja, previa.bbox)
                if solape > mejor_iou:
                    mejor_iou = solape
                    mejor = j
            vx = vy = 0.0
            if mejor >= 0:
                usadas.add(mejor)
                previa = self.pistas[mejor]
                cx = (caja[0] + caja[2]) * 0.5
                cy = (caja[1] + caja[3]) * 0.5
                pcx = (previa.bbox[0] + previa.bbox[2]) * 0.5
                pcy = (previa.bbox[1] + previa.bbox[3]) * 0.5
                vx = cx - pcx
                vy = cy - pcy
            nuevas.append(
                _Pista(
                    bbox=caja,
                    kps5=_copiar_puntos(puntos5[i]) if i < len(puntos5) else None,
                    kps=_copiar_puntos(puntos[i]) if i < len(puntos) else None,
                    kps203=_copiar_puntos(puntos203[i]) if i < len(puntos203) else None,
                    vx=vx,
                    vy=vy,
                    ancho=self.ancho,
                    alto=self.alto,
                )
            )
        self.pistas = nuevas

    def predecir(self) -> None:
        for pista in self.pistas:
            vx, vy = pista.vx, pista.vy
            pista.bbox[0] += vx
            pista.bbox[2] += vx
            pista.bbox[1] += vy
            pista.bbox[3] += vy
            _desplazar_puntos(pista.kps5, vx, vy)
            _desplazar_puntos(pista.kps, vx, vy)
            _desplazar_puntos(pista.kps203, vx, vy)
            pista.sin_correccion += 1
            cx = (pista.bbox[0] + pista.bbox[2]) * 0.5
            cy = (pista.bbox[1] + pista.bbox[3]) * 0.5
            if (
                cx < -self.margen
                or cy < -self.margen
                or (self.ancho and cx > self.ancho + self.margen)
                or (self.alto and cy > self.alto + self.margen)
            ):
                pista.perdida = True

    def empaquetar(self):
        """Devuelve (bboxes, kps5, kps, kps203) como los espera el worker."""
        import numpy as np

        if not self.pistas:
            return (
                np.empty((0, 4), np.float32),
                np.empty((0, 5, 2), np.float32),
                np.empty((0, 68, 2), np.float32),
                np.empty((0, 203, 2), np.float32),
            )
        bboxes = np.array([p.bbox for p in self.pistas], dtype=np.float32)
        kps5 = _apilar([p.kps5 for p in self.pistas], (5, 2))
        kps = _apilar([p.kps for p in self.pistas], (68, 2))
        kps203 = _apilar([p.kps203 for p in self.pistas], (203, 2))
        return bboxes, kps5, kps, kps203


def _apilar(filas: list, forma_vacia: tuple[int, int]):
    import numpy as np

    validas = [f for f in filas if f is not None]
    if len(validas) != len(filas) or not validas:
        return np.empty((0, *forma_vacia), np.float32)
    return np.stack([np.asarray(f, dtype=np.float32) for f in validas], axis=0)
