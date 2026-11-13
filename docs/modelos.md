# Modelos del directo

Drako Cam solo cambia caras en vivo, de la cámara web hacia OBS. El primer
arranque descarga estos pesos y nada más. Antes, el catálogo heredado de
VisoMaster Fusion pesaba **17,36 GB** (77 archivos). Ahora son **1,14 GB**
(8 archivos).

El arranque guarda un manifiesto con el tamaño y la fecha de cada archivo.
Si no han cambiado, no recalcula el hash y no escribe una línea por modelo.
El hash se comprueba al descargar y cuando el tamaño o la fecha cambian.

No hay un perfil de GPU que cambie de archivo. Los perfiles de 6 GB, 8 GB y
12–16 GB (PR #4) cambian resolución, fotogramas, hilos y el tope de VRAM.
Los pesos son los mismos en la RTX 4050 y en las RTX 5060–5080.

## Por qué estos ocho

| Modelo | Tamaño | Por qué |
| --- | ---: | --- |
| Inswapper128 | 278 MB | Swapper del directo. El mismo archivo fp16 cubre 128, 256, 384, 512 y Auto. En 6 GB es el que aguanta el directo con calidad completa; los otros swappers no entran en el producto. |
| Inswapper128ArcFace | 174 MB | Embedding de ese swapper y reconocimiento de la cara. |
| SCRFD2.5g | 3 MB | Detector rápido, con 5 puntos. El seguimiento ByteTrack no trae pesos. |
| FaceLandmark203 | 115 MB | Puntos faciales del directo. Afinan la alineación cuando el detector no basta. |
| Occluder | 57 MB | Máscara de oclusión (manos, objetos). La máscara de borde no es un modelo. |
| FaceParser | 94 MB | Lo usa la máscara para no comerse la boca y para recortar la cara. |
| GFPGANv1.4 | 340 MB | Restaurador en tiempo real, el predeterminado. |
| GPENBFR256 | 76 MB | El otro restaurador en tiempo real, más ligero. Se elige en Ajustes. |

## Qué ya no se descarga

Editor de cara, LivePortrait, PerformRecast, reaging, DeOldify, DDColor,
Ref-LDM, VQGAN, XSeg, el editor de embeddings, los trabajos por lotes y los
swappers y detectores que no son los de esta tabla. No están en la interfaz
ni en el registro que descarga el programa.

La cámara virtual, TensorRT, los perfiles de GPU, la emisión y el vigilante
siguen. El vídeo o la imagen como objetivo se pueden abrir para probar sin
cámara; al arrancar se ofrece la webcam.
