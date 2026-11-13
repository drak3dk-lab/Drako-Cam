"""La pantalla sencilla no añade pasos ni se sale de las fotos admitidas."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.ui.estudio.biblioteca import Biblioteca
from app.ui.estudio.controles import CLAVES_DE_DRAKO, GRUPOS, valores_de_calidad, valores_iniciales
from app.ui.estudio.logica import (
    MENSAJE_CAMARA,
    MENSAJE_CARA_PERDIDA,
    MENSAJE_FOTO,
    ajuste_calidad,
    atajos_de_favoritas,
    aviso_cara_perdida,
    extension_admitida,
    frente_a_motor,
    fuerza_a_motor,
    nitidez_a_motor,
    nombre_seguro,
    puede_entrar_en_vivo,
    texto_para_obs,
)


def test_solo_foto_camara_y_en_vivo():
    assert puede_entrar_en_vivo(False, True) == MENSAJE_FOTO
    assert puede_entrar_en_vivo(True, False) == MENSAJE_CAMARA
    assert puede_entrar_en_vivo(True, True) is None


def test_el_aviso_de_cara_perdida_espera_a_que_pase_un_rato():
    assert aviso_cara_perdida(None, 10) is None
    assert aviso_cara_perdida(10.0, 10.5, gracia=1.2) is None
    assert aviso_cara_perdida(10.0, 12.0, gracia=1.2) == MENSAJE_CARA_PERDIDA


def test_la_calidad_no_promete_60_fps_si_la_tarjeta_no_puede():
    alto = ajuste_calidad("Máximo FPS", permite_60=True)
    corto = ajuste_calidad("Máximo FPS", permite_60=False)
    assert alto.fps == "60"
    assert corto.fps == "30"
    assert ajuste_calidad("Máxima calidad", True).mejorar_cara is True
    assert ajuste_calidad("Auto", True).resolucion is None


def test_los_controles_cortos_tienen_un_punto_neutro():
    assert fuerza_a_motor(50) == 100
    assert fuerza_a_motor(0) == 0
    assert nitidez_a_motor(50) == 1.0
    assert frente_a_motor(0) == 0
    assert frente_a_motor(100) == 40


def test_el_texto_de_obs_nombra_el_dispositivo():
    texto = texto_para_obs("1920x1080", "30", "Verde")
    assert "Drako Cam" in texto
    assert "1920 × 1080" in texto
    assert "Verde" in texto


def test_extensiones_y_nombre_de_archivo():
    assert extension_admitida("cara.JPG")
    assert extension_admitida("cara.webp")
    assert not extension_admitida("cara.gif")
    assert nombre_seguro(r"C:\fotos\mi cara.png") == "mi cara.png"
    assert "/" not in nombre_seguro("../../secreto.png")


def test_biblioteca_copia_y_recuerda_favoritas(tmp_path: Path):
    origen = tmp_path / "fuera"
    origen.mkdir()
    foto = origen / "Nova.png"
    foto.write_bytes(b"\x89PNG\r\n")
    biblioteca = Biblioteca(tmp_path / "datos")
    guardada = biblioteca.anadir(foto)
    assert guardada.ruta.is_file()
    assert guardada.ruta.parent == biblioteca.carpeta
    biblioteca.fijar_favorita(guardada.id, True)
    assert biblioteca.listar()[0].favorita is True
    assert atajos_de_favoritas([guardada.id])[guardada.id] == "F1"
    gif = origen / "no.gif"
    gif.write_bytes(b"GIF89a")
    with pytest.raises(ValueError):
        biblioteca.anadir(gif)


def test_los_ajustes_que_drako_usa_siguen_en_el_panel():
    claves = set(valores_iniciales())
    for clave in CLAVES_DE_DRAKO:
        assert clave in claves
    assert [grupo.nombre for grupo in GRUPOS] == [
        "Boca",
        "Ojos",
        "Bordes y fusión",
        "Nitidez y calidad",
        "Color y luz",
        "Objetos delante",
        "Estabilidad del borde",
    ]
    maxima = valores_de_calidad("Máxima calidad", permite_alto=True)
    fluido = valores_de_calidad("Máximo FPS")
    assert maxima["FaceRestorerEnableToggle"] is True
    assert maxima["SwapperResSelection"] == "512"
    assert maxima["RestoreMouthEnableToggle"] is False
    assert maxima["AutoMouthExpressionEnableToggle"] is True
    assert maxima["AutoMouthRestoreModeSelection"] == "Face Parser Only"
    assert fluido["FaceRestorerEnableToggle"] is False
    assert fluido["OccluderEnableToggle"] is False
    assert fluido["BordermaskEnableToggle"] is True
    assert valores_de_calidad("Auto")["SimilarityThresholdSlider"] == 60
    assert valores_de_calidad("Auto")["OccluderEnableToggle"] is True
    assert valores_de_calidad("Auto")["FaceTrackingEnableToggle"] is True
    assert valores_de_calidad("Auto")["SuavizadoMascaraEnableToggle"] is True
    assert valores_de_calidad("Máxima calidad")["DFLXSegEnableToggle"] is True
    assert valores_de_calidad("Máxima calidad")["LandmarkDetectToggle"] is True
    assert valores_de_calidad("Máximo FPS")["DFLXSegEnableToggle"] is False


def test_los_ajustes_se_guardan_con_la_cara(tmp_path: Path):
    biblioteca = Biblioteca(tmp_path)
    biblioteca.guardar_ajustes("ana.png", {"SimilarityThresholdSlider": 40})
    assert biblioteca.ajustes_de("ana.png")["SimilarityThresholdSlider"] == 40
    assert biblioteca.ajustes_de("otra.png") == {}


def test_el_panel_se_construye_sin_el_motor():
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets

    from app.ui.estudio.logica import CaraVista
    from app.ui.estudio.panel import Estudio

    _aplicacion = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    estudio = Estudio()
    estudio.resize(1440, 900)
    estudio.mostrar_caras(
        [CaraVista("a.png", "Nova", "no-existe.png", True, "F1")],
        "a.png",
    )
    estudio.mostrar_camaras(["Cámara 1"], 0)
    estudio.mostrar_estado(
        sesion=True,
        en_vivo=True,
        original=False,
        tiene_foto=True,
        tiene_camara=True,
        fps=30.0,
        latencia_ms=22.0,
        vram="5,1 / 12 GB",
        proveedor="TensorRT",
        vigilante="OK",
        mensaje="",
        calidad_nota="Según la tarjeta.",
        virtual=True,
        resolucion="1920x1080",
        fps_salida="30",
        fondo="Normal",
    )
    assert estudio.boton_vivo.text() == "PARAR"
    assert estudio.pill_obs.text() == "EMITIENDO"
    estudio.pedir_en_vivo.emit(False)
    estudio.close()
