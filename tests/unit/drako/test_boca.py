"""Al hablar se abre la boca. Cerrada, se quedan los labios de la cara nueva."""

import time

import numpy as np

from app.processors.mouth_openness import (
    MouthOpennessState,
    dilatacion_al_hablar,
    fuerza_al_hablar,
)


def test_boca_cerrada_no_dilata_los_labios():
    assert dilatacion_al_hablar(8, 0.0) == 0
    assert dilatacion_al_hablar(10, 0.0) == 0
    assert fuerza_al_hablar(0.10, 0.22) == 0.0


def test_la_apertura_entra_seguida_y_no_de_golpe():
    umbral = 0.22
    justo = fuerza_al_hablar(umbral, umbral)
    media = fuerza_al_hablar(umbral + 0.05, umbral)
    abierta = fuerza_al_hablar(umbral + 0.2, umbral)
    assert justo == 0.0
    assert 0.0 < media < abierta
    assert abierta <= 1.0
    assert dilatacion_al_hablar(8, media) < dilatacion_al_hablar(8, abierta)
    assert dilatacion_al_hablar(8, 1.0) == 8


def test_el_ema_no_parpadea_alrededor_del_umbral():
    estado = MouthOpennessState()
    activo, _ = estado.update(0.30, 0.35, 0.22)
    assert activo
    # Por debajo del umbral, pero dentro de la histéresis: sigue hablando.
    activo, ema = estado.update(0.20, 0.35, 0.22)
    assert activo
    assert ema < 0.30
    # Varios fotogramas cerrados sí la apagan, sin un corte en el primero.
    for _ in range(8):
        activo, ema = estado.update(0.05, 0.35, 0.22)
    assert ema < 0.22
    assert activo is False


def test_el_estado_de_la_boca_no_cuesta_un_fotograma():
    estado = MouthOpennessState()
    ratios = np.linspace(0.0, 0.6, 200)
    inicio = time.perf_counter()
    for ratio in ratios:
        estado.update(float(ratio), 0.35, 0.22)
    milisegundos = (time.perf_counter() - inicio) / len(ratios) * 1000.0
    assert milisegundos < 0.05, milisegundos
