"""Dirección pública del servidor de acceso y clave pública Ed25519.

La clave privada de firma no va aquí: solo existe como secreto del Worker.
La URL pública tampoco es un secreto. Se puede dejar en URL_SERVIDOR
después de desplegar, o pasarla con DRAKO_CAM_LICENCIA_URL.

Si CLAVE_PUBLICA_HEX tiene valor, el programa confía en esa clave y no
en la variable de entorno. La variable solo sirve mientras el archivo
sigue vacío (pruebas o el primer arranque, antes de pegar la clave).
"""

from __future__ import annotations

import os

URL_SERVIDOR = ""
CLAVE_PUBLICA_HEX = ""

GRACIA_HORAS_DEFECTO = 24
LATIDO_SEGUNDOS_DEFECTO = 60


def _entorno(entorno: dict | None) -> dict:
    return os.environ if entorno is None else entorno


def _bloque(datos: dict) -> dict:
    bloque = datos.get("licencia_servidor") if isinstance(datos, dict) else None
    return bloque if isinstance(bloque, dict) else {}


def parsear_clave_publica(texto: str) -> bytes | None:
    limpio = (texto or "").strip().lower()
    if len(limpio) != 64 or any(caracter not in "0123456789abcdef" for caracter in limpio):
        return None
    return bytes.fromhex(limpio)


def url_aceptada(url: str) -> bool:
    from urllib.parse import urlparse

    partes = urlparse((url or "").strip())
    if partes.scheme == "https" and partes.netloc:
        return True
    return partes.scheme == "http" and partes.hostname in {"127.0.0.1", "localhost"}


def resolver_url(datos: dict, entorno: dict | None = None) -> str:
    env = _entorno(entorno)
    candidatos = [
        str(env.get("DRAKO_CAM_LICENCIA_URL", "")).strip(),
        str(_bloque(datos).get("url", "")).strip(),
        URL_SERVIDOR.strip(),
    ]
    for candidato in candidatos:
        if candidato:
            return candidato.rstrip("/")
    return ""


def resolver_clave(datos: dict, entorno: dict | None = None) -> bytes | None:
    if CLAVE_PUBLICA_HEX.strip():
        return parsear_clave_publica(CLAVE_PUBLICA_HEX)
    env = _entorno(entorno)
    de_entorno = str(env.get("DRAKO_CAM_LICENCIA_CLAVE_PUBLICA", "")).strip()
    if de_entorno:
        return parsear_clave_publica(de_entorno)
    return parsear_clave_publica(str(_bloque(datos).get("clave_publica_hex", "")))


def gracia_local_segundos(datos: dict, entorno: dict | None = None) -> int | None:
    """Horas pedidas en el equipo. Solo puede acortar la gracia firmada por el servidor."""
    env = _entorno(entorno)
    bruto = str(env.get("DRAKO_CAM_LICENCIA_GRACIA_HORAS", "")).strip()
    if not bruto and _bloque(datos).get("gracia_horas") not in (None, ""):
        bruto = str(_bloque(datos).get("gracia_horas")).strip()
    if not bruto:
        return None
    try:
        horas = float(bruto)
    except ValueError:
        return None
    if horas < 0:
        return 0
    return int(horas * 3600)
