"""Cámara virtual propia: Unity Capture como «Drako Cam», OBS solo de respaldo."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.drako.rendimiento.camara_virtual import (
    CLSID_32,
    CLSID_64,
    NOMBRE_DRAKO,
    NOMBRE_UNITY,
    abrir_con_respaldo,
    hay_adornos_de_interfaz,
    mensaje_para_usuario,
    separar_vista_y_salida,
    ya_registrada,
)

RAIZ = Path(__file__).resolve().parents[3]
SHA256_64 = "72812f5363d8ecb45632253f8c8c888844b1b62e27616f3c8cc21064ccde25e5"
SHA256_32 = "aa3ebdf03dea7f3aab3dd7b724751f49ed71672256b57c6a19aa6809cabf30ba"


class _Camara:
    def __init__(self, device: str):
        self.device = device


class _Fotograma:
    def __init__(self, marca: str):
        self.marca = marca
        self.shape = (8, 8, 3)


def test_aunque_el_ajuste_diga_obs_primero_va_drako():
    llamadas = []

    def abrir(backend, device):
        llamadas.append((backend, device))
        if device != NOMBRE_DRAKO:
            raise RuntimeError("No camera registered with this name.")
        return _Camara(NOMBRE_DRAKO)

    resultado = abrir_con_respaldo(abrir, "obs", pausa=lambda _s: None)
    assert resultado.codigo == "drako"
    assert resultado.backend == "unitycapture"
    assert resultado.dispositivo == NOMBRE_DRAKO
    assert llamadas[0] == ("unitycapture", NOMBRE_DRAKO)
    assert mensaje_para_usuario("drako") is None


def test_obs_solo_si_unity_no_esta_y_sin_espera():
    def abrir(backend, device):
        if backend != "obs":
            raise RuntimeError("No camera registered. Did you install any camera?")
        return _Camara("OBS Virtual Camera")

    def pausa(_segundos):
        raise AssertionError("un fallo de «no está» no debe esperar")

    resultado = abrir_con_respaldo(abrir, "auto", pausa=pausa)
    assert resultado.codigo == "obs"
    texto = mensaje_para_usuario("obs")
    assert texto is not None
    assert "administrador" in texto
    assert "Drako Cam" in texto
    assert "OBS" in texto


def test_reintenta_una_vez_si_el_controlador_esta_ocupado():
    veces = {"n": 0}

    def abrir(backend, device):
        veces["n"] += 1
        if veces["n"] == 1:
            raise RuntimeError("device busy")
        return _Camara(device or NOMBRE_DRAKO)

    esperas = []
    resultado = abrir_con_respaldo(abrir, "auto", pausa=esperas.append)
    assert resultado.codigo == "drako"
    assert esperas == [0.4]
    assert veces["n"] == 2


def test_sin_ninguna_camara_el_mensaje_pide_admin():
    def abrir(backend, device):
        raise RuntimeError("not found")

    resultado = abrir_con_respaldo(abrir, "unitycapture", pausa=lambda _s: None)
    assert resultado.codigo == "ninguna"
    assert resultado.camara is None
    texto = mensaje_para_usuario("ninguna") or ""
    assert "Instalar.bat" in texto
    assert "administrador" in texto
    assert "OBS" in texto


def test_nombre_generico_de_unity_se_avisa():
    def abrir(backend, device):
        if device == NOMBRE_DRAKO:
            raise RuntimeError("No camera registered with this name.")
        if device == NOMBRE_UNITY:
            return _Camara(NOMBRE_UNITY)
        raise RuntimeError("No camera registered")

    resultado = abrir_con_respaldo(abrir, "auto", pausa=lambda _s: None)
    assert resultado.codigo == "unity"
    texto = mensaje_para_usuario("unity", resultado.dispositivo) or ""
    assert NOMBRE_UNITY in texto
    assert "Meet" in texto


def test_la_salida_no_es_la_vista_adornada():
    vista = _Fotograma("con recuadros")
    limpia = _Fotograma("cara con filtro")
    assert separar_vista_y_salida((vista, limpia)) == (vista, limpia)
    assert separar_vista_y_salida(limpia) == (limpia, limpia)
    assert not hay_adornos_de_interfaz({})
    assert not hay_adornos_de_interfaz({"ShowAllDetectedFacesBBoxToggle": False})
    assert hay_adornos_de_interfaz({"ShowLandmarksEnableToggle": True})
    assert hay_adornos_de_interfaz({}, comparar=True)


def test_no_se_da_por_registrada_si_la_dll_es_otra(tmp_path: Path):
    nuestra = tmp_path / "UnityCaptureFilter64.dll"
    otra = tmp_path / "otra.dll"
    nuestra.write_bytes(b"MZ")
    otra.write_bytes(b"MZ")
    assert ya_registrada(NOMBRE_DRAKO, str(nuestra), str(nuestra))
    assert not ya_registrada(NOMBRE_UNITY, str(nuestra), str(nuestra))
    assert not ya_registrada(NOMBRE_DRAKO, str(otra), str(nuestra))
    assert not ya_registrada("", "", "")


def test_el_filtro_es_el_binario_oficial_de_64_bits():
    ruta = RAIZ / "vendor" / "unitycapture" / "UnityCaptureFilter64.dll"
    datos = ruta.read_bytes()
    assert hashlib.sha256(datos).hexdigest() == SHA256_64
    assert datos[:2] == b"MZ"
    pe = int.from_bytes(datos[0x3C:0x40], "little")
    assert datos[pe : pe + 4] == b"PE\x00\x00"
    assert int.from_bytes(datos[pe + 4 : pe + 6], "little") == 0x8664
    licencia = (RAIZ / "vendor" / "unitycapture" / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in licencia
    assert "Bernhard Schelling" in licencia
    readme = (RAIZ / "vendor" / "unitycapture" / "README.md").read_text(encoding="utf-8")
    assert "Drako Cam" in readme
    assert "3ed54c325e0ad71afcf4f246c07e5e17b3d7f2d2" in readme


def test_el_instalador_usa_el_mismo_nombre_y_clsid():
    texto = (RAIZ / "scripts" / "camara_virtual.ps1").read_text(encoding="utf-8-sig")
    assert NOMBRE_DRAKO in texto
    assert CLSID_64 in texto
    assert CLSID_32 in texto
    assert '/i:UnityCaptureName="Drako Cam"' in texto
    assert "regsvr32" in texto
    assert "&&" not in texto
    assert "||" not in texto
    assert "No se duplica" in texto
    assert "Ejecutar como administrador" in texto
