"""Descarga y verifica solo los modelos del cambio de cara en vivo.

No se ejecuta al importar el módulo: hay que llamar a descargar_modelos()
o lanzar `python download_models.py`. No termina bien hasta que todos
los requeridos están en disco y el SHA-256 coincide. Si se corta la red,
reintenta y continúa desde lo ya bajado.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.helpers.downloader import download_file
from app.helpers.integrity_checker import check_file_integrity
from app.processors.models_data import modelos_requeridos

_log = logging.getLogger("drako.descarga")


def _omitir_hash() -> bool:
    # portable.cfg vive junto a la carpeta del programa en la instalación portable.
    cfg_path = Path(__file__).resolve().parent.parent / "portable.cfg"
    if not cfg_path.is_file():
        return False
    for line in cfg_path.read_text(encoding="utf-8").splitlines():
        if line.strip().upper() == "USE_OPTIMIZED_MODELS=TRUE":
            return True
    return False


def _nota(mensaje: str) -> None:
    print(mensaje, flush=True)
    _log.info(mensaje)


def _linea_ui(prefijo: str, texto: str) -> None:
    limpio = " ".join(str(texto).split())
    print(f"{prefijo} {limpio}", flush=True)


def comprobar_modelos(
    modelos: list[dict] | None = None,
    omitir_hash: bool = False,
) -> list[dict]:
    """Recorre los modelos y dice, uno por uno, si faltan o el hash no cuadra.

    Cada entrada tiene nombre, estado (ok, falta, corrupto) y detalle.
    """
    lista = list(modelos) if modelos is not None else modelos_requeridos()
    informe: list[dict] = []
    for modelo in lista:
        nombre = str(modelo["model_name"])
        ruta = Path(str(modelo["local_path"]))
        esperado = str(modelo.get("hash") or "")
        if not ruta.is_file() or ruta.stat().st_size == 0:
            informe.append(
                {
                    "nombre": nombre,
                    "estado": "falta",
                    "detalle": "no está",
                    "ruta": str(ruta),
                }
            )
            continue
        if omitir_hash or not esperado:
            informe.append(
                {
                    "nombre": nombre,
                    "estado": "ok",
                    "detalle": "está",
                    "ruta": str(ruta),
                }
            )
            continue
        if check_file_integrity(str(ruta), esperado):
            informe.append(
                {
                    "nombre": nombre,
                    "estado": "ok",
                    "detalle": "está y el hash coincide",
                    "ruta": str(ruta),
                }
            )
        else:
            informe.append(
                {
                    "nombre": nombre,
                    "estado": "corrupto",
                    "detalle": "el hash no coincide",
                    "ruta": str(ruta),
                }
            )
    return informe


def descargar_modelos(
    al_estado=None,
    al_porcentaje=None,
    modelos: list[dict] | None = None,
    **opciones_descarga,
) -> bool:
    """True solo cuando todos los requeridos pasaron presencia y SHA-256."""
    lista = list(modelos) if modelos is not None else modelos_requeridos()
    if not lista:
        _nota("[ERROR] No hay modelos requeridos que comprobar.")
        return False

    skip_hash = _omitir_hash()
    total = len(lista)
    _nota(
        "[INFO] Drako Cam comprueba los modelos del cambio de cara en vivo "
        f"({total}). El resto no se descarga."
    )

    def _estado(texto: str) -> None:
        _linea_ui("DRAKO_ESTADO", texto)
        _nota(f"[INFO] {texto}")
        if al_estado is not None:
            al_estado(texto)

    _estado("Comprobando los modelos del cambio de cara")
    _marcar(0, al_porcentaje)

    while True:
        informe = comprobar_modelos(lista, omitir_hash=skip_hash)
        for item in informe:
            _nota(f"[INFO] {item['nombre']}: {item['detalle']}.")
        malos = [item["nombre"] for item in informe if item["estado"] != "ok"]
        if not malos:
            _nota(
                "[INFO] Todos los modelos requeridos están completos "
                "y el hash coincide."
            )
            _estado("Modelos del cambio de cara listos")
            _marcar(100, al_porcentaje)
            return True

        _nota(
            "[AVISO] Aún no están listos: "
            + ", ".join(malos)
            + ". No termino hasta que todos pasen."
        )
        nombres_malos = set(malos)
        alguno_fallo = False
        for indice, modelo in enumerate(lista):
            nombre = str(modelo["model_name"])
            if nombre not in nombres_malos:
                continue
            _estado(f"Bajando {nombre} ({indice + 1} de {total})")

            def _progreso(bajados: int, tamano: int, indice: int = indice) -> None:
                if tamano > 0:
                    fraccion = min(1.0, bajados / tamano)
                else:
                    fraccion = 0.0
                porcentaje = int((indice + fraccion) / total * 100)
                _marcar(min(porcentaje, 99), al_porcentaje)

            ok = download_file(
                nombre,
                modelo["local_path"],
                modelo["hash"],
                modelo["url"],
                skip_hash_check=skip_hash,
                al_progreso=_progreso,
                al_estado=_estado,
                **opciones_descarga,
            )
            if not ok:
                _nota(f"[ERROR] «{nombre}» no quedó verificado.")
                alguno_fallo = True
                break
        if alguno_fallo:
            return False


def _marcar(valor: int, al_porcentaje) -> None:
    ajustado = max(0, min(100, int(valor)))
    _linea_ui("DRAKO_PORCIENTO", str(ajustado))
    if al_porcentaje is not None:
        al_porcentaje(ajustado)


if __name__ == "__main__":
    raise SystemExit(0 if descargar_modelos() else 1)
