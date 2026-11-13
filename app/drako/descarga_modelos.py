"""Pide modelos en segundo plano. No bloquea el hilo que dibuja la cámara.

``solicitar_si_falta`` vuelve al momento. La descarga vive en un hilo propio.
Quien llama no debe tomar el candado de los modelos: el aviso a la interfaz
puede ejecutarse en el mismo hilo.
"""

from __future__ import annotations

import threading
from pathlib import Path

from app.drako.catalogo_modelos import (
    archivo_presente,
    esenciales,
    ficha,
    fichas,
)
from app.helpers.downloader import (
    TRABAJADORES,
    ResultadoLote,
    Trabajo,
    descargar_lote,
)


def _omitir_hash() -> bool:
    """portable.cfg junto a la carpeta del programa, igual que el arranque anterior."""
    cfg = Path(__file__).resolve().parents[2].parent / "portable.cfg"
    if not cfg.is_file():
        cfg = Path(__file__).resolve().parents[2] / "portable.cfg"
    if not cfg.is_file():
        return False
    try:
        texto = cfg.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(
        linea.strip().upper() == "USE_OPTIMIZED_MODELS=TRUE"
        for linea in texto.splitlines()
    )


def trabajos_de(nombres: list[str]) -> list[Trabajo]:
    por_nombre = {item.nombre: item for item in fichas()}
    salida: list[Trabajo] = []
    for nombre in nombres:
        item = por_nombre[nombre]
        salida.append(
            Trabajo(
                nombre=item.nombre,
                url=item.url,
                destino=item.local_path,
                hash_esperado=item.hash,
                bytes_estimados=item.bytes,
            )
        )
    return salida


def descargar_nombres(
    nombres: list[str],
    *,
    trabajadores: int = TRABAJADORES,
    cancelado: threading.Event | None = None,
    al_progreso=None,
    omitir_hash: bool | None = None,
    intentos: int = 4,
    dormir=None,
    chunk_size: int = 1024 * 1024,
    sesion_fabrica=None,
) -> ResultadoLote:
    if omitir_hash is None:
        omitir_hash = _omitir_hash()
    return descargar_lote(
        trabajos_de(nombres),
        trabajadores=trabajadores,
        cancelado=cancelado,
        omitir_hash=omitir_hash,
        al_progreso=al_progreso,
        intentos=intentos,
        dormir=dormir,
        chunk_size=chunk_size,
        sesion_fabrica=sesion_fabrica,
    )


class GestorDescarga:
    """Una cola, un hilo. Se puede cancelar; el parcial se conserva."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pendientes: list[str] = []
        self._activos: set[str] = set()
        self._avisados: set[str] = set()
        self._hilo_activo = False
        self._cancelar = threading.Event()
        self._pedido: list = []
        self._progreso: list = []
        self._fin: list = []

    def al_pedir(self, funcion) -> None:
        self._pedido.append(funcion)

    def al_progresar(self, funcion) -> None:
        self._progreso.append(funcion)

    def al_terminar(self, funcion) -> None:
        self._fin.append(funcion)

    def cancelar(self) -> None:
        self._cancelar.set()

    def pedir(self, nombres: list[str]) -> None:
        pendientes = [nombre for nombre in nombres if not archivo_presente(nombre)]
        if not pendientes:
            return
        arrancar = False
        with self._lock:
            for nombre in pendientes:
                if nombre not in self._pendientes and nombre not in self._activos:
                    self._pendientes.append(nombre)
            if self._pendientes and not self._hilo_activo:
                self._hilo_activo = True
                self._cancelar.clear()
                arrancar = True
        for nombre in pendientes:
            self._emitir(self._pedido, nombre)
        if arrancar:
            threading.Thread(
                target=self._bucle, name="drako-modelos", daemon=True
            ).start()

    def reintentar(self, nombres: list[str]) -> None:
        with self._lock:
            for nombre in nombres:
                self._avisados.discard(nombre)
        self.pedir(nombres)

    def solicitar_si_falta(self, nombre: str) -> bool:
        """True si el archivo ya está. Si falta, encola la descarga y vuelve."""
        try:
            ficha(nombre)
        except KeyError:
            return False
        if archivo_presente(nombre):
            return True
        with self._lock:
            if (
                nombre in self._avisados
                or nombre in self._activos
                or nombre in self._pendientes
            ):
                return False
            self._avisados.add(nombre)
        self.pedir([nombre])
        return False

    def _bucle(self) -> None:
        while True:
            with self._lock:
                if not self._pendientes:
                    self._hilo_activo = False
                    return
                lote = list(self._pendientes)
                self._pendientes.clear()
                self._activos.update(lote)
                self._cancelar.clear()
            resultado = descargar_nombres(
                lote,
                cancelado=self._cancelar,
                al_progreso=lambda *args: self._emitir(self._progreso, args),
            )
            with self._lock:
                self._activos.difference_update(lote)
                if resultado.correcto:
                    for nombre in lote:
                        self._avisados.discard(nombre)
            self._emitir(self._fin, resultado)

    @staticmethod
    def _emitir(oyentes: list, dato) -> None:
        for funcion in list(oyentes):
            try:
                funcion(dato)
            except Exception as exc:  # noqa: BLE001
                # Un oyente de la interfaz no puede tumbar la descarga ni la cámara.
                print(f"[WARN] Aviso de modelos ignorado: {exc}")


_gestor: GestorDescarga | None = None
_gestor_lock = threading.Lock()


def gestor() -> GestorDescarga:
    global _gestor
    with _gestor_lock:
        if _gestor is None:
            _gestor = GestorDescarga()
        return _gestor


def solicitar_si_falta(nombre: str) -> bool:
    return gestor().solicitar_si_falta(nombre)


def nombres_esenciales() -> list[str]:
    return [item.nombre for item in esenciales()]
