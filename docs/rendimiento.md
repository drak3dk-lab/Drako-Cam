# Rendimiento del directo

Webcam → cambio de cara → cámara virtual de OBS. La estabilidad va primero
y los fotogramas por segundo, después. El público usa tarjetas **Blackwell
(RTX 5060, 5060 Ti, 5070, 5070 Ti y 5080, 8–16 GB, sm_120)**. La RTX 4050
Laptop de 6 GB es solo el portátil de desarrollo y tiene un perfil de
respaldo.

Este documento separa tres cosas: lo que se ve en el código del canal
anterior, lo que se midió en una máquina **sin** GPU NVIDIA, y lo que hay
que confirmar en las tarjetas reales. No se inventan FPS de inferencia.

## Qué hacía el canal anterior

El bucle de la webcam (`MediaPipeline._feed_webcam`) y el worker
(`FrameWorker.process_frame`) hacían, en cada fotograma:

1. **Dos viajes a la GPU del mismo fotograma.** El detector secuencial
   subía el frame si no recibía un tensor, y el worker volvía a hacer
   `transpose` + `ascontiguousarray` + `tensor.to(device)`. La webcam no
   pasaba `frame_tensor`.
2. **Una bajada con reserva nueva.** Al terminar, `permute().cpu().numpy()`
   y el volteo de canales BGR creaban arrays nuevos. El anillo pinned de
   la captura solo cubría el BGR→RGB de entrada.
3. **Copia profunda del estado en cada fotograma.** Aunque los ajustes no
   hubieran cambiado, `fast_state_copy` recorría parámetros y controles
   otra vez para el worker.
4. **Detección completa siempre.** `SequentialDetector.run` llama al
   detector y, si hay cara, a ArcFace, en todos los fotogramas. ByteTrack
   suaviza; no se salta el detector.
5. **Cola larga.** Con la cola llena (hilos + 14 fotogramas de preroll) el
   hilo de captura esperaba 20 ms en vez de tirar el fotograma viejo. A
   30 FPS eso son varios cientos de milisegundos de latencia si la
   inferencia se retrasa. La vista previa y `pyvirtualcam.send` corrían en
   el hilo de la interfaz, junto con la conversión a `QPixmap`.
6. **Caché TensorRT en el directorio de trabajo**, carpeta fija
   `tensorrt-engines`, sin el nombre de la tarjeta ni la versión de
   TensorRT. Un motor de la 4050 podía intentarse en una 5070. Si la
   compilación fallaba, el modelo no se cargaba.
7. **Hasta dos swappers residentes**, sin tope de VRAM, sin modo emisión
   y con un error CUDA tratado como parada del directo al primer fallo.
   El workspace de compilación pedía el 40 % de la VRAM (en una 16 GB,
   unos 6 GB) con un mínimo de 1 GB y un respaldo de 4 GB si no se podía
   leer la tarjeta.

## Lo que se midió aquí (sin GPU NVIDIA)

Máquina del agente, CPU, NumPy 1.26, sin CUDA. No es una RTX 50. Sirve
para el coste de las copias y del canal alrededor de los modelos.

| Camino | 1280×720 | 1920×1080 |
| --- | ---: | ---: |
| Reservar en cada fotograma (`transpose` + contiguo + volteo BGR) | 4,2 ms | 9,4 ms |
| Anillo reutilizado (`copyto` sobre buffers ya creados) | 0,17 ms | 0,36 ms |

Copia del estado de la interfaz (80 claves y 4 caras con un embedding de
512, 200 repeticiones): `deepcopy` 0,27 ms frente a la copia de dos
niveles 0,013 ms.

Sobrecarga del canal **sin** red neuronal (copia, seguimiento y dos colas
de tamaño 1), 20 fotogramas:

| Perfil | Resolución del ensayo | Latencia p50 | p95 |
| --- | --- | ---: | ---: |
| 6 GB (portátil) | 1280×720 | 0,27 ms | 1,5 ms |
| Equilibrado 8 GB | 1920×1080 | 0,59 ms | 1,7 ms |
| Alto 12-16 GB | 1920×1080 | 0,59 ms | 1,7 ms |

