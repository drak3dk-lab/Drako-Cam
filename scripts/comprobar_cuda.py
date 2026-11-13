"""Comprueba si PyTorch ve una GPU CUDA. Lo llama el instalador de Windows."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        import torch
    except Exception as exc:
        print(f"No se pudo cargar PyTorch: {type(exc).__name__}: {exc}")
        return 2
    version = getattr(torch, "__version__", "desconocida")
    print(f"PyTorch: {version}")
    try:
        visible = bool(torch.cuda.is_available())
    except Exception as exc:
        print(f"No se pudo consultar CUDA: {type(exc).__name__}: {exc}")
        return 1
    if not visible:
        print("CUDA visible: no")
        return 1
    print("CUDA visible: sí")
    try:
        nombre = torch.cuda.get_device_name(0)
    except Exception as exc:
        nombre = f"(sin nombre: {exc})"
    print(f"Tarjeta: {nombre}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
