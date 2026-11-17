"""En Windows, ningún subproceso debe abrir una ventana de consola.

pythonw no tiene consola, pero cada subprocess de nvidia-smi, ffmpeg o
TensorRT sí crea una, salvo que se pida CREATE_NO_WINDOW. Esto lo aplica
a todos los Popen, run y check_output del proceso.
"""

from __future__ import annotations

import subprocess
import sys

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_instalado = False
_popen_original = subprocess.Popen


def aplicar_sin_consola(kwargs: dict) -> dict:
    """Suma CREATE_NO_WINDOW sin quitar otras banderas que ya vinieran."""
    flags = int(kwargs.get("creationflags") or 0)
    kwargs["creationflags"] = flags | _CREATE_NO_WINDOW
    return kwargs


def ocultar_consolas() -> None:
    """Sustituye subprocess.Popen una sola vez. En otros sistemas no hace nada."""
    global _instalado
    if _instalado or sys.platform != "win32":
        return
    _instalado = True
    original = subprocess.Popen

    class _PopenSinConsola(original):
        def __init__(self, *args, **kwargs):
            aplicar_sin_consola(kwargs)
            super().__init__(*args, **kwargs)

    subprocess.Popen = _PopenSinConsola


def restaurar_consolas() -> None:
    """Solo para pruebas: vuelve a dejar el Popen de la biblioteca estándar."""
    global _instalado
    subprocess.Popen = _popen_original
    _instalado = False