Esa sobrecarga cabe de sobra en un presupuesto de 33 ms (30 FPS) o de
16 ms (60 FPS). El tiempo que falta es el de detección, swap y
mejorador, y no está en esta tabla.

## Qué cambia

Todo queda detrás de ajustes, con valores por defecto pensados para el
directo. El vídeo de archivo sigue el camino anterior si se desactiva
«Hilos de captura, inferencia y salida».

| Ajuste | Por defecto | Efecto |
| --- | --- | --- |
| Perfil de VRAM | Auto | 6 GB si es una 4050 o hay menos de 7,5 GB; Equilibrado si es una 5060 de 8 GB; Alto si hay 12 GB o más, o si el nombre es 5070/5080 |
| Resolución / FPS | 1920×1080 @ 30 | El perfil de 6 GB escribe 1280×720 @ 30 la primera vez. 60 FPS solo se mantiene en el perfil Alto |
| Pipeline en GPU | Activado | Una subida a un tensor reutilizado; la bajada escribe en un anillo. El primer fotograma de cada tamaño sí reserva |
| Hilos | Activado | Captura (cola 1), inferencia (cola 2) y salida a OBS (cola 1). Si no caben, se tira el fotograma viejo |
| Detección inteligente | Activado, cada 2 | Cada 4 en el perfil de 6 GB. Entre medias se mueven caja y puntos. Si la cara sale o se pierde el rastro, se vuelve a detectar |
| Un solo swapper | Activado | El segundo modelo se descarga. Se puede desactivar |
| Mejoradores perezosos | Activado en 6 y 8 GB | Si están apagados, se descargan al empezar la webcam. Por debajo de 12 GB no conviven restaurador y mejorador de fotograma |
| Tope de VRAM | Activado | 4,5 GB en el perfil de 6 GB, 6,5 GB en 8 GB, 85 % en Alto |
| Modo emisión | Apagado | Sin vista previa Qt, prioridad de proceso alta, la cámara virtual sigue |
| Fondo virtual | Ninguno | BGR, el mismo formato que ya produce el worker. Verde o transparente usan un óvalo alrededor de la cara |
| Precisión TensorRT | FP16 | FP32 es la alternativa. FP8 e INT8 no se activan |
| Medir rendimiento | Apagado | Al activarlo, mide la sobrecarga de los tres perfiles y, si el directo ya corrió, la latencia real acumulada |

La resolución que el usuario haya puesto a mano (distinta de 720p y
1080p) no se pisa en el arranque siguiente. Solo se reescribe cuando
cambia el perfil.

### TensorRT 10 y sm_120

El proyecto fija `tensorrt-cu13==10.16.1.11` y PyTorch cu130. Blackwell
de consumo es **sm_120**. Hace falta TensorRT **10.10 o posterior**; con
una versión más vieja el programa no intenta compilar y usa CUDA.

Los motores se guardan en los datos de Drako Cam, no en la carpeta del
programa:

