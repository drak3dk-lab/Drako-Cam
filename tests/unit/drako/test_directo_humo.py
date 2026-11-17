"""Humo del directo sin GPU: lectura de la foto, motores y ventanas."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.ui.estudio.caras import (
    MOTORES_DIRECTO,
    CicloCara,
    MENSAJE_FOTO_MALA,
    MENSAJE_PREPARANDO,
    paso_lectura,
    quitar_muertos,
    texto_motor,
)


def test_no_hay_falso_error_mientras_la_foto_se_prepara():
    ciclo = CicloCara()
    ciclo.nueva_foto("ana")
    for _ in range(100):
        assert ciclo.paso() == "esperar"
    assert MENSAJE_PREPARANDO.startswith("Preparando")


def test_activar_cambiar_de_foto_y_reactivar():
    ciclo = CicloCara()
    ciclo.nueva_foto("ana")
    assert ciclo.paso() == "esperar"
    ciclo.listo([0.1, 0.2])
    assert ciclo.paso() == "activar"
    ciclo.marcar_aplicada()

    ciclo.nueva_foto("luis")
    assert ciclo.paso() == "esperar"
    assert ciclo.embedding is None
    ciclo.listo([0.3])
    assert ciclo.paso() == "activar"
    ciclo.marcar_aplicada()
    assert ciclo.aplicadas == ["ana", "luis"]

    ciclo.nueva_foto("sin-cara")
    ciclo.sin_cara()
    assert ciclo.paso() == "error"
    assert MENSAJE_FOTO_MALA.startswith("No pude leer")

    ciclo.nueva_foto("rota")
    ciclo.fallo("boom")
    assert ciclo.paso() == "error"
    assert paso_lectura(
        hay_embedding=False, en_curso=True, termino=False, excepcion=True
    ) == "esperar"


def test_el_texto_del_motor_nombra_los_seis():
    assert len(MOTORES_DIRECTO) == 6
    assert MOTORES_DIRECTO[1][1] == "lector de caras"
    texto = texto_motor(2, 6, "lector de caras")
    assert texto.startswith("Preparando el motor TensorRT (2/6): lector de caras")
    assert "La primera vez puede tardar unos minutos" in texto


def test_un_boton_borrado_sale_del_diccionario():
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    import shiboken6

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    boton = QtWidgets.QPushButton("cara")
    caras = {"viva": object(), "muerta": boton}
    shiboken6.delete(boton)
    assert quitar_muertos(caras) == 1
    assert "muerta" not in caras
    assert "viva" in caras


def test_la_salida_virtual_no_lleva_la_vista_adornada():
    import numpy as np

    from app.drako.rendimiento.camara_virtual import separar_vista_y_salida

    vista = np.zeros((4, 4, 3), dtype=np.uint8)
    vista[:] = 9
    limpio = np.zeros((4, 4, 3), dtype=np.uint8)
    limpio[:] = 3
    pintada, salida = separar_vista_y_salida((vista, limpio))
    assert int(pintada[0, 0, 0]) == 9
    assert int(salida[0, 0, 0]) == 3


def test_la_ventana_de_salida_se_cierra_con_la_x_y_con_esc(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtTest, QtWidgets

    from app.ui.estudio.biblioteca import Biblioteca
    from app.ui.estudio.motor import MotorEnVivo
    from app.ui.estudio.ventana_salida import VentanaSalida

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    avisos = []
    ventana = VentanaSalida(320, 180)
    ventana.aviso.connect(avisos.append)
    ventana.abrir()
    app.processEvents()
    assert ventana.esta_abierta()
    boton = ventana.findChild(QtWidgets.QPushButton, "cerrarSalida")
    assert boton is not None
    assert ventana.windowFlags() & QtCore.Qt.WindowType.WindowCloseButtonHint
    boton.click()
    app.processEvents()
    assert not ventana.esta_abierta()
    assert avisos and "cámara virtual sigue" in avisos[-1]

    ventana.abrir()
    app.processEvents()
    QtTest.QTest.keyClick(ventana, QtCore.Qt.Key.Key_Escape)
    app.processEvents()
    assert not ventana.esta_abierta()

    bib = Biblioteca(tmp_path)
    motor = MotorEnVivo(type("V", (), {"control": {}})(), bib)
    motor._virtual = True
    motor._salida_activa = True
    motor._ventana_salida = ventana
    ventana.aviso.connect(motor._aviso_ventana)
    ventana.abrir()
    ventana.cerrar()
    assert motor._virtual is True
    assert motor._salida_activa is True
    assert motor.estado()["ventana_abierta"] is False


def test_el_arranque_no_pregunta_por_el_workspace():
    from app.ui.estudio.logica import debe_preguntar_workspace

    assert debe_preguntar_workspace() is False


def test_el_swap_del_directo_se_anota_una_vez():
    import logging

    from app.drako.rendimiento.diagnostico import anotar_swap_en_directo

    class Cara:
        face_id = "abc"

    class Proc:
        file_type = "webcam"

    class Ventana:
        video_processor = Proc()

    class Worker:
        main_window = Ventana()

    registro = logging.getLogger("drako")
    registro.handlers.clear()
    registro.propagate = True
    with caplog_de(registro) as lineas:
        anotar_swap_en_directo(Worker(), Cara())
        anotar_swap_en_directo(Worker(), Cara())
    assert lineas.count("Cara aplicada en el directo: abc") == 1


def caplog_de(registro):
    import logging
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        lineas: list[str] = []

        class _Handler(logging.Handler):
            def emit(self, record):
                lineas.append(record.getMessage())

        handler = _Handler()
        registro.addHandler(handler)
        nivel = registro.level
        registro.setLevel(logging.INFO)
        try:
            yield lineas
        finally:
            registro.removeHandler(handler)
            registro.setLevel(nivel)

    return _cm()


def test_la_vista_llena_el_marco():
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtGui, QtWidgets

    from app.ui.estudio.vista import encajar_si_hay_imagen

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    vista = QtWidgets.QGraphicsView()
    vista.resize(800, 450)
    escena = QtWidgets.QGraphicsScene()
    vista.setScene(escena)
    pixmap = QtGui.QPixmap(36, 36)
    pixmap.fill(QtGui.QColor("#F20A1C"))
    escena.addPixmap(pixmap)
    vista.show()
    app.processEvents()

    assert encajar_si_hay_imagen(vista)
    escala = vista.transform().m11()
    assert escala > 5
    assert vista.transform().m11() == pytest.approx(vista.transform().m22())


def test_la_rueda_no_mueve_el_deslizador_sin_foco():
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtGui, QtTest, QtWidgets

    from app.ui.estudio.ajuste_panel import FiltroRueda, preparar_rueda

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    area = QtWidgets.QScrollArea()
    interior = QtWidgets.QWidget()
    caja = QtWidgets.QVBoxLayout(interior)
    slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(40)
    filtro = FiltroRueda(area)
    preparar_rueda(slider, filtro)
    caja.addWidget(slider)
    caja.addSpacing(900)
    area.setWidget(interior)
    area.resize(240, 80)
    area.show()
    app.processEvents()
    antes = area.verticalScrollBar().value()
    evento = QtGui.QWheelEvent(
        QtCore.QPointF(8, 8),
        QtCore.QPointF(8, 8),
        QtCore.QPoint(0, 0),
        QtCore.QPoint(0, -120),
        QtCore.Qt.MouseButton.NoButton,
        QtCore.Qt.KeyboardModifier.NoModifier,
        QtCore.Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    assert QtWidgets.QApplication.sendEvent(slider, evento) is True
    assert slider.value() == 40
    assert area.verticalScrollBar().value() != antes
    QtTest.QTest.mouseClick(slider, QtCore.Qt.MouseButton.LeftButton)
    app.processEvents()
    assert slider.hasFocus()
    QtWidgets.QApplication.sendEvent(slider, evento)
    assert slider.value() != 40


def test_carga_y_acceso_tienen_logo_rojo_y_se_pueden_cerrar():
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtWidgets

    from app.drako.dialogo import _DialogoBase
    from app.ui.pantalla_carga import PantallaCarga

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from PySide6.QtGui import QKeyEvent

    carga = PantallaCarga()
    assert carga.windowFlags() & QtCore.Qt.WindowType.WindowCloseButtonHint
    assert "#F20A1C" in carga.styleSheet()
    marca = carga.findChildren(QtWidgets.QLabel)[0]
    assert marca.pixmap() is not None and not marca.pixmap().isNull()
    carga.show()
    carga.keyPressEvent(
        QKeyEvent(
            QtCore.QEvent.Type.KeyPress,
            QtCore.Qt.Key.Key_Escape,
            QtCore.Qt.KeyboardModifier.NoModifier,
        )
    )
    assert not carga.isVisible()

    dialogo = _DialogoBase("Drako Cam — acceso de administrador")
    assert dialogo.windowFlags() & QtCore.Qt.WindowType.WindowCloseButtonHint
    assert "#F20A1C" in dialogo.styleSheet()
    assert dialogo.findChildren(QtWidgets.QLabel)[0].pixmap() is not None
