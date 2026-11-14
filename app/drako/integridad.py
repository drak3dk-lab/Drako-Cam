"""Comprueba que los archivos críticos no se han cambiado.

El manifiesto lo escribe la compilación. En el código fuente, si no hay
manifiesto, no se bloquea el desarrollo. En el .exe compilado, tiene que estar
y coincidir. No hay claves ni tokens aquí: solo hashes SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

NOMBRE = "integridad_manifiesto.json"


def raiz_aplicacion() -> Path:
    if en_compilado():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def en_compilado() -> bool:
    if getattr(sys, "frozen", False):
        return True
    nombre = Path(sys.executable).name.lower()
    return nombre in {"drakocam.exe", "drako-cam.exe"}


def _aviso(detalle: str) -> str:
    from app.drako.licencia_config import mensaje_contacto_telegram

    contacto = mensaje_contacto_telegram()
    if contacto:
        return detalle + " " + contacto + "."
    return detalle


def verificar_instalacion(raiz: Path | None = None) -> tuple[bool, str]:
    base = raiz if raiz is not None else raiz_aplicacion()
    manifiesto = base / NOMBRE
    if not manifiesto.is_file():
        if en_compilado() or not (base / "main.py").is_file():
            return False, _aviso(
                "Falta la comprobación de integridad de Drako Cam. El directo no puede empezar."
            )
        return True, ""
    try:
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
        archivos = datos.get("archivos")
        if not isinstance(archivos, dict) or not archivos:
            raise ValueError("manifiesto vacío")
    except (OSError, ValueError, json.JSONDecodeError):
        return False, _aviso("La comprobación de integridad está dañada.")
    for relativo, esperado in archivos.items():
        if not isinstance(relativo, str) or not isinstance(esperado, str):
            return False, "La comprobación de integridad no es válida."
        if ".." in Path(relativo).parts or Path(relativo).is_absolute():
            return False, "La comprobación de integridad no es válida."
        ruta = base / relativo
        try:
            digest = hashlib.sha256(ruta.read_bytes()).hexdigest()
        except OSError:
            return False, "Falta un archivo necesario de Drako Cam."
        if digest.lower() != esperado.strip().lower():
            return False, _aviso("Drako Cam se ha modificado y no puede continuar.")
    return True, ""


def escribir_manifiesto(raiz: Path, relativos: list[str], destino: Path | None = None) -> Path:
    archivos = {}
    for relativo in relativos:
        ruta = raiz / relativo
        archivos[relativo.replace("\\", "/")] = hashlib.sha256(ruta.read_bytes()).hexdigest()
    salida = destino or (raiz / NOMBRE)
    salida.write_text(
        json.dumps({"v": 1, "archivos": archivos}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return salida
