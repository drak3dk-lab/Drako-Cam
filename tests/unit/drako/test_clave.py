"""Contraseña de administrador: Argon2id, cambio y bloqueo."""

import json

from app.drako.clave import UMBRAL_INTENTOS, AlmacenClave
from app.drako.configuracion import ConfiguracionLocal


def _reloj(marca):
    return lambda: marca["t"]


def _almacen(tmp_path, marca=None):
    config = ConfiguracionLocal(tmp_path)
    return AlmacenClave(
        config,
        reloj=_reloj(marca or {"t": 1_000.0}),
        equipo=lambda: "PC-PRUEBA",
    )


def test_primera_clave_es_argon2id_y_no_queda_en_claro(tmp_path):
    marca = {"t": 1_000.0}
    almacen = _almacen(tmp_path, marca)
    assert not almacen.esta_configurada()
    resultado = almacen.fijar_inicial("claveadmin", "claveadmin")
    assert resultado.ok
    assert almacen.hash_publico().startswith("$argon2id$")
    texto = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "claveadmin" not in texto
    assert almacen.verificar("claveadmin").ok
    assert not almacen.verificar("otra-clave").ok


def test_rechaza_clave_corta_y_confirmacion_distinta(tmp_path):
    almacen = _almacen(tmp_path)
    corta = almacen.fijar_inicial("corta", "corta")
    assert not corta.ok and corta.motivo == "debil"
    distinta = almacen.fijar_inicial("claveadmin", "clave-otra")
    assert not distinta.ok and distinta.motivo == "no_coincide"
    assert not almacen.esta_configurada()


def test_no_se_puede_fijar_dos_veces(tmp_path):
    almacen = _almacen(tmp_path)
    assert almacen.fijar_inicial("claveadmin", "claveadmin").ok
    otra = almacen.fijar_inicial("otrasclave", "otrasclave")
    assert not otra.ok and otra.motivo == "ya_configurada"
    assert almacen.verificar("claveadmin").ok


def test_cambiar_exige_la_actual(tmp_path):
    almacen = _almacen(tmp_path)
    almacen.fijar_inicial("claveadmin", "claveadmin")
    mal = almacen.cambiar("no-es-esta", "clave-nueva", "clave-nueva")
    assert not mal.ok and mal.motivo == "incorrecta"
    assert almacen.verificar("claveadmin").ok
    bien = almacen.cambiar("claveadmin", "clave-nueva", "clave-nueva")
    assert bien.ok
    assert almacen.verificar("clave-nueva").ok
    assert not almacen.verificar("claveadmin").ok
    texto = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "clave-nueva" not in texto
    assert "claveadmin" not in texto


def test_bloqueo_temporal_y_despues_deja_entrar(tmp_path):
    marca = {"t": 5_000.0}
    almacen = _almacen(tmp_path, marca)
    almacen.fijar_inicial("claveadmin", "claveadmin")
    for _ in range(UMBRAL_INTENTOS - 1):
        resultado = almacen.verificar("mala-clave")
        assert resultado.motivo == "incorrecta"
        assert not almacen.esta_bloqueado()
    bloqueo = almacen.verificar("mala-clave")
    assert bloqueo.motivo == "bloqueada"
    assert bloqueo.segundos_bloqueo == 60
    assert almacen.esta_bloqueado()
    # Aunque ahora sea la correcta, el bloqueo se respeta.
    durante = almacen.verificar("claveadmin")
    assert not durante.ok and durante.motivo == "bloqueada"
    marca["t"] += 61
    assert not almacen.esta_bloqueado()
    assert almacen.verificar("claveadmin").ok
    datos = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert datos["auth"]["failed_attempts"] == 0
    assert datos["auth"]["pending_failures"] == []


def test_los_intentos_fallidos_no_guardan_la_clave_probada(tmp_path):
    almacen = _almacen(tmp_path)
    almacen.fijar_inicial("claveadmin", "claveadmin")
    almacen.verificar("secreto-probado")
    texto = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "secreto-probado" not in texto
    pendientes = json.loads(texto)["auth"]["pending_failures"]
    assert pendientes[0]["equipo"] == "PC-PRUEBA"
    assert pendientes[0]["tipo"] == "intento_fallido"
