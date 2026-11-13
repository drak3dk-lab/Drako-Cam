"""Reglas de la pantalla sencilla, sin Qt ni modelos.

El directo pide una foto o un perfil, y EN VIVO.
La cámara ya está. Todo lo demás es un ajuste, no un paso.
"""

from __future__ import annotations

from dataclasses import dataclass

CALIDADES = ("Auto", "Máxima calidad", "Equilibrado", "Máximo FPS")
FONDOS = ("Normal", "Verde", "Transparente")
EXTENSIONES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})

MENSAJE_FOTO = "Elige una foto o un perfil. Sin eso, EN VIVO no puede cambiar la cara."
MENSAJE_CAMARA = "No encuentro la cámara. Conéctala y pulsa EN VIVO otra vez."
MENSAJE_CARA_PERDIDA = "No te veo bien. Acércate un poco y mira a la cámara."
MENSAJE_CARGANDO = "Preparando la foto. Un momento."

_FONDO_MOTOR = {
    "Normal": "Ninguno",
    "Verde": "Verde",
    "Transparente": "Transparente",
}


@dataclass(frozen=True)
class AjusteCalidad:
    resolucion: str | None
    fps: str | None
    deteccion_cada: int | None
    mejorar_cara: bool | None
    nota: str


@dataclass(frozen=True)
class CaraVista:
    id: str
    nombre: str
    ruta: str
    favorita: bool
    atajo: str


def extension_admitida(nombre: str) -> bool:
    punto = nombre.rfind(".")
    if punto < 0:
        return False
    return nombre[punto:].lower() in EXTENSIONES


def nombre_seguro(original: str) -> str:
    """Nombre de archivo, sin carpetas ni caracteres raros."""
    base = original.replace("\\", "/").split("/")[-1].strip()
    if not base or base in {".", ".."}:
        base = "cara"
    limpio = []
    for caracter in base:
        if caracter.isalnum() or caracter in "._- ":
            limpio.append(caracter)
        else:
            limpio.append("_")
    texto = "".join(limpio).strip(" .")
    return texto or "cara"


def indice_principal(
    cajas: list[tuple[float, float, float, float]], ancho: float, alto: float
) -> int:
    """La cara de enfrente: grande y cerca del centro. 0 si no hay cajas."""
    if not cajas:
        return 0
    centro_x = ancho / 2.0
    centro_y = alto / 2.0
    alcance = max((ancho * ancho + alto * alto) ** 0.5 / 2.0, 1.0)
    mejor = 0
    mejor_nota = -1.0
    for indice, (x1, y1, x2, y2) in enumerate(cajas):
        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        medio_x = (x1 + x2) / 2.0
        medio_y = (y1 + y2) / 2.0
        distancia = ((medio_x - centro_x) ** 2 + (medio_y - centro_y) ** 2) ** 0.5
        cercania = 1.0 - min(distancia / alcance, 1.0)
        nota = area * (0.45 + 0.55 * cercania)
        if nota > mejor_nota:
            mejor = indice
            mejor_nota = nota
    return mejor


def indice_persona(
    cajas: list[tuple[float, float, float, float]],
    ancho: float,
    alto: float,
    cual: str,
) -> int:
    """Principal, la de la izquierda o la de la derecha. Nunca pide una selección."""
    if not cajas:
        return 0
    if cual == "izquierda":
        return min(range(len(cajas)), key=lambda i: (cajas[i][0] + cajas[i][2]) / 2.0)
    if cual == "derecha":
        return max(range(len(cajas)), key=lambda i: (cajas[i][0] + cajas[i][2]) / 2.0)
    return indice_principal(cajas, ancho, alto)


def puede_entrar_en_vivo(tiene_foto: bool, tiene_camara: bool) -> str | None:
    if not tiene_foto:
        return MENSAJE_FOTO
    if not tiene_camara:
        return MENSAJE_CAMARA
    return None


def aviso_cara_perdida(
    sin_cara_desde: float | None, ahora: float, gracia: float = 1.2
) -> str | None:
    """Aviso solo si la cara lleva un rato fuera. El arranque no cuenta."""
    if sin_cara_desde is None:
        return None
    if ahora - sin_cara_desde < gracia:
        return None
    return MENSAJE_CARA_PERDIDA


def ajuste_calidad(nombre: str, permite_60: bool) -> AjusteCalidad:
    if nombre == "Máxima calidad":
        return AjusteCalidad(
            "1920x1080",
            "30",
            1,
            True,
            "Más detalle. La cara se restaura en cada fotograma.",
        )
    if nombre == "Equilibrado":
        return AjusteCalidad(
            "1920x1080",
            "30",
            2,
            False,
            "1080p a 30. Es el punto estable.",
        )
    if nombre == "Máximo FPS":
        fps = "60" if permite_60 else "30"
        nota = (
            "Prioriza los fotogramas."
            if permite_60
            else "Esta tarjeta se queda en 30 FPS para no ir a tirones."
        )
        return AjusteCalidad("1280x720", fps, 4, False, nota)
    return AjusteCalidad(None, None, None, None, "Según la tarjeta que haya en el equipo.")


def fuerza_a_motor(valor: int) -> int:
    """0–100 de la pantalla → pasadas del modelo. 50 es una pasada."""
    valor = max(0, min(100, int(valor)))
    return valor * 2


def nitidez_a_motor(valor: int) -> float:
    """0–100 → 0.0–2.0. 50 deja la nitidez neutra."""
    valor = max(0, min(100, int(valor)))
    return round(valor / 50.0, 2)


def frente_a_motor(valor: int) -> int:
    """0–100 → recorte superior 0–40. Más alto conserva más frente original."""
    valor = max(0, min(100, int(valor)))
    return int(round(valor * 0.4))


def fondo_a_motor(nombre: str) -> str:
    return _FONDO_MOTOR.get(nombre, "Ninguno")


def texto_para_obs(resolucion: str, fps: str, fondo: str) -> str:
    resolucion = (resolucion or "1920x1080").replace("x", " × ")
    return (
        "En OBS:\n"
        "Fuentes → Añadir → Dispositivo de captura de vídeo\n"
        "Dispositivo: Drako Cam\n"
        f"Resolución: {resolucion}\n"
        f"FPS: {fps or '30'}\n"
        f"Fondo: {fondo or 'Normal'}\n"
    )


def atajos_de_favoritas(ids_favoritas: list[str], limite: int = 8) -> dict[str, str]:
    """Las ocho primeras favoritas reciben F1…F8, en ese orden."""
    return {
        ident: f"F{indice + 1}"
        for indice, ident in enumerate(ids_favoritas[:limite])
    }
