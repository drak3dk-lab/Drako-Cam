"""Canal en vivo de Drako Cam: perfiles de VRAM, colas y caché TensorRT.

El acceso, la licencia y el bot de Telegram no viven aquí.
Este paquete no importa PyTorch al cargarse: así la comprobación de
arranque puede importarlo en una máquina sin CUDA.
"""

from app.drako.rendimiento.perfiles import (
    PERFIL_6GB,
    PERFIL_8GB,
    PERFIL_ALTO,
    perfil_por_hardware,
)

__all__ = [
    "PERFIL_6GB",
    "PERFIL_8GB",
    "PERFIL_ALTO",
    "perfil_por_hardware",
]
