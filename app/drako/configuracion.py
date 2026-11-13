"""Archivo de configuración local (JSON). Un solo escritor, reemplazo atómico."""

from __future__ import annotations

import json
import os
from pathlib import Path


class ConfiguracionDanada(Exception):
    """El archivo existe pero no se puede leer. No se borra solo."""


class ConfiguracionLocal:
    def __init__(self, directorio: Path):
        self.directorio = Path(directorio)
        self.ruta = self.directorio / "config.json"
        self.datos: dict = {}
        self.cargar()

    def cargar(self) -> None:
        if not self.ruta.is_file():
            self.datos = {}
            return
        try:
            texto = self.ruta.read_text(encoding="utf-8")
            cargado = json.loads(texto) if texto.strip() else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfiguracionDanada(
                f"No se pudo leer {self.ruta}. No se ha modificado."
            ) from exc
        if not isinstance(cargado, dict):
            raise ConfiguracionDanada(f"{self.ruta} no tiene un objeto JSON.")
        self.datos = cargado

    def guardar(self) -> None:
        self.directorio.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix(".json.tmp")
        texto = json.dumps(self.datos, ensure_ascii=False, indent=2)
        temporal.write_text(texto, encoding="utf-8")
        try:
            os.chmod(temporal, 0o600)
        except OSError:
            pass
        os.replace(temporal, self.ruta)
        try:
            os.chmod(self.ruta, 0o600)
        except OSError:
            pass
