# Cámara virtual Unity Capture

Drako Cam incluye el filtro DirectShow de [Unity Capture](https://github.com/schellingb/UnityCapture) (schellingb) para exponer su propia cámara virtual, sin instalar ni abrir OBS.

| | |
| --- | --- |
| Proyecto | https://github.com/schellingb/UnityCapture |
| Commit | `3ed54c325e0ad71afcf4f246c07e5e17b3d7f2d2` (2023-04-14) |
| Licencia del filtro | MIT. El texto está en [LICENSE](LICENSE). |
| Archivos | `UnityCaptureFilter64.dll` y `UnityCaptureFilter32.dll` |

El filtro de 64 bits es el que usa Drako Cam (Python de 64 bits) y el que ven Meet, Zoom y Teams de 64 bits. El de 32 bits se registra también para que un programa de 32 bits pueda elegir la misma cámara. No se incluye el complemento de Unity (licencia zlib): aquí solo está el filtro que aparece como webcam.

## Nombre del dispositivo

El instalador registra el filtro con:

```bat
regsvr32 /s UnityCaptureFilter64.dll /i:UnityCaptureName="Drako Cam"
```

En Meet, Zoom y Teams la cámara se llama **Drako Cam**. Ese nombre no está grabado dentro de la DLL: Unity Capture lo escribe en el registro al registrarla (`/i:UnityCaptureName=`). Si no se pasa el nombre, el dispositivo se llama `Unity Video Capture`. Drako Cam prueba primero «Drako Cam» y, si no está, ese nombre genérico.

No hace falta tener OBS abierto. OBS Virtual Camera queda solo como respaldo si este filtro no está registrado.

## Registro

Hace falta administrador **una vez**, porque `regsvr32` escribe en `HKLM`. `Instalar.bat` lo pide solo. Si ya está registrada con esta misma DLL y el nombre «Drako Cam», no se vuelve a registrar.

Para quitarla, `Desinstalar.bat` llama a `regsvr32 /u` únicamente si la ruta del filtro apunta a esta carpeta.

Los CLSID del dispositivo 0 (los que lee pyvirtualcam) son:

- 64 bits: `{5C2CD55C-92AD-4999-8666-912BD3E70010}`
- 32 bits: `{5C2CD55C-92AD-4999-8666-912BD3E70020}`
