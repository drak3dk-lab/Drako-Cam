"""Descarga resumible, con reintentos, hash y varias a la vez.

El archivo a medias se guarda como ``<destino>.parcial`` y se continúa con
HTTP Range. Si ya existe el archivo final y el SHA-256 coincide, no se vuelve
a bajar.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import requests

from app.helpers.integrity_checker import check_file_integrity

CHUNK = 1024 * 1024
INTENTOS = 4
TIMEOUT = (10, 60)
TRABAJADORES = 3

ProgresoFn = Callable[[str, int, int, float | None, int, int], None]
DormirFn = Callable[[float], None]


@dataclass
class Trabajo:
    nombre: str
    url: str
    destino: str
    hash_esperado: str | None
    bytes_estimados: int = 0


@dataclass
class ResultadoArchivo:
    nombre: str
    estado: str
    detalle: str = ""


@dataclass
class ResultadoLote:
    archivos: list[ResultadoArchivo] = field(default_factory=list)

    @property
    def correcto(self) -> bool:
        if not self.archivos:
            return False
        return all(item.estado in ("ok", "omitido") for item in self.archivos)

    @property
    def sin_conexion(self) -> bool:
        fallos = [
            item for item in self.archivos if item.estado not in ("ok", "omitido")
        ]
        return bool(fallos) and all(item.estado == "sin_conexion" for item in fallos)

    @property
    def cancelado(self) -> bool:
        return any(item.estado == "cancelado" for item in self.archivos)


def _sesion_nueva() -> requests.Session:
    sesion = requests.Session()
    sesion.headers["User-Agent"] = "DrakoCam"
    return sesion


def _parcial(destino: str) -> Path:
    return Path(str(destino) + ".parcial")


def _espera(intento: int) -> float:
    """intento es 1 en el primer fallo. 1 s, 2 s, 4 s…"""
    return float(2 ** (intento - 1))


def _es_red(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ),
    )


def _hash_ok(ruta: Path, esperado: str | None, omitir_hash: bool) -> bool:
    if omitir_hash or not esperado:
        return True
    return check_file_integrity(str(ruta), esperado)


def descargar_uno(
    trabajo: Trabajo,
    *,
    sesion: requests.Session | None = None,
    cancelado: threading.Event | None = None,
    omitir_hash: bool = False,
    intentos: int = INTENTOS,
    dormir: DormirFn | None = None,
    chunk_size: int = CHUNK,
    al_bytes: Callable[[str, int, int], None] | None = None,
) -> ResultadoArchivo:
    """Descarga un archivo. No lanza: devuelve el estado."""
    cancelado = cancelado or threading.Event()
    dormir = dormir or time.sleep
    sesion = sesion or _sesion_nueva()
    destino = Path(trabajo.destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = _parcial(trabajo.destino)
    ultimo_detalle = ""
    fue_red = True

    if cancelado.is_set():
        return ResultadoArchivo(trabajo.nombre, "cancelado")

    if destino.is_file() and destino.stat().st_size > 0:
        if _hash_ok(destino, trabajo.hash_esperado, omitir_hash):
            return ResultadoArchivo(trabajo.nombre, "omitido")
        try:
            destino.unlink()
        except OSError as exc:
            return ResultadoArchivo(trabajo.nombre, "error", str(exc))

    for intento in range(1, intentos + 1):
        if cancelado.is_set():
            return ResultadoArchivo(trabajo.nombre, "cancelado")
        try:
            hecho = parcial.stat().st_size if parcial.is_file() else 0
            cabeceras = {"Range": f"bytes={hecho}-"} if hecho else {}
            with sesion.get(
                trabajo.url,
                stream=True,
                timeout=TIMEOUT,
                headers=cabeceras,
            ) as respuesta:
                if respuesta.status_code == 416:
                    parcial.unlink(missing_ok=True)
                    hecho = 0
                    respuesta.close()
                    continue
                respuesta.raise_for_status()
                if respuesta.status_code == 200 and hecho:
                    hecho = 0
                elif respuesta.status_code not in (200, 206):
                    raise requests.exceptions.HTTPError(
                        f"HTTP {respuesta.status_code}", response=respuesta
                    )
                total_cabecera = respuesta.headers.get("Content-Range", "")
                if "/" in total_cabecera:
                    total = int(total_cabecera.rsplit("/", 1)[-1])
                else:
                    restante = int(respuesta.headers.get("Content-Length", "0") or 0)
                    total = hecho + restante if restante else trabajo.bytes_estimados
                modo = "ab" if hecho and respuesta.status_code == 206 else "wb"
                if modo == "wb":
                    hecho = 0
                with parcial.open(modo) as salida:
                    for trozo in respuesta.iter_content(chunk_size=chunk_size):
                        if cancelado.is_set():
                            return ResultadoArchivo(trabajo.nombre, "cancelado")
                        if not trozo:
                            continue
                        salida.write(trozo)
                        hecho += len(trozo)
                        if al_bytes:
                            al_bytes(trabajo.nombre, hecho, total or hecho)
            if not _hash_ok(parcial, trabajo.hash_esperado, omitir_hash):
                parcial.unlink(missing_ok=True)
                ultimo_detalle = "el hash no coincide"
                fue_red = False
            else:
                os.replace(parcial, destino)
                return ResultadoArchivo(trabajo.nombre, "ok")
        except requests.exceptions.RequestException as exc:
            ultimo_detalle = str(exc)
            fue_red = _es_red(exc)
        if intento < intentos and not cancelado.is_set():
            dormir(_espera(intento))

    if cancelado.is_set():
        return ResultadoArchivo(trabajo.nombre, "cancelado", ultimo_detalle)
    estado = "sin_conexion" if fue_red else "error"
    return ResultadoArchivo(trabajo.nombre, estado, ultimo_detalle)


def descargar_lote(
    trabajos: list[Trabajo],
    *,
    trabajadores: int = TRABAJADORES,
    sesion_fabrica: Callable[[], requests.Session] | None = None,
    cancelado: threading.Event | None = None,
    omitir_hash: bool = False,
    intentos: int = INTENTOS,
    dormir: DormirFn | None = None,
    chunk_size: int = CHUNK,
    al_progreso: ProgresoFn | None = None,
) -> ResultadoLote:
    """Descarga en paralelo (como mucho 3). El progreso es el total del lote."""
    if not trabajos:
        return ResultadoLote()
    cancelado = cancelado or threading.Event()
    sesion_fabrica = sesion_fabrica or _sesion_nueva
    dormidos = dormir or time.sleep
    cupo = max(1, min(3, trabajadores, len(trabajos)))
    lock = threading.Lock()
    hechos: dict[str, int] = {item.nombre: 0 for item in trabajos}
    totales: dict[str, int] = {item.nombre: item.bytes_estimados for item in trabajos}
    listos = 0
    inicio = time.monotonic()
    descargado_red = 0
    base_red: dict[str, int] = {}

    def _avisar(nombre: str) -> None:
        if not al_progreso:
            return
        with lock:
            suma_hecha = sum(hechos.values())
            suma_total = sum(totales.values()) or suma_hecha
            velocidad = descargado_red / max(time.monotonic() - inicio, 0.05)
            restante = max(0, suma_total - suma_hecha)
            eta = (restante / velocidad) if velocidad > 1 else None
            hechos_ahora = suma_hecha
            total_ahora = suma_total
            cuantos = listos
        al_progreso(nombre, hechos_ahora, total_ahora, eta, cuantos, len(trabajos))

    def _uno(trabajo: Trabajo) -> ResultadoArchivo:
        nonlocal listos, descargado_red
        sesion = sesion_fabrica()

        def _al_bytes(nombre: str, hecho: int, total: int) -> None:
            nonlocal descargado_red
            with lock:
                anterior = base_red.get(nombre, 0)
                if hecho > anterior:
                    descargado_red += hecho - anterior
                    base_red[nombre] = hecho
                hechos[nombre] = max(hechos[nombre], hecho)
                if total:
                    totales[nombre] = max(totales[nombre], total)
            _avisar(nombre)

        resultado = descargar_uno(
            trabajo,
            sesion=sesion,
            cancelado=cancelado,
            omitir_hash=omitir_hash,
            intentos=intentos,
            dormir=dormidos,
            chunk_size=chunk_size,
            al_bytes=_al_bytes,
        )
        with lock:
            if resultado.estado in ("ok", "omitido"):
                listos += 1
                tam = totales[trabajo.nombre] or trabajo.bytes_estimados
                if resultado.estado == "omitido":
                    hechos[trabajo.nombre] = tam
                    totales[trabajo.nombre] = tam
        _avisar(trabajo.nombre)
        return resultado

    resultados: list[ResultadoArchivo] = []
    with ThreadPoolExecutor(max_workers=cupo) as pool:
        futuros = [pool.submit(_uno, trabajo) for trabajo in trabajos]
        for futuro in as_completed(futuros):
            resultados.append(futuro.result())
    orden = {trabajo.nombre: indice for indice, trabajo in enumerate(trabajos)}
    resultados.sort(key=lambda item: orden.get(item.nombre, 0))
    return ResultadoLote(resultados)


def download_file(
    model_name: str,
    file_path: str,
    correct_hash: str | None,
    url: str,
    skip_hash_check: bool = False,
) -> bool:
    """Compatibilidad con el descargador anterior. True si el archivo queda bien."""
    resultado = descargar_lote(
        [
            Trabajo(
                nombre=model_name,
                url=url,
                destino=file_path,
                hash_esperado=correct_hash,
            )
        ],
        trabajadores=1,
        omitir_hash=skip_hash_check,
    )
    if not resultado.archivos:
        return False
    return resultado.archivos[0].estado in ("ok", "omitido")
