"""Huella del equipo: un hash, nunca el identificador en claro."""

from __future__ import annotations

import hashlib
import os
import re
import socket
from pathlib import Path


def _identificador_maquina() -> str:
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            ) as clave:
                valor, _ = winreg.QueryValueEx(clave, "MachineGuid")
            texto = str(valor).strip()
            if texto:
                return "win:" + texto
        except OSError:
            pass
    for ruta in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            texto = ruta.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if texto:
            return "mid:" + texto
    return "host:" + (socket.gethostname() or "equipo")


def huella_equipo(
    entorno: dict | None = None,
    lector_id=None,
) -> tuple[str, str]:
    """Devuelve (sha256 hex, nombre visible del equipo)."""
    env = os.environ if entorno is None else entorno
    nombre = str(env.get("DRAKO_CAM_EQUIPO", "")).strip() or socket.gethostname() or "equipo"
    nombre = re.sub(r"[\u0000-\u001f]+", " ", nombre).strip()[:80] or "equipo"
    forzada = str(env.get("DRAKO_CAM_HUELLA", "")).strip().lower()
    if forzada:
        if not re.fullmatch(r"[0-9a-f]{64}", forzada):
            raise ValueError("DRAKO_CAM_HUELLA debe ser un SHA-256 en hexadecimal.")
        return forzada, nombre
    identificador = lector_id() if lector_id is not None else _identificador_maquina()
    material = f"drako-cam-huella-v1\n{identificador}\n{nombre}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest(), nombre
