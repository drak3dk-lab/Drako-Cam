"""Estabilidad y calidad del directo, sin un modelo nuevo.

One Euro suaviza la caja y los puntos sin el retraso de una media
exponencial fija. El fundido aguanta el último cambio de cara unos
fotogramas si el rastro se pierde, en vez de enseñar la cara real de golpe.
El preset elige resolución, restaurador y máscaras según la GPU.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np


class FiltroEuro:
    """One Euro (Casiez, 2012). Poca frecuencia en reposo, más si hay movimiento."""

    def __init__(
        self, freq_min: float = 1.0, beta: float = 0.07, corte_derivada: float = 1.0
    ):
        self.freq_min = float(freq_min)
        self.beta = float(beta)
        self.corte_derivada = float(corte_derivada)
        self._x: np.ndarray | None = None
        self._dx: np.ndarray | None = None
        self._t: float | None = None

    def paso(self, valor: np.ndarray, t: float) -> np.ndarray:
        x = np.asarray(valor, dtype=np.float32)
        if self._x is None or self._t is None or self._dx is None:
            self._x = x.copy()
            self._dx = np.zeros_like(self._x)
            self._t = float(t)
            return self._x.copy()
        dt = max(1e-4, float(t) - self._t)
        dx = (x - self._x) / dt
        alfa_d = _alfa(self.corte_derivada, dt)
        self._dx = alfa_d * dx + (1.0 - alfa_d) * self._dx
        corte = self.freq_min + self.beta * np.abs(self._dx)
        alfa = _alfa(corte, dt)
        self._x = alfa * x + (1.0 - alfa) * self._x
        self._t = float(t)
        return self._x.copy()


def _alfa(corte: float | np.ndarray, dt: float) -> np.ndarray:
    tau = 1.0 / (2.0 * np.pi * np.maximum(corte, 1e-3))
    return (1.0 / (1.0 + tau / dt)).astype(np.float32)


def ema(anterior: np.ndarray, nuevo: np.ndarray, alpha: float = 0.35) -> np.ndarray:
    return (
        alpha * np.asarray(nuevo, np.float32)
        + (1.0 - alpha) * np.asarray(anterior, np.float32)
    ).astype(np.float32)


def _ensayo(limpio: np.ndarray, semilla: int) -> dict[str, float]:
    rng = np.random.default_rng(semilla)
    n = len(limpio)
    t = np.arange(n, dtype=np.float32) / 30.0
    ruido = limpio + rng.normal(0.0, 1.6, size=n).astype(np.float32)
    euro = FiltroEuro()
    suavizado = np.empty(n, np.float32)
    media = np.empty(n, np.float32)
    estado = float(ruido[0])
    for i in range(n):
        suavizado[i] = float(euro.paso(np.array([ruido[i]]), float(t[i]))[0])
        estado = float(ema(np.array([estado]), np.array([ruido[i]]), 0.35)[0])
        media[i] = estado

    def rms(serie: np.ndarray) -> float:
        return float(np.sqrt(np.mean((serie - limpio) ** 2)))

    return {
        "bruto": rms(ruido),
        "ema": rms(media),
        "euro": rms(suavizado),
        "retraso_ema": abs(int(np.argmax(media) - np.argmax(limpio))),
        "retraso_euro": abs(int(np.argmax(suavizado) - np.argmax(limpio))),
    }


def medir_temblor(semilla: int = 0, n: int = 90) -> dict[str, dict[str, float]]:
    """RMS en píxeles frente a la señal limpia, con 1,6 px de ruido.

    «quieto» es una cara quieta. «mueve» es un seno de 0,4 Hz. La media
    exponencial 0,35 es la que ya tenía el worker. One Euro es el filtro nuevo.
    """
    t = np.arange(n, dtype=np.float32) / 30.0
    return {
        "quieto": _ensayo(np.full(n, 40.0, dtype=np.float32), semilla),
        "mueve": _ensayo(40.0 + 12.0 * np.sin(2.0 * np.pi * 0.4 * t), semilla + 1),
    }


class FundidoCara:
    """Si la cara se pierde, el último swap baja en varios fotogramas."""

    def __init__(self, fotogramas: int = 8) -> None:
        self.fotogramas = max(1, int(fotogramas))
        self.alfa = 1.0

    def paso(self, hay_cara: bool) -> float:
        paso = 1.0 / self.fotogramas
        if hay_cara:
            self.alfa = min(1.0, self.alfa + paso)
        else:
            self.alfa = max(0.0, self.alfa - paso)
        return self.alfa


@dataclass(frozen=True)
class PresetDirecto:
    nombre: str
    swap_res: str
    restaurador: bool
    mezcla: int
    oclusion: bool
    parser: bool
    color: bool
    deteccion_cada: int


PRESET_MAXIMA = PresetDirecto("Máxima calidad", "512", True, 75, True, True, True, 2)
PRESET_EQUILIBRADO = PresetDirecto("Equilibrado", "256", True, 65, True, True, True, 2)
PRESET_FPS = PresetDirecto("Máximo FPS", "128", False, 0, True, False, False, 4)
PRESET_6GB = PresetDirecto("Equilibrado", "128", True, 55, True, True, True, 4)

_POR_NOMBRE = {
    "Máxima calidad": PRESET_MAXIMA,
    "Equilibrado": PRESET_EQUILIBRADO,
    "Máximo FPS": PRESET_FPS,
}


def preset_automatico(perfil_id: str) -> PresetDirecto:
    if perfil_id == "portatil_6gb":
        return PRESET_6GB
    if perfil_id == "alto_12gb":
        return PRESET_MAXIMA
    return PRESET_EQUILIBRADO


def limitar_a_la_gpu(preset: PresetDirecto, perfil_id: str) -> PresetDirecto:
    """En 6 GB no se pide 384 ni 512: no caben con el restaurador."""
    if perfil_id == "portatil_6gb" and preset.swap_res in {"384", "512"}:
        return replace(preset, swap_res="256")
    return preset


def preset_elegido(control: dict, perfil_id: str) -> PresetDirecto:
    nombre = str(control.get("PresetCalidadSelection", "Auto"))
    base = _POR_NOMBRE.get(nombre) or preset_automatico(perfil_id)
    return limitar_a_la_gpu(base, perfil_id)


def aplicar_preset(ventana: object, preset: PresetDirecto, deteccion_cada: int) -> None:
    """Escribe resolución, restaurador, máscaras y color en los ajustes del directo."""
    from app.drako.rendimiento.perfiles import _poner

    valores_control = {
        "DeteccionCadaNSlider": str(deteccion_cada),
        "FaceRestorerEnableToggle": preset.restaurador,
    }
    valores_cara = {
        "SwapperResSelection": preset.swap_res,
        "FaceRestorerEnableToggle": preset.restaurador,
        "FaceRestorerTypeSelection": "GFPGAN-v1.4",
        "FaceRestorerBlendSlider": preset.mezcla,
        "OccluderEnableToggle": preset.oclusion,
        "BordermaskEnableToggle": True,
        "FaceParserEnableToggle": preset.parser,
        "MouthParserInsideToggle": True,
        "EndingColorTransferEnableToggle": preset.color,
        "EndingColorTransferAmountSlider": 70 if preset.color else 0,
    }
    for clave, valor in valores_control.items():
        _poner(ventana, clave, valor)
    for clave, valor in valores_cara.items():
        _poner(ventana, clave, valor)
        _escribir_en_caras(ventana, clave, valor)


def _escribir_en_caras(ventana: object, clave: str, valor: object) -> None:
    for almacen in (
        getattr(ventana, "default_parameters", None),
        getattr(ventana, "current_widget_parameters", None),
    ):
        if isinstance(almacen, dict):
            almacen[clave] = valor
    parametros = getattr(ventana, "parameters", None)
    if isinstance(parametros, dict):
        for cara in parametros.values():
            if isinstance(cara, dict):
                cara[clave] = valor
