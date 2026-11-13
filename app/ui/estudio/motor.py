"""Conecta la pantalla sencilla con el motor que ya existe.

Foto o perfil, y EN VIVO. La cara de enfrente se elige sola.
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


class _CaraPerfil:
    def __init__(self, ident: str, ruta: Path):
        self.id = ident
        self.ruta = Path(ruta)
        self.nombre = self.ruta.stem
        self.favorita = False


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
        self._aspecto = str(self.biblioteca.estado().get("aspecto") or "auto")
        self._perfil_id = ""
        self._ruta_perfil: Path | None = None
        self._todas = False
        self._persona = "principal"
        self.ventana._estudio_activo = True
        self._sin_cara: float | None = None
        self._loader = None
        self._entrando = False
        self._reintentos = 0
        self._virtual = bool(self.biblioteca.estado().get("camara_virtual") or False)
        self._salida_activa = False
        self._ventana_salida = None
        self._reloj_salida = QtCore.QTimer()
        self._reloj_salida.setInterval(33)
        self._reloj_salida.timeout.connect(self._empujar_ventana)
        self._obs_cache: tuple[float, object] | None = None
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
        self._ruta_perfil = None
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
            from app.drako.rendimiento.emision import fijar_prioridad

            fijar_prioridad(False)
            return ""
        foto = self._foto_seleccionada()
        if foto is not None and not self._camara_abierta() and self.camaras():
            self.elegir_camara(max(self.indice_camara(), 0))
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
        if activa:
            self._encender_salida()
            return
        self._virtual = False
        self.biblioteca.recordar(camara_virtual=False)
        self._poner_toggle("SendVirtCamFramesEnableToggle", False)
        procesador = getattr(self.ventana, "video_processor", None)
        if procesador is not None and hasattr(procesador, "disable_virtualcam"):
            try:
                procesador.disable_virtualcam()
            except Exception:
                pass
        self._salida_activa = self._ventana_salida is not None and self._ventana_salida.isVisible()

    def _estado_obs(self):
        from app.drako.rendimiento.obs_salida import detectar, procesos_windows

        ahora = time.monotonic()
        if self._obs_cache and ahora - self._obs_cache[0] < 3:
            return self._obs_cache[1]
        estado = detectar(procesos=procesos_windows())
        self._obs_cache = (ahora, estado)
        return estado

    def _encender_salida(self) -> str:
        from app.drako.rendimiento.emision import fijar_prioridad

        estado = self._estado_obs()
        fijar_prioridad(True)
        if estado.eleccion.backend:
            self._poner_valor("VirtCamBackendSelection", estado.eleccion.backend)
            self._virtual = True
            self.biblioteca.recordar(camara_virtual=True)
            self._poner_toggle("SendVirtCamFramesEnableToggle", True)
            procesador = getattr(self.ventana, "video_processor", None)
            if procesador is not None and hasattr(procesador, "enable_virtualcam"):
                try:
                    procesador.enable_virtualcam(backend=estado.eleccion.backend)
                except Exception as exc:
                    self.mensaje = f"No pude abrir la cámara virtual. {exc}"
        else:
            self.abrir_ventana_salida()
        self._salida_activa = True
        self.mensaje = "" if estado.eleccion.backend else estado.eleccion.motivo
        return self.texto_salida()

    def abrir_ventana_salida(self) -> None:
        from app.drako.rendimiento.camara_virtual import ConfiguracionSalida
        from app.ui.estudio.ventana_salida import VentanaSalida

        cfg = ConfiguracionSalida.desde_control(getattr(self.ventana, "control", {}))
        if self._ventana_salida is None:
            self._ventana_salida = VentanaSalida(cfg.ancho, cfg.alto)
            self._ventana_salida.aviso.connect(self._aviso_ventana)
        else:
            self._ventana_salida.fijar_tamano(cfg.ancho, cfg.alto)
        self._ventana_salida.show()
        self._ventana_salida.raise_()
        self._reloj_salida.start()
        self._salida_activa = True

    def _aviso_ventana(self, texto: str) -> None:
        self.mensaje = texto

    def _empujar_ventana(self) -> None:
        if self._ventana_salida is None or not self._ventana_salida.isVisible():
            return
        procesador = getattr(self.ventana, "video_processor", None)
        frame = getattr(procesador, "current_frame", None) if procesador else None
        if frame is None:
            return
        self._ventana_salida.mostrar_frame(frame)

    def probar_salida(self) -> str:
        texto = self._encender_salida()
        procesador = getattr(self.ventana, "video_processor", None)
        if procesador is None or getattr(procesador, "virtcam", None) is not None:
            return texto or "Salida activa. En OBS debe verse la imagen."
        from app.drako.rendimiento.camara_virtual import ConfiguracionSalida
        from app.drako.rendimiento.obs_salida import fotograma_prueba

        cfg = ConfiguracionSalida.desde_control(getattr(self.ventana, "control", {}))
        frame = fotograma_prueba(cfg.ancho, cfg.alto)
        try:
            procesador.current_frame = frame
            procesador.send_frame_to_virtualcam(frame)
        except Exception as exc:
            self.mensaje = f"No pude probar la salida. {exc}"
            return self.mensaje
        if getattr(procesador, "virtcam", None) is None:
            self.abrir_ventana_salida()
            self._ventana_salida.mostrar_frame(frame)
            return "No se abrió la cámara virtual. Dejé la ventana de salida con una prueba."
        return "Salida activa. En OBS debe verse un recuadro claro."

    def texto_salida(self) -> str:
        from app.drako.rendimiento.obs_salida import texto_indicador

        estado = self._estado_obs()
        procesador = getattr(self.ventana, "video_processor", None)
        abierto = bool(getattr(procesador, "virtcam", None))
        ventana = self._ventana_salida is not None and self._ventana_salida.isVisible()
        return texto_indicador(
            dispositivo_abierto=abierto or self._virtual,
            obs_en_marcha=estado.obs_en_marcha,
            ventana=ventana,
        )

    def detalle_salida(self) -> str:
        from app.drako.rendimiento.camara_virtual import ConfiguracionSalida

        cfg = ConfiguracionSalida.desde_control(getattr(self.ventana, "control", {}))
        nombre = self._estado_obs().eleccion.nombre or "ventana de salida"
        return f"{cfg.ancho}×{cfg.alto} · {cfg.fps} FPS · {nombre}"

    def poner_calidad(self, nombre: str) -> None:
        self._calidad = nombre
        self.biblioteca.recordar(calidad=nombre)
        ajuste = ajuste_calidad(nombre, self._permite_60())
        self.nota_calidad = ajuste.nota
        if self._salida_activa:
            self.mensaje = "La resolución y los FPS se quedan fijos mientras OBS recibe."
        else:
            if ajuste.resolucion:
                self._poner_valor("WebcamMaxResSelection", ajuste.resolucion)
            if ajuste.fps:
                self._poner_valor("WebCamMaxFPSSelection", ajuste.fps)
        if ajuste.deteccion_cada is not None:
            self._poner_valor("DeteccionCadaNSlider", ajuste.deteccion_cada)
            self._poner_toggle("DeteccionInteligenteEnableToggle", True)
        from app.ui.estudio.controles import CLAVES_RENDIMIENTO

        completo = valores_de_calidad(nombre, self._permite_60())
        self._aplicar_mapa(
            {clave: valor for clave, valor in completo.items() if clave in CLAVES_RENDIMIENTO}
        )
        if ajuste.resolucion or ajuste.fps:
            if self._salida_activa:
                return
            posicion = self.indice_camara()
            if posicion >= 0 and self._camara_abierta():
                self.elegir_camara(posicion)

    def poner_aspecto(self, ident: str) -> str:
        from app.drako.perfiles.aspecto import valores_de_aspecto

        self._aspecto = ident
        self.biblioteca.recordar(aspecto=ident)
        if ident == "auto":
            return self.analizar_aspecto()
        self._aplicar_mapa(valores_de_aspecto(ident))
        self.mensaje = ""
        return ""

    def analizar_aspecto(self) -> str:
        from app.drako.perfiles.aspecto import (
            fraccion_barba,
            luminancia_piel,
            valores_sugeridos,
        )

        rgb, etiquetas = self._muestra_de_cara()
        if rgb is None:
            self.mensaje = "Elige una foto para sugerir el aspecto."
            return self.mensaje
        luz = luminancia_piel(rgb, etiquetas)
        mapa, frase = valores_sugeridos(luz, fraccion_barba(etiquetas))
        self._aspecto = "auto"
        self._aplicar_mapa(mapa)
        self.mensaje = frase
        return frase

    def guardar_perfil(self, nombre: str) -> str:
        from app.drako.perfiles.almacen import AlmacenPerfiles
        from app.drako.rutas import directorio_perfiles
        from app.ui.estudio.controles import por_clave

        fotos = self._fotos_elegidas()
        if not fotos:
            self.mensaje = "Elige al menos una foto para el perfil."
            return self.mensaje
        almacen = AlmacenPerfiles(directorio_perfiles())
        perfil = almacen.crear(
            nombre,
            dict(self._ajustes),
            getattr(self, "_aspecto", "auto"),
            self._calidad,
            fotos,
            self._embedding_medio(),
            set(por_clave()),
        )
        self._perfil_id = perfil.id
        self.mensaje = f"Perfil guardado: {perfil.nombre}"
        return ""

    def aplicar_perfil(self, ident: str) -> str:
        from app.drako.perfiles.almacen import AlmacenPerfiles
        from app.drako.rutas import directorio_perfiles

        perfil = AlmacenPerfiles(directorio_perfiles()).cargar(ident)
        self._perfil_id = perfil.id
        self._ruta_perfil = perfil.fotos[0] if perfil.fotos else None
        self._aspecto = perfil.aspecto
        self._calidad = perfil.calidad
        self._aplicar_mapa(perfil.ajustes, guardar=False)
        for foto in perfil.fotos:
            self._pedir_embedding(foto)
        self._fundir_perfil(perfil)
        self.mensaje = perfil.nombre
        return ""

    def accion_perfil(self, ident: str, accion: str, extra: str = "") -> str:
        from app.drako.perfiles.almacen import AlmacenPerfiles
        from app.drako.rutas import directorio_perfiles

        almacen = AlmacenPerfiles(directorio_perfiles())
        if accion == "renombrar":
            almacen.renombrar(ident, extra)
        elif accion == "duplicar":
            almacen.duplicar(ident)
        elif accion == "favorito":
            almacen.favorito(ident, extra == "1")
        elif accion == "borrar":
            if self._perfil_id == ident:
                self._perfil_id = ""
                self._ruta_perfil = None
            almacen.borrar(ident)
        elif accion == "exportar" and extra:
            almacen.exportar(ident, Path(extra))
            self.mensaje = "Perfil exportado."
        elif accion == "importar" and extra:
            from app.ui.estudio.controles import por_clave

            perfil = almacen.importar(Path(extra), set(por_clave()))
            self.mensaje = f"Perfil importado: {perfil.nombre}"
        return ""

    def perfiles(self) -> list[tuple[str, str, str, bool]]:
        from app.drako.perfiles.almacen import AlmacenPerfiles
        from app.drako.rutas import directorio_perfiles

        return [
            (perfil.id, perfil.nombre, str(perfil.miniatura or ""), perfil.favorito)
            for perfil in AlmacenPerfiles(directorio_perfiles()).listar()
        ]

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
        if self._salida_activa:
            self.mensaje = "Los FPS se quedan fijos mientras OBS recibe."
            return
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
            self._todas = bool(activo)
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
        elif clave == "persona":
            texto = str(valor)
            if "izquierda" in texto:
                self._persona = "izquierda"
            elif "derecha" in texto:
                self._persona = "derecha"
            else:
                self._persona = "principal"
            if self.en_vivo:
                self._aplicar_cara(redetectar=True)
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
            "virtual": virtual or self._salida_activa,
            "salida_texto": self.texto_salida() if self._salida_activa or virtual else "APAGADA",
            "salida_detalle": self.detalle_salida(),
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
        self._encender_salida()
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
            self.mensaje = MENSAJE_CARGANDO
            self._pedir_embedding(foto.ruta)
            self._reintentar_si_sigue()
            return
        self._marcar_entrada(boton)
        if redetectar or not getattr(self.ventana, "target_faces", None):
            self._poner_valor("MaxFacesToDetectSlider", 5)
            try:
                from app.ui.widgets.actions import card_actions

                card_actions.find_target_faces(self.ventana)
            except Exception as exc:
                self.mensaje = f"No pude detectar la cara. {exc}"
                self._reintentar_si_sigue()
                return
            finally:
                if not self._todas:
                    self._poner_valor("MaxFacesToDetectSlider", 1)
        caras = list(getattr(self.ventana, "target_faces", {}).values())
        if not caras:
            self.mensaje = "No te veo. Ponte frente a la cámara."
            self._reintentar_si_sigue()
            return
        elegidas = self._elegir_destinos(caras)
        for destino in caras:
            if destino in elegidas:
                destino.assigned_input_faces = {boton.face_id: boton.embedding_store}
            else:
                destino.assigned_input_faces.clear()
            try:
                destino.calculate_assigned_input_embedding()
            except Exception:
                pass
        principal = elegidas[0]
        self.ventana.selected_target_face_id = principal.face_id
        self.ventana.cur_selected_target_face_button = principal
        self.mensaje = ""

    def _elegir_destinos(self, caras: list):
        from app.ui.estudio.logica import indice_persona

        if self._todas:
            return caras
        cajas_guardadas = getattr(self.ventana, "_cajas_destino", {}) or {}
        marco = getattr(self.ventana, "_marco_destino", (1280, 720)) or (1280, 720)
        con_caja = [
            (cara, cajas_guardadas[cara.face_id])
            for cara in caras
            if cara.face_id in cajas_guardadas
        ]
        if not con_caja:
            return [caras[0]]
        indice = indice_persona(
            [caja for _, caja in con_caja],
            float(marco[0]),
            float(marco[1]),
            self._persona,
        )
        return [con_caja[indice][0]]

    def _reintentar_si_sigue(self) -> None:
        if self.en_vivo:
            QtCore.QTimer.singleShot(800, self._reintentar_deteccion)

    def _reintentar_deteccion(self) -> None:
        if self.en_vivo and self._foto_seleccionada() is not None:
            self._aplicar_cara(redetectar=True)

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

    def _muestra_de_cara(self):
        foto = self._foto_seleccionada()
        if foto is None:
            return None, None
        try:
            import numpy as np
            from PySide6.QtGui import QImage

            imagen = QImage(str(foto.ruta)).convertToFormat(QImage.Format.Format_RGB888)
            if imagen.isNull():
                return None, None
            ancho, alto = imagen.width(), imagen.height()
            linea = int(imagen.bytesPerLine())
            buf = np.frombuffer(imagen.constBits(), dtype=np.uint8, count=alto * linea)
            rgb = np.ascontiguousarray(buf.reshape(alto, linea)[:, : ancho * 3]).reshape(
                alto, ancho, 3
            )
            return rgb, self._etiquetas(rgb)
        except Exception:
            return None, None

    def _etiquetas(self, rgb):
        try:
            import numpy as np
            import torch
            from torchvision.transforms import v2

            tensor = torch.from_numpy(np.ascontiguousarray(rgb)).permute(2, 0, 1)
            tensor = v2.functional.resize(tensor.unsqueeze(0), [512, 512]).squeeze(0)
            mascaras = self.ventana.models_processor.face_masks
            # El parser vive en el worker de máscaras, si ya está cargado.
            worker = getattr(self.ventana, "function_worker", None)
            etiquetas = None
            if worker is not None and hasattr(worker, "face_masks"):
                etiquetas = worker.face_masks._faceparser_labels(tensor)
            elif mascaras is not None:
                etiquetas = mascaras._faceparser_labels(tensor)
            if etiquetas is None:
                return None
            return etiquetas.detach().cpu().numpy()
        except Exception:
            return None

    def _fotos_elegidas(self) -> list:
        foto = self._foto_seleccionada()
        return [foto.ruta] if foto is not None else []

    def _embedding_medio(self):
        foto = self._foto_seleccionada()
        if foto is None:
            return None
        boton = self._boton_entrada(foto.ruta)
        if boton is None:
            return None
        almacen = getattr(boton, "embedding_store", None) or {}
        for vector in almacen.values():
            try:
                import numpy as np

                return np.asarray(vector, dtype=np.float32).reshape(-1).tolist()
            except Exception:
                continue
        return None

    def _embedding_activo(self):
        import numpy as np

        for destino in getattr(self.ventana, "target_faces", {}).values():
            vectores = getattr(destino, "assigned_input_embedding", None) or {}
            for vector in vectores.values():
                return np.asarray(vector, dtype=np.float32).reshape(-1)
        return None

    def _escribir_embedding(self, vector) -> None:
        for destino in getattr(self.ventana, "target_faces", {}).values():
            actual = getattr(destino, "assigned_input_embedding", None)
            if not isinstance(actual, dict) or not actual:
                continue
            clave = next(iter(actual))
            actual[clave] = vector

    def _fundir_perfil(self, perfil) -> None:
        from app.drako.perfiles.fader import mezclar, pasos

        anterior = self._embedding_activo()
        nuevo = None
        if perfil.embedding:
            import numpy as np

            nuevo = np.asarray(perfil.embedding, dtype=np.float32)
        if anterior is None or nuevo is None or anterior.shape != nuevo.shape:
            QtCore.QTimer.singleShot(700, lambda: self._asignar_fotos(perfil))
            return

        secuencia = pasos(8)

        def paso(indice: int = 0) -> None:
            if indice >= len(secuencia):
                self._asignar_fotos(perfil)
                return
            self._escribir_embedding(mezclar(anterior, nuevo, secuencia[indice]))
            QtCore.QTimer.singleShot(50, lambda indice=indice + 1: paso(indice))

        paso()

    def _asignar_fotos(self, perfil) -> None:
        botones = [self._boton_entrada(foto) for foto in perfil.fotos]
        botones = [boton for boton in botones if boton is not None]
        if not botones:
            return
        caras = list(getattr(self.ventana, "target_faces", {}).values())
        if not caras:
            self._cara_id = botones[0].face_id if hasattr(botones[0], "face_id") else self._cara_id
            return
        for destino in caras:
            destino.assigned_input_faces = {
                boton.face_id: boton.embedding_store for boton in botones
            }
            try:
                destino.calculate_assigned_input_embedding()
            except Exception:
                pass

    def _foto_seleccionada(self):
        if self._ruta_perfil is not None:
            return _CaraPerfil(self._perfil_id or "perfil", self._ruta_perfil)
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
