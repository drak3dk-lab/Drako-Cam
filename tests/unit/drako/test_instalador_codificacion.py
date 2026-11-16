"""El instalador se lee como UTF-8 para que los acentos no salgan rotos."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
BOM = b"\xef\xbb\xbf"


def test_los_textos_del_instalador_llevan_bom_utf8():
    for relativo in (
        "Instalar.bat",
        "Desinstalar.bat",
        "scripts/instalar.ps1",
        "scripts/desinstalar.ps1",
        "scripts/instalador_ventana.ps1",
    ):
        datos = (RAIZ / relativo).read_bytes()
        assert datos.startswith(BOM), relativo
        assert b"\xc3\xb3" in datos or b"\xc3\xa1" in datos or b"\xc3\xa9" in datos


def test_el_bat_cambia_la_consola_a_utf8():
    texto = (RAIZ / "Instalar.bat").read_text(encoding="utf-8-sig")
    assert "chcp 65001" in texto
    assert "instalación" in texto
