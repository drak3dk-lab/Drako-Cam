"""Caché de motores TensorRT 10, FP16, y respaldo a CUDA.

Los motores se guardan por tarjeta y por versión de TensorRT. Un motor
compilado en la RTX 4050 del portátil no se reutiliza en una RTX 5070.
FP8 e INT8 no se activan: en estos modelos no conservan la identidad.
"""

from __future__ import annotations

import re
from pathlib import Path

# Blackwell de consumo (RTX 50) es sm_120. Hace falta TensorRT 10.10 o
# posterior. El proyecto fija tensorrt-cu13 10.16, que sí lo cubre.
_TRT_MINIMO_SM120 = (10, 10)
_TRT_MINIMO_SM100 = (10, 8)

MOTIVO_FP8_INT8 = (
    "FP8 e INT8 siguen apagados. En los modelos de identidad y de puntos "
    "de la cara la cuantización no conserva la calidad (el landmark TUFA "
    "ya falla en FP16) y no hay una calibración que lo justifique. "
    "La precisión por defecto es FP16."
)


def version_tupla(texto: str | None) -> tuple[int, ...]:
    if not texto:
        return (0,)
    numeros = [int(n) for n in re.findall(r"\d+", texto)]
    return tuple(numeros) if numeros else (0,)


def sirve_tensorrt(
    version: str | None, capacidad: tuple[int, int] | None
) -> tuple[bool, str]:
    """False cuando esta versión de TensorRT no puede construir para la GPU."""
    if not version:
        return False, "TensorRT no está importable. Se usa el proveedor CUDA."
    vt = version_tupla(version)
    if capacidad is not None and capacidad >= (12, 0) and vt < _TRT_MINIMO_SM120:
        sm = f"sm_{capacidad[0]}{capacidad[1]}"
        return (
            False,
            f"TensorRT {version} no construye motores para {sm} (Blackwell, RTX 50). "
            "Hace falta TensorRT 10.10 o posterior con CUDA 13 "
            "(el proyecto fija tensorrt-cu13 10.16). Se usa CUDA.",
        )
    if capacidad is not None and capacidad >= (10, 0) and vt < _TRT_MINIMO_SM100:
        return (
            False,
            f"TensorRT {version} es anterior al soporte Blackwell. Se usa CUDA.",
        )
    return True, ""


def precision_fp16(pedida: str | None, modelo_seguro: bool) -> tuple[bool, str | None]:
    """Devuelve (activar_fp16, aviso). FP8/INT8 se rechazan y no se activan."""
    texto = (pedida or "FP16").strip().lower()
    if texto in {"fp8", "int8"}:
        return bool(modelo_seguro), MOTIVO_FP8_INT8
    if texto == "fp32":
        return False, None
    return bool(modelo_seguro), None


def bytes_workspace(vram_bytes: int | None) -> int:
    """Tope del workspace de compilación. No se come la VRAM del directo."""
    gib = 1024**3
    minimo = gib
    if not vram_bytes or vram_bytes < minimo:
        return minimo
    techo = 2 * gib if vram_bytes < 12 * gib else 3 * gib
    return int(max(minimo, min(techo, int(vram_bytes * 0.35))))


def _slug(texto: str) -> str:
    limpio = []
    for caracter in (texto or "").lower():
        limpio.append(caracter if caracter.isalnum() else "_")
    salida = "".join(limpio).strip("_")
    while "__" in salida:
        salida = salida.replace("__", "_")
    return (salida or "gpu")[:80]


def clave_cache(
    nombre_gpu: str, capacidad: tuple[int, int] | None, version_trt: str | None
) -> str:
    """Clave de carpeta: modelo de GPU + SM + versión de TensorRT."""
    if capacidad is None:
        sm = "smdesconocida"
    else:
        sm = f"sm{capacidad[0]}{capacidad[1]}"
    version = version_trt or "0"
    return f"{_slug(nombre_gpu)}__{sm}__trt{version}"


def ruta_cache(
    nombre_gpu: str,
    capacidad: tuple[int, int] | None,
    version_trt: str | None,
    base: Path | None = None,
) -> Path:
    """Carpeta persistente. Por defecto, dentro de los datos de Drako Cam."""
    if base is None:
        from app.drako.rutas import directorio_datos

        base = directorio_datos()
    return (
        Path(base)
        / "tensorrt-engines"
        / clave_cache(nombre_gpu, capacidad, version_trt)
    )


def quitar_tensorrt(proveedores: list) -> list:
    """Lista de proveedores sin TensorRT, para el respaldo."""

    def _nombre(item: object) -> str:
        if isinstance(item, tuple) and item:
            return str(item[0])
        return str(item)

    return [p for p in proveedores if _nombre(p) != "TensorrtExecutionProvider"]


def describir_cuda(gpu_id: int = 0) -> dict:
    """Datos de la GPU y de TensorRT. Nunca lanza: campos vacíos si faltan."""
    info = {
        "nombre": "gpu",
        "capacidad": None,
        "vram": 0,
        "version_trt": None,
        "sirve": False,
        "motivo": "",
    }
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(gpu_id)
            info["nombre"] = str(getattr(props, "name", "gpu") or "gpu")
            info["vram"] = int(getattr(props, "total_memory", 0) or 0)
            mayor, menor = torch.cuda.get_device_capability(gpu_id)
            info["capacidad"] = (int(mayor), int(menor))
    except Exception:
        pass
    try:
        import tensorrt as trt

        info["version_trt"] = str(trt.__version__)
    except Exception:
        info["version_trt"] = None
    sirve, motivo = sirve_tensorrt(info["version_trt"], info["capacidad"])
    info["sirve"] = sirve
    info["motivo"] = motivo
    return info


def opciones_cache(gpu_id: int = 0, base: Path | None = None) -> dict:
    """Rutas y workspace listos para `trt_ep_options`."""
    info = describir_cuda(gpu_id)
    destino = ruta_cache(info["nombre"], info["capacidad"], info["version_trt"], base)
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    texto = str(destino)
    info["ruta"] = texto
    info["workspace"] = bytes_workspace(info["vram"] or None)
    info["opciones"] = {
        "trt_engine_cache_enable": True,
        "trt_engine_cache_path": texto,
        "trt_timing_cache_enable": True,
        "trt_timing_cache_path": texto,
        "trt_dump_ep_context_model": True,
        "trt_ep_context_file_path": texto,
        "trt_max_workspace_size": info["workspace"],
        "trt_builder_optimization_level": 3,
    }
    return info
