"""Descarga los modelos que faltan y comprueba su SHA-256.

No se ejecuta al importar el módulo: hay que llamar a descargar_modelos()
o lanzar `python download_models.py`.
"""

from pathlib import Path

from app.helpers.downloader import download_file
from app.processors.models_data import models_list


def _omitir_hash() -> bool:
    # portable.cfg vive junto a la carpeta del programa en la instalación portable.
    cfg_path = Path(__file__).resolve().parent.parent / "portable.cfg"
    if not cfg_path.is_file():
        return False
    for line in cfg_path.read_text(encoding="utf-8").splitlines():
        if line.strip().upper() == "USE_OPTIMIZED_MODELS=TRUE":
            return True
    return False


def descargar_modelos() -> bool:
    """Devuelve True solo si todos los archivos quedan verificados."""
    skip_hash = _omitir_hash()
    print("[INFO] Drako Cam comprueba los modelos (hash SHA-256).")
    correctos = True
    for model_data in models_list:
        ok = download_file(
            model_data["model_name"],
            model_data["local_path"],
            model_data["hash"],
            model_data["url"],
            skip_hash_check=skip_hash,
        )
        correctos = correctos and bool(ok)
    if not correctos:
        print("[ERROR] Algún modelo no se descargó o no coincidió el hash.")
    return correctos


if __name__ == "__main__":
    raise SystemExit(0 if descargar_modelos() else 1)
