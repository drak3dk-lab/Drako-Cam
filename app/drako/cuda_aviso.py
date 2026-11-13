"""Texto del aviso cuando la máquina no tiene CUDA.

La decisión de mostrar el cuadro la toma quien llama: aquí solo está
el mensaje, para poder probarlo sin GPU.
"""

from __future__ import annotations


def mensaje_sin_cuda(hay_cuda: bool) -> str | None:
    if hay_cuda:
        return None
    return (
        "No se detectó CUDA en esta máquina. Drako Cam está pensado para una "
        "GPU NVIDIA (CUDA o TensorRT). El programa puede abrirse, pero el "
        "cambio de cara en tiempo real no usará la GPU y será demasiado lento. "
        "No se pasa a CPU en silencio: el proveedor será CPU porque esta "
        "máquina no ofrece CUDA. Instala un controlador NVIDIA reciente y "
        "comprueba que PyTorch ve la tarjeta."
    )
