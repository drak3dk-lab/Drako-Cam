"""Descarga los modelos que faltan y comprueba su SHA-256.

Por defecto solo baja los esenciales del cambio de cara en vivo.
``--todos`` baja el catálogo completo. ``--modelo NOMBRE`` baja uno.

No se ejecuta al importar el módulo: hay que llamar a descargar_modelos()
o lanzar ``python download_models.py``.
"""

from __future__ import annotations

import argparse
import sys

from app.drako.catalogo_modelos import (
    esenciales,
    fichas,
    nombres_que_cambiarion,
    sellar_manifiesto,
    texto_progreso,
)
from app.drako.descarga_modelos import descargar_nombres


def _nombres(solo_esenciales: bool, nombres: list[str] | None) -> list[str]:
    if nombres:
        conocidos = {item.nombre for item in fichas()}
        desconocidos = [nombre for nombre in nombres if nombre not in conocidos]
        if desconocidos:
            print(f"[ERROR] Modelo desconocido: {', '.join(desconocidos)}")
            return []
        return list(nombres)
    if solo_esenciales:
        return [item.nombre for item in esenciales()]
    return [item.nombre for item in fichas()]


def descargar_modelos(
    solo_esenciales: bool = True,
    nombres: list[str] | None = None,
    trabajadores: int = 3,
    al_estado=None,
) -> bool:
    """Devuelve True solo si todos los archivos pedidos quedan verificados."""
    pedidos = _nombres(solo_esenciales, nombres)
    if nombres and not pedidos:
        return False
    if not pedidos:
        print("[ERROR] No hay modelos que descargar.")
        return False
    if not nombres:
        cambiaron = [nombre for nombre in nombres_que_cambiarion() if nombre in pedidos]
        if not cambiaron:
            print("[INFO] Modelos del directo listos.")
            if al_estado:
                al_estado("Modelos del directo listos.", 100)
            return True
        pedidos = cambiaron
        print("[INFO] Comprobando los modelos del directo que cambiaron o faltan.")
    else:
        print("[INFO] Drako Cam descarga los modelos pedidos y comprueba el hash.")
    if al_estado:
        al_estado("Comprobando los modelos del directo…", 15)

    def _progreso(nombre, hechos, totales, eta, listos, archivos) -> None:
        linea = texto_progreso(nombre, hechos, totales, eta, listos, archivos)
        print("\r" + linea[:160].ljust(160), end="", flush=True)

    resultado = descargar_nombres(
        pedidos,
        trabajadores=trabajadores,
        al_progreso=_progreso,
    )
    print()
    if resultado.correcto:
        sellar_manifiesto([item.nombre for item in resultado.archivos])
        print(f"[INFO] Listo: {len(resultado.archivos)} archivo(s) en su sitio.")
        if al_estado:
            al_estado("Modelos del directo listos.", 100)
        return True
    print("[ERROR] Algún modelo no se descargó o no coincidió el hash.")
    for item in resultado.archivos:
        if item.estado not in ("ok", "omitido"):
            print(f"[ERROR] {item.nombre}: {item.estado}. {item.detalle}")
    return False


def _argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Descarga modelos de Drako Cam")
    parser.add_argument(
        "--todos",
        action="store_true",
        help="Descarga también los modelos opcionales.",
    )
    parser.add_argument(
        "--modelo",
        action="append",
        default=[],
        help="Descarga solo este modelo (se puede repetir).",
    )
    parser.add_argument("--trabajadores", type=int, default=3)
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _argumentos()
    correcto = descargar_modelos(
        solo_esenciales=not args.todos,
        nombres=args.modelo or None,
        trabajadores=max(1, min(3, args.trabajadores)),
    )
    sys.exit(0 if correcto else 1)
