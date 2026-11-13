"""La salida a OBS no cambia de tamaño ni se corta si falta la cara."""

import numpy as np

from app.drako.rendimiento.camara_virtual import encajar
from app.drako.rendimiento.obs_salida import (
    NOMBRE_UNITY,
    debe_cortar_salida,
    detectar,
    elegir,
    fotograma_prueba,
    pasos_para_obs,
    texto_indicador,
)


def test_unity_es_la_camara_que_obs_puede_elegir():
    eleccion = elegir(True, True)
    assert eleccion.backend == "unitycapture"
    assert eleccion.nombre == NOMBRE_UNITY
    assert "no es la salida" in eleccion.motivo
    assert elegir(False, True).backend == "obs"
    assert elegir(False, False).modo == "ventana"


def test_detecta_obs_sin_un_windows_real():
    presentes = {
        r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
        r"C:\Program Files\UnityCapture\UnityCaptureFilter64.dll",
    }
    estado = detectar(existe=lambda ruta: ruta in presentes, procesos=["obs64.exe"])
    assert estado.obs_instalado
    assert estado.unity
    assert estado.obs_en_marcha
    assert estado.eleccion.backend == "unitycapture"
    vacio = detectar(existe=lambda _ruta: False, procesos=[])
    assert not vacio.obs_instalado
    assert vacio.eleccion.modo == "ventana"


def test_el_indicador_no_miente_y_la_cara_perdida_no_corta():
    assert texto_indicador(dispositivo_abierto=True, obs_en_marcha=True, ventana=False) == "OBS recibiendo"
    assert texto_indicador(dispositivo_abierto=True, obs_en_marcha=False, ventana=False) == "Salida activa"
    assert texto_indicador(dispositivo_abierto=False, obs_en_marcha=True, ventana=False) == "APAGADA"
    assert debe_cortar_salida(cara_perdida=True, parar=False, panel_cerrado=False) is False
    assert debe_cortar_salida(cara_perdida=False, parar=False, panel_cerrado=True) is False
    assert debe_cortar_salida(cara_perdida=False, parar=True, panel_cerrado=False) is True


def test_el_fotograma_se_encaja_sin_cambiar_el_ancho():
    frame = np.zeros((10, 20, 3), dtype=np.uint8)
    frame[0, 0] = (1, 2, 3)
    encajado = encajar(frame, 8, 6)
    assert encajado.shape == (6, 8, 3)
    assert encajar(encajado, 8, 6) is encajado
    prueba = fotograma_prueba(32, 18)
    assert prueba.shape == (18, 32, 3)
    assert int(prueba.max()) > 200


def test_los_pasos_nombran_la_camara():
    uno, dos, tres = pasos_para_obs("Unity Video Capture")
    assert "Fuentes" in uno
    assert "Dispositivo de captura de vídeo" in dos
    assert "Unity Video Capture" in tres


def test_el_asistente_cabe_en_una_pantalla():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton

    from app.ui.estudio.asistente_obs import AsistenteObs

    _app = QApplication.instance() or QApplication([])
    estado = detectar(existe=lambda _ruta: False, procesos=[])
    dialogo = AsistenteObs(estado)
    textos = [boton.text() for boton in dialogo.findChildren(QPushButton)]
    assert "Probar salida" in textos
    assert "Ya está" in textos
    assert dialogo.dibujo._lineas[2].endswith("Aceptar.")
