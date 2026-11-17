"""Los subprocesos de Windows no deben abrir una consola."""

import subprocess

from app.drako.sin_consola import aplicar_sin_consola, ocultar_consolas


def test_suma_create_no_window_sin_pisar_otras_banderas():
    kwargs = {"creationflags": 0x10}
    aplicar_sin_consola(kwargs)
    assert kwargs["creationflags"] & 0x08000000
    assert kwargs["creationflags"] & 0x10


def test_fuera_de_windows_no_cambia_popen():
    original = subprocess.Popen
    ocultar_consolas()
    assert subprocess.Popen is original
