"""Cliente de licencias con servidor simulado: firma, gracia y revocación."""

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.drako.auditoria import generar_claves
from app.drako.configuracion import ConfiguracionLocal
from app.drako.huella import huella_equipo
from app.drako.licencia import (
    ClienteLicencia,
    DecisionAcceso,
    ErrorDeRed,
    GestorLicencia,
    RespuestaLicencia,
    canonico,
    evaluar,
    hash_codigo,
    normalizar_codigo,
    verificar_firma,
)
from app.drako.licencia_config import (
    gracia_local_segundos,
    resolver_clave,
    resolver_url,
)
from app.drako import textos_licencia as textos

RAIZ = Path(__file__).resolve().parents[3]
VECTOR = (
    '{"accion":"activar","codigo_hash":"abc","emitido":1760000000,'
    '"estado":"activa","expira":1760000180,"gracia_horas":24,"huella":"aa",'
    '"latido_segundos":60,"mensaje":"Acceso concedido en București.",'
    '"motivo":"ok","ok":true,"persona":"José","sesion":"s1","v":1}'
)
FIRMA_VECTOR = (
    "LWQ5410GLZlD8ULKr9UWv1X2iNuGynZFU+0aHPQr3Z6pO548OsrNQ81XiSlQPqdX0er9gFeOp+ofkyyWvl0AAQ=="
)
PUBLICA_VECTOR = bytes.fromhex(
    "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737"
)
HUELLA = "ab" * 32
CODIGO = "DRAKO-AAAA-BBBB-CCCC-DDDD"


def test_el_vector_firmado_por_el_servidor_verifica_y_un_cambio_no():
    carga = json.loads(VECTOR)
    assert canonico(carga) == VECTOR
    assert verificar_firma(PUBLICA_VECTOR, carga, FIRMA_VECTOR)
    carga["persona"] = "Otra"
    assert not verificar_firma(PUBLICA_VECTOR, carga, FIRMA_VECTOR)


def test_normaliza_el_codigo_y_no_acepta_letras_ambiguas():
    assert normalizar_codigo("  drako-aaaa-bbbb-cccc-dddd ") == CODIGO
    assert normalizar_codigo("DRAKO-AAA1-BBBB-CCCC-DDDD") is None
    assert normalizar_codigo("DRAKO-AAAA-BBBB-CCCC") is None


def test_la_huella_es_estable_y_no_revela_el_identificador():
    entorno = {"DRAKO_CAM_EQUIPO": "PC-CASA"}
    una, nombre = huella_equipo(entorno, lector_id=lambda: "win:GUID-SECRETO")
    otra, _ = huella_equipo(entorno, lector_id=lambda: "win:GUID-SECRETO")
    distinta, _ = huella_equipo(entorno, lector_id=lambda: "win:OTRO")
    assert una == otra
    assert len(una) == 64
    assert nombre == "PC-CASA"
    assert "GUID-SECRETO" not in una
    assert una != distinta


def test_la_clave_del_archivo_manda_sobre_el_entorno(monkeypatch):
    monkeypatch.setattr(
        "app.drako.licencia_config.CLAVE_PUBLICA_HEX", "ab" * 32
    )
    entorno = {"DRAKO_CAM_LICENCIA_CLAVE_PUBLICA": "cd" * 32}
    assert resolver_clave({}, entorno) == bytes.fromhex("ab" * 32)
    monkeypatch.setattr("app.drako.licencia_config.CLAVE_PUBLICA_HEX", "")
    monkeypatch.setattr("app.drako.licencia_config.URL_SERVIDOR", "https://archivo.example")
    entorno["DRAKO_CAM_LICENCIA_URL"] = "https://entorno.example/"
    assert resolver_url({}, entorno) == "https://entorno.example"
    assert resolver_clave({}, entorno) == bytes.fromhex("cd" * 32)
    assert gracia_local_segundos({}, {"DRAKO_CAM_LICENCIA_GRACIA_HORAS": "6"}) == 6 * 3600


