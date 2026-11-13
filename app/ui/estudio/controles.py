"""Los ajustes de calidad que Drako ya usa, con nombre y valor claro.

No incluye lotes, el editor de cara ni LivePortrait: eso no hace
falta en el directo. Cada grupo se enciende con un interruptor.
El coste es orientativo: aquí no hay una GPU para medirlo en FPS.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Control:
    clave: str
    nombre: str
    ayuda: str
    tipo: str
    minimo: float = 0
    maximo: float = 100
    paso: float = 1
    decimales: int = 0
    predeterminado: object = 0
    opciones: tuple[str, ...] = ()
    muestra_si: str | None = None

    @property
    def recomendado(self) -> object:
        return self.predeterminado


@dataclass(frozen=True)
class Grupo:
    ident: str
    nombre: str
    coste: str
    frase: str
    maestro: str
    controles: tuple[Control, ...]


def _toggle(clave: str, nombre: str, ayuda: str, activo: bool = False, muestra_si: str | None = None) -> Control:
    return Control(clave, nombre, ayuda, "toggle", predeterminado=activo, muestra_si=muestra_si)


def _slider(
    clave: str,
    nombre: str,
    ayuda: str,
    minimo: float,
    maximo: float,
    predeterminado: float,
    *,
    paso: float = 1,
    decimales: int = 0,
    muestra_si: str | None = None,
) -> Control:
    return Control(
        clave,
        nombre,
        ayuda,
        "decimal" if decimales else "slider",
        minimo,
        maximo,
        paso,
        decimales,
        predeterminado,
        muestra_si=muestra_si,
    )


def _eleccion(clave: str, nombre: str, ayuda: str, opciones: tuple[str, ...], predeterminado: str, muestra_si: str | None = None) -> Control:
    return Control(
        clave,
        nombre,
        ayuda,
        "eleccion",
        predeterminado=predeterminado,
        opciones=opciones,
        muestra_si=muestra_si,
    )


_BOCA = "RestoreMouthEnableToggle"
_OJOS = "RestoreEyesEnableToggle"
_BORDES = "BordermaskEnableToggle"
_OCLUSION = "OccluderEnableToggle"
_RESTAURAR = "FaceRestorerEnableToggle"
_COLOR = "ColorEnableToggle"
_TEXTURA = "TransferTextureEnableToggle"
_ENCAJE = "MouthParserStretchToggle"
_BOCA_ORIGINAL = "MouthParserStretchOriginalToggle"
_PARSER = "FaceParserEnableToggle"
_FUSION = "FinalBlendAdjEnableToggle"
_COSTURA = "FinalBorderBlendEnableToggle"
_CARA = "FaceAdjEnableToggle"
_PUNTOS = "LandmarksPositionAdjEnableToggle"

GRUPOS: tuple[Grupo, ...] = (
    Grupo(
        "boca",
        "Boca",
        "ligero",
        "Úsalo si los dientes o los labios se ven raros.",
        _BOCA,
        (
            _slider("RestoreMouthBlendAmountSlider", "Mezcla de la boca", "Más alto enseña más la boca nueva. Más bajo deja la tuya. Recomendado si solo quieres corregir un poco.", 1, 100, 50, muestra_si=_BOCA),
            _slider("RestoreMouthSizeFactorSlider", "Tamaño de la boca", "Súbelo si la cara sale pequeña en el encuadre y la boca no cubre.", 5, 60, 25, paso=5, muestra_si=_BOCA),
            _slider("RestoreMouthFeatherBlendSlider", "Suavizado del borde", "Difumina el corte alrededor de la boca. Súbelo si se nota el borde.", 1, 100, 10, muestra_si=_BOCA),
            _slider("RestoreXMouthRadiusFactorDecimalSlider", "Ancho de la zona", "Estira la zona a lo ancho. 1 es un círculo.", 0.3, 3.0, 1.0, paso=0.1, decimales=1, muestra_si=_BOCA),
            _slider("RestoreYMouthRadiusFactorDecimalSlider", "Alto de la zona", "Estira la zona a lo alto. 1 es un círculo.", 0.3, 3.0, 1.0, paso=0.1, decimales=1, muestra_si=_BOCA),
            _slider("RestoreXMouthOffsetSlider", "Mover en horizontal", "Desplaza la boca a izquierda o derecha si no cae en su sitio.", -300, 300, 0, muestra_si=_BOCA),
            _slider("RestoreYMouthOffsetSlider", "Mover en vertical", "Desplaza la boca arriba o abajo.", -300, 300, 0, muestra_si=_BOCA),
            _slider("RestoreEyesMouthBlurSlider", "Desenfoque del recorte", "Suaviza el borde de la boca y de los ojos a la vez.", 0, 50, 0, muestra_si=_BOCA),
            _toggle(_ENCAJE, "Encajar la boca", "Recoloca tu boca para que case con la cara nueva, sin deformarla. Puedes usarlo solo.", muestra_si=_BOCA),
            _toggle(_BOCA_ORIGINAL, "Usar mi boca original", "Encaja tu boca de verdad, no una generada. Actívalo junto con Encajar.", muestra_si=_ENCAJE),
            _slider("MouthParserStretchDecimalSlider", "Zoom de la boca", "1,05 es un pelín más grande. Bájalo si la boca se sale.", 0.90, 1.20, 1.05, paso=0.01, decimales=2, muestra_si=_ENCAJE),
            _toggle("MouthParserStretchAfterToggle", "Aplicar después de mejorar", "Pega la boca cuando el restaurador ya ha terminado. Útil si el mejorador te la borra.", muestra_si=_ENCAJE),
            _slider("MouthParserStretchSharpenDecimalSlider", "Nitidez de dientes y labios", "Marca el borde de los dientes sin granear la piel. 0 lo deja neutro.", 0, 5, 0, paso=0.1, decimales=2, muestra_si=_ENCAJE),
            _slider("MouthOriginalCavityBlurSlider", "Desenfoque del interior", "Si usas tu boca, difumina el fondo de la cavidad. Más alto quita dientes falsos.", 0, 50, 15, muestra_si=_BOCA_ORIGINAL),
            _slider("MouthOriginalCavityBlendingDecimalSlider", "Textura original del interior", "0 es sombra artificial. 1 devuelve los dientes y la textura reales.", 0, 1, 0, paso=0.05, decimales=2, muestra_si=_BOCA_ORIGINAL),
            _toggle("AutoMouthExpressionEnableToggle", "Hablar", "Al abrir la boca se ven dientes y lengua, y los labios de la cara nueva siguen ahí cuando la cierras. Entra suave, sin parpadeo."),
            _eleccion("AutoMouthRestoreModeSelection", "Al hablar", "Solo la boca cabe en el directo. Mover los labios pasa por LivePortrait en cada fotograma y no entra en 30 FPS junto al cambio.", ("Face Parser Only", "Expression Restorer"), "Face Parser Only", muestra_si="AutoMouthExpressionEnableToggle"),
            _slider("AutoMouthOpenThresholdDecimalSlider", "A partir de qué apertura", "0,22 coge una conversación. Por encima de 0,60 solo una boca muy abierta.", 0.01, 0.99, 0.22, paso=0.01, decimales=2, muestra_si="AutoMouthExpressionEnableToggle"),
            _slider("AutoMouthEMAAlphaDecimalSlider", "Suavizado al hablar", "Bajo: entra y sale despacio, sin parpadeo. 1 sigue el fotograma al instante.", 0.05, 1.0, 0.35, paso=0.01, decimales=2, muestra_si="AutoMouthExpressionEnableToggle"),
            _slider("AutoMouthMouthParserSlider", "Interior de la boca", "Cuánto se abre el hueco de dientes y lengua. 0 lo deja cerrado.", 0, 30, 8, muestra_si="AutoMouthExpressionEnableToggle"),
            _slider("AutoMouthUpperLipParserSlider", "Labio de arriba", "Poco: se ve el habla sin cambiar la forma del labio nuevo.", 0, 30, 2, muestra_si="AutoMouthExpressionEnableToggle"),
            _slider("AutoMouthLowerLipParserSlider", "Labio de abajo", "Acompaña la mandíbula al hablar. Más alto abre más.", 0, 30, 10, muestra_si="AutoMouthExpressionEnableToggle"),
        ),
    ),
    Grupo(
        "ojos",
        "Ojos",
        "ligero",
        "Úsalo si la mirada nueva no coincide con la tuya.",
        _OJOS,
        (
            _slider("RestoreEyesBlendAmountSlider", "Mezcla de los ojos", "Más alto enseña más los ojos nuevos. Más bajo deja los tuyos.", 1, 100, 50, muestra_si=_OJOS),
            _slider("RestoreEyesSizeFactorDecimalSlider", "Tamaño", "Bájalo si la cara está lejos y el recorte de los ojos se pasa.", 2, 4, 3, paso=0.5, decimales=1, muestra_si=_OJOS),
            _slider("RestoreEyesFeatherBlendSlider", "Suavizado del borde", "Fundido del contorno. Súbelo si se ve un corte.", 1, 100, 10, muestra_si=_OJOS),
            _slider("RestoreXEyesRadiusFactorDecimalSlider", "Ancho", "1 es redondo. Más de 1 alarga el recorte a lo ancho.", 0.3, 3, 1, paso=0.1, decimales=1, muestra_si=_OJOS),
            _slider("RestoreYEyesRadiusFactorDecimalSlider", "Alto", "1 es redondo. Más de 1 alarga el recorte a lo alto.", 0.3, 3, 1, paso=0.1, decimales=1, muestra_si=_OJOS),
            _slider("RestoreXEyesOffsetSlider", "Mover en horizontal", "Corrige si el recorte cae descentrado.", -300, 300, 0, muestra_si=_OJOS),
            _slider("RestoreYEyesOffsetSlider", "Mover en vertical", "Corrige si el recorte queda alto o bajo.", -300, 300, 0, muestra_si=_OJOS),
            _slider("RestoreEyesSpacingOffsetSlider", "Separación", "Acerca o separa los dos ojos.", -200, 200, 0, muestra_si=_OJOS),
        ),
    ),
    Grupo(
        "bordes",
        "Bordes y fusión",
        "ligero",
        "Evita el cuadrado negro y el corte seco alrededor de la cara.",
        _BORDES,
        (
            _slider("BorderTopSlider", "Frente", "Cuánto de tu frente original se conserva. Más alto, más tuya.", 0, 100, 10, muestra_si=_BORDES),
            _slider("TopBorderBlurSlider", "Suavizado de la frente", "Difumina ese corte.", 0, 100, 8, muestra_si=_BORDES),
            _slider("BorderBottomSlider", "Barbilla", "Cuánto de tu barbilla original se conserva.", 0, 100, 10, muestra_si=_BORDES),
            _slider("BottomBorderBlurSlider", "Suavizado de la barbilla", "Difumina ese corte.", 0, 100, 8, muestra_si=_BORDES),
            _slider("BorderLeftSlider", "Lado izquierdo", "Recorte del lado izquierdo de la cara.", 0, 100, 10, muestra_si=_BORDES),
            _slider("LeftBorderBlurSlider", "Suavizado izquierdo", "Difumina el lado izquierdo.", 0, 100, 8, muestra_si=_BORDES),
            _slider("BorderRightSlider", "Lado derecho", "Recorte del lado derecho de la cara.", 0, 100, 10, muestra_si=_BORDES),
            _slider("RightBorderBlurSlider", "Suavizado derecho", "Difumina el lado derecho.", 0, 100, 8, muestra_si=_BORDES),
            _toggle(_FUSION, "Fundido de toda la cara", "Un desenfoque final para que el cambio no se vea pegado.", muestra_si=_BORDES),
            _slider("FinalBlendAmountSlider", "Cantidad de fundido", "Poco es suficiente. Mucho empaña la cara.", 1, 50, 1, muestra_si=_FUSION),
            _toggle(_COSTURA, "Coser el borde", "Desenfoca solo la costura, no toda la cara.", muestra_si=_BORDES),
            _slider("FinalBorderBlendAmountSlider", "Grosor de la costura", "Más alto tapa mejor el corte y come un poco de detalle.", 1, 50, 5, muestra_si=_COSTURA),
            _slider("OverallMaskBlendAmountSlider", "Fundido general de máscaras", "Mezcla las máscaras entre sí. No afecta al borde rectangular.", 0, 100, 0, muestra_si=_BORDES),
            _toggle(_PARSER, "Máscara por zonas", "Devuelve partes de tu cara (pelo, cuello, fondo) encima del cambio. Pesado.", muestra_si=_BORDES),
            _slider("FaceParserSlider", "Zona de la cara", "Crece o encoge la máscara de toda la cara.", 0, 30, 0, muestra_si=_PARSER),
            _slider("FaceParserBlendSlider", "Mezcla de la zona", "Cuánto se funde esa máscara con el cambio.", 0, 100, 0, muestra_si=_PARSER),
            _slider("FaceBlurParserSlider", "Suavizado de la zona", "Borde de la máscara de la cara.", 0, 100, 5, muestra_si=_PARSER),
            _slider("MouthParserSlider", "Zona de la boca", "Máscara solo de la boca, dentro del parser.", 0, 30, 0, muestra_si=_PARSER),
            _slider("LeftEyeParserSlider", "Ojo izquierdo", "Máscara del ojo izquierdo.", 0, 30, 0, muestra_si=_PARSER),
            _slider("RightEyeParserSlider", "Ojo derecho", "Máscara del ojo derecho.", 0, 30, 0, muestra_si=_PARSER),
            _slider("HairParserSlider", "Pelo", "Deja ver tu pelo original.", 0, 30, 0, muestra_si=_PARSER),
            _slider("NeckParserSlider", "Cuello", "Deja ver tu cuello original.", 0, 30, 0, muestra_si=_PARSER),
            _slider("BackgroundParserSlider", "Fondo", "Negativo encoge el fondo que se cuela. Positivo lo deja entrar.", -50, 50, 0, muestra_si=_PARSER),
        ),
    ),
    Grupo(
        "nitidez",
        "Nitidez y calidad",
        "pesado",
        "La resolución y el parecido son ligeros. Mejorar la cara cuesta FPS.",
        _RESTAURAR,
        (
            _eleccion("SwapperResSelection", "Resolución del cambio", "128 va fluido. 256 se ve mejor. 512 es para una tarjeta holgada.", ("128", "256", "384", "512"), "128"),
            _slider("SimilarityThresholdSlider", "Parecido mínimo", "Si la cara parpadea o se suelta, bájalo. Si cambia a otra persona, súbelo.", 1, 100, 60),
            _slider("PreSwapSharpnessDecimalSlider", "Nitidez antes de cambiar", "1 es neutro. Por encima marca más la cara de origen. Puede pelearse con el restaurador.", 0, 2, 1, paso=0.1, decimales=1),
            _eleccion("FaceRestorerTypeSelection", "Modelo", "GFPGAN es el habitual. GPEN da otra textura de piel. Prueba y quédate con el que no enplastique.", ("GFPGAN-v1.4", "GFPGAN-1024", "GPEN-256", "GPEN-512", "GPEN-1024", "CodeFormer"), "GFPGAN-v1.4", muestra_si=_RESTAURAR),
            _eleccion("FaceRestorerDetTypeSelection", "Alineación", "Mezcla une tu pose con la cara nueva. Original respeta el encuadre del restaurador.", ("Original", "Blend", "Reference"), "Blend", muestra_si=_RESTAURAR),
            _slider("FaceRestorerBlendSlider", "Mezcla del restaurador", "100 es todo restaurado. Bájalo si la piel queda de plástico.", 0, 100, 80, muestra_si=_RESTAURAR),
            _toggle(_CARA, "Corregir el encuadre", "Mueve o escala la cara detectada si el cambio nace descentrado."),
            _slider("KpsXSlider", "Desplazar en horizontal", "Mueve los puntos de la cara a izquierda o derecha.", -100, 100, 0, muestra_si=_CARA),
            _slider("KpsYSlider", "Desplazar en vertical", "Mueve los puntos arriba o abajo.", -100, 100, 0, muestra_si=_CARA),
            _slider("KpsScaleSlider", "Escala de los puntos", "Separa o junta los puntos de ojos, nariz y boca.", -100, 100, 0, muestra_si=_CARA),
            _slider("FaceScaleAmountSlider", "Tamaño de la cara", "Crece o encoge la cara cambiada.", -20, 20, 0, muestra_si=_CARA),
            _toggle(_PUNTOS, "Ajustar ojos, nariz y boca", "Corrige un punto suelto: un ojo alto, la boca torcida."),
            _slider("EyeLeftXAmountSlider", "Ojo izquierdo, horizontal", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
            _slider("EyeLeftYAmountSlider", "Ojo izquierdo, vertical", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
            _slider("EyeRightXAmountSlider", "Ojo derecho, horizontal", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
            _slider("EyeRightYAmountSlider", "Ojo derecho, vertical", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
            _slider("NoseXAmountSlider", "Nariz, horizontal", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
            _slider("NoseYAmountSlider", "Nariz, vertical", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
            _slider("MouthLeftXAmountSlider", "Comisura izquierda, horizontal", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
            _slider("MouthLeftYAmountSlider", "Comisura izquierda, vertical", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
            _slider("MouthRightXAmountSlider", "Comisura derecha, horizontal", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
            _slider("MouthRightYAmountSlider", "Comisura derecha, vertical", "Mueve ese punto.", -100, 100, 0, muestra_si=_PUNTOS),
        ),
    ),
    Grupo(
        "color",
        "Color y luz",
        "pesado",
        "La textura de la piel pesa. El color solo, no tanto.",
        _COLOR,
        (
            _slider("ColorBrightnessDecimalSlider", "Brillo", "1 es el brillo del cambio. Bájalo si la cara queda lavada.", 0, 2, 1, paso=0.01, decimales=2, muestra_si=_COLOR),
            _slider("ColorContrastDecimalSlider", "Contraste", "1 es neutro.", 0, 2, 1, paso=0.01, decimales=2, muestra_si=_COLOR),
            _slider("ColorSaturationDecimalSlider", "Saturación", "1 es neutro. Bájalo si el color está demasiado vivo.", 0, 2, 1, paso=0.01, decimales=2, muestra_si=_COLOR),
            _slider("ColorSharpnessDecimalSlider", "Nitidez del color", "1 es neutro. Distinto de la nitidez de antes de cambiar.", 0, 2, 1, paso=0.1, decimales=1, muestra_si=_COLOR),
            _slider("ColorHueDecimalSlider", "Tono", "Corrige un dominante, verde o magenta.", -0.5, 0.5, 0, paso=0.01, decimales=2, muestra_si=_COLOR),
            _slider("ColorGammaDecimalSlider", "Gamma", "1 es neutro. Aclara u oscurece los medios tonos.", 0, 2, 1, paso=0.01, decimales=2, muestra_si=_COLOR),
            _slider("ColorRedSlider", "Rojo", "0 no toca el rojo.", -100, 100, 0, muestra_si=_COLOR),
            _slider("ColorGreenSlider", "Verde", "0 no toca el verde.", -100, 100, 0, muestra_si=_COLOR),
            _slider("ColorBlueSlider", "Azul", "0 no toca el azul.", -100, 100, 0, muestra_si=_COLOR),
            _toggle(_TEXTURA, "Traer la textura de mi piel", "Pasa poros y grano de tu cara a la cambiada. Se nota, y pesa.", muestra_si=_COLOR),
            _slider("TransferTextureBlendAmountSlider", "Fuerza de la textura", "30 es un punto de partida. Mucho marca rayas.", 0, 100, 30, muestra_si=_TEXTURA),
            _slider("TransferTexturePreGammaDecimalSlider", "Gamma de la textura", "1 es neutro. Muévelo si el grano queda plano.", 0, 2, 1, paso=0.05, decimales=2, muestra_si=_TEXTURA),
            _slider("TransferTexturePreContrastDecimalSlider", "Contraste de la textura", "1 es neutro.", 0, 2, 1, paso=0.05, decimales=2, muestra_si=_TEXTURA),
        ),
    ),
    Grupo(
        "oclusion",
        "Objetos delante",
        "pesado",
        "Una mano, unas gafas o un micrófono deben verse por encima de la cara.",
        _OCLUSION,
        (
            _slider("OccluderSizeSlider", "Tamaño de la oclusión", "Negativo encoge la zona tapada. Positivo la agranda. 0 es el tamaño detectado.", -100, 100, 0, muestra_si=_OCLUSION),
            _toggle("OccluderTonguePriorityToggle", "No borrar la boca por dentro", "Evita que la lengua desaparezca al agrandar la oclusión.", muestra_si=_OCLUSION),
            _slider("OccluderXSegBlurSlider", "Suavizado del objeto", "Difumina el borde del objeto que tapa la cara.", 0, 100, 8, muestra_si=_OCLUSION),
            _toggle("OclusionAdaptativaEnableToggle", "Tamaño según la cara", "Con la cara grande, la máscara se encoge un poco para no comerse los ojos detrás de las gafas.", True, muestra_si=_OCLUSION),
            _toggle("DFLXSegEnableToggle", "Máscara XSeg", "Otra máscara, más fina, para monturas, cristales y dedos. Pesa más que la oclusión simple.", muestra_si=_OCLUSION),
            _toggle("XSegExcludeInnerMouthToggle", "Proteger la boca por dentro", "XSeg no debe borrar lengua ni dientes.", True, muestra_si="DFLXSegEnableToggle"),
            _toggle("XSegExcludeInnerObstaclesToggle", "Cambiar también gafas y manos", "Apagado: gafas y manos se quedan de la cámara. Enciéndelo solo si la oclusión se come los ojos.", False, muestra_si="DFLXSegEnableToggle"),
            _slider("DFLXSegSizeSlider", "Tamaño XSeg", "Negativo agranda lo que tapa. Positivo lo encoge.", -20, 20, 0, muestra_si="DFLXSegEnableToggle"),
        ),
    ),
    Grupo(
        "estabilidad",
        "Estabilidad del borde",
        "ligero",
        "Quita el parpadeo del pelo. El promedio de la máscara son 0,25 ms por fotograma, sin la red.",
        "SuavizadoMascaraEnableToggle",
        (
            _slider("SuavizadoMascaraAlfaDecimalSlider", "Cuánto manda este fotograma", "Bajo: el borde se queda quieto y tarda un poco en seguirte. 0,45 es el punto de partida.", 0.15, 0.9, 0.45, paso=0.05, decimales=2, muestra_si="SuavizadoMascaraEnableToggle"),
            _toggle("SuavizadoPlumaEnableToggle", "Pluma según el tamaño", "Si estás lejos, el borde del pelo se suaviza más para que no parpadee.", True),
            _toggle("SuavizadoColorEnableToggle", "Color estable", "El tono de la cara no salta de un fotograma a otro.", True),
            _toggle("MantenerSwapOclusionEnableToggle", "Aguantar el cambio si te tapas", "Mientras una mano cubre la cara, se sostiene el último cambio bueno.", True),
            _toggle("SeguirCajaOclusionEnableToggle", "Seguir la caja", "Si el detector suelta la cara, la caja no salta: se acerca poco a poco.", True),
            _toggle("FaceTrackingEnableToggle", "Seguir la identidad", "ByteTrack recuerda quién eres durante el tapón. Ligero.", True),
            _slider("ByteTrackTrackBufferSlider", "Cuántos fotogramas recuerda", "45 son cerca de un segundo y medio a 30 FPS. Más alto aguanta oclusiones más largas.", 1, 120, 45, muestra_si="FaceTrackingEnableToggle"),
            _toggle("LandmarkDetectToggle", "Puntos con la cara tapada", "Usa ORFormer, pensado para caras medio tapadas. Unos 6 ms por cara en una RTX 4090; en las RTX 50 no está medido. No va en FP16: en FP16 no compila.", False),
        ),
    ),
)


def todos() -> list[Control]:
    lista: list[Control] = []
    for grupo in GRUPOS:
        lista.extend(grupo.controles)
        lista.append(
            Control(
                grupo.maestro,
                grupo.nombre,
                grupo.frase,
                "toggle",
                predeterminado=grupo.maestro == _BORDES,
            )
        )
    return lista


def por_clave() -> dict[str, Control]:
    return {control.clave: control for control in todos()}


def valores_iniciales() -> dict[str, object]:
    return {control.clave: control.predeterminado for control in todos()}


_ESTABLE = {
    "SuavizadoMascaraEnableToggle": True,
    "SuavizadoMascaraAlfaDecimalSlider": 0.45,
    "SuavizadoPlumaEnableToggle": True,
    "SuavizadoColorEnableToggle": True,
    "MantenerSwapOclusionEnableToggle": True,
    "SeguirCajaOclusionEnableToggle": True,
    "FaceTrackingEnableToggle": True,
    "ByteTrackTrackBufferSlider": 45,
    "OclusionAdaptativaEnableToggle": True,
    "OccluderEnableToggle": True,
    "OccluderTonguePriorityToggle": True,
    "OccluderXSegBlurSlider": 8,
    "DFLXSegEnableToggle": False,
    "XSegExcludeInnerMouthToggle": True,
    "XSegExcludeInnerObstaclesToggle": False,
    "LandmarkDetectToggle": False,
    "KPSSmoothingEnableToggle": True,
    "KPSEmaAlphaSlider": 25,
    "BordermaskEnableToggle": True,
    "TopBorderBlurSlider": 16,
    "BottomBorderBlurSlider": 16,
    "LeftBorderBlurSlider": 16,
    "RightBorderBlurSlider": 16,
    "FaceParserEnableToggle": True,
    "HairParserSlider": 12,
    "NeckParserSlider": 10,
    "AutoColorEnableToggle": True,
    "AutoColorTransferTypeSelection": "Reinhard Transfer (Masked)",
    "AutoColorBlendAmountSlider": 65,
    "RestoreMouthEnableToggle": True,
    "RestoreMouthBlendAmountSlider": 40,
    "RestoreMouthFeatherBlendSlider": 18,
    "MouthParserStretchToggle": True,
    "MouthParserStretchOriginalToggle": True,
    "AutoMouthExpressionEnableToggle": True,
    "AutoMouthRestoreModeSelection": "Face Parser Only",
    "AutoMouthOpenThresholdDecimalSlider": 0.22,
    "AutoMouthEMAAlphaDecimalSlider": 0.35,
    "AutoMouthMouthParserSlider": 8,
    "AutoMouthUpperLipParserSlider": 2,
    "AutoMouthLowerLipParserSlider": 10,
}


def valores_de_seis_gb() -> dict[str, object]:
    """Cara nítida en 6 GB sin el restaurador a tope, que la deja de plástico."""
    return {
        "SwapperResSelection": "256",
        "FaceRestorerEnableToggle": True,
        "FaceRestorerTypeSelection": "GFPGAN-v1.4",
        "FaceRestorerDetTypeSelection": "Blend",
        "FaceRestorerBlendSlider": 55,
    }


def valores_de_calidad(nombre: str, permite_alto: bool = False) -> dict[str, object]:
    """Un preset deja cada control en un valor concreto, no solo tres."""
    valores = valores_iniciales()
    valores.update(_ESTABLE)
    if nombre == "Máxima calidad":
        valores.update(
            {
                "SwapperResSelection": "512" if permite_alto else "256",
                "FaceRestorerEnableToggle": True,
                "FaceRestorerTypeSelection": "GFPGAN-v1.4",
                "FaceRestorerDetTypeSelection": "Blend",
                "FaceRestorerBlendSlider": 80,
                "BordermaskEnableToggle": True,
                "FinalBorderBlendEnableToggle": True,
                "FinalBorderBlendAmountSlider": 8,
                "OccluderEnableToggle": True,
                "DFLXSegEnableToggle": True,
                "LandmarkDetectToggle": False,
                "SuavizadoMascaraAlfaDecimalSlider": 0.4,
                "SimilarityThresholdSlider": 60,
                "PreSwapSharpnessDecimalSlider": 1.0,
            }
        )
    elif nombre == "Máximo FPS":
        valores.update(
            {
                "SwapperResSelection": "128",
                "FaceRestorerEnableToggle": False,
                "RestoreEyesEnableToggle": False,
                "OccluderEnableToggle": False,
                "DFLXSegEnableToggle": False,
                "LandmarkDetectToggle": False,
                "FaceTrackingEnableToggle": True,
                "SuavizadoMascaraAlfaDecimalSlider": 0.7,
                "SimilarityThresholdSlider": 45,
            }
        )
    elif nombre == "Equilibrado":
        valores.update(
            {
                "SwapperResSelection": "128",
                "FaceRestorerEnableToggle": False,
                "BordermaskEnableToggle": True,
                "FinalBorderBlendEnableToggle": True,
                "FinalBorderBlendAmountSlider": 5,
                "SimilarityThresholdSlider": 60,
                "PreSwapSharpnessDecimalSlider": 1.0,
            }
        )
    return valores


CLAVES_RENDIMIENTO = frozenset(
    {
        "SwapperResSelection",
        "FaceRestorerEnableToggle",
        "FaceRestorerTypeSelection",
        "FaceRestorerDetTypeSelection",
        "FaceRestorerBlendSlider",
        "SimilarityThresholdSlider",
        "OccluderEnableToggle",
        "DFLXSegEnableToggle",
        "LandmarkDetectToggle",
        "LandmarkDetectModelSelection",
        "SuavizadoMascaraEnableToggle",
        "SuavizadoMascaraAlfaDecimalSlider",
        "FaceTrackingEnableToggle",
        "ByteTrackTrackBufferSlider",
        "RestoreEyesEnableToggle",
    }
)


CLAVES_DE_DRAKO = (
    "RestoreMouthBlendAmountSlider",
    "RestoreMouthSizeFactorSlider",
    "RestoreMouthFeatherBlendSlider",
    "RestoreXMouthRadiusFactorDecimalSlider",
    "RestoreYMouthRadiusFactorDecimalSlider",
    "RestoreXMouthOffsetSlider",
    "RestoreYMouthOffsetSlider",
    "RestoreEyesMouthBlurSlider",
    "MouthParserStretchToggle",
    "RestoreEyesEnableToggle",
    "RestoreEyesBlendAmountSlider",
    "FaceParserEnableToggle",
    "OccluderEnableToggle",
    "BordermaskEnableToggle",
    "TopBorderBlurSlider",
    "SwapperResSelection",
    "SimilarityThresholdSlider",
    "PreSwapSharpnessDecimalSlider",
    "FaceRestorerEnableToggle",
    "FaceRestorerBlendSlider",
    "TransferTextureEnableToggle",
    "ColorEnableToggle",
    "FaceAdjEnableToggle",
    "LandmarksPositionAdjEnableToggle",
    "FinalBlendAdjEnableToggle",
    "OverallMaskBlendAmountSlider",
)
