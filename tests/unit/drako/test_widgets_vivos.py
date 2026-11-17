"""Un widget del editor ya borrado no puede cerrar el programa."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets
import shiboken6

from app.ui.qt_vivo import NOMBRES_EDITOR, cambio_activo, leer_editor, valor_slider


class _Ventana(QtWidgets.QMainWindow):
    def __getattribute__(self, name):
        if name in NOMBRES_EDITOR:
            return leer_editor(self, name)
        return super().__getattribute__(name)


def _app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_elegir_cara_no_toca_el_slider_borrado():
    _app()
    ventana = _Ventana()
    slider = QtWidgets.QSlider()
    ventana.videoSeekSlider = slider
    ventana._editor_protegido = True
    shiboken6.delete(slider)
    assert valor_slider(ventana, 0) == 0
    ventana.videoSeekSlider.setValue(3)
    ventana.videoSeekSlider.blockSignals(True)


def test_el_cambio_de_cara_sigue_aunque_el_boton_ya_no_exista():
    _app()
    ventana = _Ventana()
    boton = QtWidgets.QPushButton()
    boton.setCheckable(True)
    boton.setChecked(True)
    ventana.swapfacesButton = boton
    ventana._editor_protegido = True
    ventana._cambio_activo = True
    assert ventana.swapfacesButton.isChecked() is True
    shiboken6.delete(boton)
    assert cambio_activo(ventana) is True
    ventana.swapfacesButton.blockSignals(True)
    ventana.swapfacesButton.setChecked(False)
    assert cambio_activo(ventana) is False


def test_el_layout_borrado_acepta_set_spacing():
    _app()
    ventana = _Ventana()
    layout = QtWidgets.QHBoxLayout()
    ventana.mediaControlsMainLayout = layout
    ventana._editor_protegido = True
    shiboken6.delete(layout)
    ventana.mediaControlsMainLayout.setSpacing(12)


def test_antes_de_la_pantalla_sencilla_el_widget_es_el_real():
    _app()
    ventana = _Ventana()
    boton = QtWidgets.QPushButton()
    ventana.swapfacesButton = boton
    ventana._editor_protegido = False
    assert ventana.swapfacesButton is boton
