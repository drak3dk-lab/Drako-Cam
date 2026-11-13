# Modelos de Drako Cam

El primer arranque ya no baja el catálogo heredado de VisoMaster Fusion.
Baja el camino de cambio de cara en vivo, a la calidad de esos pesos
(el archivo completo, no una versión recortada), y el resto cuando se elige.

Los tamaños son el `Content-Length` de cada URL del registro, medido el
13 de noviembre de 2026. La suma usa gigabytes decimales (1 GB = 1 000 000 000 bytes),
que es lo que muestra la descarga.

| Conjunto | Archivos | Tamaño |
| --- | ---: | ---: |
| Antes (todo el registro) | 77 | 17,36 GB |
| Esencial (primer arranque) | 9 | 1,18 GB |
| Opcional (bajo demanda) | 68 | 16,18 GB |

## Qué cuenta como esencial

No hay un perfil por GPU que cambie de archivo. El trabajo de rendimiento
(hilos, limpieza de VRAM en reposo, TensorRT en FP16 para la lista blanca)
cambia cómo se ejecuta el mismo peso. Una RTX 4050 de 6 GB y una RTX 5060-5080
cargan los mismos modelos por defecto. Por eso el conjunto esencial es uno.

Se incluye lo que el camino en vivo y los controles de calidad usan si no se
cambia el tipo:

- **Inswapper128**, el swapper por defecto. Resolución 128, 256, 384, 512 y
  Auto salen del mismo archivo fp16.
- **Inswapper128ArcFace**, reconocimiento por defecto y embedding de ese swapper.
- **RetinaFace**, detector por defecto. Sus 5 puntos alinean la cara.
- **FaceLandmark203**, puntos faciales por defecto. El código lo marca como
  esencial y no lo suelta al apagar el resto de landmarks.
- **Occluder, XSeg y FaceParser**, la máscara y el parser del camino de calidad.
- **GFPGAN v1.4**, restaurador por defecto de los dos huecos. Peso completo.
- **RealESRGAN x2**, mejorador de fotograma por defecto. Peso completo. En 6 GB
  no es el ajuste por defecto subir a x4 con el swapper cargado.

El seguimiento ByteTrack es código, sin pesos. La cámara virtual y la salida a
OBS usan el mismo camino: no añaden un modelo.

Elegir otro swapper, detector, restaurador o la colorización descarga ese
archivo completo en ese momento. La calidad de esa opción no cambia: cambia
cuándo se baja.

## Esenciales

| Modelo | Grupo | Tamaño | Por qué |
| --- | --- | ---: | --- |
| Inswapper128 | Intercambio | 278 MB | Swapper por defecto. El mismo archivo fp16 cubre 128, 256, 384, 512 y Auto: la calidad completa de ese modelo está aquí, no en otro peso. |
| RetinaFace | Detección | 17 MB | Detector por defecto. Sus 5 puntos alinean la cara. El seguimiento ByteTrack y la cámara virtual no añaden pesos. |
| FaceLandmark203 | Puntos faciales | 115 MB | Puntos faciales por defecto (203). El programa lo trata como modelo esencial y lo conserva aunque se apaguen los demás landmarks. |
| Inswapper128ArcFace | Reconocimiento | 174 MB | Reconocimiento por defecto y embedding que Inswapper128 necesita para la identidad. Sin él el intercambio no tiene a quién parecerse. |
| GFPGANv1.4 | Restauración | 340 MB | Restaurador por defecto de los dos huecos. Es GFPGAN v1.4 completo, el que eligen los controles de calidad si no se cambia el tipo. |
| RealEsrganx2Plus | Mejora de fotograma | 34 MB | Mejorador de fotograma por defecto. Peso x2 completo. Las variantes x4 pesan lo mismo en calidad de su propia escala y se bajan al elegirlas; en 6 GB no son el ajuste por defecto. |
| Occluder | Máscara | 57 MB | Máscara de oclusión del camino de máscara. Hace falta para tapar manos y objetos a la calidad prevista, no es un sustituto más pequeño. |
| XSeg | Máscara | 70 MB | Segunda máscara (DFL XSeg). Canal independiente que se mezcla con la oclusión; el archivo es el modelo completo. |
| FaceParser | Máscara | 94 MB | Parser semántico de la cara. Delimita regiones y protege la boca cuando la oclusión está activa. |

