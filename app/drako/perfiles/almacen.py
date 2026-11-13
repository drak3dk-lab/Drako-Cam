"""Perfiles de cara en la carpeta de datos de Drako Cam.

En Windows: %APPDATA%\\DrakoCam\\perfiles. Cada perfil es una carpeta.
Exportar junta el json y las fotos en un zip para otro PC.
"""

from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from app.ui.estudio.logica import extension_admitida, nombre_seguro

ESQUEMA = 1


@dataclass
class Perfil:
    id: str
    nombre: str
    aspecto: str
    calidad: str
    ajustes: dict
    fotos: list[Path] = field(default_factory=list)
    favorito: bool = False
    embedding: list[float] | None = None
    esquema: int = ESQUEMA

    @property
    def miniatura(self) -> Path | None:
        return self.fotos[0] if self.fotos else None


def migrar(datos: dict, conocidos: set[str] | None = None) -> dict:
    """Acepta un perfil viejo o incompleto. Ignora ajustes que ya no existen."""
    if not isinstance(datos, dict):
        raise ValueError("El perfil no es un archivo válido.")
    esquema = int(datos.get("esquema") or 1)
    if esquema > ESQUEMA:
        raise ValueError("Este perfil es de una versión más nueva de Drako Cam.")
    ajustes = datos.get("ajustes") or {}
    if not isinstance(ajustes, dict):
        ajustes = {}
    if conocidos is not None:
        ajustes = {clave: valor for clave, valor in ajustes.items() if clave in conocidos}
    return {
        "esquema": ESQUEMA,
        "id": str(datos.get("id") or uuid.uuid4()),
        "nombre": str(datos.get("nombre") or "Perfil").strip() or "Perfil",
        "aspecto": str(datos.get("aspecto") or "auto"),
        "calidad": str(datos.get("calidad") or "Auto"),
        "favorito": bool(datos.get("favorito") or False),
        "ajustes": ajustes,
        "fotos": [str(nombre) for nombre in (datos.get("fotos") or []) if nombre],
        "embedding": datos.get("embedding") if isinstance(datos.get("embedding"), list) else None,
    }


