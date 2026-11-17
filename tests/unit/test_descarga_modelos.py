"""La descarga de modelos se reanuda, verifica el hash y solo pide el directo."""

from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.helpers.downloader import DOWNLOAD_CHUNK_SIZE, download_file, espera_del_intento
from app.processors.models_data import ORDEN_REQUERIDO, modelos_requeridos, models_list
from download_models import comprobar_modelos, descargar_modelos

EXCLUIDOS = (
    "SimSwap512",
    "GhostFacev1",
    "InStyleSwapper256 Version A",
    "CSCS",
    "LivePortraitMotionExtractor",
    "YoloFace11nVR180",
    "YoloFace12nVR180",
    "FaceLandmark106",
    "FaceLandmark68",
    "FaceLandmark203",
    "FaceLandmarkORFormer98",
    "GPENBFR256",
    "CodeFormer",
    "GFPGAN1024",
    "XSeg",
)


class _Servidor(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, datos: bytes, soporta_rango: bool = True, cortes: int = 0):
        self.datos = datos
        self.soporta_rango = soporta_rango
        self.cortes = cortes
        self.rangos: list[str | None] = []
        super().__init__(("127.0.0.1", 0), _Manejador)


class _Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        servidor: _Servidor = self.server  # type: ignore[assignment]
        datos = servidor.datos
        rango = self.headers.get("Range")
        servidor.rangos.append(rango)
        inicio = 0
        if rango and servidor.soporta_rango:
            inicio = int(rango.split("=", 1)[1].split("-", 1)[0] or "0")
            if inicio > len(datos):
                cuerpo = b""
                codigo = 416
            elif inicio == len(datos):
                cuerpo = b""
                codigo = 416
            else:
                cuerpo = datos[inicio:]
                codigo = 206
        else:
            cuerpo = datos
            codigo = 200
        cortar = servidor.cortes > 0 and codigo != 416 and len(cuerpo) > 4
        declarado = len(cuerpo)
        if cortar:
            servidor.cortes -= 1
            cuerpo = cuerpo[: max(4, len(cuerpo) // 2)]
        self.send_response(codigo)
        self.send_header("Content-Length", str(declarado if codigo != 416 else 0))
        self.send_header("Accept-Ranges", "bytes" if servidor.soporta_rango else "none")
        self.send_header("Connection", "close")
        if codigo == 206:
            fin = len(datos) - 1
            self.send_header("Content-Range", f"bytes {inicio}-{fin}/{len(datos)}")
        elif codigo == 416:
            self.send_header("Content-Range", f"bytes */{len(datos)}")
        self.end_headers()
        if cuerpo:
            self.wfile.write(cuerpo)
        self.close_connection = True

    def log_message(self, formato: str, *args) -> None:
        return


def _hash(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _url(servidor: _Servidor) -> str:
    host, puerto = servidor.server_address[:2]
    return f"http://{host}:{puerto}/modelo.bin"


def _servir(servidor: _Servidor):
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    return hilo


def test_el_trozo_es_de_un_mega():
    assert DOWNLOAD_CHUNK_SIZE == 1024 * 1024


def test_la_espera_crece_y_se_queda_en_60():
    assert [espera_del_intento(n) for n in (1, 2, 3, 4, 5, 6, 9)] == [
        3,
        5,
        10,
        30,
        60,
        60,
        60,
    ]


def test_continua_con_range_si_ya_hay_un_trozo(tmp_path: Path):
    datos = b"abcdefghijklmnopqrstuvwxyz" * 20
    destino = tmp_path / "modelo.bin"
    parcial = Path(str(destino) + ".part")
    parcial.write_bytes(datos[:40])
    servidor = _Servidor(datos)
    _servir(servidor)
    try:
        ok = download_file(
            "Prueba",
            str(destino),
            _hash(datos),
            _url(servidor),
            esperar=lambda _segundos: None,
        )
    finally:
        servidor.shutdown()
    assert ok is True
    assert destino.read_bytes() == datos
    assert not parcial.exists()
    assert servidor.rangos[0] == "bytes=40-"


def test_si_el_servidor_no_acepta_el_rango_empieza_de_nuevo(tmp_path: Path):
    datos = b"0123456789abcdef" * 8
    destino = tmp_path / "modelo.bin"
    parcial = Path(str(destino) + ".part")
    parcial.write_bytes(b"BASURA-QUE-NO-SIRVE")
    servidor = _Servidor(datos, soporta_rango=False)
    _servir(servidor)
    try:
        ok = download_file(
            "Prueba",
            str(destino),
            _hash(datos),
            _url(servidor),
            esperar=lambda _segundos: None,
        )
    finally:
        servidor.shutdown()
    assert ok is True
    assert destino.read_bytes() == datos
    assert not parcial.exists()
    assert servidor.rangos[0] is not None
    assert servidor.rangos[0].startswith("bytes=")


def test_un_corte_deja_el_parcial_y_el_siguiente_intento_sigue(tmp_path: Path):
    datos = bytes(range(256)) * 4
    destino = tmp_path / "modelo.bin"
    servidor = _Servidor(datos, cortes=4)
    esperas: list[int] = []
    _servir(servidor)
    try:
        ok = download_file(
            "Prueba",
            str(destino),
            _hash(datos),
            _url(servidor),
            esperar=esperas.append,
        )
    finally:
        servidor.shutdown()
    assert ok is True
    assert destino.read_bytes() == datos
    assert not Path(str(destino) + ".part").exists()
    assert len(esperas) >= 4
    assert esperas[:4] == [3, 5, 10, 30]
    rangos = [rango for rango in servidor.rangos if rango]
    assert rangos, "tenía que pedir Range al continuar"


def test_el_hash_mal_borra_y_no_se_queda_el_archivo(tmp_path: Path):
    datos = b"esto no es el archivo esperado"
    destino = tmp_path / "modelo.bin"
    servidor = _Servidor(datos)
    _servir(servidor)
    try:
        ok = download_file(
            "Prueba",
            str(destino),
            "a" * 64,
            _url(servidor),
            esperar=lambda _segundos: None,
            max_intentos=2,
        )
    finally:
        servidor.shutdown()
    assert ok is False
    assert not destino.exists()
    assert not Path(str(destino) + ".part").exists()


def test_un_archivo_valido_no_se_vuelve_a_bajar(tmp_path: Path):
    datos = b"ya-listo"
    destino = tmp_path / "modelo.bin"
    destino.write_bytes(datos)
    ok = download_file(
        "Prueba",
        str(destino),
        _hash(datos),
        "http://127.0.0.1:1/no-deberia-conectar",
        esperar=lambda _segundos: None,
        max_intentos=1,
    )
    assert ok is True
    assert destino.read_bytes() == datos


def test_comprobar_distingue_falta_corrupto_y_ok(tmp_path: Path):
    bueno = tmp_path / "bueno.bin"
    bueno.write_bytes(b"bien")
    malo = tmp_path / "malo.bin"
    malo.write_bytes(b"mal")
    modelos = [
        {
            "model_name": "Bueno",
            "local_path": str(bueno),
            "hash": _hash(b"bien"),
            "url": "http://ejemplo.invalid/bueno",
        },
        {
            "model_name": "Malo",
            "local_path": str(malo),
            "hash": _hash(b"otro"),
            "url": "http://ejemplo.invalid/malo",
        },
        {
            "model_name": "Ausente",
            "local_path": str(tmp_path / "no-esta.bin"),
            "hash": _hash(b"x"),
            "url": "http://ejemplo.invalid/ausente",
        },
    ]
    informe = {item["nombre"]: item["estado"] for item in comprobar_modelos(modelos)}
    assert informe == {"Bueno": "ok", "Malo": "corrupto", "Ausente": "falta"}


def test_no_termina_hasta_que_todos_pasan(tmp_path: Path):
    primero = b"primer-modelo-completo"
    segundo = b"segundo-modelo-completo-con-mas-bytes"
    destino_a = tmp_path / "a.bin"
    destino_b = tmp_path / "b.bin"
    destino_a.write_bytes(primero)
    servidor = _Servidor(segundo, cortes=1)
    _servir(servidor)
    estados: list[str] = []
    porcentajes: list[int] = []
    modelos = [
        {
            "model_name": "YaListo",
            "local_path": str(destino_a),
            "hash": _hash(primero),
            "url": "http://127.0.0.1:1/no",
        },
        {
            "model_name": "Falta",
            "local_path": str(destino_b),
            "hash": _hash(segundo),
            "url": _url(servidor),
        },
    ]
    try:
        ok = descargar_modelos(
            modelos=modelos,
            al_estado=estados.append,
            al_porcentaje=porcentajes.append,
            esperar=lambda _segundos: None,
        )
    finally:
        servidor.shutdown()
    assert ok is True
    assert destino_b.read_bytes() == segundo
    assert any(item["estado"] == "ok" for item in comprobar_modelos(modelos))
    assert all(item["estado"] == "ok" for item in comprobar_modelos(modelos))
    assert any("Reintentando..." in texto for texto in estados)
    assert any("Falta" in texto for texto in estados)
    assert porcentajes[-1] == 100
    assert servidor.rangos


def test_solo_estan_requeridos_los_del_directo_con_inswapper():
    nombres = [modelo["model_name"] for modelo in modelos_requeridos()]
    assert nombres == list(ORDEN_REQUERIDO)
    assert nombres == [
        "RetinaFace",
        "Inswapper128ArcFace",
        "Inswapper128",
        "GFPGANv1.4",
        "FaceParser",
        "Occluder",
    ]
    por_nombre = {modelo["model_name"]: modelo for modelo in models_list}
    for nombre in nombres:
        modelo = por_nombre[nombre]
        assert modelo["requerido"] is True
        assert modelo["url"].startswith(
            "https://github.com/visomaster/visomaster-assets/releases/download/v0.1.0/"
        )
        assert len(modelo["hash"]) == 64
        assert modelo["local_path"].endswith(
            {
                "RetinaFace": "det_10g.onnx",
                "Inswapper128ArcFace": "w600k_r50.onnx",
                "Inswapper128": "inswapper_128.fp16.onnx",
                "GFPGANv1.4": "GFPGANv1.4.onnx",
                "FaceParser": "faceparser_resnet34.onnx",
                "Occluder": "occluder.onnx",
            }[nombre]
        )
    for nombre in EXCLUIDOS:
        assert por_nombre[nombre]["requerido"] is False
        assert nombre not in nombres
