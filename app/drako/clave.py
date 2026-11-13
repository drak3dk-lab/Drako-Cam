"""Contraseña de administrador con Argon2id y bloqueo temporal.

El hash y el contador de intentos viven en la configuración local.
La contraseña en claro no se escribe en disco ni en el registro.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from app.drako.configuracion import ConfiguracionLocal

# Parámetros Argon2id recomendados por OWASP (memoria 19 MiB, 2 iteraciones).
_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

MIN_LONGITUD = 8
UMBRAL_INTENTOS = 5
BLOQUEO_BASE_S = 60
BLOQUEO_MAX_S = 15 * 60
TOPE_PENDIENTES = 50


@dataclass
class ResultadoAcceso:
    ok: bool
    motivo: str
    mensaje: str
    pendientes: list = field(default_factory=list)
    segundos_bloqueo: int = 0


class AlmacenClave:
    def __init__(self, config: ConfiguracionLocal, reloj=None, equipo=None):
        self.config = config
        self.reloj = reloj or __import__("time").time
        self._equipo = equipo or socket.gethostname

    def _auth(self) -> dict:
        auth = self.config.datos.setdefault("auth", {})
        auth.setdefault("password_hash", "")
        auth.setdefault("failed_attempts", 0)
        auth.setdefault("lock_level", 0)
        auth.setdefault("locked_until", None)
        auth.setdefault("pending_failures", [])
        return auth

    def esta_configurada(self) -> bool:
        return bool(self._auth().get("password_hash"))

    def hash_publico(self) -> str:
        return str(self._auth().get("password_hash") or "")

    def segundos_restantes(self) -> int:
        hasta = self._auth().get("locked_until")
        if not hasta:
            return 0
        restante = float(hasta) - float(self.reloj())
        if restante <= 0:
            return 0
        return int(restante + 0.999)

    def esta_bloqueado(self) -> bool:
        return self.segundos_restantes() > 0

    def fijar_inicial(self, clave: str, confirmacion: str) -> ResultadoAcceso:
        if self.esta_configurada():
            return self._resultado(
                False,
                "ya_configurada",
                "La contraseña ya está definida. Hay que cambiarla indicando la actual.",
            )
        error = self._validar_nueva(clave, confirmacion)
        if error is not None:
            return error
        self._poner_hash(clave)
        self._reiniciar_intentos()
        self.config.guardar()
        return self._resultado(True, "ok", "Contraseña de administrador guardada.")

    def verificar(self, clave: str) -> ResultadoAcceso:
        if not self.esta_configurada():
            return self._resultado(
                False,
                "no_configurada",
                "Todavía no hay una contraseña de administrador.",
            )
        if self.esta_bloqueado():
            segundos = self.segundos_restantes()
            return self._resultado(
                False,
                "bloqueada",
                self._mensaje_bloqueo(segundos),
                segundos_bloqueo=segundos,
            )
        if not self._coincide(clave):
            return self._registrar_fallo()
        pendientes = list(self._auth().get("pending_failures") or [])
        self._reiniciar_intentos()
        self._auth()["pending_failures"] = []
        hash_actual = self.hash_publico()
        if _HASHER.check_needs_rehash(hash_actual):
            self._poner_hash(clave)
        self.config.guardar()
        return self._resultado(
            True,
            "ok",
            "Acceso concedido.",
            pendientes=pendientes,
        )

    def cambiar(self, actual: str, nueva: str, confirmacion: str) -> ResultadoAcceso:
        if not self.esta_configurada():
            return self._resultado(
                False,
                "no_configurada",
                "Todavía no hay una contraseña de administrador.",
            )
        if self.esta_bloqueado():
            segundos = self.segundos_restantes()
            return self._resultado(
                False,
                "bloqueada",
                self._mensaje_bloqueo(segundos),
                segundos_bloqueo=segundos,
            )
        if not self._coincide(actual):
            return self._registrar_fallo()
        error = self._validar_nueva(nueva, confirmacion)
        if error is not None:
            return error
        self._poner_hash(nueva)
        self._reiniciar_intentos()
        self._auth()["pending_failures"] = []
        self.config.guardar()
        return self._resultado(True, "ok", "Contraseña actualizada.")

    def _validar_nueva(self, clave: str, confirmacion: str) -> ResultadoAcceso | None:
        if clave != confirmacion:
            return self._resultado(
                False,
                "no_coincide",
                "La confirmación no coincide con la contraseña.",
            )
        if len(clave) < MIN_LONGITUD or not clave.strip():
            return self._resultado(
                False,
                "debil",
                f"La contraseña debe tener al menos {MIN_LONGITUD} caracteres.",
            )
        return None

    def _poner_hash(self, clave: str) -> None:
        self._auth()["password_hash"] = _HASHER.hash(clave)

    def _coincide(self, clave: str) -> bool:
        try:
            return _HASHER.verify(self.hash_publico(), clave)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def _reiniciar_intentos(self) -> None:
        auth = self._auth()
        auth["failed_attempts"] = 0
        auth["lock_level"] = 0
        auth["locked_until"] = None

    def _registrar_fallo(self) -> ResultadoAcceso:
        auth = self._auth()
        auth["failed_attempts"] = int(auth.get("failed_attempts") or 0) + 1
        pendientes = auth.setdefault("pending_failures", [])
        equipo = self._equipo() if callable(self._equipo) else str(self._equipo)
        pendientes.append(
            {
                "tipo": "intento_fallido",
                "equipo": equipo,
                "marca_unix": float(self.reloj()),
                "detalle": "contraseña incorrecta",
            }
        )
        del pendientes[:-TOPE_PENDIENTES]
        segundos = 0
        motivo = "incorrecta"
        mensaje = "La contraseña no es correcta."
        if auth["failed_attempts"] >= UMBRAL_INTENTOS:
            nivel = int(auth.get("lock_level") or 0)
            segundos = min(BLOQUEO_MAX_S, BLOQUEO_BASE_S * (2**nivel))
            auth["locked_until"] = float(self.reloj()) + segundos
            auth["lock_level"] = nivel + 1
            auth["failed_attempts"] = 0
            motivo = "bloqueada"
            mensaje = self._mensaje_bloqueo(segundos)
            pendientes.append(
                {
                    "tipo": "bloqueo",
                    "equipo": equipo,
                    "marca_unix": float(self.reloj()),
                    "detalle": f"bloqueo {segundos}s",
                }
            )
            del pendientes[:-TOPE_PENDIENTES]
        self.config.guardar()
        return self._resultado(
            False, motivo, mensaje, segundos_bloqueo=segundos
        )

    @staticmethod
    def _mensaje_bloqueo(segundos: int) -> str:
        return (
            "Demasiados intentos fallidos. "
            f"El acceso queda bloqueado durante {segundos} segundos."
        )

    @staticmethod
    def _resultado(
        ok: bool,
        motivo: str,
        mensaje: str,
        pendientes: list | None = None,
        segundos_bloqueo: int = 0,
    ) -> ResultadoAcceso:
        return ResultadoAcceso(
            ok=ok,
            motivo=motivo,
            mensaje=mensaje,
            pendientes=list(pendientes or []),
            segundos_bloqueo=segundos_bloqueo,
        )
