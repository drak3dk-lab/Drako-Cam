"""Textos visibles del acceso por código. Todo en español."""

VERSION_AVISO = 1

TITULO_AVISO = "Antes de entrar"
INTRO_AVISO = (
    "Drako Cam es gratuito, pero solo entra quien tiene un código del administrador. "
    "No es anónimo: el administrador ve quién lo usa y desde dónde."
)
PUNTOS_AVISO = (
    (
        "Nombre y oficina",
        "El nombre de la persona y el de la oficina donde se instala el programa.",
    ),
    (
        "Código de acceso",
        "El código personal que el administrador entrega si aprueba la solicitud.",
    ),
    (
        "Nombre de este equipo",
        "El nombre de este PC, para distinguirlo de otros.",
    ),
    (
        "Dirección IP",
        "La dirección de red desde la que se conecta el programa.",
    ),
    (
        "Ubicación aproximada",
        "País y ciudad calculados por la red. No es el GPS ni una dirección exacta.",
    ),
    (
        "Uso de la sesión",
        "Hora de inicio, hora de fin y cuánto tiempo ha estado abierto.",
    ),
)
CIERRE_AVISO = (
    "No se envían imágenes, caras ni la contraseña de administrador. "
    "La base es tu consentimiento: si no aceptas, el programa no se abre. "
    "Puedes dejar de usarlo cuando quieras. Si quieres que se borren estos datos, "
    "pídeselo al administrador: puede revocar el código y eliminar el historial."
)
CASILLA_AVISO = (
    "He leído el aviso y acepto que se registren el uso, la IP y la ubicación aproximada."
)

TITULO_CODIGO = "Código personal"
TEXTO_CODIGO = (
    "Si todavía no tienes código, escribe tu nombre y la oficina y pulsa Pedir acceso. "
    "El administrador lo verá y, si lo aprueba, te pasará el código. "
    "Si ya te lo dio, escríbelo abajo y pulsa Entrar. Se guarda cifrado en este equipo."
)
MENSAJE_SOLICITUD_ENVIADA = (
    "Solicitud enviada. Cuando el administrador te pase el código, escríbelo aquí."
)
MENSAJE_SOLICITUD_PENDIENTE = (
    "Ya hay una solicitud pendiente para este equipo. "
    "Cuando te pasen el código, escríbelo aquí."
)
MENSAJE_SOLICITUD_APROBADA = (
    "Este equipo ya tiene un código aprobado. Pídeselo al administrador y escríbelo aquí. "
    "El servidor no vuelve a mostrarlo."
)
MENSAJE_SOLICITUD_LIMITADA = (
    "Demasiadas solicitudes desde esta red. Espera un rato y vuelve a probar."
)
PLACEHOLDER_CODIGO = "DRAKO-XXXX-XXXX-XXXX-XXXX"

MENSAJE_SIN_CONFIGURAR = (
    "Esta copia de Drako Cam no tiene configurado el servidor de acceso. "
    "Falta la dirección o la clave pública. Avísale al administrador."
)
MENSAJE_FORMATO = "El código debe tener la forma DRAKO-XXXX-XXXX-XXXX-XXXX."
MENSAJE_SIN_RED_PRIMERA = (
    "Hace falta conexión a internet la primera vez, para comprobar el código. "
    "No se ha guardado."
)
MENSAJE_SIN_RED = (
    "No hay conexión con el servidor de acceso y este equipo no tiene "
    "una comprobación reciente. El programa se cierra."
)
MENSAJE_GRACIA_AGOTADA = (
    "Llevas demasiado tiempo sin poder comprobar el acceso. "
    "El programa se cierra hasta que haya conexión."
)
MENSAJE_FIRMA = (
    "La respuesta del servidor de acceso no es auténtica. El programa se cierra."
)
MENSAJE_GENERICO = "No se pudo comprobar el acceso. El programa se cierra."

MENSAJES_ARRANQUE = {
    "revocado": (
        "Este código de acceso está revocado. El programa se cierra. "
        "Pide un código nuevo al administrador."
    ),
    "desconocido": (
        "Este código de acceso no es válido. El programa se cierra. "
        "Compruébalo con el administrador."
    ),
    "otro_equipo": (
        "Este código ya está ligado a otro equipo. Se ha pedido una aprobación "
        "nueva para este PC. Escribe al administrador por Telegram."
    ),
    "mal_formato": MENSAJE_FORMATO,
    "limitada": (
        "Demasiados intentos desde esta red. Espera un rato y vuelve a abrir el programa."
    ),
    "firma_invalida": MENSAJE_FIRMA,
    "sin_red": MENSAJE_SIN_RED,
    "gracia_agotada": MENSAJE_GRACIA_AGOTADA,
    "sin_configurar": MENSAJE_SIN_CONFIGURAR,
}

MENSAJES_FORMULARIO = {
    "revocado": "Ese código está revocado. Pide uno nuevo al administrador.",
    "desconocido": "Ese código no es válido. Revísalo o pide uno al administrador.",
    "otro_equipo": (
        "Ese código ya está ligado a otro equipo. Se ha pedido una aprobación "
        "nueva para este PC. Escribe al administrador por Telegram."
    ),
    "mal_formato": MENSAJE_FORMATO,
    "limitada": "Demasiados intentos desde esta red. Espera un rato y vuelve a probar.",
    "firma_invalida": (
        "La respuesta del servidor de acceso no es auténtica. No se ha guardado el código."
    ),
    "sin_red": MENSAJE_SIN_RED_PRIMERA,
    "gracia_agotada": MENSAJE_SIN_RED_PRIMERA,
    "sin_configurar": MENSAJE_SIN_CONFIGURAR,
}


def mensaje_corte_directo() -> str:
    from app.drako.licencia_config import mensaje_contacto_telegram

    contacto = mensaje_contacto_telegram()
    base = (
        "El directo se detuvo. Este equipo no tiene permiso, "
        "o no se pudo comprobar el acceso a tiempo."
    )
    if contacto:
        return base + " " + contacto + "."
    return base


def mensaje_gracia(limite_unix: float) -> str:
    import time

    hora = time.strftime("%d/%m/%Y %H:%M", time.localtime(limite_unix))
    return (
        "Ahora mismo no hay conexión con el servidor de acceso. "
        f"Puedes usar Drako Cam hasta el {hora}. "
        "Pasada esa hora, si sigue sin red, el programa no se abrirá."
    )
