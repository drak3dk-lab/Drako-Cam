"""Conecta la pantalla sencilla con el motor que ya existe.

Elige la foto, elige la cámara, pulsa EN VIVO. La detección, el
seguimiento y la cámara virtual siguen siendo los de siempre.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6 import QtCore

from app.ui.estudio.biblioteca import Biblioteca
from app.ui.estudio.controles import por_clave, valores_de_calidad
from app.ui.estudio.logica import (
    MENSAJE_CARGANDO,
    MENSAJE_FOTO,
    ajuste_calidad,
    atajos_de_favoritas,
    aviso_cara_perdida,
    fondo_a_motor,
    frente_a_motor,
    fuerza_a_motor,
    nitidez_a_motor,
    puede_entrar_en_vivo,
)
from app.ui.estudio.logica import CaraVista


class MotorEnVivo:
    def __init__(self, ventana, biblioteca: Biblioteca):
        self.ventana = ventana
        self.biblioteca = biblioteca
        self.en_vivo = False
        self.original = False
        self.mensaje = ""
        self.nota_calidad = "Según la tarjeta que haya en el equipo."
        self._cara_id = str(self.biblioteca.estado().get("ultima_cara") or "")
        self._indice = int(self.biblioteca.estado().get("ultima_camara") or 0)
        self._calidad = str(self.biblioteca.estado().get("calidad") or "Auto")
        self._sin_cara: float | None = None
        self._loader = None
        self._entrando = False
        self._reintentos = 0
        self._virtual = bool(self.biblioteca.estado().get("camara_virtual") or False)
        self._ajustes: dict[str, object] = {}
        self.al_cargar = None

    def arrancar(self) -> None:
        self._poner_valor("WebcamMaxNoSelection", "5")
        self._poner_valor("MaxFacesToDetectSlider", 1)
        self._poner_toggle("ForceSwapToggle", True)
        self._poner_toggle("KeepInputToggle", True)
        self._aplicar_mapa(valores_de_calidad(self._calidad, self._permite_60()), guardar=False)
        self._preparar_camaras()
        if self._virtual:
            QtCore.QTimer.singleShot(800, lambda: self.camara_virtual(True))

    def caras(self) -> tuple[list[CaraVista], str]:
        fotos = self.biblioteca.listar()
        atajos = atajos_de_favoritas([foto.id for foto in fotos if foto.favorita])
        vistas = [
            CaraVista(
                id=foto.id,
                nombre=foto.nombre,
                ruta=str(foto.ruta),
                favorita=foto.favorita,
                atajo=atajos.get(foto.id, ""),
            )
            for foto in fotos
        ]
        if self._cara_id and any(vista.id == self._cara_id for vista in vistas):
            return vistas, self._cara_id
        self._cara_id = vistas[0].id if vistas else ""
        return vistas, self._cara_id

    def anadir_fotos(self, rutas: list[str]) -> str:
        ultima = ""
        for ruta in rutas:
            try:
                foto = self.biblioteca.anadir(Path(ruta))
            except (OSError, ValueError) as exc:
                return str(exc)
            ultima = foto.id
            self._pedir_embedding(foto.ruta)
        if ultima:
            self.elegir_cara(ultima)
        return ""

    def poner_control(self, clave: str, valor: object) -> str:
        if clave == "LandmarkDetectToggle" and valor:
            self._poner_valor("LandmarkDetectModelSelection", "orformer98")
        self._escribir_control(clave, valor)
        self._ajustes[clave] = valor
        if self._cara_id:
            self.biblioteca.guardar_ajustes(self._cara_id, dict(self._ajustes))
        return ""

    def elegir_cara(self, ident: str) -> None:
        self._cara_id = ident
        self.biblioteca.recordar(ultima_cara=ident)
        guardados = self.biblioteca.ajustes_de(ident)
        if guardados:
            self._aplicar_mapa(guardados, guardar=False)
        elif self._ajustes:
            self.biblioteca.guardar_ajustes(ident, dict(self._ajustes))
        self.mensaje = ""
        if self.en_vivo:
            self._aplicar_cara(redetectar=False)

    def fijar_favorita(self, ident: str, favorita: bool) -> None:
        self.biblioteca.fijar_favorita(ident, favorita)

    def camaras(self) -> list[str]:
        return [nombre for _, nombre in self._lista_camaras()]

    def indice_camara(self) -> int:
        pares = self._lista_camaras()
        for posicion, (indice, _) in enumerate(pares):
            if indice == self._indice:
                return posicion
        boton = getattr(self.ventana, "selected_video_button", None)
        if boton is not None and getattr(boton, "file_type", "") == "webcam":
            indice = int(getattr(boton, "webcam_index", -1))
            for posicion, (numero, _) in enumerate(pares):
                if numero == indice:
                    return posicion
        return 0 if pares else -1

    def elegir_camara(self, posicion: int) -> str:
        pares = self._lista_camaras()
        if posicion < 0 or posicion >= len(pares):
            self.mensaje = "No hay cámara. Conecta una y vuelve a abrir Drako Cam."
            return self.mensaje
        indice, _nombre = pares[posicion]
        boton = self._boton_camara(indice)
        if boton is None:
            self.mensaje = "No encuentro esa cámara."
            return self.mensaje
        self._indice = indice
        self.biblioteca.recordar(ultima_camara=indice)
        try:
            boton.load_media()
            boton.setChecked(True)
        except Exception as exc:
            self.mensaje = f"No pude abrir la cámara. {exc}"
            return self.mensaje
        if not self._camara_abierta():
            self.mensaje = "No pude abrir la cámara. Mira que otro programa no la esté usando."
            return self.mensaje
        self.mensaje = ""
        if self.en_vivo:
            self._aplicar_cara(redetectar=True)
        return ""

    def poner_en_vivo(self, activo: bool) -> str:
        if not activo:
            self.en_vivo = False
            self._sin_cara = None
            self._fijar_cambio(False)
            self.mensaje = ""
            return ""
        foto = self._foto_seleccionada()
        aviso = puede_entrar_en_vivo(foto is not None, self._camara_abierta())
        if aviso:
            self.mensaje = aviso
            self.en_vivo = False
            return aviso
        assert foto is not None
        if self._boton_entrada(foto.ruta) is None:
            self.mensaje = MENSAJE_CARGANDO
            self._entrando = True
            self._reintentos = 0
            self._pedir_embedding(foto.ruta)
            QtCore.QTimer.singleShot(400, self._reintentar_en_vivo)
            return self.mensaje
        return self._activar()

    def ver_original(self, original: bool) -> None:
        self.original = original
        if self.en_vivo:
            self._fijar_cambio(not original)

    def camara_virtual(self, activa: bool) -> None:
        self._virtual = bool(activa)
        self.biblioteca.recordar(camara_virtual=self._virtual)
        self._poner_toggle("SendVirtCamFramesEnableToggle", self._virtual)

    def poner_calidad(self, nombre: str) -> None:
        self._calidad = nombre
        self.biblioteca.recordar(calidad=nombre)
        ajuste = ajuste_calidad(nombre, self._permite_60())
        self.nota_calidad = ajuste.nota
        if ajuste.resolucion:
            self._poner_valor("WebcamMaxResSelection", ajuste.resolucion)
        if ajuste.fps:
            self._poner_valor("WebCamMaxFPSSelection", ajuste.fps)
        if ajuste.deteccion_cada is not None:
            self._poner_valor("DeteccionCadaNSlider", ajuste.deteccion_cada)
            self._poner_toggle("DeteccionInteligenteEnableToggle", True)
        self._aplicar_mapa(valores_de_calidad(nombre, self._permite_60()))
        if ajuste.resolucion or ajuste.fps:
            posicion = self.indice_camara()
            if posicion >= 0 and self._camara_abierta():
                self.elegir_camara(posicion)

    def poner_fuerza(self, valor: int) -> None:
        self._poner_toggle("StrengthEnableToggle", int(valor) != 50)
        self._poner_valor("StrengthAmountSlider", fuerza_a_motor(valor))

    def poner_nitidez(self, valor: int) -> None:
        self._poner_toggle("ColorEnableToggle", True)
        self._poner_valor("ColorSharpnessDecimalSlider", nitidez_a_motor(valor))

    def poner_frente(self, valor: int) -> None:
        self._poner_toggle("BordermaskEnableToggle", True)
        self._poner_valor("BorderTopSlider", frente_a_motor(valor))

    def poner_fps(self, fps: int) -> None:
        if fps >= 60 and not self._permite_60():
            self.mensaje = "Esta tarjeta se queda en 30 FPS para no ir a tirones."
            fps = 30
        else:
            self.mensaje = ""
        self._poner_valor("WebCamMaxFPSSelection", str(fps))
        posicion = self.indice_camara()
        if posicion >= 0 and self._camara_abierta():
            self.elegir_camara(posicion)

    def poner_fondo(self, nombre: str) -> None:
        self._poner_valor("FondoVirtualSelection", fondo_a_motor(nombre))

    def poner_toggle(self, nombre: str, activo: bool) -> None:
        if nombre == "fps":
            return
        if nombre == "mejorar":
            self._poner_toggle("FaceRestorerEnableToggle", activo)
        elif nombre == "varias":
            self._poner_valor("MaxFacesToDetectSlider", 5 if activo else 1)
            if self.en_vivo:
                self._aplicar_cara(redetectar=True)
        elif nombre == "boca":
            self._poner_toggle("RestoreMouthEnableToggle", activo)

    def poner_ajuste(self, clave: str, valor: object) -> None:
        if clave == "borde":
            self._poner_toggle("BordermaskEnableToggle", bool(valor))
        elif clave == "restaurador":
            self._poner_valor("FaceRestorerTypeSelection", str(valor))
        elif clave == "resolucion":
            self._poner_valor("WebcamMaxResSelection", str(valor))
            posicion = self.indice_camara()
            if posicion >= 0 and self._camara_abierta():
                self.elegir_camara(posicion)
        elif clave == "proveedor":
            self._poner_valor("PrecisionTensorRTSelection", str(valor))
        elif clave == "detector":
            self._poner_valor("DetectorModelSelection", str(valor))
        elif clave == "volver_camara":
            self._preparar_camaras()
            posicion = self.indice_camara()
            if posicion >= 0:
                self.elegir_camara(posicion)

    def probar_video(self) -> None:
        from app.ui.widgets.actions import list_view_actions

        antes = getattr(self.ventana, "video_loader_worker", None)
        list_view_actions.select_target_medias(self.ventana, "files")
        despues = getattr(self.ventana, "video_loader_worker", None)
        if despues is not None and despues is not antes:
            try:
                despues.finished.connect(self._usar_video)
            except Exception:
                pass

    def estado(self) -> dict:
        fps, latencia = self._medicion()
        vram = self._vram()
        virtual = bool(self.ventana.control.get("SendVirtCamFramesEnableToggle", False))
        mensaje = self.mensaje
        if self.en_vivo and not mensaje:
            mensaje = self._vigilar_cara() or ""
        resolucion = str(self.ventana.control.get("WebcamMaxResSelection", "1920x1080"))
        fps_salida = str(self.ventana.control.get("WebCamMaxFPSSelection", "30"))
        fondo = str(self.ventana.control.get("FondoVirtualSelection", "Ninguno"))
        fondo_visible = {"Ninguno": "Normal", "Verde": "Verde", "Transparente": "Transparente"}.get(
            fondo, "Normal"
        )
        return {
            "en_vivo": self.en_vivo and not self.original,
            "cambio_activo": self.en_vivo,
            "tiene_foto": self._foto_seleccionada() is not None,
            "tiene_camara": self._camara_abierta() or bool(self.camaras()),
            "fps": fps,
            "latencia_ms": latencia,
            "vram": vram,
            "proveedor": self._proveedor(),
            "vigilante": self._vigilante(),
            "mensaje": mensaje,
            "calidad_nota": self.nota_calidad,
            "virtual": virtual,
            "resolucion": resolucion,
            "fps_salida": fps_salida,
            "fondo": fondo_visible,
            "original": self.original,
        }

    def _activar(self) -> str:
        self._poner_toggle("AutoSwapToggle", True)
        self._poner_toggle("KeepInputToggle", True)
        self._poner_toggle("ForceSwapToggle", True)
        self.en_vivo = True
        self._sin_cara = None
        self.mensaje = ""
        self._aplicar_cara(redetectar=True)
        self._fijar_cambio(not self.original)
        return ""

    def _reintentar_en_vivo(self) -> None:
        if not self._entrando:
            return
        foto = self._foto_seleccionada()
        if foto is not None and self._boton_entrada(foto.ruta) is not None:
            self._entrando = False
            self._activar()
            return
        self._reintentos += 1
        if self._reintentos > 20:
            self._entrando = False
            self.mensaje = "No pude leer la foto. Prueba con otra, de frente y con luz."
            return
        QtCore.QTimer.singleShot(300, self._reintentar_en_vivo)

    def _aplicar_cara(self, redetectar: bool) -> None:
        foto = self._foto_seleccionada()
        if foto is None:
            self.mensaje = MENSAJE_FOTO
            return
        boton = self._boton_entrada(foto.ruta)
        if boton is None:
            self._pedir_embedding(foto.ruta)
            return
        self._marcar_entrada(boton)
        if redetectar or not getattr(self.ventana, "target_faces", None):
            try:
                from app.ui.widgets.actions import card_actions

                card_actions.find_target_faces(self.ventana)
            except Exception as exc:
                self.mensaje = f"No pude detectar la cara. {exc}"
                return
        caras = list(getattr(self.ventana, "target_faces", {}).values())
        if not caras:
            self.mensaje = aviso_cara_perdida(0.0, 10.0) or ""
            return
        varias = int(self.ventana.control.get("MaxFacesToDetectSlider", 1)) > 1
        for posicion, destino in enumerate(caras):
            if not varias and posicion > 0:
                destino.assigned_input_faces.clear()
            else:
                destino.assigned_input_faces = {boton.face_id: boton.embedding_store}
            try:
                destino.calculate_assigned_input_embedding()
            except Exception:
                pass
        self.ventana.selected_target_face_id = caras[0].face_id
        self.ventana.cur_selected_target_face_button = caras[0]
        self.mensaje = ""

    def _usar_video(self) -> None:
        for boton in getattr(self.ventana, "target_videos", {}).values():
            if getattr(boton, "file_type", "") in {"video", "image"}:
                try:
                    boton.load_media()
                    boton.setChecked(True)
                except Exception as exc:
                    self.mensaje = f"No pude abrir el vídeo. {exc}"
                    return
                self.mensaje = "Vídeo de prueba. Para volver a la cámara, usa Avanzado."
                if self.en_vivo:
                    self._aplicar_cara(redetectar=True)
                return

    def _preparar_camaras(self) -> None:
        from app.ui.widgets.actions import list_view_actions

        caja = self.ventana.targetVideosFilterWebcamsCheckBox
        if not caja.isChecked():
            caja.setChecked(True)
        else:
            list_view_actions.load_target_webcams(self.ventana)
        worker = getattr(self.ventana, "video_loader_worker", None)
        if worker is not None:
            try:
                worker.finished.connect(self._camara_inicial, QtCore.Qt.ConnectionType.UniqueConnection)
            except Exception:
                try:
                    worker.finished.connect(self._camara_inicial)
                except Exception:
                    pass

    def _camara_inicial(self) -> None:
        if self._camara_abierta():
            return
        pares = self._lista_camaras()
        if not pares:
            self.mensaje = "No veo ninguna cámara. Conéctala y pulsa Volver a la cámara, en Avanzado."
            return
        posicion = 0
        for indice, (numero, _nombre) in enumerate(pares):
            if numero == self._indice:
                posicion = indice
                break
        self.elegir_camara(posicion)

    def _pedir_embedding(self, ruta: Path) -> None:
        from functools import partial

        from app.ui.widgets.actions.list_view_actions import (
            add_media_thumbnail_to_source_faces_list,
        )
        from app.ui.widgets.ui_workers import InputFacesLoaderWorker

        worker = InputFacesLoaderWorker(self.ventana, files_list=[str(ruta)])
        worker.thumbnail_ready.connect(
            partial(add_media_thumbnail_to_source_faces_list, self.ventana)
        )
        self._loader = worker
        worker.start()

    def _foto_seleccionada(self):
        if not self._cara_id:
            return None
        for foto in self.biblioteca.listar():
            if foto.id == self._cara_id:
                return foto
        return None

    def _boton_entrada(self, ruta: Path):
        buscada = str(Path(ruta).resolve())
        for boton in getattr(self.ventana, "input_faces", {}).values():
            media = str(getattr(boton, "media_path", "") or "")
            if not media:
                continue
            try:
                if str(Path(media).resolve()) == buscada:
                    return boton
            except OSError:
                if media == str(ruta):
                    return boton
        return None

    def _marcar_entrada(self, boton) -> None:
        for otro in getattr(self.ventana, "input_faces", {}).values():
            if otro is not boton and otro.isChecked():
                otro.setChecked(False)
        if not boton.isChecked():
            boton.click()

    def _lista_camaras(self) -> list[tuple[int, str]]:
        pares = []
        for boton in getattr(self.ventana, "target_videos", {}).values():
            if getattr(boton, "file_type", "") != "webcam":
                continue
            indice = int(getattr(boton, "webcam_index", len(pares)))
            pares.append((indice, f"Cámara {indice + 1}"))
        pares.sort()
        return pares

    def _boton_camara(self, indice: int):
        for boton in getattr(self.ventana, "target_videos", {}).values():
            if getattr(boton, "file_type", "") == "webcam" and int(getattr(boton, "webcam_index", -1)) == indice:
                return boton
        return None

    def _camara_abierta(self) -> bool:
        procesador = getattr(self.ventana, "video_processor", None)
        if procesador is None:
            return False
        if getattr(procesador, "file_type", "") not in {"webcam", "video", "image"}:
            return False
        captura = getattr(procesador, "media_capture", None)
        if captura in (None, False):
            return False
        abierto = getattr(captura, "isOpened", None)
        if callable(abierto):
            try:
                return bool(abierto())
            except Exception:
                return False
        return True

    def _escribir_control(self, clave: str, valor: object) -> None:
        control = por_clave().get(clave)
        if control is not None and control.tipo == "toggle":
            self._poner_toggle(clave, bool(valor))
            return
        self._poner_valor(clave, valor)

    def _aplicar_mapa(self, mapa: dict, guardar: bool = True) -> None:
        self._ajustes.update(mapa)
        ordenados = sorted(mapa.items(), key=lambda par: isinstance(par[1], bool))
        for clave, valor in ordenados:
            try:
                if clave == "LandmarkDetectToggle" and valor:
                    self._poner_valor("LandmarkDetectModelSelection", "orformer98")
                self._escribir_control(clave, valor)
            except Exception as exc:
                print(f"[AVISO] No se aplicó {clave}: {exc}")
        if guardar and self._cara_id:
            try:
                self.biblioteca.guardar_ajustes(self._cara_id, dict(self._ajustes))
            except Exception as exc:
                print(f"[AVISO] No se guardaron los ajustes de la cara: {exc}")
        if self.al_cargar is not None:
            try:
                self.al_cargar(dict(self._ajustes))
            except Exception as exc:
                print(f"[AVISO] No se pintaron los ajustes: {exc}")

    def _fijar_cambio(self, activo: bool) -> None:
        boton = self.ventana.swapfacesButton
        if boton.isChecked() == activo:
            return
        boton.click()

    def _poner_toggle(self, nombre: str, activo: bool) -> None:
        widget = (getattr(self.ventana, "parameter_widgets", None) or {}).get(nombre)
        if widget is not None and hasattr(widget, "isChecked"):
            if bool(widget.isChecked()) != bool(activo):
                widget.setChecked(bool(activo))
            return
        self._escribir(nombre, bool(activo))

    def _poner_valor(self, nombre: str, valor: object) -> None:
        widget = (getattr(self.ventana, "parameter_widgets", None) or {}).get(nombre)
        if widget is not None and hasattr(widget, "set_value"):
            es_lista = hasattr(widget, "setCurrentText") and hasattr(widget, "findData")
            if not es_lista:
                widget.blockSignals(True)
            try:
                widget.set_value(valor)
            except Exception:
                pass
            finally:
                if not es_lista:
                    widget.blockSignals(False)
            if es_lista:
                return
        self._escribir(nombre, valor)

    def _escribir(self, nombre: str, valor: object) -> None:
        from app.ui.widgets.actions import common_actions as comunes

        control = getattr(self.ventana, "control", {}) or {}
        if nombre in control:
            comunes.update_control(self.ventana, nombre, valor)
            return
        procesador = getattr(self.ventana, "video_processor", None)
        en_directo = bool(getattr(procesador, "processing", False))
        comunes.update_parameter(
            self.ventana,
            nombre,
            valor,
            enable_refresh_frame=not en_directo,
        )

    def _permite_60(self) -> bool:
        try:
            from app.drako.rendimiento.perfiles import resolver_perfil

            return bool(resolver_perfil(self.ventana.control).permite_60)
        except Exception:
            return False

    def _medicion(self) -> tuple[float | None, float | None]:
        procesador = getattr(self.ventana, "video_processor", None)
        cronometro = getattr(procesador, "cronometro_en_vivo", None)
        if cronometro is None:
            return None, None
        try:
            medida = cronometro.resumen()
        except Exception:
            return None, None
        if medida is None:
            return None, None
        return float(medida.fps), float(medida.latencia_ms)

    def _vram(self) -> str:
        try:
            import torch

            if not torch.cuda.is_available():
                return ""
            indice = int(getattr(self.ventana, "gpu_id", 0) or 0)
            libre, total = torch.cuda.mem_get_info(indice)
            usada = (total - libre) / (1024**3)
            return f"{usada:.1f} / {total / (1024**3):.0f} GB".replace(".", ",")
        except Exception:
            return ""

    def _proveedor(self) -> str:
        procesador = getattr(self.ventana, "models_processor", None)
        nombre = str(getattr(procesador, "provider_name", "") or "")
        if "tensor" in nombre.lower():
            return "TensorRT"
        if "cuda" in nombre.lower():
            return "CUDA"
        return nombre or "—"

    def _vigilante(self) -> str:
        procesador = getattr(self.ventana, "video_processor", None)
        vigilante = getattr(procesador, "vigilante", None)
        if vigilante is None:
            return "—"
        if getattr(vigilante, "proveedor_cambiado", False):
            return "CUDA"
        return "OK"

    def _vigilar_cara(self) -> str | None:
        if self.original:
            self._sin_cara = None
            return None
        detector = getattr(getattr(self.ventana, "video_processor", None), "sequential_detector", None)
        tiene = False
        if detector is not None:
            tiene = bool(getattr(detector, "_smoothed_kps", {}) or getattr(detector, "last_detected_faces", []))
        ahora = time.monotonic()
        if tiene:
            self._sin_cara = None
            return None
        if self._sin_cara is None:
            self._sin_cara = ahora
        return aviso_cara_perdida(self._sin_cara, ahora)