def _carga(codigo, huella, **cambios):
    carga = {
        "v": 1,
        "accion": "activar",
        "ok": True,
        "motivo": "ok",
        "mensaje": "",
        "persona": "Ana",
        "codigo_hash": hash_codigo(codigo),
        "huella": huella,
        "sesion": "s1",
        "estado": "activa",
        "emitido": 1_000,
        "expira": 1_180,
        "latido_segundos": 60,
        "gracia_horas": 24,
    }
    carga.update(cambios)
    return carga


def _respuesta(carga, firma_ok=True):
    return RespuestaLicencia(carga, "firma-de-prueba", firma_ok, 200)


def _guardada(carga, reloj=1_000, visto=None):
    return {
        "carga": carga,
        "firma": "firma-de-prueba",
        "reloj_validacion": float(reloj),
        "visto_hasta": float(reloj if visto is None else visto),
        "firma_ok": True,
    }


def _evaluar(**extra):
    base = dict(
        respuesta=None,
        error_red=True,
        guardada=None,
        ahora=1_000.0,
        huella=HUELLA,
        codigo=CODIGO,
        gracia_local_s=None,
        accion_esperada="activar",
        contexto="arranque",
        aplicar_borrado=True,
    )
    base.update(extra)
    return evaluar(**base)


def test_una_concesion_fresca_permite_y_una_revocacion_firmada_borra():
    ok = _evaluar(
        respuesta=_respuesta(_carga(CODIGO, HUELLA, emitido=5_000, expira=5_180)),
        error_red=False,
        ahora=5_000,
    )
    assert ok.permitir and ok.motivo == "ok"
    assert ok.concesion_nueva["reloj_validacion"] == 5_000

    guardada = _guardada(_carga(CODIGO, HUELLA), reloj=1_000)
    revocada = _carga(
        CODIGO,
        HUELLA,
        ok=False,
        motivo="revocado",
        estado="revocada",
        accion="estado",
        emitido=5_000,
        expira=5_180,
    )
    decision = _evaluar(
        respuesta=_respuesta(revocada),
        error_red=False,
        guardada=guardada,
        ahora=5_000,
        accion_esperada="estado",
    )
    assert not decision.permitir
    assert decision.motivo == "revocado"
    assert decision.borrar_codigo and decision.borrar_concesion
    assert "revocado" in decision.mensaje
    assert "se cierra" in decision.mensaje


def test_sin_red_hay_gracia_y_despues_bloqueo():
    guardada = _guardada(_carga(CODIGO, HUELLA), reloj=10_000)
    dentro = _evaluar(guardada=guardada, ahora=10_000 + 3600)
    assert dentro.permitir and dentro.motivo == "gracia"
    assert "hasta el" in dentro.mensaje

    fuera = _evaluar(guardada=guardada, ahora=10_000 + 24 * 3600 + 5)
    assert not fuera.permitir and fuera.motivo == "gracia_agotada"
    assert not fuera.borrar_codigo

    primera = _evaluar(guardada=None, ahora=10_000, contexto="formulario")
    assert not primera.permitir and primera.motivo == "sin_red"
    assert "primera vez" in primera.mensaje


def test_el_reloj_atrasado_no_alarga_el_plazo():
    guardada = _guardada(_carga(CODIGO, HUELLA), reloj=10_000, visto=10_000)
    atras = _evaluar(guardada=guardada, ahora=9_000)
    assert atras.permitir
    assert atras.concesion_nueva is None or atras.concesion_nueva["reloj_validacion"] == 10_000

    vencida = _evaluar(guardada=guardada, ahora=10_000 + 24 * 3600 + 30)
    assert not vencida.permitir
    assert vencida.concesion_nueva["visto_hasta"] == 10_000 + 24 * 3600 + 30
    otra = _evaluar(guardada=vencida.concesion_nueva, ahora=10_500)
    assert not otra.permitir


