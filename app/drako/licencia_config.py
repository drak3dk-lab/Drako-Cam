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

URL_SERVIDOR = "https://drako-cam-licencias.drakocam.workers.dev"
CLAVE_PUBLICA_HEX = "151b6d87e1d578df4584774b7d13eb02ea47665aad01cff8cbd30c83d2d97155"
CONTACTO_TELEGRAM = "Drako_XX"

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


def contacto_telegram() -> str:
    """Usuario público de Telegram, sin @. Vacío si el valor no es un usuario válido."""
    texto = CONTACTO_TELEGRAM.strip().lstrip("@")
    if not texto or len(texto) > 32:
        return ""
    if any(caracter not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_" for caracter in texto):
        return ""
    return texto


def url_contacto_telegram() -> str:
    usuario = contacto_telegram()
    if not usuario:
        return ""
    return f"https://t.me/{usuario}"


def mensaje_contacto_telegram() -> str:
    usuario = contacto_telegram()
    if not usuario:
        return ""
    return (
        "Para recibir tu código de acceso, contacta con el administrador "
        f"por Telegram: @{usuario}"
    )


def anexo_contacto_telegram() -> str:
    frase = mensaje_contacto_telegram()
    url = url_contacto_telegram()
    if not frase:
        return ""
    if not url:
        return frase
    return f"{frase}\n{url}"


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
