"""El balance de los controles no debe cerrar el programa si Qt ya borró el layout."""

import pytest

pytest.importorskip("PySide6")
shiboken6 = pytest.importorskip("shiboken6")

from PySide6 import QtWidgets

from app.ui.qt_vivo import qt_sigue, sincronizar_espaciado


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return app


def test_el_balance_ignora_un_layout_ya_borrado(qapp):
    padre = QtWidgets.QWidget()
    centro = QtWidgets.QWidget(padre)
    vista = QtWidgets.QWidget(padre)
    layout = QtWidgets.QHBoxLayout(centro)
    qapp.processEvents()

    shiboken6.delete(layout)

    assert not qt_sigue(layout)
    assert sincronizar_espaciado(layout, vista, centro, []) is False
