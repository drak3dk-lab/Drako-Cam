# Modelos del directo

Drako Cam solo cambia caras en vivo, de la cámara web hacia la cámara virtual «Drako Cam». El primer
arranque descarga estos pesos y nada más. Antes, el catálogo heredado de
VisoMaster Fusion pesaba **17,36 GB** (77 archivos). Ahora son **960 MB**
(6 archivos). Si se corta internet, la descarga sigue desde el trozo ya
bajado y no termina hasta que el SHA-256 coincide.

El arranque guarda un manifiesto con el tamaño y la fecha de cada archivo.
Si no han cambiado, no recalcula el hash y no escribe una línea por modelo.
El hash se comprueba al descargar y cuando el tamaño o la fecha cambian.

No hay un perfil de GPU que cambie de archivo. Los perfiles de 6 GB, 8 GB y
12–16 GB (PR #4) cambian resolución, fotogramas, hilos y el tope de VRAM.
Los pesos son los mismos en la RTX 4050 y en las RTX 5060–5080.

## Por qué estos seis

| Modelo | Tamaño | Por qué |
| --- | ---: | --- |
| RetinaFace | 17 MB | Detector por defecto. Sus 5 puntos alinean la cara. No hace falta otro modelo de landmarks. |
| Inswapper128ArcFace | 174 MB | Embedding de Inswapper128 y reconocimiento de la cara. |
| Inswapper128 | 278 MB | Swapper del directo. El mismo archivo fp16 cubre 128, 256, 384, 512 y Auto. |
| GFPGANv1.4 | 340 MB | Restaurador en tiempo real. Está encendido en Auto, Equilibrado y Máxima calidad. |
| FaceParser | 94 MB | Máscara por zonas, boca y «al hablar» del perfil en vivo. |
| Occluder | 57 MB | Oclusión (manos, micro). Está encendida en ese perfil. |

## Qué ya no se descarga

Editor de cara, LivePortrait, PerformRecast, reaging, DeOldify, DDColor,
Ref-LDM, VQGAN, XSeg, GPEN, SCRFD, FaceLandmark203, el editor de embeddings,
los trabajos por lotes y los swappers y detectores que no son los de esta
tabla. No se descargan al instalar, al arrancar ni bajo demanda.

La cámara virtual, TensorRT, los perfiles de GPU, la emisión y el vigilante
siguen. El vídeo o la imagen como objetivo se pueden abrir para probar sin
cámara; al arrancar se ofrece la webcam.
