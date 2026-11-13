"""Registro de uso cifrado (AES-GCM) y firmado (HMAC-SHA256).

Las claves se generan en el primer arranque y se guardan envueltas
con una clave derivada de la contraseña (Argon2id). No van en el código.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.drako.configuracion import ConfiguracionLocal

_DOMINIO_SOBRE = b"drako-cam-auditoria-v1\n"
_AAD_CLAVE = b"drako-cam-clave-auditoria"
_KDF_TIME = 2
_KDF_MEMORY = 19456
_KDF_PARALLEL = 1


class FirmaInvalida(Exception):
    """El registro fue modificado o la firma no corresponde."""


class ErrorCifrado(Exception):
    """No se pudo descifrar un evento (clave distinta o datos rotos)."""


@dataclass(frozen=True)
class ClavesAuditoria:
    cifrado: bytes
    firma: bytes


def generar_claves() -> ClavesAuditoria:
    return ClavesAuditoria(cifrado=os.urandom(32), firma=os.urandom(32))


def _derivar(contrasena: str, sal: bytes) -> bytes:
    return hash_secret_raw(
        secret=contrasena.encode("utf-8"),
        salt=sal,
        time_cost=_KDF_TIME,
        memory_cost=_KDF_MEMORY,
        parallelism=_KDF_PARALLEL,
        hash_len=32,
        type=Type.ID,
    )


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def _desde_b64(texto: str) -> bytes:
    return base64.b64decode(texto.encode("ascii"))


def envolver_claves(claves: ClavesAuditoria, contrasena: str) -> dict:
    sal = os.urandom(16)
    material = _derivar(contrasena, sal)
    aes = AESGCM(material)
    nonce_cifrado = os.urandom(12)
    nonce_firma = os.urandom(12)
    return {
        "kdf": "argon2id",
        "kdf_salt": _b64(sal),
        "enc_nonce": _b64(nonce_cifrado),
        "enc_blob": _b64(aes.encrypt(nonce_cifrado, claves.cifrado, _AAD_CLAVE)),
        "sign_nonce": _b64(nonce_firma),
        "sign_blob": _b64(aes.encrypt(nonce_firma, claves.firma, _AAD_CLAVE)),
    }


def desenvolver_claves(sobre: dict, contrasena: str) -> ClavesAuditoria:
    try:
        sal = _desde_b64(sobre["kdf_salt"])
        material = _derivar(contrasena, sal)
        aes = AESGCM(material)
        cifrado = aes.decrypt(
            _desde_b64(sobre["enc_nonce"]),
            _desde_b64(sobre["enc_blob"]),
            _AAD_CLAVE,
        )
        firma = aes.decrypt(
            _desde_b64(sobre["sign_nonce"]),
            _desde_b64(sobre["sign_blob"]),
            _AAD_CLAVE,
        )
    except Exception as exc:
        raise ErrorCifrado("No se pudieron abrir las claves del registro.") from exc
    if len(cifrado) != 32 or len(firma) != 32:
        raise ErrorCifrado("Las claves del registro no tienen el tamaño esperado.")
    return ClavesAuditoria(cifrado=cifrado, firma=firma)


def guardar_claves(
    config: ConfiguracionLocal, claves: ClavesAuditoria, contrasena: str
) -> None:
    config.datos["audit_keys"] = envolver_claves(claves, contrasena)
    config.guardar()


def obtener_claves(config: ConfiguracionLocal, contrasena: str) -> ClavesAuditoria:
    sobre = config.datos.get("audit_keys")
    if not sobre:
        claves = generar_claves()
        guardar_claves(config, claves, contrasena)
        return claves
    return desenvolver_claves(sobre, contrasena)


def _firmar(clave_firma: bytes, nonce: bytes, cifrado: bytes) -> str:
    mac = hmac.new(clave_firma, _DOMINIO_SOBRE + nonce + cifrado, hashlib.sha256)
    return mac.hexdigest()


def cifrar_evento(evento: dict, claves: ClavesAuditoria) -> dict:
    plano = json.dumps(
        evento, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    nonce = os.urandom(12)
    cifrado = AESGCM(claves.cifrado).encrypt(nonce, plano, None)
    return {
        "v": 1,
        "nonce": nonce.hex(),
        "ct": cifrado.hex(),
        "sig": _firmar(claves.firma, nonce, cifrado),
    }


def descifrar_evento(sobre: dict, claves: ClavesAuditoria) -> dict:
    try:
        nonce = bytes.fromhex(sobre["nonce"])
        cifrado = bytes.fromhex(sobre["ct"])
        firma = str(sobre["sig"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FirmaInvalida("El sobre del evento está incompleto.") from exc
    esperada = _firmar(claves.firma, nonce, cifrado)
    if len(firma) != len(esperada) or not hmac.compare_digest(firma, esperada):
        raise FirmaInvalida("La firma del evento no es válida.")
    try:
        plano = AESGCM(claves.cifrado).decrypt(nonce, cifrado, None)
        evento = json.loads(plano.decode("utf-8"))
    except Exception as exc:
        raise ErrorCifrado("No se pudo descifrar el evento.") from exc
    if not isinstance(evento, dict):
        raise ErrorCifrado("El evento descifrado no es un objeto.")
    return evento


class RegistroAuditoria:
    def __init__(self, ruta, claves: ClavesAuditoria):
        self.ruta = ruta
        self.claves = claves

    def registrar(self, evento: dict) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        linea = json.dumps(
            cifrar_evento(evento, self.claves), ensure_ascii=False, separators=(",", ":")
        )
        fd = os.open(self.ruta, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (linea + "\n").encode("utf-8"))
        finally:
            os.close(fd)

    def leer(self) -> list[dict]:
        if not self.ruta.is_file():
            return []
        eventos = []
        texto = self.ruta.read_text(encoding="utf-8")
        for numero, linea in enumerate(texto.splitlines(), start=1):
            if not linea.strip():
                continue
            try:
                sobre = json.loads(linea)
            except json.JSONDecodeError as exc:
                raise FirmaInvalida(f"La línea {numero} del registro no es JSON.") from exc
            eventos.append(descifrar_evento(sobre, self.claves))
        return eventos
