"""Suavizado temporal del directo, sin modelos ni GPU.

La máscara vive en el recorte alineado de la cara (el mismo sitio al
que la transformación afín lleva cada fotograma). Por eso un promedio
exponencial ahí no mancha el fondo cuando la cabeza se mueve despacio.
Si la cara cambia o da un salto, se olvida el fotograma anterior.

El coste que se mide aquí es solo este cálculo. La red neuronal no
entra.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import numpy as np

ALFA_MASCARA = 0.45
ALFA_COLOR = 0.35
UMBRAL_SALTO = 0.35
UMBRAL_MASCARA_VISIBLE = 0.62
LADO_MASCARA = 96


def lado_de_caja(caja) -> float:
    if caja is None:
        return 200.0
    arr = np.asarray(caja, dtype=np.float32).reshape(-1)
    if arr.size < 4:
        return 200.0
    return float(max(arr[2] - arr[0], arr[3] - arr[1], 1.0))


def centro_de_caja(caja) -> tuple[float, float] | None:
    if caja is None:
        return None
    arr = np.asarray(caja, dtype=np.float32).reshape(-1)
    if arr.size < 4:
        return None
    return float((arr[0] + arr[2]) * 0.5), float((arr[1] + arr[3]) * 0.5)


def salto_grande(
    centro_anterior: tuple[float, float] | None,
    centro: tuple[float, float] | None,
    tamano: float,
    umbral: float = UMBRAL_SALTO,
) -> bool:
    if centro_anterior is None or centro is None:
        return False
    distancia = ((centro[0] - centro_anterior[0]) ** 2 + (centro[1] - centro_anterior[1]) ** 2) ** 0.5
    return distancia > umbral * max(tamano, 1.0)


def pluma_adaptativa(
    lado_cara_px: float,
    minimo_en_frame: float = 2.5,
    base: float = 0.6,
    tope: float = 14.0,
) -> float:
    """Sigma en el recorte de 512 para que el borde, ya pegado, no baje de unos píxeles.

    Una cara pequeña se pega con menos píxeles de borde. Sin esto, el
    pelo parpadea justo cuando la persona está lejos.
    """
    lado = max(float(lado_cara_px), 1.0)
    sigma = minimo_en_frame * 512.0 / lado
    return float(min(tope, max(base, sigma)))


def tamano_oclusion(lado_cara_px: float, pedido: int, adaptativo: bool) -> int:
    """El deslizador manda. Si es adaptativo, una cara grande encoge un poco la máscara.

    Así las gafas no se comen los ojos cuando la cara llena el encuadre,
    y una mano sigue tapando cuando la cara es pequeña.
    """
    pedido = int(pedido)
    if not adaptativo:
        return int(np.clip(pedido, -40, 40))
    if lado_cara_px >= 320:
        ajuste = -4
    elif lado_cara_px >= 180:
        ajuste = -2
    else:
        ajuste = 0
    return int(np.clip(pedido + ajuste, -40, 40))


def interpolar_caja(anterior, predicha, peso_predicha: float = 0.45) -> np.ndarray:
    """Si el detector suelta la cara, la caja no salta: se acerca a la predicción."""
    previa = np.asarray(anterior, dtype=np.float32).reshape(-1)[:4]
    nueva = np.asarray(predicha, dtype=np.float32).reshape(-1)[:4]
    peso = float(np.clip(peso_predicha, 0.0, 1.0))
    return previa * (1.0 - peso) + nueva * peso


def peso_ultimo_swap(media_mascara: float, umbral: float = UMBRAL_MASCARA_VISIBLE) -> float:
    """0 usa el cambio nuevo. Cerca de 1 conserva el último mientras una mano tapa."""
    media = float(media_mascara)
    if media >= umbral:
        return 0.0
    return float(np.clip((umbral - media) / max(umbral, 1e-6), 0.0, 0.85))


def ema(anterior: np.ndarray, actual: np.ndarray, alfa: float) -> np.ndarray:
    mezcla = float(np.clip(alfa, 0.0, 1.0))
    return actual * mezcla + anterior * (1.0 - mezcla)


def estabilizar_color(
    media: np.ndarray,
    desvio: np.ndarray,
    media_anterior: np.ndarray | None,
    desvio_anterior: np.ndarray | None,
    alfa: float,
) -> tuple[np.ndarray, np.ndarray]:
    media = np.asarray(media, dtype=np.float32).reshape(-1)
    desvio = np.maximum(np.asarray(desvio, dtype=np.float32).reshape(-1), 1e-3)
    if media_anterior is None or desvio_anterior is None:
        return media, desvio
    mezcla = float(np.clip(alfa, 0.0, 1.0))
    return (
        ema(np.asarray(media_anterior, dtype=np.float32), media, mezcla),
        ema(np.asarray(desvio_anterior, dtype=np.float32), desvio, mezcla),
    )


@dataclass
class _Cara:
    mascara: np.ndarray | None = None
    centro: tuple[float, float] | None = None
    tamano: float = 0.0
    media: np.ndarray | None = None
    desvio: np.ndarray | None = None


@dataclass
class MemoriaDirecto:
    """Una memoria por identidad. El candado es el del hilo de la webcam."""

    alfa_mascara: float = ALFA_MASCARA
    alfa_color: float = ALFA_COLOR
    umbral_salto: float = UMBRAL_SALTO
    _caras: dict[str, _Cara] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def reiniciar(self, cara_id: str | None = None) -> None:
        with self._lock:
            if cara_id is None:
                self._caras.clear()
            else:
                self._caras.pop(str(cara_id), None)

    def paso_mascara(
        self,
        cara_id: str,
        mascara: np.ndarray,
        centro: tuple[float, float] | None,
        tamano: float,
        alfa: float | None = None,
    ) -> tuple[np.ndarray, bool]:
        """Devuelve la máscara suavizada y si este fotograma olvidó el anterior."""
        actual = np.asarray(mascara, dtype=np.float32)
        if actual.ndim == 3:
            actual = actual[0]
        ident = str(cara_id)
        with self._lock:
            estado = self._caras.setdefault(ident, _Cara())
            reinicio = (
                estado.mascara is None
                or estado.mascara.shape != actual.shape
                or salto_grande(estado.centro, centro, tamano, self.umbral_salto)
            )
            if reinicio:
                salida = actual.copy()
            else:
                mezcla = self.alfa_mascara if alfa is None else alfa
                salida = ema(estado.mascara, actual, mezcla)
            estado.mascara = salida
            estado.centro = centro
            estado.tamano = tamano
            return salida, reinicio

    def paso_color(
        self,
        cara_id: str,
        media: np.ndarray,
        desvio: np.ndarray,
        reiniciar: bool,
    ) -> tuple[np.ndarray, np.ndarray]:
        ident = str(cara_id)
        with self._lock:
            estado = self._caras.setdefault(ident, _Cara())
            if reiniciar:
                estado.media = None
                estado.desvio = None
            media_s, desvio_s = estabilizar_color(
                media, desvio, estado.media, estado.desvio, self.alfa_color
            )
            estado.media = media_s
            estado.desvio = desvio_s
            return media_s, desvio_s


MEMORIA = MemoriaDirecto()


def reducir_mascara(mascara: np.ndarray, lado: int = LADO_MASCARA) -> np.ndarray:
    """Baja la máscara a una rejilla fija. Vecino más cercano, sin scipy."""
    origen = np.asarray(mascara, dtype=np.float32)
    if origen.ndim == 3:
        origen = origen[0]
    alto, ancho = origen.shape
    if alto == lado and ancho == lado:
        return origen
    filas = np.linspace(0, alto - 1, lado).astype(np.int32)
    columnas = np.linspace(0, ancho - 1, lado).astype(np.int32)
    return origen[filas][:, columnas]


def preparar_mascara(
    memoria: MemoriaDirecto,
    cara_id: str,
    mascara: np.ndarray,
    centro: tuple[float, float] | None,
    tamano: float,
) -> tuple[np.ndarray, bool]:
    """EMA en una rejilla pequeña y vuelta al tamaño del recorte."""
    plano = np.asarray(mascara, dtype=np.float32)
    if plano.ndim == 3:
        plano = plano[0]
    alto, ancho = plano.shape
    pequena = reducir_mascara(plano)
    suavizada, reinicio = memoria.paso_mascara(
        cara_id, pequena, centro, tamano, alfa=memoria.alfa_mascara
    )
    return ampliar_mascara(suavizada, alto, ancho), reinicio


def ampliar_mascara(mascara: np.ndarray, alto: int, ancho: int) -> np.ndarray:
    origen = np.asarray(mascara, dtype=np.float32)
    filas = np.linspace(0, origen.shape[0] - 1, alto).astype(np.int32)
    columnas = np.linspace(0, origen.shape[1] - 1, ancho).astype(np.int32)
    return origen[filas][:, columnas]
