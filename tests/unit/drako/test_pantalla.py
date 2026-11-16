"""La ventana no puede pedir más sitio del que tiene el monitor."""

from PySide6 import QtCore

from app.drako.pantalla import medida_encajada


def test_un_portatil_bajo_no_recibe_una_ventana_mas_alta_que_la_pantalla():
    disponible = QtCore.QRect(0, 0, 1366, 720)
    ancho, alto, min_ancho, min_alto = medida_encajada(
        disponible, 1440, 900, 1100, 720, margen=16
    )
    assert ancho <= 1366 - 16
    assert alto <= 720 - 16
    assert min_ancho <= ancho
    assert min_alto <= alto
    assert min_alto <= 720 - 16


def test_el_acceso_mantiene_un_ancho_corto():
    disponible = QtCore.QRect(0, 0, 1920, 1080)
    ancho, alto, _, _ = medida_encajada(disponible, 520, 1400, 360, 280, margen=24)
    assert ancho == 520
    assert alto <= 1080 - 24
