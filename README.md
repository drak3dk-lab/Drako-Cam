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

La interfaz heredada de VisoMaster (paneles, controles y manual) sigue en inglés. Los cuadros nuevos de Drako Cam están en español.

## Requisitos

- Windows 10 u 11, 64 bits
- GPU NVIDIA, 6 GB de VRAM como mínimo (8–12 GB más cómodos)
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
5. Al terminar hay un acceso directo **Drako Cam** en el escritorio y en el menú Inicio. Ábrelo: no sale una ventana de consola.
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
4. Comprueba los modelos del cambio de cara en vivo (unos 1,18 GB) y verifica el hash. El resto —colorización, Ref-LDM, expresión, swappers alternativos— se descarga al activarlo. Si el archivo ya está, se reutiliza. El detalle está en [docs/modelos.md](docs/modelos.md).
5. Si no ve CUDA, muestra un aviso. No cambia a CPU sin decirlo.
6. Elige webcam como medio de destino y activa la cámara virtual (`pyvirtualcam`) para Zoom, Discord u OBS.

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

## Qué queda para la siguiente fase

- Face Fader
- Favoritos
- Biblioteca
- Face Picker
- Traducción al español del resto de paneles heredados de VisoMaster

## Aviso de uso

El intercambio de cara es para uso responsable, con consentimiento de las personas cuya imagen se utilice. Quien ejecuta el programa responde de lo que hace con él. No está pensado para suplantar, acosar ni engañar.
