"""Comprueba si un objeto de Qt sigue vivo antes de tocarlo.

Shiboken puede conservar el envoltorio de Python cuando el C++ ya se borró.
Llamar a un método entonces cierra el programa con RuntimeError.
La pantalla sencilla destruye el editor de vídeo. Esos nombres se leen a
través de un puente: si el C++ ya no existe, la llamada no hace nada.
"""

from __future__ import annotations

# Widgets y layouts del editor de vídeo. La pantalla sencilla no los crea.
NOMBRES_EDITOR = frozenset(
    {
        "videoSeekSlider",
        "videoSeekLineEdit",
        "timelineZoomSlider",
        "timelineScrollArea",
        "zoomLabel",
        "videoTimeLineEdit",
        "videoFpsLineEdit",
        "boxesLabel",
        "buttonMediaPlay",
        "buttonMediaRecord",
        "buttonMediaStop",
        "frameAdvanceButton",
        "frameRewindButton",
        "addMarkerButton",
        "removeMarkerButton",
        "previousMarkerButton",
        "nextMarkerButton",
        "liveSoundButton",
        "viewFullScreenButton",
        "theatreModeButton",
        "scanToolsToggleButton",
        "swapfacesButton",
        "editFacesButton",
        "findTargetFacesButton",
        "clearTargetFacesButton",
        "saveImageButton",
        "faceCompareCheckBox",
        "faceMaskCheckBox",
        "mediaControlsMainLayout",
        "mediaControlsCenterLayout",
        "mediaControlsViewportLayout",
        "mediaControlsViewportWidget",
        "mediaControlsCenterWidget",
        "horizontalLayoutMediaButtons",
        "horizontalLayoutMediaSlider",
        "controlButtonsLayout",
        "rightSideMediaWidget",
        "rightSideMediaLayout",
        "boxesLayout",
        "zoomLayout",
        "timelineContainer",
        "mediaLayout",
    }
)

_DEFECTO_METODO = {
    "indexOf": -1,
    "spacing": 0,
    "count": 0,
    "value": 0,
    "maximum": 0,
    "minimum": 0,
}


def qt_sigue(obj) -> bool:
    if obj is None or isinstance(obj, PuenteWidget):
        return False
    try:
        import shiboken6
    except ImportError:
        return True
    try:
        return bool(shiboken6.isValid(obj))
    except Exception:
        return False


def tocar(obj, accion) -> bool:
    """Ejecuta accion(obj) solo si el objeto de Qt sigue vivo."""
    if isinstance(obj, PuenteWidget):
        if not obj:
            return False
        try:
            accion(obj)
        except RuntimeError:
            return False
        return True
    if not qt_sigue(obj):
        return False
    try:
        accion(obj)
    except RuntimeError:
        return False
    return True


