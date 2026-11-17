"""Descarga reanudable de un modelo, con hash y reintentos.

El archivo crece en ``.part``. Si se corta la red, el siguiente intento
pide ``Range: bytes=<ya_bajado>-`` y sigue. Si el servidor ignora el
rango, ese archivo se empieza de nuevo. Al terminar se comprueba el
SHA-256: si coincide, ``.part`` pasa al nombre final; si no, se borra
y se vuelve a bajar.

Los cortes de red no tienen tope: la espera crece (3, 5, 10, 30 y
luego 60 segundos) y, cuando vuelve internet, continúa.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import requests
import urllib3

from app.helpers.integrity_checker import check_file_integrity

DOWNLOAD_CHUNK_SIZE = 1024 * 1024
ESPERAS_SEGUNDOS = (3, 5, 10, 30, 60)
REQUEST_TIMEOUT = (15, 60)
CODIGOS_PERMANENTES = frozenset({400, 401, 403, 404, 410})
# Un 404 no se arregla esperando. Tres respuestas iguales sí son un fallo real.
TOPE_PERMANENTE = 3

_log = logging.getLogger("drako.descarga")
if not _log.handlers:
    _log.addHandler(logging.NullHandler())


def espera_del_intento(fallo: int) -> int:
    """Segundos a esperar tras el fallo ``fallo`` (1 = el primero)."""
    indice = min(max(int(fallo), 1), len(ESPERAS_SEGUNDOS)) - 1
    return ESPERAS_SEGUNDOS[indice]


def _decir(mensaje: str, nivel: str = "info") -> None:
    print(mensaje, flush=True)
    if nivel == "error":
        _log.error(mensaje)
    elif nivel == "aviso":
        _log.warning(mensaje)
    else:
        _log.info(mensaje)


def _mb(cantidad: int) -> str:
    return f"{cantidad / (1024 * 1024):.1f} MB"


def _borrar(ruta: str) -> None:
    try:
        if ruta and os.path.isfile(ruta):
            os.remove(ruta)
    except OSError as exc:
        _decir(f"[AVISO] No pude borrar {ruta}: {exc}", "aviso")


def _rango_util(cabecera: str | None, ya: int) -> int | None:
    """Inicio que confirma el servidor, o None si el rango no sirve."""
    if not cabecera:
        return None
    texto = cabecera.strip().lower()
    if not texto.startswith("bytes"):
        return None
    try:
        espec, _, total = texto.split(" ", 1)[1].partition("/")
        inicio_texto, _, _fin = espec.partition("-")
        inicio = int(inicio_texto)
    except (ValueError, IndexError):
        return None
    if inicio != ya:
        return None
    try:
        return int(total)
    except ValueError:
        return None


def _abrir_respuesta(url: str, ya: int):
    cabeceras = {
        "User-Agent": "DrakoCam",
        "Accept-Encoding": "identity",
    }
    if ya > 0:
        cabeceras["Range"] = f"bytes={ya}-"
    return requests.get(
        url,
        headers=cabeceras,
        stream=True,
        timeout=REQUEST_TIMEOUT,
    )


def download_file(
    model_name: str,
    file_path: str,
    correct_hash: str,
    url: str,
    skip_hash_check: bool = False,
    al_progreso=None,
    al_estado=None,
    esperar=time.sleep,
    max_intentos: int | None = None,
) -> bool:
    """Baja ``url`` a ``file_path`` y solo devuelve True si el hash cuadra.

    ``max_intentos`` queda en None: se reintenta sin tope. Los tests pueden
    poner un tope. Un HTTP 400/401/403/404/410 se rinde a la tercera,
    porque no es un corte de red.
    """
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    destino = Path(file_path)
    parcial = str(destino) + ".part"

    if destino.is_file():
        if skip_hash_check:
            _decir(
                f"[INFO] «{model_name}» ya está. No compruebo el hash "
                "(modelos optimizados)."
            )
            _borrar(parcial)
            return True
        if correct_hash and check_file_integrity(str(destino), correct_hash):
            _decir(f"[INFO] «{model_name}» ya está y el hash coincide.")
            _borrar(parcial)
            return True
        _decir(
            f"[AVISO] «{model_name}» está en disco pero el hash no coincide. "
            "Lo bajo de nuevo.",
            "aviso",
        )
        _borrar(str(destino))
        _borrar(parcial)

    fallo = 0
    permanentes = 0
    while True:
        if max_intentos is not None and fallo >= max_intentos:
            _decir(
                f"[ERROR] «{model_name}» no quedó verificado tras {fallo} intentos.",
                "error",
            )
            return False
        try:
            if _bajar_una_vez(
                model_name,
                str(destino),
                parcial,
                correct_hash,
                url,
                al_progreso,
                al_estado,
            ):
                return True
            fallo += 1
            _borrar(parcial)
            _borrar(str(destino))
            _pausa(model_name, fallo, "el hash no coincidió", al_estado, esperar)
        except requests.HTTPError as exc:
            codigo = exc.response.status_code if exc.response is not None else 0
            fallo += 1
            if codigo in CODIGOS_PERMANENTES:
                permanentes += 1
                _decir(
                    f"[ERROR] El servidor respondió {codigo} al pedir «{model_name}».",
                    "error",
                )
                if permanentes >= TOPE_PERMANENTE:
                    _decir(
                        f"[ERROR] «{model_name}» no está en el servidor "
                        f"({codigo}). No sigo esperando.",
                        "error",
                    )
                    return False
            else:
                _decir(
                    f"[AVISO] Error HTTP al bajar «{model_name}»: {exc}",
                    "aviso",
                )
            _pausa(model_name, fallo, "falló la descarga", al_estado, esperar)
        except requests.RequestException as exc:
            fallo += 1
            ya = _tamano(parcial)
            _decir(
                f"[AVISO] Se cortó la red al bajar «{model_name}» "
                f"({_mb(ya)} guardados): {exc}",
                "aviso",
            )
            _pausa(model_name, fallo, "se cortó la red", al_estado, esperar)
        except OSError as exc:
            fallo += 1
            _decir(
                f"[AVISO] No pude escribir «{model_name}»: {exc}",
                "aviso",
            )
            _pausa(model_name, fallo, "no pude escribir el archivo", al_estado, esperar)


def _pausa(model_name: str, fallo: int, motivo: str, al_estado, esperar) -> None:
    segundos = espera_del_intento(fallo)
    texto = f"Reintentando... {model_name}"
    _decir(
        f"[AVISO] {texto} ({motivo}). Intento {fallo}. "
        f"Espero {segundos} s y sigo desde lo ya bajado.",
        "aviso",
    )
    if al_estado is not None:
        al_estado(texto)
    esperar(segundos)


def _tamano(ruta: str) -> int:
    try:
        return os.path.getsize(ruta) if os.path.isfile(ruta) else 0
    except OSError:
        return 0


def _bajar_una_vez(
    model_name: str,
    destino: str,
    parcial: str,
    correct_hash: str,
    url: str,
    al_progreso,
    al_estado,
) -> bool:
    ya = _tamano(parcial)
    if ya > 0:
        _decir(
            f"[INFO] «{model_name}» sigue desde {_mb(ya)}. "
            f"Pido el resto con Range bytes={ya}-."
        )
    else:
        _decir(f"[INFO] Bajando «{model_name}».")
    if al_estado is not None and ya <= 0:
        al_estado(f"Bajando {model_name}")

    respuesta = _abrir_respuesta(url, ya)
    try:
        codigo = respuesta.status_code
        if codigo == 416:
            _decir(
                f"[AVISO] El servidor dice que «{model_name}» ya no tiene más bytes. "
                "Compruebo lo guardado.",
                "aviso",
            )
        elif ya > 0 and codigo == 206:
            total = _rango_util(respuesta.headers.get("Content-Range"), ya)
            if total is None:
                _decir(
                    f"[AVISO] La respuesta de rango de «{model_name}» no cuadra. "
                    "Empiezo ese archivo de nuevo.",
                    "aviso",
                )
                ya = 0
                _borrar(parcial)
                respuesta.close()
                respuesta = _abrir_respuesta(url, 0)
                respuesta.raise_for_status()
                codigo = respuesta.status_code
                total = int(respuesta.headers.get("Content-Length", 0) or 0)
            else:
                _decir(f"[INFO] El servidor continúa «{model_name}» desde {_mb(ya)}.")
        elif ya > 0 and codigo == 200:
            _decir(
                f"[AVISO] El servidor no acepta continuar «{model_name}». "
                "Empiezo ese archivo de nuevo.",
                "aviso",
            )
            ya = 0
            _borrar(parcial)
            total = int(respuesta.headers.get("Content-Length", 0) or 0)
        else:
            respuesta.raise_for_status()
            total = int(respuesta.headers.get("Content-Length", 0) or 0)
            if ya > 0:
                ya = 0
                _borrar(parcial)

        if codigo != 416:
            modo = "ab" if ya > 0 and codigo == 206 else "wb"
            if modo == "wb":
                ya = 0
            ultimo_aviso = time.monotonic()
            with open(parcial, modo) as salida:
                try:
                    # raw.stream entrega los bytes ya leídos antes de avisar
                    # de que la conexión se cortó. iter_content se los traga.
                    for trozo in respuesta.raw.stream(
                        DOWNLOAD_CHUNK_SIZE, decode_content=False
                    ):
                        if not trozo:
                            continue
                        salida.write(trozo)
                        ya += len(trozo)
                        ahora = time.monotonic()
                        if al_progreso is not None and (ahora - ultimo_aviso) >= 0.4:
                            ultimo_aviso = ahora
                            al_progreso(ya, total)
                except (
                    requests.RequestException,
                    urllib3.exceptions.HTTPError,
                    urllib3.exceptions.ProtocolError,
                ) as exc:
                    salida.flush()
                    if isinstance(exc, requests.RequestException):
                        raise
                    raise requests.RequestException(str(exc)) from exc
                salida.flush()
                try:
                    os.fsync(salida.fileno())
                except OSError:
                    pass
            if al_progreso is not None:
                al_progreso(ya, total if total else ya)
            if total and ya < total:
                raise requests.RequestException(
                    f"«{model_name}» se cortó en {_mb(ya)} de {_mb(total)}."
                )
    finally:
        respuesta.close()

    if not os.path.isfile(parcial) or os.path.getsize(parcial) == 0:
        raise requests.RequestException(
            f"«{model_name}» no dejó datos en el archivo temporal."
        )

    if not correct_hash:
        _decir(
            f"[AVISO] «{model_name}» no tiene hash de referencia. Lo dejo igualmente.",
            "aviso",
        )
        os.replace(parcial, destino)
        return True

    if al_estado is not None:
        al_estado(f"Comprobando el hash de {model_name}")
    _decir(f"[INFO] Comprobando el hash de «{model_name}».")
    if not check_file_integrity(parcial, correct_hash):
        _decir(
            f"[AVISO] El hash de «{model_name}» no coincide. Lo borro y lo bajo otra vez.",
            "aviso",
        )
        return False

    os.replace(parcial, destino)
    _decir(f"[INFO] «{model_name}» quedó completo y el hash coincide.")
    _decir(f"[INFO] Guardado en {destino}.")
    return True


# Lote en segundo plano. Lo usa el panel de modelos. El arranque y el
# instalador usan download_file (reintento sin tope, archivo .part).
# Este lote solo debe recibir los modelos de ORDEN_REQUERIDO.

CHUNK = DOWNLOAD_CHUNK_SIZE
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

