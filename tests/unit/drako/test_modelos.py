"""Catálogo esencial, descarga resumible y reutilización de lo ya bajado."""

from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

from app.drako.catalogo_modelos import (
    ESENCIAL,
    archivo_presente,
    esenciales,
    fichas,
    opcionales,
    suma_bytes,
    texto_progreso,
    texto_tamano,
)
from app.helpers.downloader import Trabajo, descargar_lote, descargar_uno
from app.processors.models_data import models_list


def test_cada_modelo_del_registro_esta_clasificado():
    nombres = [item["model_name"] for item in models_list]
    fichas_nombres = [item.nombre for item in fichas()]
    assert fichas_nombres == nombres
    assert all(item.porque.strip() for item in fichas())
    assert all(item.bytes > 0 for item in fichas())
    clases = {item.clase for item in fichas()}
    assert clases == {ESENCIAL}


def test_el_camino_en_vivo_es_el_conjunto_esencial():
    nombres = {item.nombre for item in esenciales()}
    assert nombres == {
        "Inswapper128",
        "Inswapper128ArcFace",
        "SCRFD2.5g",
        "FaceLandmark203",
        "Occluder",
        "FaceParser",
        "GFPGANv1.4",
        "GPENBFR256",
    }
    assert opcionales() == []
    for excluido in (
        "DeoldifyArt",
        "RefLdm",
        "VQGAN",
        "FaceReaging",
        "LivePortraitWarpingSpade",
        "GhostFacev1",
        "SimSwap512",
        "AlphaFace",
        "XSeg",
        "RetinaFace",
    ):
        assert excluido not in nombres


def test_el_primer_arranque_pesa_menos_que_el_catalogo():
    esencial = suma_bytes(esenciales())
    assert esencial == 1_136_934_120
    assert texto_tamano(esencial) == "1,14 GB"
    assert esencial < 2_000_000_000


def test_la_documentacion_lista_cada_modelo_y_los_totales():
    texto = Path("docs/modelos.md").read_text(encoding="utf-8")
    assert "1,14 GB" in texto
    assert "17,36 GB" in texto
    for item in fichas():
        assert item.nombre in texto


def test_el_progreso_dice_el_total_y_lo_que_queda():
    linea = texto_progreso("Inswapper128", 500_000_000, 1_178_796_654, 90, 2, 9)
    assert "Inswapper128" in linea
    assert "GB" in linea
    assert "quedan" in linea
    assert "1 min 30 s" in linea


def test_por_defecto_solo_pide_esenciales(monkeypatch):
    import download_models
    from app.helpers.downloader import ResultadoArchivo, ResultadoLote

    vistos: dict[str, list[str]] = {}

    def falso(nombres, **_kwargs):
        vistos["nombres"] = list(nombres)
        return ResultadoLote(
            [ResultadoArchivo(nombre, "omitido") for nombre in nombres]
        )

    monkeypatch.setattr(download_models, "descargar_nombres", falso)
    assert download_models.descargar_modelos() is True
    assert vistos["nombres"] == [item.nombre for item in esenciales()]


def test_el_manifiesto_evita_repetir_la_comprobacion(tmp_path, monkeypatch):
    from app.drako.catalogo_modelos import (
        ESENCIAL,
        Ficha,
        nombres_que_cambiarion,
        sellar_manifiesto,
    )

    archivo = tmp_path / "peso.onnx"
    archivo.write_bytes(b"abc")
    ficha = Ficha(
        "Peso", 3, "Intercambio", ESENCIAL, "porque", "http://x", str(archivo), "ab"
    )
    monkeypatch.setattr("app.drako.catalogo_modelos.fichas", lambda: [ficha])
    monkeypatch.setattr(
        "app.drako.catalogo_modelos.ruta_manifiesto",
        lambda: tmp_path / "manifiesto.json",
    )
    assert nombres_que_cambiarion() == ["Peso"]
    sellar_manifiesto(["Peso"])
    assert nombres_que_cambiarion() == []
    archivo.write_bytes(b"abcd")
    assert nombres_que_cambiarion() == ["Peso"]


def test_archivo_ya_valido_no_se_vuelve_a_bajar(tmp_path):
    contenido = b"peso-ya-en-disco"
    destino = tmp_path / "modelo.onnx"
    destino.write_bytes(contenido)
    digest = hashlib.sha256(contenido).hexdigest()
    resultado = descargar_uno(
        Trabajo("YaEsta", "http://127.0.0.1:1/no-debe-conectar", str(destino), digest)
    )
    assert resultado.estado == "omitido"
    assert destino.read_bytes() == contenido


