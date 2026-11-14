# Drako Cam

Programa de escritorio para **cambiar la cara en tiempo real** (webcam y cámara virtual para Zoom, Discord u OBS). Está pensado para Windows con GPU NVIDIA (CUDA / TensorRT). El administrador es Drako.

Drako Cam es un trabajo derivado de [VisoMaster Fusion](https://github.com/VisoMasterFusion/VisoMaster-Fusion) (GPL-3.0), commit `f2d6f5ebe190b631ee5c8972332083cf7f8a3e72`. El motor de intercambio, las máscaras de oclusión, la webcam y la cámara virtual vienen de ese proyecto y de VisoMaster (@argenspin, @Alucard24 y la comunidad). La licencia completa está en [LICENSE](LICENSE). Los cambios de este derivado están en [NOTICE](NOTICE).

Los **pesos de los modelos no están en el repositorio**. El primer arranque los descarga y comprueba el SHA-256. Si el archivo no coincide, se borra y se vuelve a bajar.

## Qué hace esta versión

- Pide una contraseña de administrador al abrir. En el primer arranque hay un asistente para fijarla. Se guarda solo el hash Argon2id, en la configuración local. Esa contraseña no está en el código.
- Después pide un código de acceso personal, la primera vez, y lo guarda cifrado. Si aún no lo tiene, puede pedir acceso con su nombre y el de la oficina. Drako lo aprueba o lo rechaza en Telegram y, si lo aprueba, recibe el código para pasárselo. Si lo revoca, el programa se cierra. Sin red hay una gracia (por defecto 24 horas desde la última comprobación correcta) y luego se bloquea. El aviso de privacidad es obligatorio la primera vez.
- Se puede cambiar la contraseña desde el menú **Drako → Cambiar contraseña…**, y el código desde **Drako → Cambiar código de acceso…**.
- Tras 5 intentos fallidos el acceso se bloquea 60 segundos (el bloqueo se alarga si se repite, hasta 15 minutos).
- Anota en local, cifrado (AES-GCM) y firmado (HMAC-SHA256), cada apertura, cierre, duración, intento fallido y cara usada. De la cara solo guarda el nombre del archivo y un hash, nunca la imagen ni el embedding.
- Puede avisar a un bot de Telegram. Si no hay red, encola y reintenta. Si Telegram no está configurado, el programa funciona igual.
- Escribe logs rotativos, muestra un cuadro si hay una excepción no controlada, reabre la webcam si se desconecta y avisa en pantalla si no hay CUDA.
- El directo (webcam → cambio de cara → OBS) usa perfiles de VRAM, motores TensorRT FP16 con caché por tarjeta y un canal que tira fotogramas viejos. El detalle y lo que hay que medir en la GPU real está en [docs/rendimiento.md](docs/rendimiento.md).

La pantalla principal está en español. Al abrir se ve la cámara. El uso es: elegir una foto o un perfil y pulsar **EN VIVO**. La cara de enfrente se cambia sola y la imagen sale a OBS. No se abre un vídeo, no hay prueba sin cámara y no se elige otra persona. Si falta la foto, EN VIVO lo dice. Cómo añadir la fuente está en [OBS](#obs).

El símbolo de Drako Cam es la D plateada con el ojo rojo hecho lente, el archivo que aprobó Drako: `assets/drakocam/isotipo.png`. No se redibuja: el icono de 48 px en adelante sale de ese PNG. En 16 y 32 px se usa una reducción del mismo archivo. El logo de la marca, sin tocar, está en `assets/marca/`. Para usarlo en la app en vez de la variante de producto, cambia `app/ui/core/media/logo.usar` a `marca`. El rojo `#F20A1C` solo marca EN VIVO y el foco. `python scripts/generar_icono.py` escribe `installer/logo.ico` de 16 a 256.

## Requisitos

- Windows 10 u 11, 64 bits
- GPU NVIDIA. El uso previsto es una RTX 5060, 5070 o 5080 (8–16 GB). La RTX 4050 de 6 GB del portátil de desarrollo sigue teniendo un perfil propio.
- Controlador NVIDIA reciente (en VisoMaster se recomienda `>= 576.57` para CUDA 12.9)
- Red la primera vez (dependencias y modelos)
- Unos 20–30 GB libres
- Python 3.12, [uv](https://docs.astral.sh/uv/) o Conda, y FFmpeg

Sin CUDA el programa avisa y puede abrirse, pero el directo no irá a velocidad de cámara.

## Instalación fácil

Para Windows 10 u 11, de 64 bits, con internet. No hace falta instalar Python, FFmpeg ni nada más antes. La carpeta puede tener espacios, por ejemplo `C:\Users\SEXTO PISO\Downloads\Drako-Cam`.

### Doble clic en Instalar.bat

1. Copia la carpeta de Drako Cam a tu equipo.
2. Doble clic en `Instalar.bat`.
3. Espera. Instala uv y Python 3.12 solo, sin el alias de la Microsoft Store y sin activar nada. Luego descarga varios gigabytes (PyTorch y TensorRT) y puede tardar más de media hora. Hacen falta unos 25 GB libres, mejor 30. No cierres la ventana.
4. Si algo falla, la ventana se queda abierta con el motivo. El detalle queda en `%LOCALAPPDATA%\DrakoCam\logs\instalacion.log`.
5. Al terminar hay un acceso directo **Drako Cam** en el escritorio y en el menú Inicio, con el isotipo metálico. `Instalar.bat` no puede llevar icono propio; el acceso directo sí. Ábrelo: no sale una ventana de consola.
6. Si no hay una GPU NVIDIA con CUDA, la instalación termina igual y lo dice con claridad. El programa puede abrirse, pero el directo no irá a velocidad de cámara.

Volver a ejecutar `Instalar.bat` repara o actualiza lo que falte (componentes y accesos directos).

### Con el instalador .exe

Cuando se publica una versión (una etiqueta `v*` en GitHub), el archivo `DrakoCam-Setup-….exe` queda adjunto a esa release. Doble clic, siguiente, siguiente. Copia el programa a tu carpeta personal y ejecuta la misma preparación al final.

Para quitarlo: Configuración de Windows → Aplicaciones → Drako Cam → Desinstalar. Pregunta antes de borrar la contraseña y los registros. El archivo `.exe` no incluye los pesos de los modelos: se descargan la primera vez que se abre el programa.

### Quitar lo instalado con Instalar.bat

Doble clic en `Desinstalar.bat`. Borra el entorno de Python y los accesos directos. No borra `%APPDATA%\DrakoCam` (contraseña, registros y avisos) salvo que escribas `SI` cuando lo pregunte. La carpeta del programa no se borra: puedes eliminarla a mano si ya no la quieres.

## Instalación manual

Abre PowerShell en la carpeta del proyecto.

```powershell
git clone https://github.com/drak3dk-lab/Drako-Cam
cd Drako-Cam

uv venv --python 3.12
uv pip install -r requirements_cu13.txt --python .venv\Scripts\python.exe
```

Si PowerShell dice que la ejecución de scripts está deshabilitada, no uses `activate`. El programa se abre con `.venv\Scripts\python.exe` (o `pythonw.exe` si no quieres consola). El instalador de un clic ya lo hace así.

Con Conda, el entorno se llama `drakocam`:

```powershell
conda create -n drakocam python=3.12 -y
conda activate drakocam
pip install uv
uv pip install -r requirements_cu13.txt
```

FFmpeg, una de estas dos:

```powershell
winget install -e --id Gyan.FFmpeg --version 7.1.1
```

o descomprime [ffmpeg 7.1.1 essentials](https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-7.1.1-essentials_build.zip) y añade su carpeta `bin` al `PATH`.

## Ejecutar

Después de la instalación fácil, abre el acceso directo **Drako Cam**.

También vale un doble clic en `Start.bat`, o desde la carpeta del proyecto, sin activar el entorno:

```powershell
& ".\.venv\Scripts\python.exe" ".\main.py"
```

1. La primera vez el programa pide **crear** la contraseña de administrador (8 caracteres como mínimo) y repetirla. Esa contraseña es de este PC. No está escrita en el programa.
2. Después, cada apertura pide esa contraseña.
3. La primera vez muestra el aviso de privacidad (se registran el uso, la IP y la ciudad y el país aproximados) y pide el código de acceso. El código se guarda cifrado y no se vuelve a pedir.
4. Comprueba los modelos. Los que falten se descargan y se verifica el hash. Puede tardar y ocupar varios gigabytes.
5. Si no ve CUDA, muestra un aviso. No cambia a CPU sin decirlo.
6. En la pantalla: elige una foto (o arrástrala) o un perfil y pulsa **EN VIVO**. Para OBS, enciende la cámara virtual y, en OBS, añade un dispositivo de captura de vídeo llamado **Drako Cam**.

El código de acceso y el servidor que lo comprueba se explican en [server/README.md](server/README.md). Hasta que esa URL y la clave pública estén en `app/drako/licencia_config.py`, el programa avisa de que el acceso no está configurado y no entra.

Para saltarte la descarga en una prueba de importación:

```powershell
python main.py --comprobar-importaciones
```

Eso no abre la ventana: solo comprueba que el código importa y que la sintaxis es válida.

## Contraseña, registro y Telegram

La configuración **no va en el código** ni en git. En Windows está en:

`%APPDATA%\DrakoCam\`

| Archivo | Contenido |
| --- | --- |
| `config.json` | Hash Argon2id, bloqueo, claves del registro envueltas, el código de acceso cifrado y, si quieres, token de Telegram |
| `auditoria.log` | Eventos cifrados y firmados |
| `cola_telegram.json` | Avisos pendientes de enviar |
| `logs\drako-cam.log` | Log rotativo de la aplicación |

Para mover esa carpeta: variable `DRAKO_CAM_DATA_DIR`.

Telegram, en el menú **Drako → Avisos de Telegram…**, o con variables de entorno (tienen prioridad sobre el archivo):

```powershell
$env:DRAKO_CAM_TELEGRAM_BOT_TOKEN = "el token del bot"
$env:DRAKO_CAM_TELEGRAM_CHAT_ID = "el chat id"
```

No pongas el token en el código ni lo subas al repositorio. Si esas variables no existen y el menú se deja vacío, no se envía nada y el resto del programa sigue.

El registro cifrado se abre con la misma contraseña de administrador. Quien copie solo `auditoria.log` no lee los eventos.

## Probar sin GPU ni webcam

Las pruebas nuevas no miden FPS ni abren la cámara. Hace falta Python 3.12 y:

```powershell
uv pip install pytest argon2-cffi cryptography
python -m pytest tests/unit/drako -q
python main.py --comprobar-importaciones
```

Cubren la contraseña, el cifrado y la firma del registro, la cola de Telegram sin red, el cliente de licencias (servidor simulado, gracia sin red y revocación) y el aviso de privacidad.

El servidor de acceso se prueba aparte, sin desplegarlo:

```powershell
cd server
npm install
npm test
```

## Pantalla principal

1. Elige una foto en la galería, o pulsa **Añadir foto**. También vale un perfil guardado, o soltar un JPG, PNG, WEBP o BMP.
2. La cámara ya está elegida (la última, o la primera). Si hay varias, el selector está junto a **EN VIVO**.
3. Pulsa **EN VIVO**. La persona de enfrente se cambia sola y la imagen sale a la cámara virtual, sin otro botón. El preset de arranque mantiene la calidad visible: cambio a 256, restaurador, bordes, color y boca. **Máximo FPS** es opcional y es el único que baja ese detalle. En 6 GB la webcam va a 1280×720, que es lo que Meet envía. **PARAR** quita el cambio de cara; la salida hacia OBS sigue, al mismo tamaño. **Original / Cambiada** compara sin cerrar la cámara.

## OBS

La primera vez se abre un asistente. También está en **Cómo añadirlo**.

1. Instala [OBS Studio](https://obsproject.com). Si puedes, instala también [Unity Capture](https://github.com/schellingb/UnityCapture): es la cámara que OBS lista como fuente y no se mezcla con la salida del propio OBS.
2. Pulsa **EN VIVO** en Drako Cam. La salida se abre sola, a un tamaño y unos FPS fijos. No los cambies en mitad del directo: OBS perdería la fuente.
3. En OBS, en Fuentes, pulsa **+** → **Dispositivo de captura de vídeo** → elige **Unity Video Capture**. Si no está, elige **OBS Virtual Camera**. La cámara virtual se enciende sola al pulsar **EN VIVO**.
4. Si prefieres no usar cámara virtual, pulsa **Ventana OBS** (o Ctrl+O). Se abre una ventana aparte, sin botones ni marco, titulada exactamente **Drako Cam - Salida OBS**. En OBS: **+** → **Captura de ventana** → elige ese título. El vídeo ocupa toda la ventana, con la relación de aspecto correcta y negro si sobra espacio, así que no hace falta recortar. Puedes cambiarle el tamaño; Drako Cam recuerda el tamaño y el sitio. Déjala detrás de otras ventanas: sigue pintando. Si la minimizas, Windows a veces deja de componerla y OBS se queda con el último fotograma; en ese caso déjala detrás, no en la barra de tareas. Ctrl+O o **Cerrar ventana** la cierra sin apagar la cámara virtual.
5. **Probar salida** manda un recuadro claro para comprobar que OBS la ve.

Si se pierde la cara, la salida no se corta. Cerrar el panel de ajustes tampoco. El indicador dice **OBS recibiendo** cuando OBS está abierto y la salida va, o **Salida activa** si la salida va y OBS todavía no.

Favoritos con estrella, y F1–F8 para saltar entre ellos. **Modo compacto** deja la ventana pequeña al lado de OBS. Si la cara se pierde, el programa lo dice y la transición suave sigue siendo la del motor.

A la derecha, **Ajustar cara** tiene la boca, los ojos, los bordes, la nitidez, el color y los objetos que tapan la cara. Cada grupo se enciende con un interruptor. **Ver antes** (mantener pulsado) enseña la cara sin cambio. Esos ajustes se guardan con la foto. Auto, Máxima calidad, Equilibrado y Máximo FPS los dejan en valores concretos.

## Qué queda para la siguiente fase

- Medir FPS de inferencia en una RTX 50 real
- Afinar el parecido con más de una foto de la misma persona a la vez

## Aviso de uso

El intercambio de cara es para uso responsable, con consentimiento de las personas cuya imagen se utilice. Quien ejecuta el programa responde de lo que hace con él. No está pensado para suplantar, acosar ni engañar.
