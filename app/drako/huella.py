"""Huella del equipo: un hash de varios identificadores de hardware.

El nombre del PC no entra en el hash. Si la persona no escribe un nombre,
el programa muestra PC- y ocho caracteres del hash, no el nombre de Windows.
Un valor DRAKO_CAM_HUELLA de 64 hexadecimales lo sustituye, solo para pruebas.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
from pathlib import Path


def huella_equipo(
    entorno: dict | None = None,
    lector_id=None,
) -> tuple[str, str]:
    """Devuelve (sha256 hex, nombre visible). La huella no revela el hardware."""
    env = os.environ if entorno is None else entorno
    forzada = str(env.get("DRAKO_CAM_HUELLA", "")).strip().lower()
    if forzada:
        if not re.fullmatch(r"[0-9a-f]{64}", forzada):
            raise ValueError("DRAKO_CAM_HUELLA debe ser un SHA-256 en hexadecimal.")
        return forzada, _nombre(env, forzada)
    if lector_id is not None:
        fuentes = [str(lector_id()).strip()]
    else:
        fuentes = recoger_fuentes()
    fuentes = [fuente for fuente in fuentes if fuente]
    if not fuentes:
        raise RuntimeError("No se pudo leer un identificador de este equipo.")
    material = "drako-cam-huella-v2\n" + "\n".join(sorted(fuentes))
    huella = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return huella, _nombre(env, huella)


def recoger_fuentes() -> list[str]:
    """Identificadores de hardware. Sin el nombre del PC ni datos de la persona."""
    fuentes: list[str] = []
    maquina = _identificador_maquina()
    if maquina:
        fuentes.append("maquina:" + maquina)
    volumen = _serie_volumen()
    if volumen:
        fuentes.append("volumen:" + volumen)
    placa = _uuid_placa()
    if placa:
        fuentes.append("placa:" + placa)
    return fuentes


def _nombre(entorno: dict, huella: str) -> str:
    pedido = str(entorno.get("DRAKO_CAM_EQUIPO", "")).strip()
    pedido = re.sub(r"[\u0000-\u001f]+", " ", pedido).strip()[:80]
    if pedido:
        return pedido
    return f"PC-{huella[:8]}"


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
            return ""
    for ruta in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            texto = ruta.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if texto:
            return "mid:" + texto
    return ""


def _serie_volumen() -> str:
    if platform.system() != "Windows":
        return ""
    orden = (
        "Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\" "
        "| Select-Object -ExpandProperty VolumeSerialNumber"
    )
    return _powershell(orden, "vol")


def _uuid_placa() -> str:
    if platform.system() == "Windows":
        orden = (
            "Get-CimInstance Win32_ComputerSystemProduct "
            "| Select-Object -ExpandProperty UUID"
        )
        return _powershell(orden, "uuid")
    try:
        texto = Path("/sys/class/dmi/id/product_uuid").read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not texto or texto.lower() in {"none", "ffffffff-ffff-ffff-ffff-ffffffffffff"}:
        return ""
    return "linux:" + texto


def _powershell(orden: str, prefijo: str) -> str:
    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", orden],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    lineas = [linea.strip() for linea in (resultado.stdout or "").splitlines() if linea.strip()]
    texto = lineas[-1] if lineas else ""
    if not texto or texto.lower() in {"none", "ffffffff-ffff-ffff-ffff-ffffffffffff"}:
        return ""
    return f"win:{prefijo}:{texto}"