def test_una_firma_invalida_o_caducada_no_renueva_la_gracia():
    guardada = _guardada(_carga(CODIGO, HUELLA), reloj=10_000)
    falsa = _evaluar(
        respuesta=_respuesta(_carga(CODIGO, HUELLA, emitido=20_000, expira=20_180), firma_ok=False),
        error_red=False,
        guardada=guardada,
        ahora=10_100,
    )
    assert falsa.permitir and falsa.motivo == "gracia"
    assert falsa.concesion_nueva["reloj_validacion"] == 10_000

    caducada = _evaluar(
        respuesta=_respuesta(_carga(CODIGO, HUELLA, emitido=1_000, expira=1_180)),
        error_red=False,
        guardada=guardada,
        ahora=10_100,
    )
    assert caducada.motivo == "gracia"
    assert caducada.concesion_nueva["reloj_validacion"] == 10_000


def test_la_gracia_local_solo_acorta_la_firmada():
    guardada = _guardada(_carga(CODIGO, HUELLA, gracia_horas=24), reloj=10_000)
    corta = _evaluar(guardada=guardada, ahora=10_000 + 2 * 3600, gracia_local_s=3600)
    assert not corta.permitir
    larga = _evaluar(guardada=guardada, ahora=10_000 + 2 * 3600, gracia_local_s=48 * 3600)
    assert larga.permitir


def test_otro_equipo_y_sesion_desconocida():
    ajena = _carga(
        CODIGO, HUELLA, ok=False, motivo="otro_equipo", estado="otro_equipo", emitido=5_000, expira=5_180
    )
    decision = _evaluar(respuesta=_respuesta(ajena), error_red=False, ahora=5_000, aplicar_borrado=False)
    assert decision.motivo == "otro_equipo" and not decision.borrar_codigo
    perdida = _carga(
        CODIGO,
        HUELLA,
        ok=False,
        motivo="sesion_desconocida",
        estado="activa",
        accion="latido",
        emitido=5_000,
        expira=5_180,
        sesion="",
    )
    decision = _evaluar(
        respuesta=_respuesta(perdida),
        error_red=False,
        ahora=5_000,
        accion_esperada="latido",
    )
    assert decision.reactivar and not decision.permitir


class ServidorFalso:
    def __init__(self):
        self.privada = Ed25519PrivateKey.generate()
        self.publica = self.privada.public_key().public_bytes(
            encoding=Encoding.Raw, format=PublicFormat.Raw
        )
        self.personas = {}
        self.sesiones = {}
        self.contador = 0
        self.ahora = 1_700_000_000
        self.fallar = False
        self.corromper = False

    def dar(self, codigo, nombre="Ana"):
        self.personas[normalizar_codigo(codigo)] = {
            "nombre": nombre,
            "huella": None,
            "revocado": False,
        }

    def post(self, url, cuerpo, timeout=None):
        if self.fallar:
            raise ErrorDeRed("sin red")
        accion = url.rsplit("/", 1)[-1]
        if accion == "solicitud":
            return self._firmar(
                "solicitud",
                True,
                "enviada",
                "pendiente",
                "",
                cuerpo.get("huella") or "",
                str(cuerpo.get("nombre") or ""),
                "sol-1",
            )
        codigo = normalizar_codigo(cuerpo.get("codigo", "")) or ""
        huella = cuerpo.get("huella") or ""
        persona = self.personas.get(codigo)
        if not persona:
            return self._firmar(accion, False, "desconocido", "desconocida", codigo, huella, "", "")
        if persona["revocado"]:
            return self._firmar(accion, False, "revocado", "revocada", codigo, huella, persona["nombre"], "")
        if persona["huella"] and persona["huella"] != huella:
            return self._firmar(accion, False, "otro_equipo", "otro_equipo", codigo, huella, persona["nombre"], "")
        if accion == "estado":
            if persona["huella"]:
                return self._firmar(accion, True, "ok", "activa", codigo, huella, persona["nombre"], "")
            return self._firmar(accion, True, "sin_vincular", "sin_vincular", codigo, huella, persona["nombre"], "")
        if accion == "latido":
            sesion = cuerpo.get("sesion") or ""
            if self.sesiones.get(sesion) != codigo:
                return self._firmar(
                    accion, False, "sesion_desconocida", "activa", codigo, huella, persona["nombre"], ""
                )
            return self._firmar(accion, True, "ok", "activa", codigo, huella, persona["nombre"], sesion)
        if accion == "cerrar":
            self.sesiones.pop(cuerpo.get("sesion") or "", None)
            return self._firmar(
                accion, True, "ok", "cerrada", codigo, huella, persona["nombre"], cuerpo.get("sesion") or ""
            )
        persona["huella"] = huella
        self.contador += 1
        sesion = f"sesion-{self.contador}"
        self.sesiones[sesion] = codigo
        return self._firmar(accion, True, "ok", "activa", codigo, huella, persona["nombre"], sesion)

    def _firmar(self, accion, ok, motivo, estado, codigo, huella, persona, sesion):
        carga = {
            "v": 1,
            "accion": accion,
            "ok": ok,
            "motivo": motivo,
            "mensaje": "",
            "persona": persona,
            "codigo_hash": hash_codigo(codigo) if codigo else "",
            "huella": huella,
            "sesion": sesion,
            "estado": estado,
            "emitido": self.ahora,
            "expira": self.ahora + 180,
            "latido_segundos": 60,
            "gracia_horas": 24,
        }
        if self.corromper:
            carga["persona"] = persona + " "
        firma = base64.b64encode(self.privada.sign(canonico(carga).encode("utf-8"))).decode("ascii")
        if self.corromper:
            carga["persona"] = persona
        return 200, {"carga": carga, "firma": firma}


