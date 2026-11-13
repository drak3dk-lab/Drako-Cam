"""Dónde vive la configuración local de Drako Cam.

Nada de esto se versiona. En Windows cae en %APPDATA%\\DrakoCam.
DRAKO_CAM_DATA_DIR permite mover la carpeta (útil en pruebas).
"""

from __future__ import annotations

import os
from pathlib import Path


def directorio_datos(entorno: os._Environ | dict | None = None) -> Path:
    """Carpeta de configuración, registro cifrado y cola de avisos."""
    env = os.environ if entorno is None else entorno
    forzado = str(env.get("DRAKO_CAM_DATA_DIR", "")).strip()
    if forzado:
        return Path(forzado).expanduser()
    if os.name == "nt":
        base = str(env.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return Path(base) / "DrakoCam"
    base = str(env.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return Path(base) / "DrakoCam"


def directorio_perfiles(entorno: os._Environ | dict | None = None) -> Path:
    """Perfiles de cara. En Windows: %APPDATA%\\DrakoCam\\perfiles."""
    return directorio_datos(entorno) / "perfiles"
