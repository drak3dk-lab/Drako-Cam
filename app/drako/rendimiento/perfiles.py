"""Perfiles de VRAM según la GPU detectada.

El público de Drako Cam usa RTX 5060–5080 (Blackwell, 8–16 GB).
El portátil de desarrollo (RTX 4050, 6 GB) queda como perfil de respaldo.
"""

from __future__ import annotations

from dataclasses import dataclass

ID_6GB = "portatil_6gb"
ID_8GB = "equilibrado_8gb"
ID_ALTO = "alto_12gb"

ETIQUETA_AUTO = "Auto"
ETIQUETA_8GB = "Equilibrado 8 GB"
ETIQUETA_ALTO = "Alto 12-16 GB"
ETIQUETA_6GB = "6 GB (portátil)"

_ETIQUETAS = {
    ETIQUETA_8GB: ID_8GB,
    ETIQUETA_ALTO: ID_ALTO,
    ETIQUETA_6GB: ID_6GB,
}

# Resoluciones que el propio perfil escribe. Una resolución distinta
# (el usuario la eligió) no se pisa en el siguiente arranque.
RESOLUCIONES_DE_PERFIL = frozenset({"1280x720", "1920x1080"})


@dataclass(frozen=True)
class Perfil:
    id: str
    titulo: str
    resolucion: str
    fps: int
    permite_60: bool
    deteccion_cada: int
    hilos: int
    tope_gb: float | None
    mejoradores_pesados: bool
    mejoradores_perezosos: bool
    un_swapper: bool = True

    @property
    def etiqueta(self) -> str:
        for texto, ident in _ETIQUETAS.items():
            if ident == self.id:
                return texto
        return self.titulo


PERFIL_6GB = Perfil(
    id=ID_6GB,
    titulo="6 GB (portátil)",
    resolucion="1280x720",
    fps=30,
    permite_60=False,
    deteccion_cada=2,
    hilos=1,
    tope_gb=4.5,
    mejoradores_pesados=False,
    mejoradores_perezosos=True,
)
PERFIL_8GB = Perfil(
    id=ID_8GB,
    titulo="Equilibrado 8 GB",
    resolucion="1280x720",
    fps=30,
    permite_60=False,
    deteccion_cada=2,
    hilos=2,
    tope_gb=6.5,
    mejoradores_pesados=False,
    mejoradores_perezosos=True,
)
PERFIL_ALTO = Perfil(
    id=ID_ALTO,
    titulo="Alto 12-16 GB",
    resolucion="1920x1080",
    fps=30,
    permite_60=True,
    deteccion_cada=2,
    hilos=2,
    tope_gb=None,
    mejoradores_pesados=True,
    mejoradores_perezosos=False,
)

_POR_ID = {p.id: p for p in (PERFIL_6GB, PERFIL_8GB, PERFIL_ALTO)}


def perfil_por_id(ident: str) -> Perfil:
    return _POR_ID.get(ident, PERFIL_8GB)


def perfil_por_etiqueta(etiqueta: str) -> Perfil | None:
    ident = _ETIQUETAS.get(etiqueta)
    if ident is None:
        return None
    return perfil_por_id(ident)


def perfil_por_hardware(nombre: str, vram_bytes: int) -> Perfil:
    """Elige el perfil con el nombre de la GPU y la VRAM detectada.

    La VRAM manda cuando el nombre y el tamaño no coinciden: una
    5060 Ti de 16 GB entra en Alto. Una 4050 entra en el perfil de 6 GB
    aunque la lectura de memoria venga inflada por la memoria compartida.
    Sin datos, se asume el perfil de 8 GB (el caso más habitual).
    """
    texto = (nombre or "").lower()
    gb = (vram_bytes / (1024**3)) if vram_bytes else 0.0
    if "4050" in texto or (0 < gb < 7.5):
        return PERFIL_6GB
    if "5060" in texto and 0 < gb < 12:
        return PERFIL_8GB
    if gb >= 12 or any(modelo in texto for modelo in ("5070", "5080", "5090")):
        return PERFIL_ALTO
    if gb >= 7.5 or "5060" in texto or gb == 0:
        return PERFIL_8GB
    return PERFIL_6GB


def resolver_perfil(
    control: dict | None, nombre: str = "", vram_bytes: int = 0
) -> Perfil:
    """Perfil pedido en ajustes, o el automático si la selección es Auto."""
    control = control or {}
    etiqueta = str(control.get("PerfilVramSelection", ETIQUETA_AUTO))
    fijo = perfil_por_etiqueta(etiqueta)
    if fijo is not None:
        return fijo
    return perfil_por_hardware(nombre, vram_bytes)


