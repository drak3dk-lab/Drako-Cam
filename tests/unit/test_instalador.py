"""Comprueba los scripts del instalador de un clic sin necesidad de Windows."""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _texto(relativo: str) -> str:
    return (RAIZ / relativo).read_text(encoding="utf-8")


def _bytes(relativo: str) -> bytes:
    return (RAIZ / relativo).read_bytes()


def test_bats_llaman_a_powershell_solo_para_ese_proceso():
    for nombre in ("Instalar.bat", "Desinstalar.bat"):
        texto = _texto(nombre)
        assert "ExecutionPolicy Bypass" in texto
        assert "Set-ExecutionPolicy" not in texto
        assert r'cd /d "%~dp0"' in texto
        assert '-File "%~dp0scripts\\' in texto
        assert "pause >nul" in texto
        assert "Press any key" not in texto
        assert "SystemRoot" in texto
        assert "powershell.exe" in texto.lower()


def test_powershell_es_utf8_con_bom_y_sin_sintaxis_de_la_version_7():
    for nombre in ("scripts/instalar.ps1", "scripts/desinstalar.ps1"):
        datos = _bytes(nombre)
        assert datos.startswith(b"\xef\xbb\xbf"), nombre
        texto = datos.decode("utf-8-sig")
        assert "??" not in texto
        assert "&&" not in texto
        assert "||" not in texto
        assert "#Requires -Version 5.1" in texto
        _llaves_equilibradas(texto, nombre)


def test_instalar_cubre_lo_que_drako_necesita():
    texto = _texto("scripts/instalar.ps1")
    for fragmento in (
        "Python 3.12",
        "7.1.1",
        "Gyan.FFmpeg",
        "requirements_cu13.txt",
        "Drako Cam.lnk",
        "pythonw.exe",
        "main.py",
        "comprobar_cuda.py",
        "No se pudo terminar la instalación",
        "winget no está",
        "https://astral.sh/uv/install.ps1",
        "irm https://astral.sh/uv/install.ps1 | iex",
        "-ExecutionPolicy",
        "Bypass",
        ".local",
        "tensorrt-cu13",
        "Microsoft Store",
        "Lo reutilizo",
        "solicitud_instalador",
        "--contacto",
        "Nombre de la persona",
        "Nombre de la oficina donde se instala",
        "Falta la configuración del servidor de acceso",
        "La instalación ha terminado igual",
        "GpuPreference=2",
        "Fijar-GpuDedicada",
        "NvOptimusEnablement",
    ):
        assert fragmento in texto
    assert 'Join-Path $env:APPDATA "DrakoCam"' not in texto
    assert "Scripts\\activate" not in texto
    assert "Activate.ps1" not in texto
    assert "Set-ExecutionPolicy" not in texto


def test_desinstalar_no_borra_appdata_sin_confirmacion():
    texto = _texto("scripts/desinstalar.ps1")
    assert 'Join-Path $env:APPDATA "DrakoCam"' in texto
    assert "BorrarDatos" in texto
    assert "Confirma" in texto
    assert "Drako Cam.lnk" in texto
    assert ".venv" in texto
    assert "No se ha borrado nada." in texto
    assert "Quitar-PreferenciaGpu" in texto
    assert "GpuPreference" in texto


def test_arrancar_vbs_es_ascii_y_no_abre_consola():
    datos = _bytes("scripts/Arrancar.vbs")
    assert all(byte < 128 for byte in datos)
    texto = datos.decode("ascii")
    assert "--comprobar" in texto
    assert "pythonw.exe" in texto
    assert "main.py" in texto
    assert "ffmpeg-7.1.1-essentials_build" in texto
    assert "ChrW(243)" in texto
    assert "ChrW(225)" in texto
    assert ", 0, True" not in texto


def test_inno_copia_la_app_y_reutiliza_instalar_bat():
    datos = _bytes("installer/DrakoCam.iss")
    assert datos.startswith(b"\xef\xbb\xbf")
    texto = datos.decode("utf-8-sig")
    for info in ("installer/info-antes.txt", "installer/info-despues.txt"):
        assert _bytes(info).startswith(b"\xef\xbb\xbf")
    assert "PrivilegesRequired=lowest" in texto
    assert "Spanish.isl" in texto
    assert "Instalar.bat" in texto
    assert "-DesdeInstalador" in texto
    assert "desinstalar.ps1" in texto
    assert "-Silencioso" in texto
    assert "*.onnx" in texto
    assert "*.pth" in texto
    assert "*.safetensors" in texto
    assert "Drako Cam" in texto
    assert "{localappdata}\\Drako Cam" in texto
    assert "GpuPreference=2;" in texto
    assert "UserGpuPreferences" in texto
    for requerido in (
        "main.py",
        "download_models.py",
        "requirements_cu13.txt",
        "pyproject.toml",
        "version.json",
        "scripts\\*",
        "app\\*",
    ):
        assert requerido in texto


def test_workflow_compila_en_windows_y_solo_publica_con_etiqueta():
    texto = _texto(".github/workflows/instalador-windows.yml")
    assert "windows-latest" in texto
    assert '- "v*"' in texto
    assert "innosetup-6.7.4.exe" in texto
    assert "startsWith(github.ref, 'refs/tags/v')" in texto
    assert "gh release create" in texto
    assert "SoloComprobar" in texto
    assert "ExecutionPolicy Bypass" in texto
    assert "secrets." not in texto


def test_readme_explica_la_instalacion_facil():
    texto = _texto("README.md")
    assert "## Instalación fácil" in texto
    assert "Instalar.bat" in texto
    assert "Desinstalar.bat" in texto
    assert "DrakoCam-Setup" in texto
    assert "%APPDATA%\\DrakoCam" in texto
    assert "Instalador de un clic" not in texto


def test_comprobar_cuda_tiene_sintaxis_valida_y_codigos_claros():
    ruta = RAIZ / "scripts" / "comprobar_cuda.py"
    fuente = ruta.read_text(encoding="utf-8")
    ast.parse(fuente)
    assert "CUDA visible: no" in fuente
    assert "CUDA visible: sí" in fuente
    assert "return 2" in fuente
    assert "return 1" in fuente
    assert "return 0" in fuente


def test_start_bat_usa_el_python_del_entorno():
    texto = _texto("Start.bat")
    assert "ffmpeg-7.1.1-essentials_build\\bin" in texto
    assert 'set "PATH=' in texto
    assert '"%~dp0.venv\\Scripts\\python.exe"' in texto
    assert '"%~dp0main.py"' in texto
    assert "activate" not in texto.lower()


def _llaves_equilibradas(texto: str, nombre: str) -> None:
    profundidad = 0
    estado = "codigo"
    i = 0
    while i < len(texto):
        caracter = texto[i]
        if estado == "codigo":
            if caracter == "#":
                estado = "comentario"
            elif caracter == "'":
                estado = "simple"
            elif caracter == '"':
                estado = "doble"
            elif caracter == "{":
                profundidad += 1
            elif caracter == "}":
                profundidad -= 1
                assert profundidad >= 0, nombre
        elif estado == "comentario":
            if caracter == "\n":
                estado = "codigo"
        elif estado == "simple":
            if caracter == "'":
                if i + 1 < len(texto) and texto[i + 1] == "'":
                    i += 1
                else:
                    estado = "codigo"
        elif estado == "doble":
            if caracter == "`" and i + 1 < len(texto):
                i += 1
            elif caracter == '"':
                estado = "codigo"
        i += 1
    assert estado == "codigo", nombre
    assert profundidad == 0, nombre