def _gestor(tmp_path, servidor, marca):
    config = ConfiguracionLocal(tmp_path)
    cliente = ClienteLicencia("https://licencias.test", servidor.publica, servidor)
    gestor = GestorLicencia(
        config,
        generar_claves(),
        cliente,
        HUELLA,
        "PC-CASA",
        reloj=lambda: marca["t"],
    )
    gestor.aceptar_aviso()
    return gestor


def test_guarda_el_codigo_cifrado_y_la_revocacion_lo_borra(tmp_path):
    servidor = ServidorFalso()
    servidor.dar(CODIGO, "Ana")
    marca = {"t": float(servidor.ahora)}
    gestor = _gestor(tmp_path, servidor, marca)
    decision = gestor.probar_codigo("drako aaaa bbbb cccc dddd")
    assert isinstance(decision, DecisionAcceso)
    assert decision.permitir
    crudo = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert CODIGO not in crudo
    assert "Ana" not in crudo
    assert gestor.leer_codigo() == CODIGO
    assert gestor.sesion_id == "sesion-1"

    servidor.personas[CODIGO]["revocado"] = True
    marca["t"] = float(servidor.ahora)
    bloqueo = gestor.comprobar_arranque()
    assert not bloqueo.permitir and bloqueo.motivo == "revocado"
    assert gestor.leer_codigo() is None


def test_la_primera_vez_sin_red_no_entra_y_luego_la_gracia_si(tmp_path):
    servidor = ServidorFalso()
    servidor.dar(CODIGO)
    marca = {"t": float(servidor.ahora)}
    gestor = _gestor(tmp_path, servidor, marca)
    servidor.fallar = True
    assert not gestor.probar_codigo(CODIGO).permitir
    assert gestor.leer_codigo() is None

    servidor.fallar = False
    assert gestor.probar_codigo(CODIGO).permitir
    servidor.fallar = True
    marca["t"] += 3600
    gracia = gestor.comprobar_arranque()
    assert gracia.permitir and gracia.motivo == "gracia"
    marca["t"] += 24 * 3600
    assert not gestor.comprobar_arranque().permitir


def test_el_latido_reabre_la_sesion_si_el_servidor_ya_no_la_tiene(tmp_path):
    servidor = ServidorFalso()
    servidor.dar(CODIGO)
    marca = {"t": float(servidor.ahora)}
    gestor = _gestor(tmp_path, servidor, marca)
    gestor.probar_codigo(CODIGO)
    servidor.sesiones.clear()
    decision = gestor.comprobar_latido()
    assert decision.permitir
    assert gestor.sesion_id == "sesion-2"