def fraccion_vram(perfil: Perfil, vram_bytes: int | None) -> float | None:
    """Fracción de la VRAM que PyTorch puede reservar. None si no hay dato."""
    if not vram_bytes or vram_bytes <= 0:
        return None
    if perfil.tope_gb is None:
        return 0.85
    tope = perfil.tope_gb * (1024**3)
    return max(0.35, min(0.92, tope / vram_bytes))


def hilos_webcam(control: dict, perfil: Perfil) -> int:
    """Hilos de inferencia del directo. Con el canal nuevo, el perfil manda."""
    if not control.get("PipelineHilosEnableToggle", True):
        try:
            return max(1, int(control.get("nThreadsSlider", perfil.hilos)))
        except (TypeError, ValueError):
            return perfil.hilos
    return max(1, perfil.hilos)


def tamano_cola_inferencia(control: dict) -> int | None:
    """1 en directo: se procesa el fotograma nuevo y se tira el viejo."""
    if control.get("PipelineHilosEnableToggle", True):
        return 1
    return None


def es_rtx_50(nombre: str) -> bool:
    texto = (nombre or "").lower()
    return any(modelo in texto for modelo in ("5060", "5070", "5080", "5090"))


def con_captura(perfil: Perfil, nombre: str, vram_bytes: int = 0) -> Perfil:
    """720p en 6 y 8 GB. 1080p solo en una RTX 50."""
    from dataclasses import replace

    if es_rtx_50(nombre):
        return replace(perfil, resolucion="1920x1080")
    if perfil.id == ID_ALTO:
        return perfil
    return replace(perfil, resolucion="1280x720")


def _poner(ventana: object, clave: str, valor: object) -> None:
    control = getattr(ventana, "control", None)
    if isinstance(control, dict):
        control[clave] = valor
    widgets = getattr(ventana, "parameter_widgets", None) or {}
    widget = widgets.get(clave) if isinstance(widgets, dict) else None
    if widget is None or not hasattr(widget, "set_value"):
        return
    bloqueado = False
    if hasattr(widget, "blockSignals"):
        widget.blockSignals(True)
        bloqueado = True
    try:
        widget.set_value(valor)
    except Exception:
        pass
    finally:
        if bloqueado:
            widget.blockSignals(False)


def escribir_perfil(ventana: object, perfil: Perfil, *, forzar: bool) -> None:
    """Copia el perfil a los ajustes. La resolución solo cambia si `forzar`."""
    control = getattr(ventana, "control", None)
    if not isinstance(control, dict):
        return
    if forzar:
        actual = str(control.get("WebcamMaxResSelection", ""))
        if actual in RESOLUCIONES_DE_PERFIL or not actual:
            _poner(ventana, "WebcamMaxResSelection", perfil.resolucion)
        fps = str(control.get("WebCamMaxFPSSelection", "30"))
        if fps in {"23", "30", "60"} or forzar:
            nuevo_fps = perfil.fps
            if fps == "60" and perfil.permite_60:
                nuevo_fps = 60
            elif fps == "60" and not perfil.permite_60:
                nuevo_fps = 30
            elif actual in RESOLUCIONES_DE_PERFIL or not actual:
                nuevo_fps = perfil.fps
            _poner(ventana, "WebCamMaxFPSSelection", str(nuevo_fps))
        _poner(ventana, "nThreadsSlider", str(perfil.hilos))
        _poner(ventana, "DeteccionCadaNSlider", str(perfil.deteccion_cada))
        _poner(ventana, "UnSoloSwapperEnableToggle", perfil.un_swapper)
        _poner(
            ventana, "MejoradoresPerezososEnableToggle", perfil.mejoradores_perezosos
        )
        _poner(ventana, "PermitirMejoradoresPesadosToggle", perfil.mejoradores_pesados)
        control["_PerfilAplicado"] = perfil.id
    vp = getattr(ventana, "video_processor", None)
    if vp is not None and forzar:
        try:
            vp.num_threads = perfil.hilos
        except Exception:
            pass


def aplicar_al_arranque(
    ventana: object, nombre: str = "", vram_bytes: int = 0
) -> Perfil:
    """Aplica el perfil si cambió la GPU o es el primer arranque.

    No toca la licencia ni la sesión. Si el llamador no pasa hardware,
    se intenta leer CUDA; si no hay, se queda el perfil de 8 GB.
    """
    control = getattr(ventana, "control", None)
    if not isinstance(control, dict):
        return PERFIL_8GB
    if not nombre and not vram_bytes:
        hw = detectar_hardware()
        if hw is not None:
            nombre, vram_bytes = hw
    perfil = con_captura(resolver_perfil(control, nombre, vram_bytes), nombre, vram_bytes)
    forzar = control.get("_PerfilAplicado") != perfil.id
    escribir_perfil(ventana, perfil, forzar=forzar)
    return perfil


