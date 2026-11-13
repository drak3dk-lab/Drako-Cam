# Drako Cam

Programa de escritorio para **cambiar la cara en tiempo real** (webcam y cámara virtual para Zoom, Discord u OBS). Está pensado para Windows con GPU NVIDIA (CUDA / TensorRT). El administrador es Drako.

Drako Cam es un trabajo derivado de [VisoMaster Fusion](https://github.com/VisoMasterFusion/VisoMaster-Fusion) (GPL-3.0), commit `f2d6f5ebe190b631ee5c8972332083cf7f8a3e72`. El motor de intercambio, las máscaras de oclusión, la webcam y la cámara virtual vienen de ese proyecto y de VisoMaster (@argenspin, @Alucard24 y la comunidad). La licencia completa está en [LICENSE](LICENSE). Los cambios de este derivado están en [NOTICE](NOTICE).

Los **pesos de los modelos no están en el repositorio**. El primer arranque los descarga y comprueba el SHA-256. Si el archivo no coincide, se borra y se vuelve a bajar.

## Qué hace esta versión

- Pide una contraseña de administrador al abrir. En el primer arranque hay un asistente para fijarla. Se guarda solo el hash Argon2id, en la configuración local.
- Se puede cambiar desde el menú **Drako → Cambiar contraseña…**, indicando la actual.
- Tras 5 intentos fallidos el acceso se bloquea 60 segundos (el bloqueo se alarga si se repite, hasta 15 minutos).
- Anota en local, cifrado (AES-GCM) y firmado (HMAC-SHA256), cada apertura, cierre, duración, intento fallido y cara usada. De la cara solo guarda el nombre del archivo y un hash, nunca la imagen ni el embedding.
- Puede avisar a un bot de Telegram. Si no hay red, encola y reintenta. Si Telegram no está configurado, el programa funciona igual.
- Escribe logs rotativos, muestra un cuadro si hay una excepción no controlada, reabre la webcam si se desconecta y avisa en pantalla si no hay CUDA.

La interfaz heredada de VisoMaster (paneles, controles y manual) sigue en inglés. Los cuadros nuevos de Drako Cam están en español.

## Requisitos

- Windows 10 u 11, 64 bits
- GPU NVIDIA, 6 GB de VRAM como mínimo (8–12 GB más cómodos)
- Controlador NVIDIA reciente (en VisoMaster se recomienda `>= 576.57` para CUDA 12.9)
- Red la primera vez (dependencias y modelos)
- Unos 20–30 GB libres
- Python 3.12, [uv](https://docs.astral.sh/uv/) o Conda, y FFmpeg

Sin CUDA el programa avisa y puede abrirse, pero el directo no irá a velocidad de cámara.

## Instalar en Windows con NVIDIA

Abre PowerShell en la carpeta del proyecto.

```powershell
git clone https://github.com/drak3dk-lab/Drako-Cam
cd Drako-Cam

uv venv --python 3.12
.venv\Scripts\activate
uv pip install -r requirements_cu13.txt
```

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

Doble clic en `Start.bat`, o desde la carpeta del proyecto:

```powershell
python main.py
```

1. La primera vez el programa pide **crear** la contraseña de administrador (8 caracteres como mínimo) y repetirla.
2. Después, cada apertura pide esa contraseña.
3. Comprueba los modelos. Los que falten se descargan y se verifica el hash. Puede tardar y ocupar varios gigabytes.
4. Si no ve CUDA, muestra un aviso. No cambia a CPU sin decirlo.
5. Elige webcam como medio de destino y activa la cámara virtual (`pyvirtualcam`) para Zoom, Discord u OBS.

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
| `config.json` | Hash Argon2id, bloqueo, claves del registro envueltas y, si quieres, token de Telegram |
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

Cubren la contraseña, el cifrado y la firma del registro, la cola de Telegram sin red y el cliente simulado.

## Qué queda para la siguiente fase

- Face Fader
- Favoritos
- Biblioteca
- Face Picker
- Instalador de un clic
- Traducción al español del resto de paneles heredados de VisoMaster

## Aviso de uso

El intercambio de cara es para uso responsable, con consentimiento de las personas cuya imagen se utilice. Quien ejecuta el programa responde de lo que hace con él. No está pensado para suplantar, acosar ni engañar.
