# Repo privado y copia protegida

Esto es lo que tiene que hacer Drako. No hace falta tocar código.

## 1. Poner el repositorio en privado

1. Abre https://github.com/drak3dk-lab/Drako-Cam
2. Entra en **Settings**.
3. Baja hasta **Danger Zone**.
4. Pulsa **Change visibility**.
5. Elige **Private** y confirma.

A partir de ahí, quien no tenga permiso en GitHub no puede ver el código ni los releases.

## 2. No pongas secretos en el repositorio

No subas tokens, contraseñas ni el archivo `installer/descarga.url`.
El bot de Telegram y la clave de firma siguen solo en Cloudflare, como hasta ahora.
En el PC donde se instala, si el release es privado, la persona ejecuta una vez `gh auth login`.
El programa no guarda ese token.

## 3. Compilar el .exe

En Windows, dentro de la carpeta del programa:

```
powershell -ExecutionPolicy Bypass -File scripts\compilar_nuitka.ps1
```

Eso crea `DrakoCam.exe` y `integridad_manifiesto.json`.
La comprobación de licencia y la del hash van dentro de lo compilado.
No publiques el release hasta que des el ok. El script no lo publica.

Si Nuitka no puede usarse en ese PC, la alternativa es PyArmor:

```
pyarmor gen -O dist main.py
```

Tampoco subas el resultado sin el ok.

## 4. Enlace de descarga para el instalador

Cuando el release exista y hayas dado el ok:

1. Crea el release en GitHub y sube el archivo.
2. Copia la URL del archivo. Se parece a
   `https://github.com/drak3dk-lab/Drako-Cam/releases/download/vX.Y.Z/DrakoCam.zip`
3. En el PC que prepara el instalador, crea `installer/descarga.url` con esa URL en una sola línea.
4. Quien instale desde un repo privado ejecuta antes `gh auth login`.
5. La descarga la hace `scripts\descargar_release.ps1`. Usa la sesión de `gh`. No lleva un token dentro.

## 5. Qué pasa si alguien copia la carpeta

El programa pide el código y lo ata a ese PC.
Si el PC es otro, el bot de Telegram pide una aprobación nueva.
Hasta que la apruebes, ese PC no entra.
Si retiras el permiso, o si el programa no puede hablar con el servidor durante unos tres minutos, se para el directo y el aviso dice que escriban a @Drako_XX.
Copiar el .exe a otro PC no sirve: la licencia no viaja con el archivo.
