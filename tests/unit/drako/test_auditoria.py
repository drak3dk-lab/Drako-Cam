"""Registro cifrado y firmado, y la sesión que lo alimenta."""

import json

from app.drako.arranque import activar_sesion
from app.drako.auditoria import (
    ErrorCifrado,
    FirmaInvalida,
    RegistroAuditoria,
    desenvolver_claves,
    generar_claves,
    obtener_claves,
)
from app.drako.clave import AlmacenClave
from app.drako.configuracion import ConfiguracionLocal
from app.drako.sesion import SesionUso, resumir_cara
from app.drako.telegram_cliente import ClienteTelegram, ErrorDeRed


class _Mudo:
    def __init__(self):
        self.textos = []

    def configurado(self):
        return True

    def avisar(self, texto):
        self.textos.append(texto)
        return "enviado"

    def iniciar_reintentos(self):
        return None


def test_el_archivo_no_contiene_el_texto_y_la_firma_detecta_cambios(tmp_path):
    claves = generar_claves()
    registro = RegistroAuditoria(tmp_path / "auditoria.log", claves)
    secreto = "CARA-SECRETA-NO-DEBE-VERSE"
    registro.registrar(
        {
            "tipo": "cara_usada",
            "equipo": "EQUIPO-X",
            "cara_nombre": secreto,
            "cara_hash": "abc",
        }
    )
    crudo = (tmp_path / "auditoria.log").read_text(encoding="utf-8")
    assert secreto not in crudo
    assert "EQUIPO-X" not in crudo
    eventos = registro.leer()
    assert eventos[0]["cara_nombre"] == secreto

    sobre = json.loads(crudo)
    ct = sobre["ct"]
    # Cambia un carácter hexadecimal sin tocar la firma.
    invertido = ("0" if ct[0] != "0" else "1") + ct[1:]
    sobre["ct"] = invertido
    (tmp_path / "auditoria.log").write_text(json.dumps(sobre) + "\n", encoding="utf-8")
    try:
        registro.leer()
        raise AssertionError("una línea alterada no debe leerse")
    except FirmaInvalida:
        pass


def test_claves_envueltas_no_se_abren_con_otra_contrasena(tmp_path):
    config = ConfiguracionLocal(tmp_path)
    obtener_claves(config, "claveadmin")
    texto = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "claveadmin" not in texto
    try:
        desenvolver_claves(config.datos["audit_keys"], "otra-clave-distinta")
        raise AssertionError("la otra contraseña no debe abrir las claves")
    except ErrorCifrado:
        pass
    assert obtener_claves(config, "claveadmin").cifrado


def test_sesion_cifra_fallos_apertura_cara_y_cierre(tmp_path):
    marca = {"t": 10_000.0}

    def reloj():
        return marca["t"]

    config = ConfiguracionLocal(tmp_path)
    almacen = AlmacenClave(config, reloj=reloj, equipo=lambda: "EQUIPO-X")
    assert almacen.fijar_inicial("claveadmin", "claveadmin").ok
    assert not almacen.verificar("no-vale").ok
    assert not almacen.verificar("tampoco").ok
    entrada = almacen.verificar("claveadmin")
    assert entrada.ok
    assert len(entrada.pendientes) == 2

    claves = obtener_claves(config, "claveadmin")
    telegram = _Mudo()
    registro = RegistroAuditoria(tmp_path / "auditoria.log", claves)
    sesion = SesionUso(registro, telegram, equipo="EQUIPO-X", reloj=reloj)
    sesion.volcar_pendientes(entrada.pendientes)
    sesion.abrir()
    marca["t"] = 10_012.5
    nombre, huella = resumir_cara("C:/Usuarios/Drako/Cara Demo.png", {"m": b"embedding"})
    assert nombre == "Cara Demo.png"
    assert "embedding" not in huella
    sesion.registrar_cara(nombre, huella)
    sesion.cerrar()
    sesion.cerrar()

    crudo = (tmp_path / "auditoria.log").read_text(encoding="utf-8")
    assert "EQUIPO-X" not in crudo
    assert "Cara Demo" not in crudo
    assert b"embedding".decode() not in crudo
    eventos = registro.leer()
    assert [evento["tipo"] for evento in eventos] == [
        "intento_fallido",
        "intento_fallido",
        "apertura",
        "cara_usada",
        "cierre",
    ]
    assert eventos[-1]["duracion_segundos"] == 12.5
    assert eventos[-2]["cara_hash"] == huella
    assert len(huella) == 64
    # Los fallos ya se avisaron al ocurrir; al volcarlos no se repite el aviso.
    assert [texto for texto in telegram.textos if "apertura" in texto]
    assert not any("intento_fallido" in texto for texto in telegram.textos)


def test_activar_sesion_no_exige_telegram(tmp_path):
    from types import SimpleNamespace

    config = ConfiguracionLocal(tmp_path)
    almacen = AlmacenClave(config, equipo=lambda: "PC")
    almacen.fijar_inicial("claveadmin", "claveadmin")
    telegram = ClienteTelegram("", "", _SinRed(), tmp_path / "cola.json")
    contexto = SimpleNamespace(directorio=tmp_path, config=config, telegram=telegram)
    del almacen
    sesion, _claves = activar_sesion(contexto, "claveadmin", [])
    sesion.cerrar()
    assert telegram.avisar("hola") == "omitido"
    assert not (tmp_path / "cola.json").exists()


class _SinRed:
    def enviar(self, token, chat_id, texto):
        raise ErrorDeRed("sin red")