def test_modo_optimizado_conserva_el_archivo_aunque_el_hash_no_coincida(tmp_path):
    destino = tmp_path / "opt.onnx"
    destino.write_bytes(b"optimizado")
    resultado = descargar_uno(
        Trabajo("Opt", "http://127.0.0.1:1/no", str(destino), "0" * 64),
        omitir_hash=True,
    )
    assert resultado.estado == "omitido"
    assert destino.read_bytes() == b"optimizado"


class _Servidor:
    def __init__(self, handler):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.hilo = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.hilo.start()

    @property
    def url(self) -> str:
        host, puerto = self.httpd.server_address
        return f"http://{host}:{puerto}"

    def cerrar(self) -> None:
        self.httpd.shutdown()
        self.hilo.join(timeout=2)


def _handler(archivos: dict[str, bytes], fallos: int = 0, pausa: float = 0.0):
    class Handler(BaseHTTPRequestHandler):
        datos = archivos
        restantes = fallos
        rangos: ClassVar[list[int]] = []
        en_vuelo = 0
        maximo = 0
        candado = threading.Lock()

        def do_GET(self):
            import time

            with type(self).candado:
                type(self).en_vuelo += 1
                type(self).maximo = max(type(self).maximo, type(self).en_vuelo)
            try:
                if pausa:
                    time.sleep(pausa)
                with type(self).candado:
                    if type(self).restantes > 0:
                        type(self).restantes -= 1
                        self.send_response(500)
                        self.end_headers()
                        return
                data = type(self).datos[self.path]
                inicio = 0
                rango = self.headers.get("Range")
                if rango:
                    inicio = int(rango.split("=")[1].split("-")[0])
                    with type(self).candado:
                        type(self).rangos.append(inicio)
                    cuerpo = data[inicio:]
                    self.send_response(206)
                    self.send_header(
                        "Content-Range",
                        f"bytes {inicio}-{len(data) - 1}/{len(data)}",
                    )
                else:
                    cuerpo = data
                    self.send_response(200)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
            finally:
                with type(self).candado:
                    type(self).en_vuelo -= 1

        def log_message(self, fmt, *args):
            return

    return Handler


def test_reanuda_con_range_y_comprueba_el_hash(tmp_path):
    contenido = b"abcdefghijklmnopqrstuvwxyz" * 20
    handler = _handler({"/peso": contenido})
    servidor = _Servidor(handler)
    try:
        destino = tmp_path / "peso.onnx"
        parcial = Path(str(destino) + ".parcial")
        parcial.write_bytes(contenido[:40])
        digest = hashlib.sha256(contenido).hexdigest()
        resultado = descargar_uno(
            Trabajo(
                "Peso", servidor.url + "/peso", str(destino), digest, len(contenido)
            ),
            chunk_size=16,
        )
        assert resultado.estado == "ok"
        assert destino.read_bytes() == contenido
        assert not parcial.exists()
        assert handler.rangos == [40]
    finally:
        servidor.cerrar()


def test_reintenta_con_espera_creciente(tmp_path):
    contenido = b"datos-buenos"
    handler = _handler({"/ok": contenido}, fallos=2)
    servidor = _Servidor(handler)
    esperas: list[float] = []
    try:
        destino = tmp_path / "ok.onnx"
        digest = hashlib.sha256(contenido).hexdigest()
        resultado = descargar_uno(
            Trabajo("Ok", servidor.url + "/ok", str(destino), digest),
            intentos=4,
            dormir=esperas.append,
        )
        assert resultado.estado == "ok"
        assert esperas == [1.0, 2.0]
        assert destino.read_bytes() == contenido
    finally:
        servidor.cerrar()


def test_hash_incorrecto_no_deja_el_archivo(tmp_path):
    handler = _handler({"/mal": b"contenido-malo"})
    servidor = _Servidor(handler)
    try:
        destino = tmp_path / "mal.onnx"
        resultado = descargar_uno(
            Trabajo("Mal", servidor.url + "/mal", str(destino), "ab" * 32),
            intentos=2,
            dormir=lambda _segundos: None,
        )
        assert resultado.estado == "error"
        assert not destino.exists()
        assert not Path(str(destino) + ".parcial").exists()
    finally:
        servidor.cerrar()


def test_sin_conexion_no_lanza():
    resultado = descargar_uno(
        Trabajo(
            "Nada", "http://127.0.0.1:1/no", "/tmp/no-existe-drako.onnx", "ab" * 32
        ),
        intentos=2,
        dormir=lambda _segundos: None,
    )
    assert resultado.estado == "sin_conexion"


