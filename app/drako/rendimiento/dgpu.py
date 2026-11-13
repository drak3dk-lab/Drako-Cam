"""Forzar la GPU NVIDIA en portátiles híbridos, y avisar si no es así.

Python no puede exportar el símbolo NvOptimusEnablement: tiene que
vivir en el ejecutable, y el de la aplicación es python.exe. El
equivalente que Windows sí honra es la preferencia de gráficos por
aplicación, en el registro del usuario:

    HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences
    valor = ruta del exe, datos = GpuPreference=2;

GpuPreference=2 pide la GPU de alto rendimiento. El instalador lo
escribe para python.exe, pythonw.exe y main.py. Al arrancar, Drako
Cam lo vuelve a escribir por si la copia es portable y no pasó por
Inno Setup. Si CUDA acaba viendo una GPU integrada, se avisa.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

CLAVE_REGISTRO = r"Software\Microsoft\DirectX\UserGpuPreferences"
VALOR_PREFERENCIA = "GpuPreference=2;"

_INTEGRADA = (
    "intel",
    "uhd graphics",
    "iris",
    "radeon graphics",
    "radeon(tm) graphics",
    "basic render",
)
_NVIDIA = ("nvidia", "geforce", "rtx", "gtx", "quadro")


@dataclass(frozen=True)
class Dispositivo:
    indice: int
    nombre: str
    vram_bytes: int


def es_integrada(nombre: str | None) -> bool:
    texto = (nombre or "").lower()
    if any(marca in texto for marca in _NVIDIA):
        return False
    return any(marca in texto for marca in _INTEGRADA)


def es_nvidia_dedicada(nombre: str | None) -> bool:
    texto = (nombre or "").lower()
    return any(marca in texto for marca in _NVIDIA) and not es_integrada(nombre)


def aviso_gpu_integrada(nombre: str | None) -> str | None:
    if not nombre or not es_integrada(nombre):
        return None
    return (
        f"Drako Cam está usando la GPU integrada ({nombre}). "
        "En un portátil híbrido el cambio de cara tiene que ir por la "
        "NVIDIA dedicada. Cierra el programa, ábrelo otra vez (el "
        "instalador marca python.exe como GPU de alto rendimiento) y, "
        "si sigue igual, en Windows ve a Configuración → Pantalla → "
        "Gráficos y pon Drako Cam en «Alto rendimiento»."
    )


def elegir_indice(dispositivos: list[Dispositivo], pedido: int) -> int:
    """Se queda con la NVIDIA de más VRAM si el índice pedido no lo es."""
    if not dispositivos:
        return pedido
    if 0 <= pedido < len(dispositivos) and es_nvidia_dedicada(
        dispositivos[pedido].nombre
    ):
        return pedido
    nvidia = [d for d in dispositivos if es_nvidia_dedicada(d.nombre)]
    if not nvidia:
        return pedido if pedido >= 0 else 0
    return max(nvidia, key=lambda d: d.vram_bytes).indice


def rutas_de_aplicacion(extra: list[str] | None = None) -> list[str]:
    rutas = []
    for candidata in [sys.executable, *(extra or [])]:
        if not candidata:
            continue
        try:
            rutas.append(os.path.abspath(candidata))
        except Exception:
            rutas.append(candidata)
    # Sin duplicados, conservando el orden.
    vistos = []
    for ruta in rutas:
        if ruta not in vistos:
            vistos.append(ruta)
    return vistos


def preferir_gpu_dedicada(rutas: list[str] | None = None) -> list[str]:
    """Escribe la preferencia en Windows. En otros sistemas no hace nada.

    Devuelve las rutas que quedó escritas. No lanza.
    """
    if os.name != "nt":
        return []
    objetivos = rutas_de_aplicacion(rutas)
    if not objetivos:
        return []
    try:
        import winreg
    except Exception:
        return []
    escritas: list[str] = []
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLAVE_REGISTRO) as clave:
            for ruta in objetivos:
                winreg.SetValueEx(clave, ruta, 0, winreg.REG_SZ, VALOR_PREFERENCIA)
                escritas.append(ruta)
    except Exception:
        return escritas
    return escritas


def indice_nvidia(pedido: int = 0) -> int:
    """Índice CUDA de la GPU NVIDIA. `pedido` si no se puede mirar."""
    try:
        import torch
    except Exception:
        return pedido
    try:
        if not torch.cuda.is_available():
            return pedido
        dispositivos = []
        for indice in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(indice)
            dispositivos.append(
                Dispositivo(
                    indice=indice,
                    nombre=str(getattr(props, "name", "") or ""),
                    vram_bytes=int(getattr(props, "total_memory", 0) or 0),
                )
            )
        return elegir_indice(dispositivos, pedido)
    except Exception:
        return pedido


def nombre_dispositivo(indice: int = 0) -> str | None:
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        return str(torch.cuda.get_device_name(indice))
    except Exception:
        return None