`%APPDATA%\DrakoCam\tensorrt-engines\<modelo>__sm120__trt<versión>\`

Ejemplo: `nvidia_geforce_rtx_5070__sm120__trt10.16.1.11`. Si cambia la
tarjeta o la versión de TensorRT, la carpeta es otra y se compila de
nuevo. La primera vez sale el cuadro «Compilando TensorRT». Si la
compilación o la carga fallan, se reintenta sin TensorRT. No se cierra
el proceso.

El workspace de compilación queda en 2 GB por debajo de 12 GB de VRAM y
en 3 GB a partir de ahí, para no comerse la memoria del directo.

FP16 se activa solo en los modelos de `fp16_safe_models_list`. TUFA y
ORFormer siguen en FP32: en FP16 ya se midió salida inservible o un
fallo de compilación. FP8 e INT8 quedan apagados por el mismo motivo:
no hay una calibración que conserve la identidad, y activarlos sería
bajar la calidad a cambio de velocidad.

### Gafas, manos y el parpadeo del borde

El suavizado temporal de la máscara final no existía: el bloque
«Final Mask Smoothing» de `frame_worker_pipeline` sigue comentado
porque era un desenfoque de textura, no un promedio entre fotogramas.
Ahora el directo hace otra cosa, en `app/drako/rendimiento/suavizado.py`:

- La máscara se promedia en el recorte ya alineado (la transformación
  afín lleva cada fotograma al mismo sitio). Si la cara cambia o el
  centro salta más de un 35 % del tamaño, se olvida el fotograma
  anterior.
- La pluma crece cuando la cara ocupa pocos píxeles, para que el pelo
  no parpadee de lejos.
- El color del cambio se promedia entre fotogramas. El EMA que ya
  había solo corría con el color automático encendido.
- Si una mano tapa la cara, se sostiene el último cambio bueno y
  ByteTrack interpola la caja en vez de soltarla.
- La oclusión, con tamaño adaptativo, queda encendida en Auto,
  Equilibrado y Máxima calidad. XSeg y ORFormer solo en Máxima
  calidad: XSeg afina montura y dedos; ORFormer está hecho para caras
  tapadas.

ORFormer no vuelve a la lista de FP16. En FP16 la compilación no
termina (acceso inválido, medido en el propio `models_data`). En FP32
cuesta unos 6 ms por cara en una RTX 4090. En las RTX 50 no está
medido. El oclusor y XSeg ya se descargan con el resto de modelos; no
hace falta marcarlos como imprescindibles aparte.

Coste del suavizado de máscara, sin red neuronal, en esta máquina
(CPU, máscara de 512 reducida a 96, 30 repeticiones): **0,25 ms** por
fotograma. Entra de sobra en un presupuesto de 33 ms (30 FPS) o de
16 ms (60 FPS). La oclusión y XSeg son otra historia: son una pasada
de red cada fotograma, por eso el panel los marca como pesados y
Máximo FPS los deja apagados. ORFormer, si se enciende, suma esos
~6 ms de la 4090; no los sumo al 0,25 ms.

### Hablar

El directo usa el auto-mouth en modo **Face Parser Only**. Al abrir la
boca, y solo entonces, dilata el interior y los labios (dientes y
lengua) con una entrada proporcional al promedio temporal que ya
tenía el estado. Con la boca cerrada esas dilataciones valen 0: se
queda la forma de los labios de la cara nueva, no una boca pegada.

El otro modo, Expression Restorer, mueve los labios con LivePortrait
en cada fotograma. El propio ajuste lo describe como más lento. No
entra en el presupuesto de 30 FPS junto al cambio, así que el preset
no lo enciende. Está en el grupo Boca por si la tarjeta sobra.

El estado de apertura (EMA, histéresis y la dilatación) no llega a
0,05 ms por fotograma en esta CPU. La máscara de la boca, cuando se
abre, sí es una pasada del parser de cara: pesa, y solo corre mientras
se habla.

### GPU dedicada en un portátil híbrido

`python.exe` no puede exportar `NvOptimusEnablement`: ese símbolo tiene
que vivir en el ejecutable, y el ejecutable es el de Python. Windows
sí honra la preferencia por aplicación:

`HKCU\Software\Microsoft\DirectX\UserGpuPreferences`
`GpuPreference=2;` (alto rendimiento)

La escriben el instalador de Inno Setup, `scripts/instalar.ps1` y el
propio arranque, para `python.exe`, `pythonw.exe` y `main.py`. Si CUDA
acaba viendo una GPU integrada (Intel UHD/Iris o Radeon Graphics), el
programa avisa. Si hay varias CUDA y la primera no es NVIDIA, se elige
la NVIDIA con más VRAM.

### Si CUDA falla o el directo se atasca

El vigilante no mata el proceso. Un error CUDA suelta ese fotograma,
vacía colas y limpia la caché. Si se repite en pocos segundos, pasa el
proveedor a CUDA (sin TensorRT) y sigue. Si aun así sigue fallando, o
si no llega ningún fotograma tras varias recuperaciones, se detiene el
directo y se muestra el cuadro de siempre. La aplicación queda abierta.

## Calidad del directo, medida sin GPU

El temblor es el error RMS, en píxeles, de un punto con 1,6 px de ruido
de detección, frente a la posición limpia. La media exponencial 0,35 es
la que ya tenía el worker. One Euro (frecuencia mínima 1,0 Hz, beta 0,07)
es el filtro del seguimiento. 30 FPS, 90 fotogramas, semilla fija.

| Señal | En bruto | Media 0,35 | One Euro | Retraso del pico |
| --- | ---: | ---: | ---: | ---: |
| Cara quieta | 1,55 px | 0,78 px | 0,75 px | igual que la media |
| Cara que se mueve (0,4 Hz) | 1,35 px | 1,40 px | 1,05 px | 4 fotogramas, igual que la media |

En reposo One Euro deja el temblor a la mitad de la detección y un poco
por debajo de la media. En movimiento la media se queda por detrás del
gesto y empeora el error; One Euro lo baja de 1,40 px a 1,05 px sin
añadir retraso.

Si el rastro se pierde, el fundido baja el último swap en 8 fotogramas
en vez de enseñar la cara real al instante.

La sobrecarga del canal, ya con One Euro, sigue fuera del presupuesto
de un fotograma. No incluye detección ni swap:

| Perfil | Resolución | Latencia p50 | p95 |
| --- | --- | ---: | ---: |
| 6 GB | 1280×720, detección cada 4 | 0,30 ms | 2,66 ms |
| RTX 50 (Alto) | 1920×1080, detección cada 2 | 0,64 ms | 5,18 ms |

A 30 FPS el fotograma dura 33 ms. Esta sobrecarga no es el FPS del
cambio de cara: eso hay que medirlo en la 4050 y en una RTX 50.

El preset Auto pone el swap a 128 px con GFPGAN en 6 GB, a 256 px en
8 GB y a 512 px (el pixel boost de Inswapper) en 12 GB o más. Máximo
FPS fuerza 128 px y apaga el restaurador. En 6 GB, Máxima calidad no
pasa de 256 px.

## Qué hay que validar en las tarjetas reales

Esta rama no se ejecutó sobre una RTX 50 ni sobre la 4050. Antes de
dar por buenos los FPS:

1. **RTX 5060 u 5060 Ti de 8 GB.** Perfil Equilibrado, 1080p30, un
   swapper, sin mejorador de fotograma junto al restaurador. Anotar FPS
   y latencia con «Medir rendimiento» mientras la webcam está en marcha
   y OBS recibe la cámara virtual.
2. **RTX 5070 / 5070 Ti / 5080.** Perfil Alto, 1080p30 y, si va holgado,
   1080p60. Comprobar que restaurador y mejorador pueden quedarse
   cargados sin pasar del tope (85 % de la VRAM).
3. **RTX 4050 Laptop, 6 GB, híbrida.** Perfil de 6 GB, 720p30, tope
   ~4,5 GB. Confirmar el aviso si Windows arranca en la integrada y que,
   tras la preferencia `GpuPreference=2`, CUDA ve la 4050.
4. **Primera compilación TensorRT** en cada tarjeta: el cuadro aparece,
   termina, y el segundo arranque no recompila. La carpeta del motor
   lleva el nombre de esa GPU y `trt10.16`. Un motor copiado de otra
   tarjeta no se reutiliza.
5. **Fallo de TensorRT.** Renombrar la carpeta de motores o forzar un
   modelo incompatible y comprobar que el directo sigue en CUDA.
6. **OBS.** Resolución y FPS bloqueados a los ajustes. Fondo «Ninguno»
   en BGR. «Verde» y «Transparente» solo como recorte elíptico, no como
   máscara de pelo.
7. **Modo emisión.** La vista previa deja de pintarse, la cámara virtual
   sigue, y el proceso sube de prioridad (en Windows, clase alta).
8. **Watchdog.** Un fallo CUDA inyectado (o un modelo que no carga) no
   cierra Drako Cam; como mucho detiene el directo después de reintentar.

El acceso por código, la licencia y el bot de Telegram no forman parte
de este canal y siguen el mismo orden de arranque: contraseña, código
de acceso, y después la ventana.
