"""Aspecto de la cara, aparte de la velocidad.

Hombre, barba, mujer y tono de piel se pueden juntar. Auto solo
mira el tono medio y el pelo de la mitad baja de la cara: no adivina
el género si no hay barba.
"""

from __future__ import annotations

import numpy as np

CLASE_PIEL = 1
CLASE_PELO = 17

ETIQUETAS = (
    ("auto", "Auto (recomendado)"),
    ("hombre-clara", "Hombre, piel clara"),
    ("hombre-oscura", "Hombre, piel oscura"),
    ("barba-clara", "Hombre con barba, piel clara"),
    ("barba-oscura", "Hombre con barba, piel oscura"),
    ("mujer-clara", "Mujer, piel clara"),
    ("mujer-oscura", "Mujer, piel oscura"),
)

_NEUTRO = {
    "ColorEnableToggle": True,
    "ColorBrightnessDecimalSlider": 1.0,
    "ColorContrastDecimalSlider": 1.0,
    "ColorSaturationDecimalSlider": 1.0,
    "ColorGammaDecimalSlider": 1.0,
    "ColorSharpnessDecimalSlider": 1.0,
    "ColorHueDecimalSlider": 0.0,
    "FaceParserEnableToggle": True,
    "HairParserSlider": 4,
    "NeckParserSlider": 2,
    "BorderTopSlider": 10,
    "BorderBottomSlider": 12,
    "TopBorderBlurSlider": 8,
    "BottomBorderBlurSlider": 8,
    "FinalBorderBlendEnableToggle": True,
    "FinalBorderBlendAmountSlider": 5,
    "PreSwapSharpnessDecimalSlider": 1.0,
    "AutoMouthMouthParserSlider": 8,
    "AutoMouthUpperLipParserSlider": 2,
    "AutoMouthLowerLipParserSlider": 10,
}

_PARTES = {
    "hombre": {
        "BorderBottomSlider": 14,
        "AutoMouthUpperLipParserSlider": 1,
        "PreSwapSharpnessDecimalSlider": 1.05,
        "HairParserSlider": 3,
    },
    "barba": {
        "HairParserSlider": 14,
        "BorderBottomSlider": 18,
        "BottomBorderBlurSlider": 12,
        "AutoMouthUpperLipParserSlider": 1,
        "AutoMouthLowerLipParserSlider": 8,
        "NeckParserSlider": 4,
    },
    "mujer": {
        "HairParserSlider": 10,
        "TopBorderBlurSlider": 12,
        "AutoMouthUpperLipParserSlider": 3,
        "PreSwapSharpnessDecimalSlider": 0.95,
        "FinalBorderBlendAmountSlider": 6,
    },
    "oscura": {
        "ColorBrightnessDecimalSlider": 1.06,
        "ColorSaturationDecimalSlider": 0.92,
        "ColorGammaDecimalSlider": 1.05,
        "ColorSharpnessDecimalSlider": 0.95,
    },
    "clara": {
        "ColorBrightnessDecimalSlider": 0.96,
        "ColorSaturationDecimalSlider": 0.98,
        "ColorGammaDecimalSlider": 0.98,
        "PreSwapSharpnessDecimalSlider": 1.05,
    },
}

_COMBOS = {
    "hombre-clara": ("hombre", "clara"),
    "hombre-oscura": ("hombre", "oscura"),
    "barba-clara": ("barba", "clara"),
    "barba-oscura": ("barba", "oscura"),
    "mujer-clara": ("mujer", "clara"),
    "mujer-oscura": ("mujer", "oscura"),
}


def valores_de_aspecto(ident: str) -> dict[str, object]:
    """Solo el aspecto. No toca resolución, FPS ni el restaurador."""
    valores = dict(_NEUTRO)
    for parte in _COMBOS.get(ident, ()):
        valores.update(_PARTES[parte])
    return valores


def sugerir(luminancia: float, fraccion_barba: float) -> tuple[str, str]:
    """Devuelve el identificador y una frase. Sin barba no elige hombre o mujer."""
    luz = float(np.clip(luminancia, 0.0, 1.0))
    barba = float(np.clip(fraccion_barba, 0.0, 1.0))
    piel = "oscura" if luz < 0.42 else "clara"
    tono = "Piel oscura" if piel == "oscura" else "Piel clara"
    if barba >= 0.10:
        return f"barba-{piel}", f"{tono}, hombre con barba"
    if barba >= 0.04:
        return f"hombre-{piel}", f"{tono}, hombre"
    return f"auto-{piel}", f"{tono}. No veo barba, así que no elijo hombre o mujer."


def valores_sugeridos(luminancia: float, fraccion_barba: float) -> tuple[dict[str, object], str]:
    ident, frase = sugerir(luminancia, fraccion_barba)
    if ident.startswith("auto-"):
        piel = ident.split("-", 1)[1]
        valores = dict(_NEUTRO)
        valores.update(_PARTES[piel])
        return valores, frase
    return valores_de_aspecto(ident), frase


def luminancia_piel(rgb: np.ndarray, etiquetas: np.ndarray | None = None) -> float:
    imagen = np.asarray(rgb)
    if etiquetas is None:
        return _luminancia_recorte(imagen)
    piel = np.asarray(etiquetas) == CLASE_PIEL
    if int(piel.sum()) < 10:
        return _luminancia_recorte(imagen)
    return float(imagen[piel].mean()) / 255.0


def fraccion_barba(etiquetas: np.ndarray | None) -> float:
    """Pelo en la mitad baja de la cara. Sin mapa, no hay barba que afirmar."""
    if etiquetas is None:
        return 0.0
    mapa = np.asarray(etiquetas)
    if mapa.ndim != 2 or mapa.size == 0:
        return 0.0
    alto = mapa.shape[0]
    zona = np.zeros(mapa.shape, dtype=bool)
    zona[int(alto * 0.55) : int(alto * 0.92), :] = True
    pelo = mapa == CLASE_PELO
    piel = mapa == CLASE_PIEL
    base = int((zona & (pelo | piel)).sum())
    if base < 10:
        return 0.0
    return float((zona & pelo).sum()) / float(base)


def _luminancia_recorte(imagen: np.ndarray) -> float:
    if imagen.size == 0:
        return 0.5
    alto, ancho = imagen.shape[:2]
    recorte = imagen[int(alto * 0.3) : int(alto * 0.7), int(ancho * 0.3) : int(ancho * 0.7)]
    if recorte.size == 0:
        recorte = imagen
    return float(recorte.mean()) / 255.0