## Opcionales

| Modelo | Grupo | Tamaño | Por qué |
| --- | --- | ---: | --- |
| AlphaFace | Intercambio | 555 MB | Swapper alternativo. El camino por defecto usa Inswapper128; este archivo completo se descarga al elegirlo. |
| InStyleSwapper256 Version A | Intercambio | 277 MB | Swapper alternativo. El camino por defecto usa Inswapper128; este archivo completo se descarga al elegirlo. |
| InStyleSwapper256 Version B | Intercambio | 277 MB | Swapper alternativo. El camino por defecto usa Inswapper128; este archivo completo se descarga al elegirlo. |
| InStyleSwapper256 Version C | Intercambio | 277 MB | Swapper alternativo. El camino por defecto usa Inswapper128; este archivo completo se descarga al elegirlo. |
| SimSwap512 | Intercambio | 239 MB | Swapper alternativo. El camino por defecto usa Inswapper128; este archivo completo se descarga al elegirlo. |
| GhostFacev1 | Intercambio | 515 MB | Swapper alternativo. El camino por defecto usa Inswapper128; este archivo completo se descarga al elegirlo. |
| GhostFacev2 | Intercambio | 739 MB | Swapper alternativo. El camino por defecto usa Inswapper128; este archivo completo se descarga al elegirlo. |
| GhostFacev3 | Intercambio | 856 MB | Swapper alternativo. El camino por defecto usa Inswapper128; este archivo completo se descarga al elegirlo. |
| CSCS | Intercambio | 739 MB | Swapper alternativo. El camino por defecto usa Inswapper128; este archivo completo se descarga al elegirlo. |
| SCRFD2.5g | Detección | 3 MB | Detector alternativo. El camino en vivo usa RetinaFace. Se descarga al elegirlo en los ajustes. |
| YoloFace8n | Detección | 13 MB | Detector alternativo. El camino en vivo usa RetinaFace. Se descarga al elegirlo en los ajustes. |
| YunetN | Detección | 318 KB | Detector alternativo. El camino en vivo usa RetinaFace. Se descarga al elegirlo en los ajustes. |
| YoloFace11nVR180 | Detección | 11 MB | Detector de VR180. El modo VR está apagado por defecto. Se descarga al activarlo. |
| YoloFace12nVR180 | Detección | 11 MB | Detector de VR180. El modo VR está apagado por defecto. Se descarga al activarlo. |
| FaceLandmark5 | Puntos faciales | 110 MB | Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. Se descarga al elegirlo. |
| FaceLandmark68 | Puntos faciales | 98 MB | Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. Se descarga al elegirlo. |
| FaceLandmark3d68 | Puntos faciales | 144 MB | Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. Se descarga al elegirlo. |
| FaceLandmark98 | Puntos faciales | 44 MB | Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. Se descarga al elegirlo. |
| FaceLandmark106 | Puntos faciales | 5 MB | Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. Se descarga al elegirlo. |
| FaceLandmark478 | Puntos faciales | 5 MB | Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. Se descarga al elegirlo. |
| FaceLandmarkTUFA98 | Puntos faciales | 146 MB | Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. Se descarga al elegirlo. |
| FaceLandmarkTUFA314 | Puntos faciales | 147 MB | Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. Se descarga al elegirlo. |
| FaceLandmarkORFormer98 | Puntos faciales | 75 MB | Puntos faciales alternativos. El modelo por defecto es el de 203 puntos. Se descarga al elegirlo. |
| FaceBlendShapes | Puntos faciales | 2 MB | Dependencia del landmark de 478 puntos. No lo usa el modelo de 203. |
| SimSwapArcFace | Reconocimiento | 209 MB | Embedding de un swapper que no es el predeterminado. Inswapper128 usa Inswapper128ArcFace. |
| GhostArcFace | Reconocimiento | 261 MB | Embedding de un swapper que no es el predeterminado. Inswapper128 usa Inswapper128ArcFace. |
| CSCSArcFace | Reconocimiento | 261 MB | Embedding de un swapper que no es el predeterminado. Inswapper128 usa Inswapper128ArcFace. |
| CSCSIDArcFace | Reconocimiento | 262 MB | Embedding de un swapper que no es el predeterminado. Inswapper128 usa Inswapper128ArcFace. |
| GFPGAN1024 | Restauración | 366 MB | Restaurador alternativo. El predeterminado de los dos huecos es GFPGAN v1.4, con su peso completo. Este se descarga al elegirlo. |
| GPENBFR256 | Restauración | 76 MB | Restaurador alternativo. El predeterminado de los dos huecos es GFPGAN v1.4, con su peso completo. Este se descarga al elegirlo. |
| GPENBFR512 | Restauración | 284 MB | Restaurador alternativo. El predeterminado de los dos huecos es GFPGAN v1.4, con su peso completo. Este se descarga al elegirlo. |
| GPENBFR1024 | Restauración | 285 MB | Restaurador alternativo. El predeterminado de los dos huecos es GFPGAN v1.4, con su peso completo. Este se descarga al elegirlo. |
| GPENBFR2048 | Restauración | 285 MB | Restaurador alternativo. El predeterminado de los dos huecos es GFPGAN v1.4, con su peso completo. Este se descarga al elegirlo. |
| CodeFormer | Restauración | 189 MB | Restaurador alternativo. El predeterminado de los dos huecos es GFPGAN v1.4, con su peso completo. Este se descarga al elegirlo. |
| VQFRv2 | Restauración | 360 MB | Restaurador alternativo. El predeterminado de los dos huecos es GFPGAN v1.4, con su peso completo. Este se descarga al elegirlo. |
| RestoreFormerPlusPlus | Restauración | 148 MB | Restaurador alternativo. El predeterminado de los dos huecos es GFPGAN v1.4, con su peso completo. Este se descarga al elegirlo. |
| RealEsrganx4Plus | Mejora de fotograma | 34 MB | Mejorador de fotograma distinto del predeterminado (RealESRGAN x2). Se descarga al elegirlo; el archivo es el peso completo de esa variante. |
| RealEsrx4v3 | Mejora de fotograma | 5 MB | Mejorador de fotograma distinto del predeterminado (RealESRGAN x2). Se descarga al elegirlo; el archivo es el peso completo de esa variante. |
| BSRGANx2 | Mejora de fotograma | 34 MB | Mejorador de fotograma distinto del predeterminado (RealESRGAN x2). Se descarga al elegirlo; el archivo es el peso completo de esa variante. |
| BSRGANx4 | Mejora de fotograma | 34 MB | Mejorador de fotograma distinto del predeterminado (RealESRGAN x2). Se descarga al elegirlo; el archivo es el peso completo de esa variante. |
| UltraSharpx4 | Mejora de fotograma | 34 MB | Mejorador de fotograma distinto del predeterminado (RealESRGAN x2). Se descarga al elegirlo; el archivo es el peso completo de esa variante. |
| UltraMixx4 | Mejora de fotograma | 34 MB | Mejorador de fotograma distinto del predeterminado (RealESRGAN x2). Se descarga al elegirlo; el archivo es el peso completo de esa variante. |
| DeoldifyArt | Color | 128 MB | Colorización. No interviene en el cambio de cara en vivo. Se descarga al elegirla como mejorador de fotograma. |
| DeoldifyStable | Color | 437 MB | Colorización. No interviene en el cambio de cara en vivo. Se descarga al elegirla como mejorador de fotograma. |
| DeoldifyVideo | Color | 437 MB | Colorización. No interviene en el cambio de cara en vivo. Se descarga al elegirla como mejorador de fotograma. |
| DDColorArt | Color | 980 MB | Colorización. No interviene en el cambio de cara en vivo. Se descarga al elegirla como mejorador de fotograma. |
| DDcolor | Color | 980 MB | Colorización. No interviene en el cambio de cara en vivo. Se descarga al elegirla como mejorador de fotograma. |
| combo_relu3_3_relu3_1 | Máscara | 7 MB | Textura VGG para diferencia y transferencia. Apagada por defecto. |
| RD64ClipText | Máscara | 5 MB | Máscara por texto (CLIP). No es el parser de la cara. Se descarga al activarla. |
| LivePortraitMotionExtractor | Expresión | 113 MB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| LivePortraitAppearanceFeatureExtractor | Expresión | 3 MB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| LivePortraitStitchingEye | Expresión | 581 KB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| LivePortraitStitchingLip | Expresión | 151 KB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| LivePortraitStitching | Expresión | 182 KB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| LivePortraitWarpingSpade | Expresión | 421 MB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| PerformRecastAppearanceFeatureExtractor | Expresión | 358 MB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| PerformRecastMotionExtractor | Expresión | 113 MB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| PerformRecastWarpingModule | Expresión | 205 MB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| PerformRecastSpadeGenerator | Expresión | 344 MB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| RefLDMVAEEncoder | Denoiser | 92 MB | Denoiser Ref-LDM / VQGAN. No forma parte del cambio de cara por defecto. Se descarga al activar el denoiser. |
| RefLDMVAEDecoder | Denoiser | 136 MB | Denoiser Ref-LDM / VQGAN. No forma parte del cambio de cara por defecto. Se descarga al activar el denoiser. |
| RefLDM_UNET_EXTERNAL_KV | Denoiser | 472 MB | Denoiser Ref-LDM / VQGAN. No forma parte del cambio de cara por defecto. Se descarga al activar el denoiser. |
| LivePortraitWarpingSpadeFix | Expresión | 421 MB | Expresión o editor (LivePortrait o PerformRecast). Apagado en el camino por defecto. Se descarga al activarlo. |
| RefLdm | Denoiser | 1,17 GB | Denoiser Ref-LDM / VQGAN. No forma parte del cambio de cara por defecto. Se descarga al activar el denoiser. |
| VQGAN | Denoiser | 779 MB | Denoiser Ref-LDM / VQGAN. No forma parte del cambio de cara por defecto. Se descarga al activar el denoiser. |
| FaceReaging | Edad | 124 MB | Cambio de edad. Apagado en el camino en vivo. Se descarga al activarlo. |
| AlphaFaceIdentityProjection | Intercambio | 1 MB | Matriz de identidad de AlphaFace. Solo hace falta si se elige ese swapper. |
| MouthActionDetector | Boca | 11 MB | Detector de acción de boca para la expresión automática. Apagado por defecto. |

## Descarga

- El arranque (`main.py`, `download_models.py` sin argumentos y
  `Start_Portable.bat`) pide solo los esenciales.
- `python download_models.py --todos` y «Revert to Original Models» del
  launcher piden el catálogo.
- «Ajustes > Modelos» lista instalado o disponible, el tamaño, y tiene
  **Descargar todos**.
- La descarga se puede reanudar (archivo `.parcial` y HTTP Range), reintenta
  con espera de 1 s, 2 s y 4 s, baja 3 archivos a la vez como máximo, comprueba
  SHA-256 y muestra el total y el tiempo que queda.
- Si el archivo final ya existe y el hash coincide, no se vuelve a bajar.
  Con `USE_OPTIMIZED_MODELS=TRUE` se conserva el archivo optimizado y no se
  exige el hash del original.
- Si no hay red al activar un modelo opcional, la cámara sigue y el aviso lo
  dice. La descarga no bloquea el hilo de la imagen.
