"""Medición de FPS y latencia, y recomendación de perfil.

Sin modelos cargados mide la sobrecarga del canal (copias, colas,
seguimiento). Con el directo en marcha, el cronómetro usa las marcas
de los fotogramas reales. La inferencia de los modelos hay que
confirmarla en la GPU de destino: aquí no se inventa ese tiempo.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Medicion:
    perfil: str
    fps: float
    latencia_ms: float
    p95_ms: float
    muestras: int
    nota: str


class CronometroEnVivo:
    """Latencia de extremo a extremo de los fotogramas que sí se muestran."""

    def __init__(self, capacidad: int = 180) -> None:
        self._pendientes: deque[float] = deque()
        self.latencias_ms: deque[float] = deque(maxlen=capacidad)
        self.salidas: deque[float] = deque(maxlen=capacidad)
        self._lock = threading.Lock()

    def en_cola(self, t0: float) -> None:
        with self._lock:
            self._pendientes.append(t0)

    def descartar(self, n: int = 1) -> None:
        with self._lock:
            for _ in range(max(0, n)):
                if self._pendientes:
                    self._pendientes.popleft()

    def cerrar(self) -> float | None:
        with self._lock:
            if not self._pendientes:
                return None
            t0 = self._pendientes.popleft()
            ahora = time.perf_counter()
            ms = (ahora - t0) * 1000.0
            self.latencias_ms.append(ms)
            self.salidas.append(ahora)
            return ms

    def resumen(self, perfil: str = "en vivo") -> Medicion | None:
        with self._lock:
            if len(self.latencias_ms) < 5:
                return None
            vals = sorted(self.latencias_ms)
            salidas = list(self.salidas)
        p50 = vals[len(vals) // 2]
        p95 = vals[min(len(vals) - 1, int(len(vals) * 0.95))]
        fps = 0.0
        if len(salidas) >= 2:
            span = salidas[-1] - salidas[0]
            if span > 0:
                fps = (len(salidas) - 1) / span
        return Medicion(
            perfil=perfil,
            fps=fps,
            latencia_ms=p50,
            p95_ms=p95,
            muestras=len(vals),
            nota="Fotogramas reales del directo, de la captura a la salida.",
        )


def _percentil(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    orden = sorted(vals)
    indice = min(len(orden) - 1, max(0, int(round(q * (len(orden) - 1)))))
    return orden[indice]


def medir_sobrecarga(
    perfil_id: str,
    fotogramas: int = 24,
    ancho: int = 320,
    alto: int = 180,
    deteccion_cada: int = 2,
) -> Medicion:
    """Tiempo del canal sin red neuronal: copia, seguimiento y cola."""
    import numpy as np

    from app.drako.rendimiento.buffers import AnilloAnfitrion
    from app.drako.rendimiento.colas import ColaLatencia
    from app.drako.rendimiento.deteccion import PoliticaDeteccion, RastreadorRostros

    anillo = AnilloAnfitrion(3)
    cola_cap = ColaLatencia(1)
    cola_sal = ColaLatencia(1)
    politica = PoliticaDeteccion(cada_n=deteccion_cada)
    rastreador = RastreadorRostros()
    latencias: list[float] = []
    t_anterior = time.perf_counter()
    intervalos: list[float] = []
    caja = np.array([[40, 30, 120, 140]], dtype=np.float32)
    kps = np.zeros((1, 5, 2), dtype=np.float32)
    kps68 = np.zeros((1, 68, 2), dtype=np.float32)
    kps203 = np.zeros((1, 203, 2), dtype=np.float32)
    for n in range(fotogramas):
        t0 = time.perf_counter()
        frame = np.full((alto, ancho, 3), n % 255, dtype=np.uint8)
        copia = anillo.copiar(frame)
        cola_cap.poner_fresco(copia)
        tomado = cola_cap.tomar(0.05)
        if politica.debe_detectar(rastreador.perdido()):
            rastreador.corregir(caja, kps, kps68, kps203, ancho, alto)
            politica.anotar(True)
        else:
            rastreador.predecir()
            if rastreador.perdido():
                rastreador.corregir(caja, kps, kps68, kps203, ancho, alto)
                politica.anotar(True)
        cola_sal.poner_fresco(tomado)
        cola_sal.tomar(0.05)
        t1 = time.perf_counter()
        latencias.append((t1 - t0) * 1000.0)
        intervalos.append(t1 - t_anterior)
        t_anterior = t1
    fps = 0.0
    if len(intervalos) > 1 and sum(intervalos[1:]) > 0:
        fps = (len(intervalos) - 1) / sum(intervalos[1:])
    return Medicion(
        perfil=perfil_id,
        fps=fps,
        latencia_ms=_percentil(latencias, 0.5),
        p95_ms=_percentil(latencias, 0.95),
        muestras=len(latencias),
        nota=(
            "Sobrecarga del canal en CPU, sin el tiempo de los modelos. "
            "Sirve para comparar perfiles, no para prometer FPS de inferencia."
        ),
    )


def comparar_copias(fotogramas: int = 20, ancho: int = 640, alto: int = 360) -> dict:
    """Tiempo del camino viejo (reservar cada vez) frente al anillo.

    Es la medida que documenta el cuello de las copias por fotograma.
    """
    import numpy as np

    from app.drako.rendimiento.buffers import AnilloAnfitrion

    frame = np.zeros((alto, ancho, 3), dtype=np.uint8)
    t0 = time.perf_counter()
    for _ in range(fotogramas):
        chw = np.ascontiguousarray(frame.transpose(2, 0, 1))
        del chw
        rgb = np.ascontiguousarray(frame[:, :, ::-1])
        del rgb
    viejo_ms = (time.perf_counter() - t0) * 1000.0 / fotogramas

    anillo = AnilloAnfitrion(4)
    # El primer fotograma reserva; no entra en la media.
    anillo.copiar(frame)
    t1 = time.perf_counter()
    for _ in range(fotogramas):
        anillo.copiar(frame)
    nuevo_ms = (time.perf_counter() - t1) * 1000.0 / fotogramas
    return {
        "viejo_ms": viejo_ms,
        "anillo_ms": nuevo_ms,
        "fotogramas": fotogramas,
        "ancho": ancho,
        "alto": alto,
        "bytes": alto * ancho * 3,
    }


def recomendar(mediciones: list[Medicion], perfil_hardware: str) -> str:
    """El perfil de la GPU manda. Se baja un escalón si la sobrecarga no cabe en 30 FPS."""
    from app.drako.rendimiento.perfiles import ID_6GB, ID_8GB, ID_ALTO

    orden = [ID_ALTO, ID_8GB, ID_6GB]
    if perfil_hardware not in orden:
        perfil_hardware = ID_8GB
    por_id = {m.perfil: m for m in mediciones}
    candidato = perfil_hardware
    medida = por_id.get(candidato)
    # 30 FPS dejan ~33 ms. La sobrecarga del canal (sin modelos) tiene que
    # quedar muy por debajo: si el p95 ya pasa de 12 ms, el escalón sobra.
    if medida is not None and medida.p95_ms > 12.0:
        indice = orden.index(candidato)
        if indice < len(orden) - 1:
            candidato = orden[indice + 1]
    titulos = {
        ID_ALTO: "Alto 12-16 GB",
        ID_8GB: "Equilibrado 8 GB",
        ID_6GB: "6 GB (portátil)",
    }
    return titulos.get(candidato, candidato)


def informe(mediciones: list[Medicion], perfil_hardware: str) -> str:
    """Texto en español para el cuadro de la medición."""
    lineas = ["Medición del canal en vivo (sin el tiempo de los modelos):", ""]
    for m in mediciones:
        lineas.append(
            f"• {m.perfil}: {m.fps:.0f} FPS de sobrecarga, "
            f"latencia {m.latencia_ms:.2f} ms (p95 {m.p95_ms:.2f} ms, n={m.muestras})"
        )
    lineas.append("")
    lineas.append(
        f"Recomendación para esta máquina: {recomendar(mediciones, perfil_hardware)}."
    )
    lineas.append(
        "Hay que repetir la medición con la webcam en marcha en la GPU real. "
        "El tiempo de detección, cambio de cara y mejorador no está incluido."
    )
    if mediciones:
        lineas.append(mediciones[0].nota)
    return "\n".join(lineas)


def medir_perfiles_de_hardware(perfil_hardware: str) -> tuple[list[Medicion], str]:
    from app.drako.rendimiento.perfiles import PERFIL_6GB, PERFIL_8GB, PERFIL_ALTO

    mediciones = []
    for perfil, escala in (
        (PERFIL_6GB, (640, 360)),
        (PERFIL_8GB, (960, 540)),
        (PERFIL_ALTO, (960, 540)),
    ):
        # Resolución reducida a propósito: esta medición es de sobrecarga
        # del canal, y tiene que terminar al momento en la interfaz.
        mediciones.append(
            medir_sobrecarga(
                perfil.id,
                fotogramas=12,
                ancho=escala[0],
                alto=escala[1],
                deteccion_cada=perfil.deteccion_cada,
            )
        )
    return mediciones, informe(mediciones, perfil_hardware)
