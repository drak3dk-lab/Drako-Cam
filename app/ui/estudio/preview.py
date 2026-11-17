"""Genera capturas de la pantalla, sin cámara ni modelos.

Sirve para revisar el diseño. En Windows la cámara real ocupa el hueco.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets

from app.ui.estudio.logica import CaraVista
from app.ui.estudio.panel import Estudio


def _avatar(ruta: Path, color: str, letra: str) -> None:
    imagen = QtGui.QImage(176, 176, QtGui.QImage.Format.Format_RGB32)
    imagen.fill(QtGui.QColor("#121620"))
    pintor = QtGui.QPainter(imagen)
    pintor.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    pintor.setPen(QtCore.Qt.PenStyle.NoPen)
    pintor.setBrush(QtGui.QColor(color))
    pintor.drawEllipse(38, 28, 100, 100)
    pintor.setPen(QtGui.QColor("#04060A"))
    fuente = pintor.font()
    fuente.setPixelSize(42)
    fuente.setBold(True)
    pintor.setFont(fuente)
    pintor.drawText(imagen.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, letra)
    pintor.end()
    imagen.save(str(ruta))


def _estado(estudio: Estudio, *, sesion: bool, mensaje: str = "") -> None:
    estudio.mostrar_estado(
        sesion=sesion,
        en_vivo=sesion and not mensaje,
        original=False,
        tiene_foto=True,
        tiene_camara=True,
        fps=59.8 if sesion else None,
        latencia_ms=22.0 if sesion else None,
        vram="5,1 / 12 GB",
        proveedor="TensorRT",
        vigilante="OK",
        mensaje=mensaje,
        calidad_nota="Según la tarjeta que haya en el equipo.",
        virtual=sesion,
        resolucion="1920x1080",
        fps_salida="30",
        fondo="Normal",
    )


def main(destino: Path) -> None:
    aplicacion = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    carpeta = destino / "_avatares"
    carpeta.mkdir(parents=True, exist_ok=True)
    colores = (("#5CE1F0", "N"), ("#F1F4F9", "L"), ("#6FD9A3", "A"), ("#D7DEEA", "S"))
    caras = []
    for indice, (color, letra) in enumerate(colores, start=1):
        ruta = carpeta / f"cara-{indice}.png"
        _avatar(ruta, color, letra)
        caras.append(
            CaraVista(
                id=ruta.name,
                nombre=f"Cara {indice}",
                ruta=str(ruta),
                favorita=indice <= 3,
                atajo=f"F{indice}" if indice <= 3 else "",
            )
        )
    estudio = Estudio()
    estudio.resize(1440, 900)
    estudio.mostrar_caras(caras, caras[0].id)
    estudio.mostrar_camaras(["Cámara 1  ·  Logitech", "Cámara 2"], 0)
    _estado(estudio, sesion=True)
    estudio.show()
    from PySide6 import QtTest

    QtTest.QTest.qWait(500)
    for caja in estudio.ajustes.findChildren(QtWidgets.QCheckBox):
        if caja.text() == "Boca":
            caja.setChecked(True)
            break
    aplicacion.processEvents()
    estudio.grab().save(str(destino / "halo-principal.png"))
    estudio.ajustes.grab().save(str(destino / "halo-ajustar.png"))

    estudio._alternar_compacto()
    aplicacion.processEvents()
    estudio.grab().save(str(destino / "halo-compacto.png"))
    estudio._alternar_compacto()
    _estado(estudio, sesion=True, mensaje="No te veo bien. Acércate un poco y mira a la cámara.")
    aplicacion.processEvents()
    estudio.grab().save(str(destino / "halo-sin-cara.png"))
    print(destino)


if __name__ == "__main__":
    salida = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/cursor/artifacts")
    main(salida)
