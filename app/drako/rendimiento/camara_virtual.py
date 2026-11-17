"""Salida a la cámara virtual propia de Drako Cam.

El fotograma del pipeline ya es BGR y va limpio: la cara con el filtro,
sin letreros ni recuadros de la interfaz. Se abre en BGR para no hacer
otra conversión. El fondo verde o transparente es opcional y se compone
en un buffer fijo del tamaño bloqueado.

En Windows el backend es Unity Capture, registrado como «Drako Cam».
OBS Virtual Camera solo se abre si esa cámara no está disponible.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfiguracionSalida:
    ancho: int
    alto: int
    fps: int
    fondo: str  # ninguno | verde | transparente
    formato: str  # bgr | rgba

    @classmethod
    def desde_control(
        cls,
        control: dict | None,
        fps_respaldo: float = 30,
        ancho_respaldo: int = 0,
        alto_respaldo: int = 0,
    ) -> "ConfiguracionSalida":
        control = control or {}
        ancho, alto = _parse_resolucion(
            str(control.get("WebcamMaxResSelection", "")),
            ancho_respaldo,
            alto_respaldo,
        )
        try:
            fps = int(control.get("WebCamMaxFPSSelection", 0) or 0)
        except (TypeError, ValueError):
            fps = 0
        if fps <= 0:
            fps = int(fps_respaldo) if fps_respaldo and fps_respaldo > 0 else 30
        fondo = str(control.get("FondoVirtualSelection", "Ninguno"))
        fondo_id = {"Verde": "verde", "Transparente": "transparente"}.get(
            fondo, "ninguno"
        )
        formato = "rgba" if fondo_id == "transparente" else "bgr"
        return cls(ancho=ancho, alto=alto, fps=fps, fondo=fondo_id, formato=formato)


def _parse_resolucion(texto: str, ancho: int, alto: int) -> tuple[int, int]:
    if "x" in texto.lower():
        try:
            a, b = texto.lower().split("x", 1)
            return max(1, int(a)), max(1, int(b))
        except ValueError:
            pass
    if ancho > 0 and alto > 0:
        return ancho, alto
    return 1280, 720


class PreparadorSalida:
    """Redimensiona y, si se pide, recorta el fondo. Reutiliza los buffers."""

    def __init__(self) -> None:
        self._bgr = None
        self._rgba = None
        self._mascara = None
        self._caja: tuple | None = None
        self.reservas = 0

    def preparar(self, frame, cfg: ConfiguracionSalida, bboxes=None):
        import numpy as np

        if frame is None:
            return None
        src = np.ascontiguousarray(frame)
        if src.ndim != 3 or src.shape[2] < 3:
            return src
        if cfg.formato == "rgba":
            destino = self._asegurar_rgba(cfg.alto, cfg.ancho)
        else:
            destino = self._asegurar_bgr(cfg.alto, cfg.ancho)
        self._copiar_redimension(
            src, destino[:, :, :3] if cfg.formato == "rgba" else destino
        )
        if cfg.fondo == "ninguno":
            return destino
        caja = _caja_principal(bboxes, destino.shape[1], destino.shape[0])
        if caja is None:
            return destino
        if cfg.fondo == "verde":
            _aplicar_verde(destino, caja, self)
            return destino
        _aplicar_alfa(destino, caja, self)
        return destino

    def _asegurar_bgr(self, alto: int, ancho: int):
        import numpy as np

        forma = (alto, ancho, 3)
        if self._bgr is None or self._bgr.shape != forma:
            self._bgr = np.empty(forma, dtype=np.uint8)
            self.reservas += 1
        return self._bgr

    def _asegurar_rgba(self, alto: int, ancho: int):
        import numpy as np

        forma = (alto, ancho, 4)
        if self._rgba is None or self._rgba.shape != forma:
            self._rgba = np.empty(forma, dtype=np.uint8)
            self.reservas += 1
        self._rgba[:, :, 3] = 255
        return self._rgba

    def _copiar_redimension(self, src, dst) -> None:
        import numpy as np

        if src.shape[0] == dst.shape[0] and src.shape[1] == dst.shape[1]:
            np.copyto(dst, src[:, :, :3])
            return
        try:
            import cv2

            cv2.resize(
                src[:, :, :3],
                (dst.shape[1], dst.shape[0]),
                dst=dst,
                interpolation=cv2.INTER_LINEAR,
            )
            return
        except Exception:
            pass
        ys = (np.linspace(0, src.shape[0] - 1, dst.shape[0])).astype(np.int32)
        xs = (np.linspace(0, src.shape[1] - 1, dst.shape[1])).astype(np.int32)
        np.copyto(dst, src[:, :, :3][ys][:, xs])


def _caja_principal(bboxes, ancho: int, alto: int) -> tuple[int, int, int, int] | None:
    if bboxes is None:
        return None
    try:
        if hasattr(bboxes, "size") and int(bboxes.size) == 0:
            return None
        if len(bboxes) == 0:
            return None
        fila = bboxes[0]
        x1, y1, x2, y2 = (
            float(fila[0]),
            float(fila[1]),
            float(fila[2]),
            float(fila[3]),
        )
    except Exception:
        return None
    margen_x = (x2 - x1) * 0.15
    margen_y = (y2 - y1) * 0.2
    ix1 = max(0, int(x1 - margen_x))
    iy1 = max(0, int(y1 - margen_y))
    ix2 = min(ancho, int(x2 + margen_x))
    iy2 = min(alto, int(y2 + margen_y))
    if ix2 <= ix1 or iy2 <= iy1:
        return None
    return ix1, iy1, ix2, iy2


def _mascara(
    preparador: PreparadorSalida, alto: int, ancho: int, caja: tuple[int, int, int, int]
):
    import numpy as np

    if (
        preparador._mascara is not None
        and preparador._caja == caja
        and preparador._mascara.shape
        == (
            alto,
            ancho,
        )
    ):
        return preparador._mascara
    mascara = np.zeros((alto, ancho), dtype=bool)
    x1, y1, x2, y2 = caja
    cy = (y1 + y2) * 0.5
    cx = (x1 + x2) * 0.5
    ry = max(1.0, (y2 - y1) * 0.5)
    rx = max(1.0, (x2 - x1) * 0.5)
    yy, xx = np.ogrid[0:alto, 0:ancho]
    mascara[((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0] = True
    preparador._mascara = mascara
    preparador._caja = caja
    preparador.reservas += 1
    return mascara


def _aplicar_verde(destino, caja, preparador: PreparadorSalida) -> None:
    mascara = _mascara(preparador, destino.shape[0], destino.shape[1], caja)
    fuera = ~mascara
    destino[fuera, 0] = 0
    destino[fuera, 1] = 255
    destino[fuera, 2] = 0


def encajar(frame, ancho: int, alto: int):
    """Deja el fotograma en el tamaño ya abierto. No reabre el dispositivo."""
    import numpy as np

    src = np.asarray(frame)
    if src.ndim != 3 or ancho <= 0 or alto <= 0:
        return src
    if src.shape[0] == alto and src.shape[1] == ancho:
        return src
    canales = src.shape[2]
    destino = np.empty((alto, ancho, canales), dtype=np.uint8)
    ys = np.linspace(0, src.shape[0] - 1, alto).astype(np.int32)
    xs = np.linspace(0, src.shape[1] - 1, ancho).astype(np.int32)
    np.copyto(destino, src[ys][:, xs])
    return destino


def _aplicar_alfa(destino, caja, preparador: PreparadorSalida) -> None:
    mascara = _mascara(preparador, destino.shape[0], destino.shape[1], caja)
    destino[:, :, 3] = 0
    destino[mascara, 3] = 255


# Nombre que ve Meet, Zoom y Teams. Unity Capture lo guarda en el registro
# al llamar a regsvr32 /i:UnityCaptureName=...
NOMBRE_DRAKO = "Drako Cam"
NOMBRE_UNITY = "Unity Video Capture"
BACKEND_UNITY = "unitycapture"
BACKEND_OBS = "obs"

# CLSID del dispositivo 0 en schellingb/UnityCapture (filtro DirectShow).
CLSID_64 = "{5C2CD55C-92AD-4999-8666-912BD3E70010}"
CLSID_32 = "{5C2CD55C-92AD-4999-8666-912BD3E70020}"


def intentos(backend: str | None = None) -> list[tuple[str, str | None]]:
    """Unity Capture primero. OBS solo entra si la cámara propia no abre.

    El ajuste heredado puede decir ``obs``. No cambia el orden: la cámara
    «Drako Cam» se prueba igual. ``None`` como dispositivo deja que el
    backend use el primero que tenga registrado.
    """
    pedido = str(backend or "auto").strip().lower()
    unity = [
        (BACKEND_UNITY, NOMBRE_DRAKO),
        (BACKEND_UNITY, NOMBRE_UNITY),
        (BACKEND_UNITY, None),
    ]
    obs = [(BACKEND_OBS, None)]
    if pedido == "obs":
        return unity + obs
    return unity + obs


def _ausente(exc: BaseException) -> bool:
    texto = str(exc).lower()
    marcas = (
        "no camera",
        "no virtual camera",
        "not installed",
        "did you install",
        "not found",
        "failed to find",
        "no se encuentra",
    )
    return any(marca in texto for marca in marcas)


@dataclass(frozen=True)
class ResultadoApertura:
    camara: object
    backend: str
    dispositivo: str
    codigo: str  # drako | unity | obs | ninguna


def abrir_con_respaldo(
    abrir,
    backend_pedido: str | None = None,
    pausa=None,
    al_fallar=None,
) -> ResultadoApertura:
    """Prueba cada candidato. Reintenta una vez solo si el fallo no es «no está»."""
    if pausa is None:
        import time

        pausa = time.sleep
    for backend, device in intentos(backend_pedido):
        for intento in (1, 2):
            try:
                camara = abrir(backend, device)
            except Exception as exc:
                if al_fallar is not None:
                    al_fallar(backend, device, exc, intento)
                if _ausente(exc) or intento == 2:
                    break
                pausa(0.4)
                continue
            nombre = str(getattr(camara, "device", "") or device or "")
            return ResultadoApertura(
                camara, backend, nombre, _codigo(backend, nombre)
            )
    return ResultadoApertura(None, "", "", "ninguna")


def _codigo(backend: str, nombre: str) -> str:
    if backend == BACKEND_OBS:
        return "obs"
    if nombre.strip() == NOMBRE_DRAKO:
        return "drako"
    return "unity"


def titulo_para_usuario(codigo: str) -> str:
    if codigo == "ninguna":
        return "Cámara virtual no disponible"
    if codigo == "obs":
        return "Respaldo OBS"
    return "Cámara virtual"


def mensaje_para_usuario(codigo: str, dispositivo: str = "") -> str | None:
    if codigo == "drako":
        return None
    if codigo == "unity":
        visto = dispositivo.strip() or NOMBRE_UNITY
        return (
            f"La cámara virtual responde como «{visto}», no como «{NOMBRE_DRAKO}». "
            "En Meet, Zoom o Teams elige ese nombre. "
            "Para verla como «Drako Cam», ejecuta Instalar.bat como administrador."
        )
    if codigo == "obs":
        return (
            "No está la cámara «Drako Cam». Se usa OBS Virtual Camera como respaldo. "
            "OBS no es obligatorio: cierra Drako Cam y ejecuta Instalar.bat como "
            "administrador para registrar la cámara propia. Solo hace falta una vez."
        )
    if codigo == "ninguna":
        return (
            "No se pudo abrir la cámara virtual. Ejecuta Instalar.bat como "
            "administrador para registrar «Drako Cam». Solo hace falta una vez. "
            "No hace falta tener OBS instalado ni abierto."
        )
    return None


def ya_registrada(nombre: str, servidor: str, dll: str) -> bool:
    """True si ese CLSID ya apunta a nuestra DLL y se llama Drako Cam."""
    if str(nombre or "").strip() != NOMBRE_DRAKO:
        return False
    if not servidor or not dll:
        return False
    import os

    try:
        return os.path.normcase(os.path.abspath(servidor)) == os.path.normcase(
            os.path.abspath(dll)
        )
    except OSError:
        return False


def separar_vista_y_salida(paquete):
    """La vista de la app puede llevar adornos. La salida a la cámara, no."""
    if (
        isinstance(paquete, tuple)
        and len(paquete) == 2
        and getattr(paquete[0], "shape", None) is not None
        and getattr(paquete[1], "shape", None) is not None
    ):
        return paquete[0], paquete[1]
    return paquete, paquete


def hay_adornos_de_interfaz(control: dict | None, comparar: bool = False) -> bool:
    """Recuadros, puntos y la comparación son de la interfaz, no de la señal."""
    if comparar:
        return True
    control = control or {}
    return bool(
        control.get("ShowAllDetectedFacesBBoxToggle")
        or control.get("ShowByteTrackBBoxToggle")
        or control.get("ShowLandmarksEnableToggle")
    )