class AlmacenPerfiles:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)

    def asegurar(self) -> None:
        self.raiz.mkdir(parents=True, exist_ok=True)

    def listar(self) -> list[Perfil]:
        self.asegurar()
        perfiles = []
        for carpeta in sorted(self.raiz.iterdir(), key=lambda item: item.name):
            if not carpeta.is_dir():
                continue
            try:
                perfiles.append(self.cargar(carpeta.name))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        perfiles.sort(key=lambda perfil: (not perfil.favorito, perfil.nombre.lower()))
        return perfiles

    def cargar(self, ident: str) -> Perfil:
        carpeta = self._carpeta(ident)
        datos = json.loads((carpeta / "perfil.json").read_text(encoding="utf-8"))
        limpio = migrar(datos)
        fotos = []
        for nombre in limpio["fotos"]:
            ruta = carpeta / "fotos" / Path(nombre).name
            if ruta.is_file():
                fotos.append(ruta)
        return Perfil(
            id=carpeta.name,
            nombre=limpio["nombre"],
            aspecto=limpio["aspecto"],
            calidad=limpio["calidad"],
            ajustes=limpio["ajustes"],
            fotos=fotos,
            favorito=limpio["favorito"],
            embedding=limpio["embedding"],
            esquema=limpio["esquema"],
        )

    def crear(
        self,
        nombre: str,
        ajustes: dict,
        aspecto: str,
        calidad: str,
        fotos: list[Path],
        embedding: list[float] | None = None,
        conocidos: set[str] | None = None,
    ) -> Perfil:
        self.asegurar()
        ident = uuid.uuid4().hex[:12]
        return self._escribir(
            ident, nombre, ajustes, aspecto, calidad, fotos, False, embedding, conocidos
        )

    def renombrar(self, ident: str, nombre: str) -> Perfil:
        perfil = self.cargar(ident)
        perfil.nombre = nombre.strip() or perfil.nombre
        return self._escribir(
            perfil.id,
            perfil.nombre,
            perfil.ajustes,
            perfil.aspecto,
            perfil.calidad,
            perfil.fotos,
            perfil.favorito,
            perfil.embedding,
        )

    def duplicar(self, ident: str) -> Perfil:
        perfil = self.cargar(ident)
        return self.crear(
            f"{perfil.nombre} copia",
            perfil.ajustes,
            perfil.aspecto,
            perfil.calidad,
            perfil.fotos,
            perfil.embedding,
        )

    def favorito(self, ident: str, valor: bool) -> Perfil:
        perfil = self.cargar(ident)
        return self._escribir(
            perfil.id,
            perfil.nombre,
            perfil.ajustes,
            perfil.aspecto,
            perfil.calidad,
            perfil.fotos,
            valor,
            perfil.embedding,
        )

    def borrar(self, ident: str) -> None:
        carpeta = self._carpeta(ident)
        if carpeta.is_dir():
            shutil.rmtree(carpeta)

    def exportar(self, ident: str, destino: Path) -> Path:
        perfil = self.cargar(ident)
        destino = Path(destino)
        if destino.suffix.lower() != ".zip":
            destino = destino.with_suffix(".zip")
        with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as paquete:
            paquete.write(self._carpeta(ident) / "perfil.json", "perfil.json")
            for foto in perfil.fotos:
                paquete.write(foto, f"fotos/{foto.name}")
        return destino

    def importar(self, origen: Path, conocidos: set[str] | None = None) -> Perfil:
        origen = Path(origen)
        temporal = self.raiz / f"_import_{uuid.uuid4().hex[:8]}"
        temporal.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(origen) as paquete:
                paquete.extractall(temporal)
            datos = json.loads((temporal / "perfil.json").read_text(encoding="utf-8"))
            limpio = migrar(datos, conocidos)
            fotos = []
            carpeta_fotos = temporal / "fotos"
            if carpeta_fotos.is_dir():
                fotos = [
                    ruta
                    for ruta in carpeta_fotos.iterdir()
                    if ruta.is_file() and extension_admitida(ruta.name)
                ]
            return self.crear(
                limpio["nombre"],
                limpio["ajustes"],
                limpio["aspecto"],
                limpio["calidad"],
                fotos,
                limpio["embedding"],
                conocidos,
            )
        finally:
            shutil.rmtree(temporal, ignore_errors=True)

    def _escribir(
        self,
        ident: str,
        nombre: str,
        ajustes: dict,
        aspecto: str,
        calidad: str,
        fotos: list[Path],
        favorito: bool,
        embedding: list[float] | None,
        conocidos: set[str] | None = None,
    ) -> Perfil:
        self.asegurar()
        carpeta = self.raiz / ident
        destino_fotos = carpeta / "fotos"
        destino_fotos.mkdir(parents=True, exist_ok=True)
        nombres = []
        for foto in fotos:
            origen = Path(foto)
            if not origen.is_file() or not extension_admitida(origen.name):
                continue
            nombre_archivo = nombre_seguro(origen.name)
            destino = destino_fotos / nombre_archivo
            if origen.resolve() != destino.resolve():
                shutil.copy2(origen, destino)
            nombres.append(nombre_archivo)
        limpio = migrar(
            {
                "esquema": ESQUEMA,
                "id": ident,
                "nombre": nombre,
                "aspecto": aspecto,
                "calidad": calidad,
                "favorito": favorito,
                "ajustes": ajustes,
                "fotos": nombres,
                "embedding": embedding,
            },
            conocidos,
        )
        temporal = carpeta / "perfil.json.tmp"
        temporal.write_text(json.dumps(limpio, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(carpeta / "perfil.json")
        return self.cargar(ident)

    def _carpeta(self, ident: str) -> Path:
        return self.raiz / ident
