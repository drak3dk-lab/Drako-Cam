"""Icono de la app a partir del isotipo oficial.

Sale del PNG aprobado. 48 px en adelante es ese archivo, bien
reducido. 16 y 32 usan la reducción preparada para que el ojo se lea.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

TAMANOS = (16, 24, 32, 48, 64, 128, 256)


def _png(lado: int) -> bytes:
    from PySide6.QtCore import QBuffer, QIODevice
    from app.ui.estudio.ojo import pixmap_simbolo

    imagen = pixmap_simbolo(lado).toImage()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    imagen.save(buf, "PNG")
    return bytes(buf.data())


def _ico(pngs: list[tuple[int, bytes]]) -> bytes:
    cabecera = struct.pack("<HHH", 0, 1, len(pngs))
    entradas = b""
    datos = b""
    offset = 6 + 16 * len(pngs)
    for lado, blob in pngs:
        ancho = 0 if lado >= 256 else lado
        entradas += struct.pack("<BBBBHHII", ancho, ancho, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        datos += blob
    return cabecera + entradas + datos


def main() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    pngs = [(lado, _png(lado)) for lado in TAMANOS]
    destino = RAIZ / "installer" / "logo.ico"
    destino.write_bytes(_ico(pngs))
    print(f"Icono con {len(pngs)} tamaños en {destino}")


if __name__ == "__main__":
    main()