def test_una_respuesta_corrupta_no_guarda_el_codigo(tmp_path):
    servidor = ServidorFalso()
    servidor.dar(CODIGO)
    servidor.corromper = True
    marca = {"t": float(servidor.ahora)}
    gestor = _gestor(tmp_path, servidor, marca)
    decision = gestor.probar_codigo(CODIGO)
    assert not decision.permitir
    assert decision.motivo == "firma_invalida"
    assert gestor.leer_codigo() is None


def test_la_solicitud_no_entrega_el_codigo_ni_lo_guarda(tmp_path):
    servidor = ServidorFalso()
    marca = {"t": float(servidor.ahora)}
    gestor = _gestor(tmp_path, servidor, marca)
    decision = gestor.enviar_solicitud("Ana García", "Sexta planta")
    assert decision.motivo == "enviada"
    assert "DRAKO-" not in decision.mensaje
    assert gestor.leer_codigo() is None


def test_sin_servidor_el_instalador_avisa_y_no_falla(monkeypatch, capsys):
    monkeypatch.setattr("app.drako.licencia_config.URL_SERVIDOR", "")
    monkeypatch.setattr("app.drako.licencia_config.CLAVE_PUBLICA_HEX", "")
    monkeypatch.delenv("DRAKO_CAM_LICENCIA_URL", raising=False)
    monkeypatch.delenv("DRAKO_CAM_LICENCIA_CLAVE_PUBLICA", raising=False)
    from app.drako.solicitud_instalador import main

    assert main(["--estado"]) == 10
    assert "Falta la configuración del servidor" in capsys.readouterr().out


def test_el_aviso_nombra_ip_uso_y_ubicacion_y_no_hay_secretos_en_el_repo():
    texto = " ".join(
        [textos.INTRO_AVISO, textos.CIERRE_AVISO, textos.CASILLA_AVISO]
        + [f"{titulo} {detalle}" for titulo, detalle in textos.PUNTOS_AVISO]
    )
    assert "IP" in texto
    assert "ubicación aproximada" in texto
    assert "consentimiento" in texto
    guia = (RAIZ / "server" / "README.md").read_text(encoding="utf-8")
    for obligatorio in (
        "npx wrangler secret put SIGNING_SEED",
        "npx wrangler secret put TELEGRAM_BOT_TOKEN",
        "npx wrangler secret put TELEGRAM_ADMIN_CHAT_ID",
        "npx wrangler secret put TELEGRAM_WEBHOOK_SECRET",
        "@BotFather",
        "Europe/Bucharest",
        "DRAKO_CAM_LICENCIA_URL",
        "/pendientes",
        "callback_query",
        "Aprobar",
    ):
        assert obligatorio in guia
    esquema = (RAIZ / "server" / "src" / "esquema.ts").read_text(encoding="utf-8")
    for nombre in ("0001_inicio.sql", "0002_solicitudes.sql"):
        sql = (RAIZ / "server" / "migrations" / nombre).read_text(encoding="utf-8").strip()
        assert sql in esquema
    toml = (RAIZ / "server" / "wrangler.toml").read_text(encoding="utf-8")
    assert "SIGNING_SEED =" not in toml
    assert "MODO_PRUEBA" not in toml
    sospechosos = []
    candidatos = list((RAIZ / "server" / "src").rglob("*.ts"))
    candidatos += [
        RAIZ / "server" / "wrangler.toml",
        RAIZ / "server" / "generar-claves.mjs",
        RAIZ / "server" / "README.md",
    ]
    candidatos += list((RAIZ / "app" / "drako").rglob("*.py"))
    for ruta in candidatos:
        contenido = ruta.read_text(encoding="utf-8", errors="ignore")
        if __import__("re").search(r"\d{6,}:[A-Za-z0-9_-]{20,}", contenido):
            sospechosos.append(str(ruta.relative_to(RAIZ)))
    assert sospechosos == []
