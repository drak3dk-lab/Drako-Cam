"""Modo emisión: menos vista previa, más prioridad, mismo tope de VRAM.

La vista previa de Qt es la que se apaga. La cámara virtual sigue.
"""

from __future__ import annotations

import os


def debe_omitir_preview(control: dict | None) -> bool:
    if not control:
        return False
    return bool(control.get("ModoEmisionEnableToggle", False))


def fijar_prioridad(alta: bool, sistema: str | None = None) -> str:
    """Sube o devuelve la prioridad del proceso. No lanza si el SO lo impide."""
    sistema = sistema or os.name
    if sistema == "nt":
        try:
            import ctypes

            kernel = ctypes.windll.kernel32
            # HIGH_PRIORITY_CLASS / NORMAL_PRIORITY_CLASS
            clase = 0x00000080 if alta else 0x00000020
            ok = kernel.SetPriorityClass(kernel.GetCurrentProcess(), clase)
            if not ok:
                return "sin_permiso"
            return "alta" if alta else "normal"
        except Exception:
            return "sin_permiso"
    try:
        if alta:
            os.nice(-5)
            return "alta"
        return "normal"
    except Exception:
        return "sin_permiso"


def aplicar_modo(activo: bool, sistema: str | None = None) -> dict:
    prioridad = fijar_prioridad(activo, sistema=sistema)
    return {"activo": bool(activo), "preview": not bool(activo), "prioridad": prioridad}