class PuenteWidget:
    """Habla con un widget del editor. Si el C++ ya se borró, no lanza."""

    def __init__(self, nombre: str, widget, ventana):
        object.__setattr__(self, "_nombre", nombre)
        object.__setattr__(self, "_widget", widget)
        object.__setattr__(self, "_ventana", ventana)
        object.__setattr__(self, "markers", set())

    def _vivo(self) -> bool:
        return qt_sigue(object.__getattribute__(self, "_widget"))

    def _llamar(self, metodo: str, por_defecto, *args, **kwargs):
        widget = object.__getattribute__(self, "_widget")
        if not qt_sigue(widget):
            return por_defecto
        try:
            return getattr(widget, metodo)(*args, **kwargs)
        except RuntimeError:
            return por_defecto

    def __bool__(self) -> bool:
        return self._vivo()

    def value(self) -> int:
        try:
            return int(self._llamar("value", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def maximum(self) -> int:
        try:
            return int(self._llamar("maximum", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def minimum(self) -> int:
        try:
            return int(self._llamar("minimum", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def isChecked(self) -> bool:
        nombre = object.__getattribute__(self, "_nombre")
        ventana = object.__getattribute__(self, "_ventana")
        widget = object.__getattribute__(self, "_widget")
        if qt_sigue(widget):
            try:
                return bool(widget.isChecked())
            except RuntimeError:
                pass
        if nombre == "swapfacesButton":
            return bool(getattr(ventana, "_cambio_activo", False))
        if nombre == "editFacesButton":
            return bool(getattr(ventana, "_edicion_activa", False))
        return False

    def setChecked(self, valor) -> None:
        nombre = object.__getattribute__(self, "_nombre")
        ventana = object.__getattribute__(self, "_ventana")
        if nombre == "swapfacesButton":
            ventana._cambio_activo = bool(valor)
        elif nombre == "editFacesButton":
            ventana._edicion_activa = bool(valor)
        self._llamar("setChecked", None, bool(valor))

    def click(self) -> None:
        nombre = object.__getattribute__(self, "_nombre")
        ventana = object.__getattribute__(self, "_ventana")
        if not self._vivo():
            if nombre == "swapfacesButton":
                ventana._cambio_activo = not bool(getattr(ventana, "_cambio_activo", False))
            return
        self._llamar("click", None)
        if nombre == "swapfacesButton":
            try:
                ventana._cambio_activo = bool(self._llamar("isChecked", False))
            except RuntimeError:
                pass

    def __getattr__(self, item):
        def metodo(*args, **kwargs):
            return self._llamar(item, _DEFECTO_METODO.get(item), *args, **kwargs)

        return metodo


def leer_editor(ventana, nombre: str):
    """Lee un widget del editor sin pasar por Shiboken.

    En un QMainWindow, recuperar el atributo de un widget ya borrado lanza
    RuntimeError antes de que podamos comprobar si sigue vivo. object.__getattribute__
    devuelve el envoltorio de Python y el puente absorbe la llamada.
    """
    valor = object.__getattribute__(ventana, nombre)
    return atributo_editor(ventana, nombre, valor)


def atributo_editor(ventana, nombre: str, valor):
    """Devuelve el widget real, o un puente si la pantalla sencilla ya está puesta."""
    if nombre not in NOMBRES_EDITOR:
        return valor
    try:
        protegido = object.__getattribute__(ventana, "_editor_protegido")
    except AttributeError:
        return valor
    if not protegido:
        return valor
    return PuenteWidget(nombre, valor, ventana)


def valor_de(widget, por_defecto: int = 0) -> int:
    if isinstance(widget, PuenteWidget):
        return widget.value()
    if not qt_sigue(widget):
        return por_defecto
    try:
        return int(widget.value())
    except Exception:
        return por_defecto


def valor_slider(ventana, por_defecto: int = 0) -> int:
    return valor_de(getattr(ventana, "videoSeekSlider", None), por_defecto)


def slider_responde(ventana) -> bool:
    slider = getattr(ventana, "videoSeekSlider", None)
    if isinstance(slider, PuenteWidget):
        return bool(slider)
    return qt_sigue(slider)


def marcado(widget, por_defecto: bool = False) -> bool:
    if isinstance(widget, PuenteWidget):
        return bool(widget.isChecked())
    if widget is None or not qt_sigue(widget):
        return por_defecto
    try:
        return bool(widget.isChecked())
    except RuntimeError:
        return por_defecto


def cambio_activo(ventana) -> bool:
    """El cambio de cara sigue activo aunque el botón del editor ya no exista."""
    boton = getattr(ventana, "swapfacesButton", None)
    if isinstance(boton, PuenteWidget) or qt_sigue(boton):
        try:
            return bool(boton.isChecked())
        except RuntimeError:
            pass
    return bool(getattr(ventana, "_cambio_activo", False))


def edicion_activa(ventana) -> bool:
    boton = getattr(ventana, "editFacesButton", None)
    if isinstance(boton, PuenteWidget) or qt_sigue(boton):
        try:
            return bool(boton.isChecked())
        except RuntimeError:
            pass
    return bool(getattr(ventana, "_edicion_activa", False))


def casilla(ventana, nombre: str, por_defecto: bool = False) -> bool:
    widget = getattr(ventana, nombre, None)
    return marcado(widget, por_defecto)


def sincronizar_espaciado(layout, vista, centro, separadores, espaciado=12, margen=12) -> bool:
    """Ajusta el espaciado solo si el layout y los widgets siguen existiendo."""
    if not (qt_sigue(layout) and qt_sigue(vista) and qt_sigue(centro)):
        return False
    try:
        layout.setSpacing(espaciado)
        for separador in separadores:
            if not qt_sigue(separador):
                continue
            caja = separador.layout()
            if not qt_sigue(caja):
                continue
            caja.setContentsMargins(margen, 0, margen, 0)
        ancho = max(centro.sizeHint().width(), centro.minimumSizeHint().width())
        vista.setMinimumWidth(ancho)
    except RuntimeError:
        return False
    return True
