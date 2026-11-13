"""Política de reconexión de la webcam, sin depender de OpenCV.

Tras varios fotogramas fallidos se pide reabrir el dispositivo.
Si los reintentos se agotan, se pide parar y avisar en pantalla.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionCamara:
    esperar_s: float
    reabrir: bool
    rendirse: bool


class PoliticaReconexion:
    def __init__(
        self,
        fallos_para_reabrir: int = 8,
        espera_s: float = 0.25,
        max_reaperturas: int = 30,
    ):
        if fallos_para_reabrir < 1:
            raise ValueError("fallos_para_reabrir debe ser al menos 1")
        self.fallos_para_reabrir = fallos_para_reabrir
        self.espera_s = espera_s
        self.max_reaperturas = max_reaperturas
        self._fallos = 0
        self._reaperturas = 0

    def fallo(self) -> DecisionCamara:
        self._fallos += 1
        if self._fallos < self.fallos_para_reabrir:
            return DecisionCamara(self.espera_s, False, False)
        self._fallos = 0
        self._reaperturas += 1
        if self._reaperturas > self.max_reaperturas:
            return DecisionCamara(self.espera_s, False, True)
        espera = min(2.0, self.espera_s * self._reaperturas)
        return DecisionCamara(espera, True, False)

    def exito(self) -> None:
        self._fallos = 0
        self._reaperturas = 0
