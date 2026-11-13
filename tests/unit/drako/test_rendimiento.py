"""Perfiles, colas, TensorRT, seguimiento y recuperación. Sin GPU."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.drako.rendimiento.benchmark import (
    CronometroEnVivo,
    medir_sobrecarga,
    recomendar,
)
from app.drako.rendimiento.buffers import AnilloAnfitrion
from app.drako.rendimiento.camara_virtual import ConfiguracionSalida, PreparadorSalida
from app.drako.rendimiento.colas import ColaLatencia, poner_descartando, soltar_tarea
from app.drako.rendimiento.deteccion import PoliticaDeteccion, RastreadorRostros
from app.drako.rendimiento.dgpu import (
    Dispositivo,
    aviso_gpu_integrada,
    elegir_indice,
    es_integrada,
    preferir_gpu_dedicada,
)
from app.drako.rendimiento.emision import aplicar_modo, debe_omitir_preview
from app.drako.rendimiento.estado import copia_estado
from app.drako.rendimiento.perfiles import (
    PERFIL_6GB,
    PERFIL_8GB,
    PERFIL_ALTO,
    acciones_de_modelos,
    fraccion_vram,
    perfil_por_hardware,
    escribir_perfil,
    resolver_perfil,
)
from app.drako.rendimiento.tensorrt import (
    MOTIVO_FP8_INT8,
    bytes_workspace,
    clave_cache,
    precision_fp16,
    quitar_tensorrt,
    ruta_cache,
    sirve_tensorrt,
)
from app.drako.rendimiento.watchdog import Vigilante
import main as entrada


def test_one_euro_sigue_la_cabeza_cuando_se_mueve():
    from app.drako.rendimiento.one_euro import alpha_por_velocidad

    quieto = alpha_por_velocidad(0, ajuste=25)
    movido = alpha_por_velocidad(30, ajuste=25)
    assert quieto < 0.5
    assert movido > 0.75
    assert movido > quieto


def test_perfiles_por_gpu():
    assert (
        perfil_por_hardware("NVIDIA GeForce RTX 4050 Laptop GPU", 6 * 1024**3).id
        == PERFIL_6GB.id
    )
    assert (
        perfil_por_hardware("NVIDIA GeForce RTX 5060", 8 * 1024**3).id == PERFIL_8GB.id
    )
    assert (
        perfil_por_hardware("NVIDIA GeForce RTX 5060 Ti", 16 * 1024**3).id
        == PERFIL_ALTO.id
    )
    assert (
        perfil_por_hardware("NVIDIA GeForce RTX 5070", 12 * 1024**3).id
        == PERFIL_ALTO.id
    )
    assert (
        perfil_por_hardware("NVIDIA GeForce RTX 5080", 16 * 1024**3).id
        == PERFIL_ALTO.id
    )
    assert perfil_por_hardware("", 0).id == PERFIL_8GB.id
    assert PERFIL_ALTO.permite_60 and PERFIL_ALTO.resolucion == "1920x1080"
    assert PERFIL_8GB.fps == 30 and not PERFIL_8GB.permite_60
    assert PERFIL_6GB.resolucion == "1280x720" and PERFIL_6GB.tope_gb == 4.5
    assert PERFIL_6GB.deteccion_cada == 2
    assert PERFIL_8GB.resolucion == "1280x720"
    from app.drako.rendimiento.perfiles import con_captura

    rtx = con_captura(PERFIL_8GB, "NVIDIA GeForce RTX 5060", 8 * 1024**3)
    assert rtx.resolucion == "1920x1080"
    portatil = con_captura(PERFIL_6GB, "NVIDIA GeForce RTX 4050 Laptop GPU", 6 * 1024**3)
    assert portatil.resolucion == "1280x720"
    assert PERFIL_ALTO.mejoradores_pesados and not PERFIL_6GB.mejoradores_pesados


def test_auto_respeta_una_resolucion_elegida_a_mano():
    control = {
        "PerfilVramSelection": "Auto",
        "WebcamMaxResSelection": "2560x1440",
        "WebCamMaxFPSSelection": "30",
    }
    perfil = resolver_perfil(control, "NVIDIA GeForce RTX 5070", 12 * 1024**3)
    assert perfil.id == PERFIL_ALTO.id

    class Ventana:
        parameter_widgets: dict = {}

    ventana = Ventana()
    ventana.control = control
    escribir_perfil(ventana, perfil, forzar=True)
    # 1440p no es una resolución que escriba el perfil: no se pisa.
    assert control["WebcamMaxResSelection"] == "2560x1440"
    assert control["_PerfilAplicado"] == PERFIL_ALTO.id


def test_fraccion_de_vram_deja_margen():
    assert fraccion_vram(PERFIL_6GB, 6 * 1024**3) == 4.5 / 6
    assert fraccion_vram(PERFIL_8GB, 8 * 1024**3) < 0.9
    assert fraccion_vram(PERFIL_ALTO, 16 * 1024**3) == 0.85
    assert fraccion_vram(PERFIL_6GB, 0) is None


def test_mejoradores_pesados_solo_en_alto():
    control = {
        "FrameEnhancerEnableToggle": True,
        "FaceRestorerEnableToggle": True,
        "PermitirMejoradoresPesadosToggle": False,
        "MejoradoresPerezososEnableToggle": True,
        "UnSoloSwapperEnableToggle": True,
    }
    assert "quitar_enhancer_pesado" in acciones_de_modelos(control, PERFIL_8GB)
    control["PermitirMejoradoresPesadosToggle"] = True
    assert "conservar_enhancer" in acciones_de_modelos(control, PERFIL_ALTO)
    control["FrameEnhancerEnableToggle"] = False
    assert "descargar_enhancer_inactivo" in acciones_de_modelos(control, PERFIL_6GB)


def test_cola_de_latencia_tira_el_fotograma_viejo():
    cola = ColaLatencia(1)
    tirados = []
    cola.poner_fresco("a", al_descartar=lambda: tirados.append("a"))
    n = cola.poner_fresco("b", al_descartar=lambda: tirados.append("x"))
    assert n == 1 and tirados == ["x"]
    assert cola.tomar(0.1) == "b"
    assert cola.tomar(0.01) is None
    assert len(cola) == 0


def test_poner_descartando_suelta_la_reserva():
    import queue

    sueltos = []
    cola = queue.Queue(maxsize=1)
    vieja = (
        0,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        {"liberar": lambda: sueltos.append("vieja")},
    )
    nueva = (
        1,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        {"liberar": lambda: sueltos.append("nueva")},
    )
    assert poner_descartando(cola, vieja)
    assert poner_descartando(cola, nueva)
    assert sueltos == ["vieja"]
    assert cola.get_nowait()[0] == 1
    soltar_tarea(nueva)
    assert sueltos == ["vieja", "nueva"]


def test_deteccion_sigue_y_redetecta_si_se_sale():
    politica = PoliticaDeteccion(cada_n=3)
    rastreador = RastreadorRostros(max_sin_correccion=4)
    assert politica.debe_detectar(rastreador.perdido())
    caja = np.array([[10, 10, 40, 50]], np.float32)
    kps = np.zeros((1, 5, 2), np.float32)
    kps[0, 0] = (20, 20)
    rastreador.corregir(caja, kps, kps, kps, 100, 100)
    politica.anotar(True)
    assert not politica.debe_detectar(rastreador.perdido())
    rastreador.pistas[0].vx = 30
    rastreador.predecir()
    # Sigue dentro.
    assert not rastreador.perdido()
    for _ in range(5):
        rastreador.predecir()
    assert rastreador.perdido()
    bboxes, *_ = rastreador.empaquetar()
    assert bboxes.shape[1] == 4


def test_anillo_no_reserva_en_el_segundo_fotograma():
    anillo = AnilloAnfitrion(2)
    frame = np.zeros((8, 8, 3), np.uint8)
    primero = anillo.copiar(frame)
    reservas = anillo.reservas
    segundo = anillo.copiar(frame)
    assert anillo.reservas == reservas
    assert primero is not segundo
    assert anillo.copiar(frame) is primero


def test_salida_obs_bloquea_tamano_y_fondo():
    cfg = ConfiguracionSalida.desde_control(
        {
            "WebcamMaxResSelection": "1920x1080",
            "WebCamMaxFPSSelection": "30",
            "FondoVirtualSelection": "Verde",
        }
    )
    assert (cfg.ancho, cfg.alto, cfg.fps, cfg.formato) == (1920, 1080, 30, "bgr")
    prep = PreparadorSalida()
    frame = np.full((4, 4, 3), 10, np.uint8)
    caja = np.array([[1, 1, 2, 2]], np.float32)
    salida = prep.preparar(frame, cfg, caja)
    assert salida.shape == (1080, 1920, 3)
    # Esquina lejos de la cara: verde en BGR.
    assert tuple(salida[0, 0]) == (0, 255, 0)
    otra = prep.preparar(frame, cfg, caja)
    assert otra is salida
    cfg_alfa = ConfiguracionSalida.desde_control(
        {
            "WebcamMaxResSelection": "64x64",
            "WebCamMaxFPSSelection": "60",
            "FondoVirtualSelection": "Transparente",
        }
    )
    assert cfg_alfa.formato == "rgba" and cfg_alfa.fps == 60
    alfa = prep.preparar(frame, cfg_alfa, np.array([[20, 20, 40, 40]], np.float32))
    assert alfa.shape == (64, 64, 4)
    assert alfa[0, 0, 3] == 0
    assert alfa[30, 30, 3] == 255


def test_tensorrt_se_clavea_por_gpu_y_version(tmp_path):
    a = clave_cache("NVIDIA GeForce RTX 5070", (12, 0), "10.16.1.11")
    b = clave_cache("NVIDIA GeForce RTX 4050 Laptop GPU", (8, 9), "10.16.1.11")
    c = clave_cache("NVIDIA GeForce RTX 5070", (12, 0), "10.9.0")
    assert a != b and a != c
    assert "sm120" in a and "trt10.16.1.11" in a
    ruta = ruta_cache("RTX 5080", (12, 0), "10.16.1.11", base=tmp_path)
    assert ruta.parent.name == "tensorrt-engines"
    assert sirve_tensorrt("10.16.1.11", (12, 0))[0]
    ok, motivo = sirve_tensorrt("10.9.0", (12, 0))
    assert not ok and "Blackwell" in motivo
    assert not sirve_tensorrt(None, (12, 0))[0]
    assert bytes_workspace(6 * 1024**3) == 2 * 1024**3
    assert bytes_workspace(16 * 1024**3) == 3 * 1024**3
    fp16, aviso = precision_fp16("FP16", True)
    assert fp16 and aviso is None
    assert precision_fp16("FP32", True) == (False, None)
    activo, aviso_fp8 = precision_fp16("fp8", True)
    assert activo and aviso_fp8 == MOTIVO_FP8_INT8
    assert "INT8" in MOTIVO_FP8_INT8
    proveedores = [("TensorrtExecutionProvider", {}), ("CUDAExecutionProvider", {})]
    assert quitar_tensorrt(proveedores)[0][0] == "CUDAExecutionProvider"


def test_modo_emision_apaga_la_vista_previa():
    assert debe_omitir_preview({"ModoEmisionEnableToggle": True})
    assert not debe_omitir_preview({})
    resultado = aplicar_modo(False, sistema="posix")
    assert resultado["preview"] and resultado["activo"] is False


def test_elige_la_nvidia_y_avisa_si_es_integrada():
    dispositivos = [
        Dispositivo(0, "Intel UHD Graphics", 2 * 1024**3),
        Dispositivo(1, "NVIDIA GeForce RTX 5060", 8 * 1024**3),
    ]
    assert elegir_indice(dispositivos, 0) == 1
    assert elegir_indice(dispositivos, 1) == 1
    assert es_integrada("Intel Iris Xe")
    assert not es_integrada("NVIDIA GeForce RTX 5080")
    texto = aviso_gpu_integrada("Intel UHD Graphics")
    assert texto and "integrada" in texto
    assert aviso_gpu_integrada("NVIDIA GeForce RTX 5070") is None
    assert preferir_gpu_dedicada(["/tmp/python"]) == []


def test_vigilante_recupera_y_solo_al_final_pide_parar():
    v = Vigilante(
        ventana_s=10, max_errores=3, atasco_s=1, pausa_entre_recuperaciones_s=0
    )
    primera = v.error_cuda(0)
    assert not primera.detener and not primera.cambiar_proveedor
    v.error_cuda(1)
    tercera = v.error_cuda(2)
    assert not tercera.detener and tercera.cambiar_proveedor
    cuarta = v.error_cuda(3)
    assert cuarta.detener
    v.latido(0)
    assert v.atasco(0.2) is None
    atascado = v.atasco(5)
    assert atascado is not None and not atascado.detener


def test_cronometro_descarta_el_fotograma_viejo():
    cron = CronometroEnVivo()
    cron.en_cola(1.0)
    cron.en_cola(2.0)
    cron.descartar(1)
    assert cron.cerrar() is not None
    assert cron.cerrar() is None


def test_sobrecarga_y_recomendacion():
    medida = medir_sobrecarga(
        PERFIL_8GB.id, fotogramas=6, ancho=32, alto=18, deteccion_cada=2
    )
    assert medida.muestras == 6
    assert medida.latencia_ms >= 0
    assert recomendar([medida], PERFIL_ALTO.id) in {
        "Alto 12-16 GB",
        "Equilibrado 8 GB",
        "6 GB (portátil)",
    }


def test_copia_de_estado_no_llega_al_array():
    arr = np.zeros(3)
    origen = {"cara": {"slider": 1, "embed": arr}}
    copia = copia_estado(origen)
    copia["cara"]["slider"] = 2
    assert origen["cara"]["slider"] == 1
    assert copia["cara"]["embed"] is arr


def test_el_arranque_conserva_acceso_y_licencia():
    texto = Path(entrada.__file__).read_text(encoding="utf-8")
    assert texto.index("solicitar_acceso") < texto.index("solicitar_licencia")
    assert "vigilante.detener()" in texto
    assert "preferir_gpu_dedicada" in texto
    assert entrada.comprobar_importaciones() == 0
