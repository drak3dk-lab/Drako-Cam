"""El instalador se lee como UTF-8 para que los acentos no salgan rotos."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
BOM = b"\xef\xbb\xbf"


def test_los_textos_del_instalador_llevan_bom_utf8():
    for relativo in (
        "scripts/instalar.ps1",
        "scripts/desinstalar.ps1",
        "scripts/instalador_ventana.ps1",
    ):
        datos = (RAIZ / relativo).read_bytes()
        assert datos.startswith(BOM), relativo
        assert b"\xc3\xb3" in datos or b"\xc3\xa1" in datos or b"\xc3\xa9" in datos


def test_los_bat_no_llevan_bom_para_que_echo_off_valga():
    """cmd no reconoce @echo off si el archivo empieza por la marca UTF-8."""
    for relativo in ("Instalar.bat", "Desinstalar.bat"):
        datos = (RAIZ / relativo).read_bytes()
        assert not datos.startswith(BOM), relativo
        assert datos.startswith(b"@echo off\r\n"), relativo
        assert b"\necho on" not in datos.lower()
        assert b"\n" not in datos.replace(b"\r\n", b"")
        assert b"chcp 65001" in datos
        assert b"\xc3\xb3" in datos or b"\xc3\xa1" in datos
        assert datos.count(b"@echo off") >= 2


def test_el_bat_cambia_la_consola_a_utf8():
    texto = (RAIZ / "Instalar.bat").read_text(encoding="utf-8")
    assert "chcp 65001" in texto
    assert "instalación" in texto
    assert texto.startswith("@echo off")
