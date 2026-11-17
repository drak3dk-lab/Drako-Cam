"""Aspecto y perfiles se guardan sin depender de la velocidad ni de la GPU."""

import json
from pathlib import Path

import numpy as np

from app.drako.perfiles.almacen import AlmacenPerfiles, migrar
from app.drako.perfiles.aspecto import (
    fraccion_barba,
    luminancia_piel,
    sugerir,
    valores_de_aspecto,
    valores_sugeridos,
)
from app.drako.perfiles.fader import mezclar, pasos
from app.drako.rutas import directorio_perfiles
from app.ui.estudio.controles import CLAVES_RENDIMIENTO, valores_de_calidad


def _png(ruta: Path) -> None:
    ruta.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\xef\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_el_aspecto_no_toca_la_velocidad():
    aspecto = valores_de_aspecto("mujer-oscura")
    assert "SwapperResSelection" not in aspecto
    assert "FaceRestorerEnableToggle" not in aspecto
    assert aspecto["HairParserSlider"] == 10
    assert aspecto["ColorBrightnessDecimalSlider"] == 1.06
    velocidad = {
        clave: valor
        for clave, valor in valores_de_calidad("Máximo FPS").items()
        if clave in CLAVES_RENDIMIENTO
    }
    assert "ColorBrightnessDecimalSlider" not in velocidad
    assert "HairParserSlider" not in velocidad
    assert velocidad["OccluderEnableToggle"] is False


def test_auto_junta_tono_y_barba_sin_adivinar_genero():
    ident, frase = sugerir(0.3, 0.2)
    assert ident == "barba-oscura"
    assert "barba" in frase
    ident, frase = sugerir(0.7, 0.0)
    assert ident == "auto-clara"
    assert "No veo barba" in frase
    mapa, _ = valores_sugeridos(0.3, 0.0)
    assert mapa["ColorBrightnessDecimalSlider"] == 1.06


def test_la_barba_es_pelo_en_la_mitad_baja():
    mapa = np.ones((20, 20), dtype=np.int32)
    mapa[12:18, 6:14] = 17
    assert fraccion_barba(mapa) > 0.1
    assert fraccion_barba(None) == 0.0
    rgb = np.zeros((20, 20, 3), dtype=np.uint8)
    rgb[mapa == 1] = 40
    assert luminancia_piel(rgb, mapa) < 0.3


def test_un_perfil_viejo_o_incompleto_se_abre():
    datos = migrar({"nombre": "Juanito", "ajustes": {"NoExiste": 1, "HairParserSlider": 9}})
    assert datos["esquema"] == 1
    assert datos["nombre"] == "Juanito"
    assert "NoExiste" in datos["ajustes"]
    filtrado = migrar(datos, {"HairParserSlider"})
    assert filtrado["ajustes"] == {"HairParserSlider": 9}
    assert filtrado["calidad"] == "Auto"


def test_guardar_cargar_exportar_e_importar(tmp_path: Path):
    foto = tmp_path / "juanito.png"
    _png(foto)
    almacen = AlmacenPerfiles(tmp_path / "perfiles")
    perfil = almacen.crear(
        "La cara de Juanito",
        {"HairParserSlider": 14, "AjusteQueYaNoEsta": True},
        "barba-oscura",
        "Equilibrado",
        [foto],
        [0.1, 0.2],
        {"HairParserSlider"},
    )
    cargado = almacen.cargar(perfil.id)
    assert cargado.nombre == "La cara de Juanito"
    assert cargado.ajustes == {"HairParserSlider": 14}
    assert cargado.fotos[0].is_file()
    assert cargado.embedding == [0.1, 0.2]
    copia = almacen.duplicar(perfil.id)
    assert copia.id != perfil.id
    almacen.favorito(perfil.id, True)
    assert almacen.listar()[0].favorito is True
    destino = tmp_path / "juanito.zip"
    almacen.exportar(perfil.id, destino)
    otro = AlmacenPerfiles(tmp_path / "otro")
    importado = otro.importar(destino, {"HairParserSlider"})
    assert importado.nombre == "La cara de Juanito"
    assert importado.fotos
    almacen.borrar(perfil.id)
    assert all(item.id != perfil.id for item in almacen.listar())


def test_el_fundido_no_es_un_corte():
    anterior = np.array([1.0, 0.0], dtype=np.float32)
    nuevo = np.array([0.0, 1.0], dtype=np.float32)
    medio = mezclar(anterior, nuevo, 0.5)
    assert abs(float(np.linalg.norm(medio)) - 1.0) < 1e-5
    assert medio[0] > 0 and medio[1] > 0
    assert np.allclose(mezclar(anterior, nuevo, 0.0), anterior)
    assert np.allclose(mezclar(anterior, nuevo, 1.0), nuevo)
    assert pasos(3) == [0.0, 0.5, 1.0]


def test_la_carpeta_de_perfiles_cuelga_de_los_datos(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DRAKO_CAM_DATA_DIR", str(tmp_path))
    assert directorio_perfiles() == tmp_path / "perfiles"