def test_cancelar_conserva_el_parcial(tmp_path):
    contenido = b"x" * 800
    handler = _handler({"/largo": contenido})
    servidor = _Servidor(handler)
    cancelado = threading.Event()
    try:
        destino = tmp_path / "largo.onnx"

        def al_bytes(_nombre, hecho, _total):
            if hecho >= 100:
                cancelado.set()

        resultado = descargar_uno(
            Trabajo(
                "Largo", servidor.url + "/largo", str(destino), None, len(contenido)
            ),
            cancelado=cancelado,
            chunk_size=100,
            al_bytes=al_bytes,
        )
        assert resultado.estado == "cancelado"
        parcial = Path(str(destino) + ".parcial")
        assert parcial.is_file()
        assert 0 < parcial.stat().st_size < len(contenido)
        assert not destino.exists()
    finally:
        servidor.cerrar()


def test_descarga_en_paralelo_como_maximo_tres(tmp_path):
    archivos = {f"/{letra}": letra.encode() * 30 for letra in "abc"}
    handler = _handler(archivos, pausa=0.3)
    servidor = _Servidor(handler)
    try:
        trabajos = []
        for letra in "abc":
            contenido = archivos[f"/{letra}"]
            destino = tmp_path / f"{letra}.bin"
            trabajos.append(
                Trabajo(
                    letra,
                    servidor.url + f"/{letra}",
                    str(destino),
                    hashlib.sha256(contenido).hexdigest(),
                    len(contenido),
                )
            )
        resultado = descargar_lote(trabajos, trabajadores=8, chunk_size=8)
        assert resultado.correcto
        assert 2 <= handler.maximo <= 3
    finally:
        servidor.cerrar()


def test_solicitar_si_falta_vuelve_sin_esperar(monkeypatch):
    import time

    from app.drako.descarga_modelos import GestorDescarga
    from app.helpers.downloader import ResultadoArchivo, ResultadoLote

    def lento(nombres, **_kwargs):
        time.sleep(0.3)
        return ResultadoLote(
            [ResultadoArchivo(nombre, "sin_conexion") for nombre in nombres]
        )

    monkeypatch.setattr("app.drako.descarga_modelos.descargar_nombres", lento)
    monkeypatch.setattr(
        "app.drako.descarga_modelos.archivo_presente", lambda _nombre: False
    )
    gestor = GestorDescarga()
    inicio = time.monotonic()
    assert gestor.solicitar_si_falta("DeoldifyArt") is False
    assert time.monotonic() - inicio < 0.15
    assert gestor.solicitar_si_falta("DeoldifyArt") is False
    time.sleep(0.5)


def test_el_lanzador_no_exige_los_opcionales():
    import sys
    from unittest.mock import MagicMock

    for nombre in ("PySide6", "PySide6.QtWidgets", "PySide6.QtCore", "PySide6.QtGui"):
        sys.modules.setdefault(nombre, MagicMock())
    from app.ui.launcher.cfgtools import check_models_presence

    _falta, rutas = check_models_presence()
    esenciales_rutas = {item.local_path for item in esenciales()}
    assert set(rutas) <= esenciales_rutas
    assert any("inswapper_128" in ruta for ruta in rutas)
    for item in opcionales():
        assert item.local_path not in rutas


def test_un_archivo_presente_se_reconoce(tmp_path, monkeypatch):
    destino = tmp_path / "cara.onnx"
    destino.write_bytes(b"abc")

    def falsa(nombre):
        from app.drako.catalogo_modelos import Ficha

        return Ficha(
            nombre, 3, "Intercambio", ESENCIAL, "x", "http://x", str(destino), "ab"
        )

    monkeypatch.setattr("app.drako.catalogo_modelos.ficha", falsa)
    assert archivo_presente("Inswapper128") is True
    destino.unlink()
    assert archivo_presente("Inswapper128") is False


def test_la_interfaz_nombra_ajustes_y_descargar_todos():
    panel = Path("app/ui/widgets/panel_modelos.py").read_text(encoding="utf-8")
    main = Path("app/ui/main_ui.py").read_text(encoding="utf-8")
    assert "Descargar todos" in panel
    assert "setTabText" in panel and "Ajustes" in panel
    assert "setModal(False)" in panel
    assert "instalar_panel_modelos" in main
    procesador = Path("app/processors/models_processor.py").read_text(encoding="utf-8")
    assert "solicitar_si_falta" in procesador
