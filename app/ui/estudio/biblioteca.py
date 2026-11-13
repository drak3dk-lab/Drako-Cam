"""Fotos de la biblioteca, en la carpeta de datos de Drako Cam.

No guarda embeddings ni imágenes en el repositorio. Solo copia el
archivo que la persona elige y recuerda el nombre.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.ui.estudio.logica import extension_admitida, nombre_seguro


@dataclass(frozen=True)
class Foto:
    id: str
    nombre: str
    ruta: Path
    favorita: bool


class Biblioteca:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        self.carpeta = self.raiz / "biblioteca"
        self.ruta_estado = self.raiz / "estudio.json"

    def asegurar(self) -> None:
        self.carpeta.mkdir(parents=True, exist_ok=True)

    def estado(self) -> dict:
        if not self.ruta_estado.is_file():
            return {}
        try:
            datos = json.loads(self.ruta_estado.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return datos if isinstance(datos, dict) else {}

    def guardar_estado(self, **cambios: object) -> dict:
        datos = self.estado()
        datos.update(cambios)
        self.raiz.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta_estado.with_suffix(".json.tmp")
        temporal.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporal.replace(self.ruta_estado)
        return datos

    def listar(self) -> list[Foto]:
        self.asegurar()
        favoritas = set(self.estado().get("favoritas") or [])
        fotos: list[Foto] = []
        for ruta in sorted(self.carpeta.iterdir(), key=lambda item: item.name.lower()):
            if not ruta.is_file() or not extension_admitida(ruta.name):
                continue
            fotos.append(
                Foto(
                    id=ruta.name,
                    nombre=ruta.stem,
                    ruta=ruta,
                    favorita=ruta.name in favoritas,
                )
            )
        orden = list(self.estado().get("favoritas") or [])
        if not orden:
            return fotos
        peso = {nombre: indice for indice, nombre in enumerate(orden)}
        fotos.sort(key=lambda foto: (not foto.favorita, peso.get(foto.id, 10_000), foto.nombre.lower()))
        return fotos

    def anadir(self, origen: Path) -> Foto:
        origen = Path(origen)
        if not origen.is_file():
            raise FileNotFoundError(str(origen))
        if not extension_admitida(origen.name):
            raise ValueError("Usa una foto JPG, PNG, WEBP o BMP.")
        self.asegurar()
        destino = self._destino_libre(nombre_seguro(origen.name))
        if origen.resolve() != destino.resolve():
            shutil.copy2(origen, destino)
        return Foto(id=destino.name, nombre=destino.stem, ruta=destino, favorita=False)

    def fijar_favorita(self, ident: str, favorita: bool) -> list[str]:
        estado = self.estado()
        actuales = [nombre for nombre in (estado.get("favoritas") or []) if isinstance(nombre, str)]
        if favorita and ident not in actuales:
            actuales.append(ident)
        if not favorita:
            actuales = [nombre for nombre in actuales if nombre != ident]
        self.guardar_estado(favoritas=actuales)
        return actuales

    def recordar(self, **cambios: object) -> None:
        self.guardar_estado(**cambios)

    def ajustes_de(self, ident: str) -> dict:
        todos = self.estado().get("ajustes") or {}
        if not isinstance(todos, dict):
            return {}
        dato = todos.get(ident) or {}
        return dict(dato) if isinstance(dato, dict) else {}

    def guardar_ajustes(self, ident: str, ajustes: dict) -> None:
        todos = self.estado().get("ajustes") or {}
        if not isinstance(todos, dict):
            todos = {}
        else:
            todos = dict(todos)
        todos[ident] = ajustes
        self.guardar_estado(ajustes=todos)

    def _destino_libre(self, nombre: str) -> Path:
        candidato = self.carpeta / nombre
        if not candidato.exists():
            return candidato
        tallo = candidato.stem
        sufijo = candidato.suffix
        indice = 2
        while True:
            prueba = self.carpeta / f"{tallo}-{indice}{sufijo}"
            if not prueba.exists():
                return prueba
            indice += 1
