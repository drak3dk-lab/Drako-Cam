"""Clasificación de los pesos: esenciales del cambio de cara en vivo, o bajo demanda.

No hay un perfil de GPU que cambie de archivo. El trabajo de rendimiento
(hilos, limpieza de VRAM, TensorRT FP16) usa los mismos pesos en una RTX 4050
de 6 GB y en una RTX 5060-5080. Lo esencial es el camino por defecto a calidad
completa: el mismo archivo, no una versión recortada.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.processors.models_data import models_list

ESENCIAL = "esencial"
OPCIONAL = "opcional"

MENSAJE_SIN_CONEXION = (
    "No hay conexión. El cambio de cara sigue con los modelos ya instalados. "
    "Cuando haya red, descárgalo en Ajustes > Modelos."
)

_ALT_SWAP = (
    "Swapper alternativo. El camino por defecto usa Inswapper128; "
    "este archivo completo se descarga al elegirlo."
)
_ALT_ARC = (
    "Embedding de un swapper que no es el predeterminado. "
    "Inswapper128 usa Inswapper128ArcFace."
)
_ALT_DET = (
    "Detector alternativo. El camino en vivo usa RetinaFace. "
    "Se descarga al elegirlo en los ajustes."
)
_ALT_LMK = (
    "Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. "
    "Se descarga al elegirlo."
)
_ALT_REST = (
    "Restaurador alternativo. El predeterminado de los dos huecos es GFPGAN v1.4, "
    "con su peso completo. Este se descarga al elegirlo."
)
_ALT_MEJORA = (
    "Mejorador de fotograma distinto del predeterminado (RealESRGAN x2). "
    "Se descarga al elegirlo; el archivo es el peso completo de esa variante."
)
_COLOR = (
    "Colorización. No interviene en el cambio de cara en vivo. "
    "Se descarga al elegirla como mejorador de fotograma."
)
_EXPR = (
    "Expresión o editor (LivePortrait o PerformRecast). "
    "Apagado en el camino por defecto. Se descarga al activarlo."
)
_DENOISE = (
    "Denoiser Ref-LDM / VQGAN. No forma parte del cambio de cara por defecto. "
    "Se descarga al activar el denoiser."
)

# nombre -> (bytes, grupo, clase, por qué)
_META_FILAS: dict[str, tuple[int, str, str, str]] = {
    "Inswapper128": (
        277_680_638,
        "Intercambio",
        ESENCIAL,
        (
            "Swapper por defecto. El mismo archivo fp16 cubre 128, 256, 384, 512 y "
            "Auto: la calidad completa de ese modelo está aquí, no en otro peso."
        ),
    ),
    "Inswapper128ArcFace": (
        174_383_860,
        "Reconocimiento",
        ESENCIAL,
        (
            "Reconocimiento por defecto y embedding que Inswapper128 necesita para "
            "la identidad. Sin él el intercambio no tiene a quién parecerse."
        ),
    ),
    "RetinaFace": (
        16_923_827,
        "Detección",
        ESENCIAL,
        (
            "Detector por defecto. Sus 5 puntos alinean la cara. El seguimiento "
            "ByteTrack y la cámara virtual no añaden pesos."
        ),
    ),
    "FaceLandmark203": (
        114_666_491,
        "Puntos faciales",
        ESENCIAL,
        (
            "Puntos faciales por defecto (203). El programa lo trata como modelo "
            "esencial y lo conserva aunque se apaguen los demás landmarks."
        ),
    ),
    "Occluder": (
        57_308_418,
        "Máscara",
        ESENCIAL,
        (
            "Máscara de oclusión del camino de máscara. Hace falta para tapar manos "
            "y objetos a la calidad prevista, no es un sustituto más pequeño."
        ),
    ),
    "XSeg": (
        70_324_682,
        "Máscara",
        ESENCIAL,
        (
            "Segunda máscara (DFL XSeg). Canal independiente que se mezcla con la "
            "oclusión; el archivo es el modelo completo."
        ),
    ),
    "FaceParser": (
        93_632_554,
        "Máscara",
        ESENCIAL,
        (
            "Parser semántico de la cara. Delimita regiones y protege la boca "
            "cuando la oclusión está activa."
        ),
    ),
    "GFPGANv1.4": (
        340_256_690,
        "Restauración",
        ESENCIAL,
        (
            "Restaurador por defecto de los dos huecos. Es GFPGAN v1.4 completo, "
            "el que eligen los controles de calidad si no se cambia el tipo."
        ),
    ),
    "RealEsrganx2Plus": (
        33_619_494,
        "Mejora de fotograma",
        ESENCIAL,
        (
            "Mejorador de fotograma por defecto. Peso x2 completo. Las variantes x4 "
            "pesan lo mismo en calidad de su propia escala y se bajan al elegirlas; "
            "en 6 GB no son el ajuste por defecto."
        ),
    ),
    "AlphaFace": (554_528_732, "Intercambio", OPCIONAL, _ALT_SWAP),
    "AlphaFaceIdentityProjection": (
        1_048_704,
        "Intercambio",
        OPCIONAL,
        "Matriz de identidad de AlphaFace. Solo hace falta si se elige ese swapper.",
    ),
    "InStyleSwapper256 Version A": (277_295_431, "Intercambio", OPCIONAL, _ALT_SWAP),
    "InStyleSwapper256 Version B": (277_295_431, "Intercambio", OPCIONAL, _ALT_SWAP),
    "InStyleSwapper256 Version C": (277_295_431, "Intercambio", OPCIONAL, _ALT_SWAP),
    "SimSwap512": (239_249_146, "Intercambio", OPCIONAL, _ALT_SWAP),
    "GhostFacev1": (514_877_142, "Intercambio", OPCIONAL, _ALT_SWAP),
    "GhostFacev2": (738_728_361, "Intercambio", OPCIONAL, _ALT_SWAP),
    "GhostFacev3": (855_515_261, "Intercambio", OPCIONAL, _ALT_SWAP),
    "CSCS": (738_639_216, "Intercambio", OPCIONAL, _ALT_SWAP),
    "SimSwapArcFace": (208_969_332, "Reconocimiento", OPCIONAL, _ALT_ARC),
    "GhostArcFace": (260_678_021, "Reconocimiento", OPCIONAL, _ALT_ARC),
    "CSCSArcFace": (261_029_411, "Reconocimiento", OPCIONAL, _ALT_ARC),
    "CSCSIDArcFace": (262_080_575, "Reconocimiento", OPCIONAL, _ALT_ARC),
    "SCRFD2.5g": (3_290_207, "Detección", OPCIONAL, _ALT_DET),
    "YoloFace8n": (12_639_351, "Detección", OPCIONAL, _ALT_DET),
    "YunetN": (317_640, "Detección", OPCIONAL, _ALT_DET),
    "YoloFace11nVR180": (
        10_564_942,
        "Detección",
        OPCIONAL,
        "Detector de VR180. El modo VR está apagado por defecto. Se descarga al activarlo.",
    ),
    "YoloFace12nVR180": (
        10_518_494,
        "Detección",
        OPCIONAL,
        "Detector de VR180. El modo VR está apagado por defecto. Se descarga al activarlo.",
    ),
    "FaceLandmark5": (109_887_314, "Puntos faciales", OPCIONAL, _ALT_LMK),
    "FaceLandmark68": (97_904_402, "Puntos faciales", OPCIONAL, _ALT_LMK),
    "FaceLandmark3d68": (143_607_619, "Puntos faciales", OPCIONAL, _ALT_LMK),
    "FaceLandmark98": (43_701_237, "Puntos faciales", OPCIONAL, _ALT_LMK),
    "FaceLandmark106": (5_030_888, "Puntos faciales", OPCIONAL, _ALT_LMK),
    "FaceLandmark478": (4_955_447, "Puntos faciales", OPCIONAL, _ALT_LMK),
    "FaceLandmarkTUFA98": (146_485_992, "Puntos faciales", OPCIONAL, _ALT_LMK),
    "FaceLandmarkTUFA314": (147_481_325, "Puntos faciales", OPCIONAL, _ALT_LMK),
    "FaceLandmarkORFormer98": (75_339_735, "Puntos faciales", OPCIONAL, _ALT_LMK),
    "FaceBlendShapes": (
        1_862_967,
        "Puntos faciales",
        OPCIONAL,
        "Dependencia del landmark de 478 puntos. No lo usa el modelo de 203.",
    ),
    "RD64ClipText": (
        4_720_707,
        "Máscara",
        OPCIONAL,
        "Máscara por texto (CLIP). No es el parser de la cara. Se descarga al activarla.",
    ),
    "combo_relu3_3_relu3_1": (
        6_946_741,
        "Máscara",
        OPCIONAL,
        "Textura VGG para diferencia y transferencia. Apagada por defecto.",
    ),
    "GFPGAN1024": (365_875_079, "Restauración", OPCIONAL, _ALT_REST),
    "GPENBFR256": (75_715_262, "Restauración", OPCIONAL, _ALT_REST),
    "GPENBFR512": (284_250_449, "Restauración", OPCIONAL, _ALT_REST),
    "GPENBFR1024": (285_101_993, "Restauración", OPCIONAL, _ALT_REST),
    "GPENBFR2048": (285_469_146, "Restauración", OPCIONAL, _ALT_REST),
    "CodeFormer": (188_577_164, "Restauración", OPCIONAL, _ALT_REST),
    "VQFRv2": (359_622_963, "Restauración", OPCIONAL, _ALT_REST),
    "RestoreFormerPlusPlus": (147_850_126, "Restauración", OPCIONAL, _ALT_REST),
    "RealEsrganx4Plus": (33_606_180, "Mejora de fotograma", OPCIONAL, _ALT_MEJORA),
    "RealEsrx4v3": (4_871_181, "Mejora de fotograma", OPCIONAL, _ALT_MEJORA),
    "BSRGANx2": (33_531_571, "Mejora de fotograma", OPCIONAL, _ALT_MEJORA),
    "BSRGANx4": (33_606_180, "Mejora de fotograma", OPCIONAL, _ALT_MEJORA),
    "UltraSharpx4": (33_606_180, "Mejora de fotograma", OPCIONAL, _ALT_MEJORA),
    "UltraMixx4": (33_606_180, "Mejora de fotograma", OPCIONAL, _ALT_MEJORA),
    "DeoldifyArt": (127_578_150, "Color", OPCIONAL, _COLOR),
    "DeoldifyStable": (436_769_415, "Color", OPCIONAL, _COLOR),
    "DeoldifyVideo": (436_769_415, "Color", OPCIONAL, _COLOR),
    "DDColorArt": (979_790_589, "Color", OPCIONAL, _COLOR),
    "DDcolor": (979_790_589, "Color", OPCIONAL, _COLOR),
    "LivePortraitMotionExtractor": (112_648_514, "Expresión", OPCIONAL, _EXPR),
    "LivePortraitAppearanceFeatureExtractor": (3_355_896, "Expresión", OPCIONAL, _EXPR),
    "LivePortraitStitchingEye": (580_926, "Expresión", OPCIONAL, _EXPR),
    "LivePortraitStitchingLip": (150_609, "Expresión", OPCIONAL, _EXPR),
    "LivePortraitStitching": (182_363, "Expresión", OPCIONAL, _EXPR),
    "LivePortraitWarpingSpade": (421_233_092, "Expresión", OPCIONAL, _EXPR),
    "LivePortraitWarpingSpadeFix": (421_233_096, "Expresión", OPCIONAL, _EXPR),
    "PerformRecastAppearanceFeatureExtractor": (
        358_267_936,
        "Expresión",
        OPCIONAL,
        _EXPR,
    ),
    "PerformRecastMotionExtractor": (113_091_452, "Expresión", OPCIONAL, _EXPR),
    "PerformRecastWarpingModule": (205_083_656, "Expresión", OPCIONAL, _EXPR),
    "PerformRecastSpadeGenerator": (343_562_601, "Expresión", OPCIONAL, _EXPR),
    "RefLDMVAEEncoder": (92_469_009, "Denoiser", OPCIONAL, _DENOISE),
    "RefLDMVAEDecoder": (136_161_053, "Denoiser", OPCIONAL, _DENOISE),
    "RefLDM_UNET_EXTERNAL_KV": (471_789_072, "Denoiser", OPCIONAL, _DENOISE),
    "RefLdm": (1_171_354_376, "Denoiser", OPCIONAL, _DENOISE),
    "VQGAN": (778_550_621, "Denoiser", OPCIONAL, _DENOISE),
    "FaceReaging": (
        124_230_760,
        "Edad",
        OPCIONAL,
        "Cambio de edad. Apagado en el camino en vivo. Se descarga al activarlo.",
    ),
    "MouthActionDetector": (
        11_327_570,
        "Boca",
        OPCIONAL,
        "Detector de acción de boca para la expresión automática. Apagado por defecto.",
    ),
}


@dataclass(frozen=True)
class Ficha:
    nombre: str
    bytes: int
    grupo: str
    clase: str
    porque: str
    url: str
    local_path: str
    hash: str

    @property
    def esencial(self) -> bool:
        return self.clase == ESENCIAL


def fichas() -> list[Ficha]:
    """Todas las fichas, en el orden del registro."""
    salida: list[Ficha] = []
    for item in models_list:
        nombre = item["model_name"]
        bytes_, grupo, clase, porque = _META_FILAS[nombre]
        salida.append(
            Ficha(
                nombre=nombre,
                bytes=bytes_,
                grupo=grupo,
                clase=clase,
                porque=porque,
                url=item["url"],
                local_path=item["local_path"],
                hash=item["hash"],
            )
        )
    return salida


def ficha(nombre: str) -> Ficha:
    for item in fichas():
        if item.nombre == nombre:
            return item
    raise KeyError(nombre)


def esenciales() -> list[Ficha]:
    return [item for item in fichas() if item.esencial]


def opcionales() -> list[Ficha]:
    return [item for item in fichas() if not item.esencial]


def suma_bytes(items: list[Ficha]) -> int:
    return sum(item.bytes for item in items)


def archivo_presente(nombre: str) -> bool:
    """True si el archivo final ya está en disco. No recalcula el hash.

    Un archivo ya descargado —también uno optimizado, de otro tamaño— se
    reutiliza. La comprobación SHA-256 ocurre al descargar, no en cada fotograma.
    """
    from pathlib import Path

    ruta = Path(ficha(nombre).local_path)
    try:
        return ruta.is_file() and ruta.stat().st_size > 0
    except OSError:
        return False


def texto_tamano(cantidad: int) -> str:
    """Tamaño en unidades decimales (las de la descarga), con coma decimal."""
    if cantidad >= 1_000_000_000:
        return f"{cantidad / 1_000_000_000:.2f} GB".replace(".", ",")
    if cantidad >= 1_000_000:
        return f"{cantidad / 1_000_000:.0f} MB"
    if cantidad >= 1_000:
        return f"{cantidad / 1_000:.0f} KB"
    return f"{cantidad} B"


def texto_duracion(segundos: float | None) -> str:
    if segundos is None or segundos < 0 or segundos > 48 * 3600:
        return "calculando el tiempo"
    total = int(segundos)
    minutos, segs = divmod(total, 60)
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas} h {minutos} min"
    if minutos:
        return f"{minutos} min {segs} s"
    return f"{segs} s"


def texto_progreso(
    nombre: str,
    hechos: int,
    totales: int,
    segundos_restantes: float | None,
    listos: int,
    archivos: int,
) -> str:
    return (
        f"{nombre}: {texto_tamano(hechos)} de {texto_tamano(totales)}"
        f" · quedan {texto_duracion(segundos_restantes)}"
        f" · {listos} de {archivos} archivos"
    )
