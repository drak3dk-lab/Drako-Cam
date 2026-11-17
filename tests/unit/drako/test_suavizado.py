"""El borde no debe parpadear, y un tapón no debe borrar el cambio."""

import time

import numpy as np

from app.drako.rendimiento.suavizado import (
    MemoriaDirecto,
    ema,
    estabilizar_color,
    interpolar_caja,
    peso_ultimo_swap,
    pluma_adaptativa,
    preparar_mascara,
    salto_grande,
    tamano_oclusion,
)


def test_el_promedio_se_queda_entre_los_dos_fotogramas():
    anterior = np.zeros((8, 8), dtype=np.float32)
    actual = np.ones((8, 8), dtype=np.float32)
    mezcla = ema(anterior, actual, 0.5)
    assert np.allclose(mezcla, 0.5)


def test_cambiar_de_cara_olvida_la_mascara_anterior():
    memoria = MemoriaDirecto(alfa_mascara=0.2)
    primera = np.zeros((96, 96), dtype=np.float32)
    preparar_mascara(memoria, "ana", primera, (10, 10), 100)
    segunda = np.ones((96, 96), dtype=np.float32)
    salida, reinicio = preparar_mascara(memoria, "luis", segunda, (10, 10), 100)
    assert reinicio
    assert np.allclose(salida, 1.0)


def test_un_salto_rapido_reinicia_el_suavizado():
    assert salto_grande((0, 0), (50, 0), tamano=100, umbral=0.35)
    assert not salto_grande((0, 0), (10, 0), tamano=100, umbral=0.35)
    memoria = MemoriaDirecto(alfa_mascara=0.1, umbral_salto=0.35)
    base = np.zeros((96, 96), dtype=np.float32)
    preparar_mascara(memoria, "ana", base, (0, 0), 100)
    salida, reinicio = preparar_mascara(
        memoria, "ana", np.ones((96, 96), dtype=np.float32), (80, 0), 100
    )
    assert reinicio
    assert salida.mean() > 0.99


def test_sin_salto_el_borde_no_cambia_de_golpe():
    memoria = MemoriaDirecto(alfa_mascara=0.4)
    preparar_mascara(memoria, "ana", np.zeros((96, 96), dtype=np.float32), (0, 0), 120)
    salida, reinicio = preparar_mascara(
        memoria, "ana", np.ones((96, 96), dtype=np.float32), (4, 0), 120
    )
    assert not reinicio
    assert 0.3 < float(salida.mean()) < 0.5


def test_la_pluma_crece_cuando_la_cara_es_pequena():
    lejos = pluma_adaptativa(80)
    cerca = pluma_adaptativa(400)
    assert lejos > cerca
    assert cerca >= 0.6
    assert lejos <= 14


def test_la_oclusion_se_encoge_en_una_cara_grande():
    assert tamano_oclusion(400, 0, True) == -4
    assert tamano_oclusion(200, 0, True) == -2
    assert tamano_oclusion(100, 0, True) == 0
    assert tamano_oclusion(400, 0, False) == 0


def test_la_caja_no_salta_si_el_detector_suelta_la_cara():
    caja = interpolar_caja([0, 0, 10, 10], [10, 10, 20, 20], 0.5)
    assert np.allclose(caja, [5, 5, 15, 15])


def test_una_mano_conserva_el_ultimo_cambio():
    assert peso_ultimo_swap(0.9) == 0.0
    assert peso_ultimo_swap(0.2) > 0.5
    assert peso_ultimo_swap(0.0) <= 0.85


def test_el_color_no_salta_entero_en_un_fotograma():
    media, desvio = estabilizar_color(
        np.array([10, 20, 30], dtype=np.float32),
        np.array([2, 2, 2], dtype=np.float32),
        np.array([0, 0, 0], dtype=np.float32),
        np.array([2, 2, 2], dtype=np.float32),
        0.25,
    )
    assert np.all(media < np.array([10, 20, 30]))
    assert np.all(media > 0)
    assert np.allclose(desvio, 2)


def test_el_suavizado_cabe_en_el_presupuesto_de_un_fotograma():
    memoria = MemoriaDirecto()
    mascara = np.random.rand(512, 512).astype(np.float32)
    inicio = time.perf_counter()
    repeticiones = 30
    for indice in range(repeticiones):
        preparar_mascara(memoria, "ana", mascara, (100 + indice, 80), 180)
    milisegundos = (time.perf_counter() - inicio) / repeticiones * 1000.0
    # Un fotograma a 30 FPS tiene 33 ms. Esto es solo la máscara, sin la red.
    assert milisegundos < 8.0, milisegundos
    print(f"suavizado de máscara 512→96: {milisegundos:.2f} ms")
