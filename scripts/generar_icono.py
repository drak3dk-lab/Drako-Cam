"""Genera el icono del instalador a partir del SVG provisional.

El archivo que se sustituye es app/ui/core/media/logo.svg.
Luego: python scripts/generar_icono.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


def main() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    from app.ui.estudio.ojo import RUTA_LOGO, renderer

    _app = QApplication.instance() or QApplication([])
    destino = RAIZ / "installer" / "logo.ico"
    imagen = QImage(256, 256, QImage.Format.Format_ARGB32)
    imagen.fill(0)
    pintor = QPainter(imagen)
    renderer(False).render(pintor)
    pintor.end()
    if not imagen.save(str(destino), "ICO"):
        png = destino.with_suffix(".png")
        imagen.save(str(png), "PNG")
        raise SystemExit(f"Qt no escribió el ICO. Quedó el PNG en {png}.")
    print(f"Icono escrito en {destino} desde {RUTA_LOGO}")


if __name__ == "__main__":
    main()
