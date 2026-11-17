"""El manifiesto detecta un archivo cambiado y no exige nada en el código fuente."""

import json
from pathlib import Path

from app.drako.integridad import escribir_manifiesto, verificar_instalacion


def test_sin_manifiesto_el_codigo_fuente_sigue(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    ok, aviso = verificar_instalacion(tmp_path)
    assert ok
    assert aviso == ""


def test_un_archivo_cambiado_no_pasa(tmp_path: Path):
    (tmp_path / "main.py").write_text("original\n", encoding="utf-8")
    escribir_manifiesto(tmp_path, ["main.py"])
    (tmp_path / "main.py").write_text("tocado\n", encoding="utf-8")
    ok, aviso = verificar_instalacion(tmp_path)
    assert not ok
    assert "modificado" in aviso


def test_el_manifiesto_no_acepta_rutas_que_salen_de_la_carpeta(tmp_path: Path):
    (tmp_path / "integridad_manifiesto.json").write_text(
        json.dumps({"v": 1, "archivos": {"../secreto.txt": "ab" * 32}}),
        encoding="utf-8",
    )
    ok, aviso = verificar_instalacion(tmp_path)
    assert not ok
    assert aviso
