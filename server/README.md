# Servidor de acceso de Drako Cam

Drako Cam es gratis, pero no entra cualquiera. Tú creas un código para cada persona. El programa lo comprueba en este servidor. Tú ves quién lo abre, en qué PC, desde qué IP, la ciudad y el país aproximados, a qué hora entra y cuánto tiempo lo usa.

Las horas de los avisos están en **Europe/Bucharest** (hora de Bucarest).

Hay dos cosas distintas:

- **Contraseña de administrador.** La elige cada persona la primera vez que abre el programa en su PC. No está en este repositorio y no debes escribirla aquí.
- **Código de acceso.** Lo creas tú con el bot de Telegram (`/nuevo Ana`). Ese código es el permiso.

Nada de esto se despliega solo. Los pasos de abajo los haces tú, una vez, en una cuenta gratuita de Cloudflare.

## Qué vas a necesitar

- Un móvil o el programa Telegram.
- Una cuenta de correo para Cloudflare.
- Node.js, la versión LTS, desde [https://nodejs.org](https://nodejs.org). Al terminar la instalación, cierra PowerShell y ábrelo otra vez.
- La carpeta `server` de este proyecto.

Comprueba Node abriendo PowerShell y escribiendo:

```powershell
node -v
```

Tiene que salir un número, por ejemplo `v22.14.0`. Si dice que no reconoce `node`, cierra PowerShell, ábrelo de nuevo y, si sigue igual, reinstala Node.js.

## 1. Crear el bot con BotFather

1. Abre Telegram.
2. Busca `@BotFather` (el nombre lleva una marca azul).
3. Pulsa **Iniciar**.
4. Escribe `/newbot` y envíalo.
5. Te pide un nombre visible. Escribe, por ejemplo: `Drako Cam acceso`.
6. Te pide un usuario. Tiene que terminar en `bot` y no estar cogido. Prueba algo como `DrakoCamAccesoBot`.
7. BotFather te contesta con un **token**. Es una línea larga, con números, dos puntos y letras. Ese es el secreto `TELEGRAM_BOT_TOKEN`.
8. Cópialo a un bloc de notas en tu PC. No lo mandes por chat, no lo subas a GitHub y no lo pegues en el código.

## 2. Saber tu chat id

1. En Telegram, busca `@userinfobot`.
2. Pulsa **Iniciar**.
3. Te contesta con tu **Id**. Es un número. Ese número es el secreto `TELEGRAM_ADMIN_CHAT_ID`.
4. Ábrelo en el bloc de notas, junto al token.
5. Abre **tu** bot (el que acabas de crear) y pulsa **Iniciar**. Si no lo haces, el bot no puede escribirte.

El bot solo obedece a ese chat id. Si otra persona le escribe, no contesta.

## 3. Cuenta gratuita de Cloudflare

1. Entra en [https://dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up).
2. Crea la cuenta con el plan **Free** (gratuito). No hace falta tarjeta para este servidor.
3. Confirma el correo si te lo pide.

## 4. Entrar desde el proyecto

Abre PowerShell en la carpeta del proyecto y entra en `server`:

```powershell
cd server
npm install
npx wrangler login
```

`npm install` baja las herramientas a esta carpeta. Tarda un poco la primera vez.

`npx wrangler login` abre el navegador. Entra en la cuenta de Cloudflare que acabas de crear y acepta. Cuando diga que ya estás dentro, vuelve a PowerShell.

## 5. Crear la base de datos

```powershell
npx wrangler d1 create drako-cam-licencias
```

Verás un identificador parecido a esto:

```text
database_id = "8f3e1c2a-0000-4000-8000-000000000000"
```

Abre el archivo `server/wrangler.toml` con el Bloc de notas. Busca la línea que dice:

```toml
database_id = "00000000-0000-0000-0000-000000000000"
```

Sustituye los ceros por el identificador que te dio el comando. Guarda el archivo. Ese identificador no es una contraseña: puede estar en el archivo.

Crea las tablas:

```powershell
npx wrangler d1 migrations apply drako-cam-licencias --remote
```

Si pregunta si quieres continuar, escribe `yes` y pulsa Enter.

## 6. Generar las claves de firma

El servidor firma cada respuesta. La app solo cree una respuesta si la firma coincide con la clave pública. La clave privada no sale del servidor.

En la misma carpeta `server`:

```powershell
node generar-claves.mjs
```

Salen tres valores. Cópialos al bloc de notas. No los subas a GitHub.

1. `SIGNING_SEED`: la clave privada. Solo va al secreto del Worker.
2. `CLAVE_PUBLICA_HEX`: 64 letras y números. Va en la app. No es secreta.
3. `TELEGRAM_WEBHOOK_SECRET`: una clave para que solo Telegram hable con el bot. Va al secreto del Worker.

Cierra la ventana cuando los hayas copiado. El comando no guarda esos valores en el disco.

## 7. Guardar los secretos

Cada comando pide el valor. Pégalo y pulsa Enter. No se escribe en el proyecto.

```powershell
npx wrangler secret put SIGNING_SEED
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_ADMIN_CHAT_ID
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
```

| Comando | Qué pegas |
| --- | --- |
| `SIGNING_SEED` | El primer valor de `generar-claves.mjs` |
| `TELEGRAM_BOT_TOKEN` | El token que te dio BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | El número de `@userinfobot` |
| `TELEGRAM_WEBHOOK_SECRET` | El tercer valor de `generar-claves.mjs` |

Si te equivocas, vuelve a lanzar el mismo `npx wrangler secret put ...` y pega el valor bueno. El nuevo sustituye al anterior.

## 8. Publicar el servidor

```powershell
npx wrangler deploy
```

Al final aparece una dirección como esta:

```text
https://drako-cam-licencias.tu-cuenta.workers.dev
```

Cópiala. Es pública. Puede quedar en la configuración de la app.

## 9. Decirle a Telegram dónde está el bot

Sigue en PowerShell, en la carpeta `server`. Cambia la idea, no pegues el token dentro de un archivo:

```powershell
$token = Read-Host "Pega el token del bot"
$secreto = Read-Host "Pega TELEGRAM_WEBHOOK_SECRET"
$direccion = Read-Host "Pega la URL del Worker, sin barra al final"
$cuerpo = @{
  url = "$direccion/telegram/webhook"
  secret_token = $secreto
  allowed_updates = @("message")
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$token/setWebhook" -ContentType "application/json; charset=utf-8" -Body $cuerpo
```

Tiene que contestar algo como `ok : True`.

Cierra esa ventana de PowerShell cuando termines: el token ha quedado en la memoria de esa sesión, no en un archivo.

Si más adelante quieres comprobarlo:

```powershell
$token = Read-Host "Pega el token del bot"
Invoke-RestMethod "https://api.telegram.org/bot$token/getWebhookInfo"
```

La URL tiene que ser la de tu Worker, terminada en `/telegram/webhook`.

## 10. Poner la URL y la clave pública en la app

Abre `app/drako/licencia_config.py` con el Bloc de notas. Arriba del todo hay dos líneas vacías. Déjalas así, con tus datos:

```python
URL_SERVIDOR = "https://drako-cam-licencias.tu-cuenta.workers.dev"
CLAVE_PUBLICA_HEX = "pega-aqui-los-64-caracteres"
```

Guarda. Esas dos cosas **no son secretos**. La URL es la dirección del servidor. La clave pública solo sirve para comprobar firmas; con ella no se puede firmar.

La clave privada (`SIGNING_SEED`), el token del bot, tu chat id y el secreto del webhook **no** se escriben en ese archivo ni en ningún otro del proyecto.

También puedes pasar la URL sin tocar el archivo, en PowerShell, antes de abrir el programa:

```powershell
$env:DRAKO_CAM_LICENCIA_URL = "https://drako-cam-licencias.tu-cuenta.workers.dev"
```

Si `CLAVE_PUBLICA_HEX` en el archivo está vacío, la clave pública puede ir en:

```powershell
$env:DRAKO_CAM_LICENCIA_CLAVE_PUBLICA = "los-64-caracteres"
```

Cuando el archivo ya tiene la clave, el programa usa esa y no la de la variable. Así, quien reciba la copia no cambia la clave con una variable.

Para acortar las horas sin conexión en un PC concreto (no puede alargarlas por encima de lo que firme el servidor):

```powershell
$env:DRAKO_CAM_LICENCIA_GRACIA_HORAS = "6"
```

## 11. Probar el bot

1. Abre tu bot en Telegram.
2. Escribe `/ayuda`.
3. Tiene que contestarte la lista de comandos. Si no contesta, mira la sección «Si algo falla».

Comandos:

| Comando | Qué hace |
| --- | --- |
| `/nuevo Ana García` | Crea un código único para Ana. Se lo das a esa persona. |
| `/lista` | Muestra los códigos, el nombre y si ya tienen equipo. |
| `/revocar DRAKO-....` | Ese código deja de valer. Si el programa está abierto, se cierra en el siguiente latido (como mucho un minuto). |
| `/activos` | Quién lo está usando ahora: persona, PC, ciudad, país y desde cuándo. |
| `/historial DRAKO-....` | Últimas sesiones: inicio, duración, PC, ciudad, país e IP. |
| `/borrar DRAKO-....` | Borra a esa persona y su historial. El código deja de existir. |
| `/ayuda` | Vuelve a mostrar la lista. |

El código tiene esta forma: `DRAKO-XXXX-XXXX-XXXX-XXXX`. Se puede escribir con o sin guiones.

El primer PC que lo active se queda ligado a ese código. Otro PC con el mismo código no entra. Si Ana cambia de ordenador, revoca el código y crea otro con `/nuevo`.

## 12. Qué ve la otra persona

1. La primera vez, el programa pide **crear** la contraseña de administrador de ese PC. La elige ella. Tú no la ves y no va en el código.
2. Después sale el **aviso de privacidad**. Explica que se registran el uso, la IP y la ubicación aproximada (país y ciudad). Tiene que marcar la casilla y aceptar. Si sale, el programa no se abre.
3. Luego pide el **código** que tú le diste. Solo la primera vez. Se guarda cifrado en su PC.
4. A partir de ahí el programa abre con la contraseña de siempre y, en silencio, comprueba el código al arrancar y más o menos cada minuto.
5. Si revocas el código y hay internet, ve un mensaje claro y el programa se cierra.
6. Si no hay internet, puede seguir usándolo durante las horas de gracia desde la última comprobación buena. Por defecto son **24 horas**. Pasadas esas horas, si sigue sin red, no entra.

La gracia es a propósito: un corte de internet no les echa al momento. También quiere decir que, si alguien desconecta el cable después de que revoques su código, puede seguir hasta que se acabe ese plazo. En cuanto el programa vuelve a hablar con el servidor, el código revocado no entra.

## 13. Cambiar las 24 horas

Abre `server/wrangler.toml`. La línea es:

```toml
GRACIA_HORAS = "24"
```

Pon las horas que quieras, entre 0 y 168, guarda y publica otra vez:

```powershell
npx wrangler deploy
```

El valor nuevo entra en la siguiente comprobación correcta. No hace falta volver a poner los secretos.

`LATIDO_SEGUNDOS` es cada cuántos segundos el programa avisa de que sigue abierto. El valor de fábrica es 60. `SESION_ACTIVA_SECS` es cuánto puede pasar sin un latido antes de dar la sesión por terminada. El valor de fábrica es 180. Si el programa se cierra de golpe y no avisa, desaparece de `/activos` a los tres minutos y el historial muestra la duración hasta el último latido.

## 14. Qué no se sube a GitHub

Este repositorio es público. No subas:

- el token del bot
- tu chat id
- `SIGNING_SEED`
- `TELEGRAM_WEBHOOK_SECRET`
- una exportación de la base de datos (ahí están los códigos y las IP)

Sí pueden estar en el código la URL `workers.dev` y `CLAVE_PUBLICA_HEX`.

La contraseña de administrador de la app tampoco se escribe en ningún archivo. El asistente del primer arranque la pide y solo guarda su huella.

## Si algo falla

**El bot no contesta.** Abre el bot y pulsa Iniciar. Vuelve a hacer el paso 9. En `getWebhookInfo`, `last_error_message` dice el motivo si Telegram no pudo entregar el mensaje.

**`wrangler` no entra.** Repite `npx wrangler login` y acepta en el navegador. El comando hay que lanzarlo desde la carpeta `server`.

**El deploy se queja de la base de datos.** `database_id` en `wrangler.toml` sigue siendo todo ceros. Pega el id del paso 5.

**La app dice que el servidor no está configurado.** `URL_SERVIDOR` o `CLAVE_PUBLICA_HEX` están vacíos en `app/drako/licencia_config.py`, y tampoco están las variables de entorno.

**La app dice que la respuesta no es auténtica.** La clave pública del archivo no es la pareja de `SIGNING_SEED`. Vuelve a ejecutar `node generar-claves.mjs`, guarda la semilla otra vez con `npx wrangler secret put SIGNING_SEED`, publica con `npx wrangler deploy` y pega la clave pública nueva en la app.

**Quieres borrar los datos de una persona.** En el bot: `/borrar` y el código. Eso elimina el código y el historial. `/revocar` solo impide entrar; el historial se queda.

## Comprobar el servidor sin publicarlo

No hace falta para usarlo. Si cambias el código del Worker:

```powershell
cd server
npm test
```

Eso usa Vitest y Miniflare, en local, sin cuenta y sin red de Telegram.
