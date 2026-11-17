"""La galería no duplica fotos y puede borrarlas o renombrarlas."""

from pathlib import Path

from app.ui.estudio.biblioteca import Biblioteca


def _foto(carpeta: Path, nombre: str, contenido: bytes) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre
    ruta.write_bytes(contenido)
    return ruta


def test_no_duplica_el_mismo_archivo(tmp_path):
    origen = tmp_path / "fuera"
    primera = _foto(origen, "elizabeth carter.png", b"misma-cara")
    biblioteca = Biblioteca(tmp_path / "datos")
    una = biblioteca.anadir(primera)
    otra = biblioteca.anadir(_foto(origen, "elizabeth carter-2.png", b"misma-cara"))
    assert una.id == otra.id
    assert len(biblioteca.listar()) == 1
    assert not (biblioteca.carpeta / "elizabeth carter-2.png").exists()


def test_borrar_quita_el_archivo_y_el_estado(tmp_path):
    biblioteca = Biblioteca(tmp_path / "datos")
    foto = biblioteca.anadir(_foto(tmp_path / "fuera", "ana.png", b"ana"))
    biblioteca.recordar(ultima_cara=foto.id)
    biblioteca.fijar_favorita(foto.id, True)
    biblioteca.guardar_ajustes(foto.id, {"boca": 40})
    biblioteca.borrar(foto.id)
    assert biblioteca.listar() == []
    assert not foto.ruta.exists()
    estado = biblioteca.estado()
    assert estado["ultima_cara"] == ""
    assert foto.id not in (estado.get("favoritas") or [])
    assert foto.id not in (estado.get("ajustes") or {})


def test_renombrar_actualiza_el_archivo_y_la_cara_activa(tmp_path):
    biblioteca = Biblioteca(tmp_path / "datos")
    foto = biblioteca.anadir(_foto(tmp_path / "fuera", "19_13355.png", b"cara"))
    biblioteca.recordar(ultima_cara=foto.id)
    nueva = biblioteca.renombrar(foto.id, "Elena")
    assert nueva.nombre == "Elena"
    assert nueva.ruta.is_file()
    assert not foto.ruta.exists()
    assert biblioteca.estado()["ultima_cara"] == nueva.id
