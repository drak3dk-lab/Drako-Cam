"""Cliente del servidor de acceso: firma, gracia sin red y código cifrado.

La respuesta solo se cree si la firma Ed25519 coincide con la clave pública.
Una respuesta antigua no alarga la gracia: tiene que estar dentro de su plazo.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.drako.auditoria import (
    ClavesAuditoria,
    ErrorCifrado,
    FirmaInvalida,
    cifrar_evento,
    descifrar_evento,
)
from app.drako.configuracion import ConfiguracionLocal
from app.drako.licencia_config import gracia_local_segundos, resolver_clave, resolver_url, url_aceptada
from app.drako.textos_licencia import (
    MENSAJE_SOLICITUD_APROBADA,
    MENSAJE_SOLICITUD_ENVIADA,
    MENSAJE_SOLICITUD_LIMITADA,
    MENSAJE_SOLICITUD_PENDIENTE,
    MENSAJES_ARRANQUE,
    MENSAJES_FORMULARIO,
    VERSION_AVISO,
    mensaje_gracia,
)

logger = logging.getLogger("drako.licencia")

SESGO_S = 600
EXITOS = {"ok", "sin_vincular", "ya_cerrada"}
DEFINITIVOS = {"revocado", "desconocido", "otro_equipo"}
ESTADOS_VALIDOS = {"activa", "sin_vincular", "cerrada"}


class ErrorDeRed(Exception):
    """No hubo una respuesta utilizable del servidor."""


class ErrorConfiguracionLicencia(Exception):
    """Falta la URL o la clave pública."""


def normalizar_codigo(bruto: str) -> str | None:
    if not isinstance(bruto, str):
        return None
    limpio = "".join(caracter for caracter in bruto.upper() if not caracter.isspace()).replace("-", "")
    alfabeto = set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
    if not limpio.startswith("DRAKO"):
        return None
    cuerpo = limpio[5:]
    if len(cuerpo) != 16 or any(caracter not in alfabeto for caracter in cuerpo):
        return None
    return f"DRAKO-{cuerpo[0:4]}-{cuerpo[4:8]}-{cuerpo[8:12]}-{cuerpo[12:16]}"


def hash_codigo(codigo: str) -> str:
    normal = normalizar_codigo(codigo) or ""
    return hashlib.sha256(normal.encode("utf-8")).hexdigest()


def canonico(valor) -> str:
    return json.dumps(_ordenar(valor), ensure_ascii=False, separators=(",", ":"))


def _ordenar(valor):
    if isinstance(valor, dict):
        return {clave: _ordenar(valor[clave]) for clave in sorted(valor)}
    if isinstance(valor, list):
        return [_ordenar(item) for item in valor]
    if isinstance(valor, bool) or valor is None or isinstance(valor, (int, str)):
        return valor
    if isinstance(valor, float):
        if not valor.is_integer():
            raise ValueError("La carga firmada solo usa números enteros.")
        return int(valor)
    raise ValueError("Tipo no admitido en la carga firmada.")


def verificar_firma(clave: bytes, carga: dict, firma_b64: str) -> bool:
    if not clave or not isinstance(carga, dict) or not isinstance(firma_b64, str):
        return False
    try:
        firma = base64.b64decode(firma_b64, validate=True)
        Ed25519PublicKey.from_public_bytes(clave).verify(firma, canonico(carga).encode("utf-8"))
        return True
    except (InvalidSignature, ValueError):
        return False


class _SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TransporteUrllib:
    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self._abridor = urllib.request.build_opener(_SinRedireccion)

    def post(self, url: str, cuerpo: dict, timeout: float | None = None) -> tuple[int, dict]:
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        peticion = urllib.request.Request(
            url,
            data=datos,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "DrakoCam-Licencia/1",
            },
            method="POST",
        )
        espera = self.timeout if timeout is None else timeout
        try:
            with self._abridor.open(peticion, timeout=espera) as respuesta:
                estado = int(getattr(respuesta, "status", 200))
                bruto = respuesta.read(65536)
        except urllib.error.HTTPError as exc:
            estado = int(exc.code)
            bruto = exc.read(65536)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ErrorDeRed("Sin conexión con el servidor de acceso.") from exc
        try:
            cargado = json.loads(bruto.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ErrorDeRed("El servidor de acceso contestó algo ilegible.") from exc
        if not isinstance(cargado, dict):
            raise ErrorDeRed("El servidor de acceso contestó algo ilegible.")
        return estado, cargado


@dataclass(frozen=True)
class RespuestaLicencia:
    carga: dict
    firma: str
    firma_ok: bool
    estado_http: int


@dataclass(frozen=True)
class DecisionAcceso:
    permitir: bool
    motivo: str
    mensaje: str
    concesion_nueva: dict | None = None
    borrar_concesion: bool = False
    borrar_codigo: bool = False
    reactivar: bool = False


class ClienteLicencia:
    def __init__(self, url: str, clave_publica: bytes, transporte, timeout: float = 12.0):
        self.url = (url or "").rstrip("/")
        self.clave_publica = clave_publica or b""
        self.transporte = transporte
        self.timeout = timeout

    def configurado(self) -> bool:
        return bool(self.url and self.clave_publica and url_aceptada(self.url))

    def activar(self, codigo: str, huella: str, equipo: str) -> RespuestaLicencia:
        return self._pedir("/v1/activar", codigo, huella, equipo, "")

    def estado(self, codigo: str, huella: str, equipo: str) -> RespuestaLicencia:
        return self._pedir("/v1/estado", codigo, huella, equipo, "")

    def latido(self, codigo: str, huella: str, equipo: str, sesion: str) -> RespuestaLicencia:
        return self._pedir("/v1/latido", codigo, huella, equipo, sesion)

    def cerrar(
        self,
        codigo: str,
        huella: str,
        equipo: str,
        sesion: str,
        timeout: float | None = None,
    ) -> RespuestaLicencia:
        return self._pedir("/v1/cerrar", codigo, huella, equipo, sesion, timeout)

    def solicitar(self, nombre: str, oficina: str, huella: str, equipo: str) -> RespuestaLicencia:
        if not self.configurado():
            raise ErrorConfiguracionLicencia("Servidor de acceso sin configurar.")
        estado, datos = self.transporte.post(
            self.url + "/v1/solicitud",
            {"nombre": nombre, "oficina": oficina, "huella": huella, "equipo": equipo},
            None,
        )
        return self._interpretar(estado, datos)

    def _pedir(
        self,
        ruta: str,
        codigo: str,
        huella: str,
        equipo: str,
        sesion: str,
        timeout: float | None = None,
    ) -> RespuestaLicencia:
        if not self.configurado():
            raise ErrorConfiguracionLicencia("Servidor de acceso sin configurar.")
        estado, datos = self.transporte.post(
            self.url + ruta,
            {"codigo": codigo, "huella": huella, "equipo": equipo, "sesion": sesion},
            timeout,
        )
        return self._interpretar(estado, datos)

    def _interpretar(self, estado: int, datos: dict) -> RespuestaLicencia:
        carga = datos.get("carga")
        firma = datos.get("firma")
        if estado != 200 or not isinstance(carga, dict) or not isinstance(firma, str):
            raise ErrorDeRed("El servidor de acceso no devolvió una concesión firmada.")
        return RespuestaLicencia(
            carga=carga,
            firma=firma,
            firma_ok=verificar_firma(self.clave_publica, carga, firma),
            estado_http=estado,
        )


def _textos(contexto: str) -> dict:
    return MENSAJES_FORMULARIO if contexto == "formulario" else MENSAJES_ARRANQUE


def _denegar(motivo: str, contexto: str, **extra) -> DecisionAcceso:
    return DecisionAcceso(
        permitir=False,
        motivo=motivo,
        mensaje=_textos(contexto).get(motivo) or MENSAJES_ARRANQUE["sin_red"],
        **extra,
    )


def _forma(carga: dict) -> bool:
    if carga.get("v") != 1 or not isinstance(carga.get("ok"), bool):
        return False
    return all(clave in carga for clave in ("accion", "motivo", "huella", "codigo_hash", "estado", "emitido", "expira"))


def _encaja(carga: dict, huella: str, codigo: str) -> bool:
    if str(carga.get("huella") or "") != huella:
        return False
    esperado = hash_codigo(codigo)
    recibido = str(carga.get("codigo_hash") or "")
    if len(recibido) != len(esperado):
        return False
    return hmac.compare_digest(recibido, esperado)


def _fresca(carga: dict, ahora: float) -> bool:
    try:
        emitido = int(carga["emitido"])
        expira = int(carga["expira"])
    except (KeyError, TypeError, ValueError):
        return False
    if emitido > ahora + SESGO_S:
        return False
    return ahora <= expira + SESGO_S


def gracia_efectiva_segundos(carga: dict, local_s: int | None) -> int:
    try:
        firmada = int(carga.get("gracia_horas")) * 3600
    except (TypeError, ValueError):
        firmada = 24 * 3600
    firmada = max(0, min(firmada, 168 * 3600))
    if local_s is None:
        return firmada
    return min(firmada, max(0, int(local_s)))


def _empaquetar(carga: dict, firma: str, ahora: float) -> dict:
    return {
        "carga": carga,
        "firma": firma,
        "reloj_validacion": float(ahora),
        "visto_hasta": float(ahora),
    }


def _concesion_util(guardada: dict | None, huella: str, codigo: str) -> dict | None:
    if not guardada or not guardada.get("firma_ok") or not isinstance(guardada.get("carga"), dict):
        return None
    carga = guardada["carga"]
    if not _forma(carga) or carga.get("ok") is not True:
        return None
    if str(carga.get("estado")) not in ESTADOS_VALIDOS or not _encaja(carga, huella, codigo):
        return None
    return guardada


def evaluar(
    *,
    respuesta: RespuestaLicencia | None,
    error_red: bool,
    guardada: dict | None,
    ahora: float,
    huella: str,
    codigo: str,
    gracia_local_s: int | None,
    accion_esperada: str,
    contexto: str = "arranque",
    aplicar_borrado: bool = True,
) -> DecisionAcceso:
    if respuesta is not None and respuesta.firma_ok and _forma(respuesta.carga):
        carga = respuesta.carga
        if str(carga.get("accion")) == accion_esperada and _encaja(carga, huella, codigo) and _fresca(carga, ahora):
            motivo = str(carga.get("motivo") or "")
            if carga.get("ok") is True and motivo in EXITOS and str(carga.get("estado")) in ESTADOS_VALIDOS:
                return DecisionAcceso(
                    permitir=True,
                    motivo="ok",
                    mensaje="",
                    concesion_nueva=_empaquetar(carga, respuesta.firma, ahora),
                )
            if motivo == "sesion_desconocida" and carga.get("estado") == "activa":
                return DecisionAcceso(False, "sesion_desconocida", "", reactivar=True)
            if motivo in DEFINITIVOS:
                return _denegar(
                    motivo,
                    contexto,
                    borrar_codigo=aplicar_borrado,
                    borrar_concesion=aplicar_borrado,
                )
    return _gracia_o_bloqueo(
        guardada, ahora, huella, codigo, gracia_local_s, contexto, error_red, respuesta
    )


def _gracia_o_bloqueo(
    guardada: dict | None,
    ahora: float,
    huella: str,
    codigo: str,
    gracia_local_s: int | None,
    contexto: str,
    error_red: bool,
    respuesta: RespuestaLicencia | None,
) -> DecisionAcceso:
    util = _concesion_util(guardada, huella, codigo)
    if util is not None:
        try:
            reloj = float(util["reloj_validacion"])
            visto = float(util.get("visto_hasta") or reloj)
        except (KeyError, TypeError, ValueError):
            reloj, visto = 0.0, 0.0
        gracia = gracia_efectiva_segundos(util["carga"], gracia_local_s)
        if reloj > 0 and max(ahora, visto) <= reloj + gracia:
            concesion = None
            if ahora > visto:
                concesion = {**util, "visto_hasta": float(ahora)}
            return DecisionAcceso(
                True,
                "gracia",
                mensaje_gracia(reloj + gracia),
                concesion_nueva=concesion,
            )
        concesion = {**util, "visto_hasta": float(ahora)} if ahora > visto else None
        return _denegar("gracia_agotada", contexto, concesion_nueva=concesion)
    if respuesta is not None and not respuesta.firma_ok and not error_red:
        return _denegar("firma_invalida", contexto)
    return _denegar("sin_red", contexto)


class GestorLicencia:
    def __init__(
        self,
        config: ConfiguracionLocal,
        claves: ClavesAuditoria,
        cliente: ClienteLicencia,
        huella: str,
        equipo: str,
        gracia_local_s: int | None = None,
        reloj=None,
    ):
        self.config = config
        self.claves = claves
        self.cliente = cliente
        self.huella = huella
        self.equipo = equipo
        self.gracia_local_s = gracia_local_s
        self.reloj = reloj or time.time
        self._lock = threading.Lock()
        guardada = self._leer_concesion()
        self.sesion_id = ""
        if guardada:
            self.sesion_id = str(guardada["carga"].get("sesion") or "")

    def aviso_aceptado(self) -> bool:
        aviso = self.config.datos.get("licencia_aviso")
        return (
            isinstance(aviso, dict)
            and aviso.get("aceptada") is True
            and aviso.get("version") == VERSION_AVISO
        )

    def aceptar_aviso(self, ahora: float | None = None) -> None:
        self.config.datos["licencia_aviso"] = {
            "aceptada": True,
            "version": VERSION_AVISO,
            "marca_unix": float(self.reloj() if ahora is None else ahora),
        }
        self.config.guardar()

    def paso(self) -> str:
        if not self.aviso_aceptado():
            return "privacidad"
        if not self.cliente.configurado():
            return "sin_configurar"
        if not self.leer_codigo():
            return "codigo"
        return "comprobar"

    def leer_codigo(self) -> str | None:
        sobre = self.config.datos.get("licencia_codigo")
        if not isinstance(sobre, dict):
            return None
        try:
            evento = descifrar_evento(sobre, self.claves)
        except (FirmaInvalida, ErrorCifrado):
            return None
        return normalizar_codigo(str(evento.get("codigo") or ""))

    def probar_codigo(self, bruto: str) -> DecisionAcceso:
        with self._lock:
            normal = normalizar_codigo(bruto)
            if not normal:
                return _denegar("mal_formato", "formulario")
            if not self.cliente.configurado():
                return _denegar("sin_configurar", "formulario")
            codigo_anterior = self.leer_codigo()
            sesion_anterior = self.sesion_id
            try:
                respuesta = self.cliente.activar(normal, self.huella, self.equipo)
                error_red = False
            except ErrorDeRed:
                respuesta = None
                error_red = True
            decision = evaluar(
                respuesta=respuesta,
                error_red=error_red,
                guardada=None,
                ahora=float(self.reloj()),
                huella=self.huella,
                codigo=normal,
                gracia_local_s=self.gracia_local_s,
                accion_esperada="activar",
                contexto="formulario",
                aplicar_borrado=False,
            )
            if not decision.permitir:
                return decision
            if codigo_anterior and sesion_anterior and codigo_anterior != normal:
                try:
                    self.cliente.cerrar(codigo_anterior, self.huella, self.equipo, sesion_anterior, timeout=4)
                except ErrorDeRed:
                    logger.warning("No se pudo avisar del cierre de la sesión anterior.")
            self._guardar_codigo(normal)
            self._persistir(decision)
            return decision

    def enviar_solicitud(self, nombre: str, oficina: str) -> DecisionAcceso:
        with self._lock:
            if not self.cliente.configurado():
                return _denegar("sin_configurar", "formulario")
            try:
                respuesta = self.cliente.solicitar(nombre, oficina, self.huella, self.equipo)
            except ErrorDeRed:
                return _denegar("sin_red", "formulario")
            if not respuesta.firma_ok or str(respuesta.carga.get("accion")) != "solicitud":
                return _denegar("firma_invalida", "formulario")
            if str(respuesta.carga.get("huella") or "") != self.huella:
                return _denegar("firma_invalida", "formulario")
            motivo = str(respuesta.carga.get("motivo") or "")
            textos = {
                "enviada": MENSAJE_SOLICITUD_ENVIADA,
                "ya_pendiente": MENSAJE_SOLICITUD_PENDIENTE,
                "ya_aprobada": MENSAJE_SOLICITUD_APROBADA,
                "limitada": MENSAJE_SOLICITUD_LIMITADA,
                "mal_formato": MENSAJES_FORMULARIO["mal_formato"],
            }
            return DecisionAcceso(
                permitir=False,
                motivo=motivo or "sin_red",
                mensaje=textos.get(motivo) or MENSAJES_FORMULARIO["sin_red"],
            )

    def comprobar_arranque(self) -> DecisionAcceso:
        with self._lock:
            codigo = self.leer_codigo()
            if not codigo:
                return _denegar("desconocido", "arranque")
            if not self.cliente.configurado():
                return _denegar("sin_configurar", "arranque")
            guardada = self._leer_concesion()
            try:
                respuesta = self.cliente.estado(codigo, self.huella, self.equipo)
                error_red = False
            except ErrorDeRed:
                respuesta = None
                error_red = True
            decision = self._evaluar(respuesta, error_red, guardada, codigo, "estado", "arranque", True)
            if error_red or not decision.permitir:
                self._persistir(decision)
                return decision
            try:
                respuesta_activar = self.cliente.activar(codigo, self.huella, self.equipo)
            except ErrorDeRed:
                self._persistir(decision)
                return decision
            final = self._evaluar(
                respuesta_activar,
                False,
                decision.concesion_nueva or guardada,
                codigo,
                "activar",
                "arranque",
                True,
            )
            self._persistir(final)
            return final

    def comprobar_latido(self) -> DecisionAcceso:
        with self._lock:
            codigo = self.leer_codigo()
            if not codigo:
                return _denegar("desconocido", "arranque", borrar_codigo=True, borrar_concesion=True)
            if not self.cliente.configurado():
                return _denegar("sin_configurar", "arranque")
            guardada = self._leer_concesion()
            try:
                respuesta = self.cliente.latido(codigo, self.huella, self.equipo, self.sesion_id)
                error_red = False
            except ErrorDeRed:
                respuesta = None
                error_red = True
            decision = self._evaluar(respuesta, error_red, guardada, codigo, "latido", "arranque", True)
            if decision.reactivar and not error_red:
                try:
                    respuesta = self.cliente.activar(codigo, self.huella, self.equipo)
                    decision = self._evaluar(
                        respuesta, False, guardada, codigo, "activar", "arranque", True
                    )
                except ErrorDeRed:
                    decision = self._evaluar(None, True, guardada, codigo, "latido", "arranque", True)
            self._persistir(decision)
            return decision

    def cerrar_sesion(self) -> None:
        with self._lock:
            codigo = self.leer_codigo()
            if not codigo or not self.sesion_id or not self.cliente.configurado():
                return
            try:
                self.cliente.cerrar(codigo, self.huella, self.equipo, self.sesion_id, timeout=4)
            except ErrorDeRed:
                logger.warning("Sin red al cerrar la sesión de acceso.")

    def _evaluar(
        self,
        respuesta: RespuestaLicencia | None,
        error_red: bool,
        guardada: dict | None,
        codigo: str,
        accion: str,
        contexto: str,
        aplicar_borrado: bool,
    ) -> DecisionAcceso:
        return evaluar(
            respuesta=respuesta,
            error_red=error_red,
            guardada=guardada,
            ahora=float(self.reloj()),
            huella=self.huella,
            codigo=codigo,
            gracia_local_s=self.gracia_local_s,
            accion_esperada=accion,
            contexto=contexto,
            aplicar_borrado=aplicar_borrado,
        )

    def _guardar_codigo(self, codigo: str) -> None:
        self.config.datos["licencia_codigo"] = cifrar_evento(
            {"tipo": "codigo_acceso", "codigo": codigo}, self.claves
        )

    def _leer_concesion(self) -> dict | None:
        sobre = self.config.datos.get("licencia_concesion")
        if not isinstance(sobre, dict):
            return None
        try:
            evento = descifrar_evento(sobre, self.claves)
        except (FirmaInvalida, ErrorCifrado):
            return None
        carga = evento.get("carga")
        firma = evento.get("firma")
        if not isinstance(carga, dict) or not isinstance(firma, str):
            return None
        if not verificar_firma(self.cliente.clave_publica, carga, firma):
            return None
        try:
            reloj = float(evento["reloj_validacion"])
            visto = float(evento.get("visto_hasta") or reloj)
        except (KeyError, TypeError, ValueError):
            return None
        return {
            "carga": carga,
            "firma": firma,
            "reloj_validacion": reloj,
            "visto_hasta": visto,
            "firma_ok": True,
        }

    def _persistir(self, decision: DecisionAcceso) -> None:
        if decision.borrar_codigo:
            self.config.datos.pop("licencia_codigo", None)
            self.sesion_id = ""
        if decision.borrar_concesion:
            self.config.datos.pop("licencia_concesion", None)
            self.sesion_id = ""
        elif decision.concesion_nueva is not None:
            self.config.datos["licencia_concesion"] = cifrar_evento(
                decision.concesion_nueva, self.claves
            )
            sesion = str(decision.concesion_nueva["carga"].get("sesion") or "")
            if sesion:
                self.sesion_id = sesion
        if decision.borrar_codigo or decision.borrar_concesion or decision.concesion_nueva is not None:
            self.config.guardar()


def crear_gestor(contexto, claves: ClavesAuditoria, entorno: dict | None = None, transporte=None, reloj=None) -> GestorLicencia:
    from app.drako.huella import huella_equipo

    datos = contexto.config.datos
    url = resolver_url(datos, entorno)
    clave = resolver_clave(datos, entorno) or b""
    cliente = ClienteLicencia(url, clave, transporte or TransporteUrllib())
    huella, equipo = huella_equipo(entorno)
    return GestorLicencia(
        contexto.config,
        claves,
        cliente,
        huella,
        equipo,
        gracia_local_s=gracia_local_segundos(datos, entorno),
        reloj=reloj,
    )
