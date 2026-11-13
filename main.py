"""Drako Cam — cambio de cara en tiempo real.

Trabajo derivado de VisoMaster Fusion (GPL-3.0):
https://github.com/VisoMasterFusion/VisoMaster-Fusion

El acceso de administrador, el registro de uso y los avisos son de Drako Cam.
Los pesos de los modelos no van en el repositorio: se descargan al arrancar
y se comprueba su hash.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

# Hay que fijarlo antes de importar torch, que ocurre dentro de _run_app.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "garbage_collection_threshold:0.8")

MODULOS_DRAKO = (
    "app.drako",
    "app.drako.rutas",
    "app.drako.configuracion",
    "app.drako.clave",
    "app.drako.auditoria",
    "app.drako.telegram_cliente",
    "app.drako.sesion",
    "app.drako.registro",
    "app.drako.cuda_aviso",
    "app.drako.camara",
    "app.drako.arranque",
)


def _argumentos(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Drako Cam")
    parser.add_argument(
        "--gpu-id",
        type=int,
        default=0,
        help="Identificador de la GPU CUDA (predeterminado: 0).",
    )
    parser.add_argument(
        "--comprobar-importaciones",
        action="store_true",
        help="Comprueba la sintaxis y las importaciones de Drako Cam, y termina.",
    )
    parser.add_argument(
        "--omitir-modelos",
        action="store_true",
        help="No descarga modelos en este arranque.",
    )
    return parser.parse_known_args(argv)


def comprobar_importaciones() -> int:
    """Sale 0 si el código nuevo importa y el árbol Python tiene sintaxis válida."""
    errores: list[str] = []
    for ruta in list(RAIZ.glob("*.py")) + list((RAIZ / "app").rglob("*.py")):
        try:
            ast.parse(ruta.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errores.append(f"{ruta}: {exc}")
        except UnicodeError as exc:
            errores.append(f"{ruta}: {exc}")
    for nombre in MODULOS_DRAKO:
        try:
            __import__(nombre)
        except Exception as exc:
            errores.append(f"import {nombre}: {type(exc).__name__}: {exc}")
    if errores:
        print("Drako Cam: hay errores de importación o de sintaxis.", file=sys.stderr)
        for linea in errores:
            print(f"  - {linea}", file=sys.stderr)
        return 1
    print("Drako Cam: importaciones y sintaxis correctas.")
    print("PyTorch, Qt y CUDA se comprueban al abrir el programa en Windows.")
    return 0


def _avisar_modelos() -> bool:
    print(
        "[INFO] Comprobando modelos. Si faltan, se descargan y se verifica el hash."
    )
    print("[INFO] La primera vez puede tardar: hace falta red y varios gigabytes.")
    try:
        from download_models import descargar_modelos

        return descargar_modelos()
    except Exception as exc:
        print(f"[ERROR] No se pudieron comprobar los modelos: {exc}")
        return False


def _run_app(argv: list[str] | None = None) -> int:
    args, restantes = _argumentos(argv)
    if args.comprobar_importaciones:
        return comprobar_importaciones()

    from app.drako.arranque import activar_sesion, preparar_contexto
    from app.drako.configuracion import ConfiguracionDanada
    from app.drako.cuda_aviso import mensaje_sin_cuda
    from app.drako.dialogo import instalar_menu, solicitar_acceso
    from app.drako.registro import mensaje_para_usuario, ruta_log_actual
    from app.drako.sesion import fijar_sesion

    try:
        contexto = preparar_contexto()
    except ConfiguracionDanada as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    logger = contexto.logger
    logger.info("Arranque de Drako Cam.")

    import torch

    torch.set_grad_enabled(False)

    from PySide6 import QtWidgets

    import qdarktheme
    from app.ui import main_ui
    from app.ui.core.proxy_style import ProxyStyle

    aplicacion = QtWidgets.QApplication(restantes)
    aplicacion.setStyle(ProxyStyle())
    with open(RAIZ / "app" / "ui" / "styles" / "true_dark_styles.qss", "r", encoding="utf-8") as hoja:
        estilo = hoja.read()
    estilo = (
        qdarktheme.load_stylesheet(theme="dark", custom_colors={"primary": "#4090a3"})
        + "\n"
        + estilo
    )
    aplicacion.setStyleSheet(estilo)

    def mostrar_error(texto: str) -> None:
        QtWidgets.QMessageBox.critical(None, "Drako Cam — error inesperado", texto)

    from app.drako.registro import instalar_captura_global

    instalar_captura_global(
        logger, mostrar=mostrar_error, ruta_log=ruta_log_actual(contexto.directorio)
    )

    acceso = solicitar_acceso(contexto)
    if acceso is None:
        logger.info("Arranque cancelado en la pantalla de acceso.")
        return 0
    contrasena, pendientes = acceso
    try:
        sesion, claves = activar_sesion(contexto, contrasena, pendientes)
    finally:
        del contrasena
        del acceso

    omitir = args.omitir_modelos or os.environ.get("DRAKO_CAM_OMITIR_MODELOS") == "1"
    if not omitir and not _avisar_modelos():
        QtWidgets.QMessageBox.warning(
            None,
            "Drako Cam — modelos",
            "Algunos modelos no se descargaron o no pasaron la verificación de hash. "
            "Revisa la consola. Puedes volver a abrir el programa cuando haya red.",
        )

    ventana = main_ui.MainWindow(gpu_id=args.gpu_id)
    instalar_menu(ventana, contexto, claves)
    ventana.show()

    texto_cuda = mensaje_sin_cuda(bool(torch.cuda.is_available()))
    if texto_cuda:
        logger.warning(texto_cuda)
        QtWidgets.QMessageBox.warning(ventana, "Drako Cam — sin CUDA", texto_cuda)

    def al_salir() -> None:
        try:
            sesion.cerrar()
        finally:
            fijar_sesion(None)
            contexto.telegram.detener_reintentos()

    aplicacion.aboutToQuit.connect(al_salir)
    return aplicacion.exec()


def _mensaje_fatal(exc: BaseException) -> None:
    from app.drako.registro import mensaje_para_usuario
    from app.drako.rutas import directorio_datos

    ruta = directorio_datos() / "logs" / "drako-cam.log"
    texto = mensaje_para_usuario(exc, ruta if ruta.is_file() else None)
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)
    print("\nTraza completa:")
    traceback.print_exc()


if __name__ == "__main__":
    try:
        sys.exit(_run_app())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        try:
            _mensaje_fatal(exc)
        except Exception:
            print(f"[ERROR] Drako Cam se detuvo: {exc}", file=sys.stderr)
            traceback.print_exc()
        sys.exit(1)
