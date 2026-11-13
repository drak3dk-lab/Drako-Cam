"""Logs, excepciones, reconexión de cámara y aviso de CUDA."""

import ast
import logging
from pathlib import Path

import main as entrada
from app.drako.camara import PoliticaReconexion
from app.drako.cuda_aviso import mensaje_sin_cuda
from app.drako.registro import (
    configurar_logs,
    instalar_captura_global,
    mensaje_para_usuario,
)
from app.drako.rutas import directorio_datos


def test_mensaje_cuda_solo_cuando_falta():
    assert mensaje_sin_cuda(True) is None
    texto = mensaje_sin_cuda(False)
    assert texto is not None
    assert "CUDA" in texto
    assert "no se pasa a CPU en silencio" in texto.lower() or "No se pasa a CPU" in texto


def test_reconnexion_de_webcam_reabre_y_luego_se_rinde():
    politica = PoliticaReconexion(fallos_para_reabrir=3, espera_s=0.1, max_reaperturas=1)
    assert politica.fallo().reabrir is False
    assert politica.fallo().reabrir is False
    decision = politica.fallo()
    assert decision.reabrir and not decision.rendirse
    politica.exito()
    politica.fallo()
    politica.fallo()
    reabierta = politica.fallo()
    assert reabierta.reabrir and not reabierta.rendirse
    politica.fallo()
    politica.fallo()
    rendicion = politica.fallo()
    assert rendicion.rendirse and not rendicion.reabrir


def test_log_rotativo_y_excepcion_visible(tmp_path, capsys):
    import sys

    logger = configurar_logs(tmp_path, max_bytes=400, copias=2)
    vistos = []
    ruta = tmp_path / "logs" / "drako-cam.log"
    gancho_anterior = sys.excepthook
    instalar_captura_global(logger, mostrar=vistos.append, ruta_log=ruta)
    try:
        logger.info("arranque de prueba %s", "x" * 80)
        for indice in range(30):
            logger.info("linea %s %s", indice, "y" * 40)
        assert ruta.is_file()
        assert list((tmp_path / "logs").glob("drako-cam.log*"))
        try:
            raise RuntimeError("fallo visible de prueba")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
        assert vistos
        assert "Drako Cam" in vistos[0]
        assert "fallo visible de prueba" in vistos[0]
        assert "fallo visible de prueba" in ruta.read_text(encoding="utf-8")
        capturado = capsys.readouterr()
        assert "Drako Cam" in capturado.err
    finally:
        sys.excepthook = gancho_anterior
        logging.getLogger("drako").handlers.clear()


def test_directorio_de_datos_respeta_la_variable(tmp_path):
    assert directorio_datos({"DRAKO_CAM_DATA_DIR": str(tmp_path)}) == tmp_path


def test_directorio_windows(monkeypatch):
    class Ruta:
        def __init__(self, valor):
            self.valor = str(valor)

        def __truediv__(self, otro):
            return Ruta(f"{self.valor}/{otro}")

        def __eq__(self, otro):
            return isinstance(otro, Ruta) and self.valor == otro.valor

    monkeypatch.setattr("app.drako.rutas.Path", Ruta)
    monkeypatch.setattr("app.drako.rutas.os.name", "nt")
    ruta = directorio_datos({"APPDATA": "C:/Users/Drako/AppData/Roaming"})
    assert ruta == Ruta("C:/Users/Drako/AppData/Roaming/DrakoCam")


def test_el_arbol_importa(capsys):
    assert entrada.comprobar_importaciones() == 0
    salida = capsys.readouterr().out
    assert "importaciones y sintaxis correctas" in salida


def test_manifiesto_de_modelos_tiene_hash_y_no_esta_el_peso(tmp_path):
    del tmp_path
    texto = Path("app/processors/models_data.py").read_text(encoding="utf-8")
    assert "cee626bc81721d71c5d6cb1f76f830b9ae46f595514b0884dd8ae34785576764" in texto
    assert "9999fe3ade7a1b1be74aef7935365688be89c58098f9bc0dbba143c4988252c4" in texto
    assert "emp.npy" in texto
    assert "model.pb" in texto
    assert not Path("model_assets/alphaface/emp.npy").exists()
    assert not Path("model_assets/mouth_action_detector/model.pb").exists()
    assert not Path("model_assets/vgg_combo_relu3_3_relu3_1.onnx").exists()
    ast.parse(Path("download_models.py").read_text(encoding="utf-8"))
    assert "def descargar_modelos" in Path("download_models.py").read_text(encoding="utf-8")


def test_mensaje_de_usuario_nombra_el_programa():
    texto = mensaje_para_usuario(RuntimeError("sin cámara"), Path("logs/drako-cam.log"))
    assert "Drako Cam" in texto
    assert "sin cámara" in texto
