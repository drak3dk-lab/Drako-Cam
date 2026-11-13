"""Solicitud de acceso desde el instalador, sin ventanas.

Sale 0 si el servidor está listo o si la solicitud se envió.
Sale 10 si falta la URL o la clave pública: la instalación puede terminar.
Sale 1 si el envío falló. El instalador no debe tratarlo como un fallo grave.
"""

from __future__ import annotations

import argparse
import sys

from app.drako.huella import huella_equipo
from app.drako.licencia import ClienteLicencia, ErrorConfiguracionLicencia, ErrorDeRed, TransporteUrllib
from app.drako.licencia_config import anexo_contacto_telegram, resolver_clave, resolver_url
from app.drako.textos_licencia import (
    MENSAJE_SIN_CONFIGURAR,
    MENSAJE_SOLICITUD_APROBADA,
    MENSAJE_SOLICITUD_ENVIADA,
    MENSAJE_SOLICITUD_LIMITADA,
    MENSAJE_SOLICITUD_PENDIENTE,
)

MENSAJE_INSTALADOR_SIN_SERVIDOR = (
    "Falta la configuración del servidor de acceso. "
    "La instalación ha terminado igual. Cuando esté configurado, "
    "pide el código al abrir Drako Cam."
)


def _con_contacto(texto: str) -> str:
    extra = anexo_contacto_telegram()
    if not extra or extra in texto:
        return texto
    return f"{texto}\n\n{extra}"


def servidor_configurado(entorno: dict | None = None) -> bool:
    datos: dict = {}
    url = resolver_url(datos, entorno)
    clave = resolver_clave(datos, entorno)
    return bool(url and clave)


def enviar(nombre: str, oficina: str, transporte=None, entorno: dict | None = None) -> tuple[int, str]:
    if not servidor_configurado(entorno):
        return 10, MENSAJE_INSTALADOR_SIN_SERVIDOR
    datos: dict = {}
    cliente = ClienteLicencia(
        resolver_url(datos, entorno),
        resolver_clave(datos, entorno) or b"",
        transporte or TransporteUrllib(),
    )
    huella, equipo = huella_equipo(entorno)
    try:
        respuesta = cliente.solicitar(nombre.strip(), oficina.strip(), huella, equipo)
    except ErrorConfiguracionLicencia:
        return 10, MENSAJE_INSTALADOR_SIN_SERVIDOR
    except ErrorDeRed:
        return 1, _con_contacto(
            "No se pudo enviar la solicitud. Podrás pedirla al abrir Drako Cam."
        )
    if not respuesta.firma_ok or str(respuesta.carga.get("huella") or "") != huella:
        return 1, "La respuesta del servidor de acceso no es auténtica. No se ha dado por enviada."
    motivo = str(respuesta.carga.get("motivo") or "")
    textos = {
        "enviada": _con_contacto(MENSAJE_SOLICITUD_ENVIADA),
        "ya_pendiente": _con_contacto(MENSAJE_SOLICITUD_PENDIENTE),
        "ya_aprobada": _con_contacto(MENSAJE_SOLICITUD_APROBADA),
        "limitada": MENSAJE_SOLICITUD_LIMITADA,
        "mal_formato": "Escribe el nombre de la persona y el de la oficina.",
    }
    if motivo not in textos:
        return 1, MENSAJE_SIN_CONFIGURAR
    return 0, textos[motivo]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Solicita el código de acceso de Drako Cam.")
    parser.add_argument("--estado", action="store_true", help="Solo dice si el servidor está configurado.")
    parser.add_argument("--contacto", action="store_true", help="Muestra cómo pedir el código por Telegram.")
    parser.add_argument("--nombre", default="")
    parser.add_argument("--oficina", default="")
    args = parser.parse_args(argv)
    if args.contacto:
        print(anexo_contacto_telegram() or "No hay un contacto de Telegram configurado.")
        return 0
    if args.estado:
        if servidor_configurado():
            print("Servidor de acceso configurado.")
            return 0
        print(MENSAJE_INSTALADOR_SIN_SERVIDOR)
        return 10
    codigo, texto = enviar(args.nombre, args.oficina)
    print(texto)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