def detectar_hardware() -> tuple[str, int] | None:
    """(nombre, bytes) de la GPU CUDA actual, o None si no se puede leer."""
    try:
        import torch
    except Exception:
        return None
    try:
        if not torch.cuda.is_available():
            return None
        indice = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(indice)
        nombre = str(getattr(props, "name", "") or "")
        total = int(getattr(props, "total_memory", 0) or 0)
        return nombre, total
    except Exception:
        return None


def acciones_de_modelos(control: dict, perfil: Perfil) -> list[str]:
    """Qué hay que descargar al empezar el directo, sin tocar la GPU.

    Devuelve etiquetas para poder probarlas. Quien llama ejecuta las
    descargas si el procesador de modelos existe.
    """
    acciones: list[str] = []
    if control.get("UnSoloSwapperEnableToggle", perfil.un_swapper):
        acciones.append("un_swapper")
    perezoso = bool(
        control.get("MejoradoresPerezososEnableToggle", perfil.mejoradores_perezosos)
    )
    pesados = bool(
        control.get("PermitirMejoradoresPesadosToggle", perfil.mejoradores_pesados)
    )
    enhancer = bool(control.get("FrameEnhancerEnableToggle", False))
    restorer = bool(control.get("FaceRestorerEnableToggle", False)) or bool(
        control.get("FaceRestorerEnable2Toggle", False)
    )
    if perezoso and not enhancer:
        acciones.append("descargar_enhancer_inactivo")
    if perezoso and not restorer:
        acciones.append("descargar_restorer_inactivo")
    if enhancer and restorer and not pesados:
        acciones.append("quitar_enhancer_pesado")
    elif enhancer and pesados:
        acciones.append("conservar_enhancer")
    return acciones


def aplicar_acciones_de_modelos(ventana: object, acciones: list[str]) -> None:
    """Descarga modelos según `acciones_de_modelos`. No lanza."""
    fw = getattr(ventana, "function_worker", None)
    if fw is None:
        return
    try:
        if (
            "descargar_enhancer_inactivo" in acciones
            or "quitar_enhancer_pesado" in acciones
        ):
            fw.unload_frame_enhancer_models()
            if "quitar_enhancer_pesado" in acciones:
                print(
                    "[AVISO] Con menos de 12 GB no se dejan a la vez el mejorador "
                    "de fotograma y el restaurador. Se descarga el mejorador de "
                    "fotograma. En el perfil Alto (12 GB o más) pueden convivir."
                )
        if "descargar_restorer_inactivo" in acciones and hasattr(
            fw, "unload_face_restorer_models"
        ):
            fw.unload_face_restorer_models()
    except Exception as exc:
        print(f"[AVISO] No se pudieron ajustar los modelos en VRAM: {exc}")


def preparar_directo(video_processor: object) -> Perfil:
    """Ajusta hilos, cola y tope de VRAM justo antes del directo de webcam."""
    ventana = getattr(video_processor, "main_window", None)
    control = getattr(ventana, "control", {}) if ventana is not None else {}
    if not isinstance(control, dict):
        control = {}
    hw = detectar_hardware()
    nombre, vram = hw if hw is not None else ("", 0)
    perfil = resolver_perfil(control, nombre, vram)
    video_processor.num_threads = hilos_webcam(control, perfil)
    video_processor._cola_inferencia = tamano_cola_inferencia(control)
    from app.drako.rendimiento.watchdog import Vigilante

    video_processor.vigilante = Vigilante()
    video_processor.vigilante.latido()
    if ventana is not None and control.get("TopeVramAutomaticoEnableToggle", True):
        _aplicar_fraccion(getattr(ventana, "gpu_id", 0), perfil, vram)
        aplicar_acciones_de_modelos(ventana, acciones_de_modelos(control, perfil))
    return perfil


def _aplicar_fraccion(gpu_id: int, perfil: Perfil, vram_bytes: int) -> None:
    fraccion = fraccion_vram(perfil, vram_bytes or None)
    if fraccion is None:
        return
    try:
        import torch

        if not torch.cuda.is_available():
            return
        torch.cuda.set_per_process_memory_fraction(fraccion, int(gpu_id))
        print(f"[INFO] Tope de VRAM ({perfil.titulo}): {fraccion:.0%} de la tarjeta.")
    except Exception as exc:
        print(f"[AVISO] No se pudo aplicar el tope de VRAM: {exc}")
