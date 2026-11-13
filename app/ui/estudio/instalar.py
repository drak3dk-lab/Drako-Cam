"""Sustituye la ventana heredada por la pantalla sencilla.

Si algo falla aquí, la ventana de VisoMaster se queda como estaba.
El motor de cambio de cara no se toca.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app.drako.rutas import directorio_datos
from app.ui.estudio.biblioteca import Biblioteca
from app.ui.estudio.motor import MotorEnVivo
from app.ui.estudio.panel import Estudio


def instalar(ventana) -> bool:
    try:
        estudio = Estudio()
        biblioteca = Biblioteca(directorio_datos())
        biblioteca.asegurar()
        motor = MotorEnVivo(ventana, biblioteca)
        _conectar(estudio, motor)
        vista = ventana.graphicsViewFrame
        vista.setParent(None)
        estudio.adoptar_vista(vista)
        vista.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        vista.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        vista.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        vista.setStyleSheet("background: #050608; border: none;")
        for muelle in (
            getattr(ventana, "input_Target_DockWidget", None),
            getattr(ventana, "input_Faces_DockWidget", None),
            getattr(ventana, "jobManagerDockWidget", None),
            getattr(ventana, "controlOptionsDockWidget", None),
        ):
            if muelle is not None:
                muelle.hide()
        _ocultar_menus_heredados(ventana)
        _quitar_lo_que_no_es_la_camara(ventana)
        from app.ui.estudio.ojo import icono

        ventana.setWindowIcon(icono())
        ventana.setWindowTitle("Drako Cam")
        ventana.setCentralWidget(estudio)
        ventana.setMinimumSize(1100, 720)
        if ventana.width() < 1280 or ventana.height() < 800:
            ventana.resize(1440, 900)
        ventana._estudio = estudio
        ventana._motor_estudio = motor
        _refrescar(estudio, motor)
        motor.arrancar()
        temporizador = QtCore.QTimer(estudio)
        temporizador.setInterval(400)
        temporizador.timeout.connect(lambda: _refrescar(estudio, motor))
        temporizador.start()
        estudio._reloj_estado = temporizador
        if not biblioteca.estado().get("obs_visto"):
            QtCore.QTimer.singleShot(900, lambda: _mostrar_asistente(estudio, motor))
        return True
    except Exception as exc:
        print(f"[AVISO] La pantalla sencilla no se abrió. Sigue la ventana anterior. {exc}")
        return False


def _conectar(estudio: Estudio, motor: MotorEnVivo) -> None:
    estudio.pedir_fotos.connect(lambda rutas: _hacer(estudio, motor, lambda: motor.anadir_fotos(list(rutas))))
    estudio.pedir_cara.connect(lambda ident: _hacer(estudio, motor, lambda: motor.elegir_cara(ident) or ""))
    estudio.pedir_favorita.connect(
        lambda ident, activa: _hacer(estudio, motor, lambda: motor.fijar_favorita(ident, activa) or "")
    )
    estudio.pedir_camara.connect(lambda indice: _hacer(estudio, motor, lambda: motor.elegir_camara(indice)))
    estudio.pedir_en_vivo.connect(lambda activo: _hacer(estudio, motor, lambda: motor.poner_en_vivo(activo)))
    estudio.pedir_original.connect(lambda original: _hacer(estudio, motor, lambda: motor.ver_original(original) or ""))
    estudio.pedir_virtual.connect(lambda activa: _hacer(estudio, motor, lambda: motor.camara_virtual(activa) or ""))
    estudio.pedir_probar_salida.connect(lambda: _hacer(estudio, motor, lambda: motor.probar_salida() or ""))
    estudio.pedir_ventana_salida.connect(
        lambda: _hacer(estudio, motor, lambda: motor.alternar_ventana_salida() or "")
    )
    estudio.pedir_asistente_obs.connect(lambda: _mostrar_asistente(estudio, motor))
    estudio.pedir_calidad.connect(lambda nombre: _hacer(estudio, motor, lambda: motor.poner_calidad(nombre) or ""))
    estudio.pedir_aspecto.connect(lambda ident: _hacer(estudio, motor, lambda: motor.poner_aspecto(ident) or ""))
    estudio.pedir_perfil.connect(lambda ident: _hacer(estudio, motor, lambda: motor.aplicar_perfil(ident) or ""))
    estudio.pedir_guardar_perfil.connect(
        lambda nombre: _hacer(estudio, motor, lambda: motor.guardar_perfil(nombre) or "")
    )
    estudio.pedir_accion_perfil.connect(
        lambda ident, accion, extra: _hacer(
            estudio, motor, lambda: motor.accion_perfil(ident, accion, extra) or ""
        )
    )
    estudio.pedir_fuerza.connect(lambda valor: _hacer(estudio, motor, lambda: motor.poner_fuerza(valor) or ""))
    estudio.pedir_nitidez.connect(lambda valor: _hacer(estudio, motor, lambda: motor.poner_nitidez(valor) or ""))
    estudio.pedir_frente.connect(lambda valor: _hacer(estudio, motor, lambda: motor.poner_frente(valor) or ""))
    estudio.pedir_fps.connect(lambda fps: _hacer(estudio, motor, lambda: motor.poner_fps(fps) or ""))
    estudio.pedir_fondo.connect(lambda nombre: _hacer(estudio, motor, lambda: motor.poner_fondo(nombre) or ""))
    estudio.pedir_toggle.connect(
        lambda nombre, activo: _hacer(estudio, motor, lambda: motor.poner_toggle(nombre, activo) or "")
    )
    estudio.pedir_ajuste.connect(
        lambda clave, valor: _hacer(estudio, motor, lambda: motor.poner_ajuste(clave, valor) or "")
    )
    estudio.pedir_control.connect(
        lambda clave, valor: _hacer(estudio, motor, lambda: motor.poner_control(clave, valor) or "")
    )
    motor.al_cargar = estudio.ajustes.fijar


def _hacer(estudio: Estudio, motor: MotorEnVivo, accion) -> None:
    try:
        accion()
    except Exception as exc:
        motor.mensaje = "No pude hacerlo. Prueba otra vez."
        print(f"[AVISO] Pantalla sencilla: {exc}")
    _refrescar(estudio, motor)


def _refrescar(estudio: Estudio, motor: MotorEnVivo) -> None:
    try:
        caras, seleccion = motor.caras()
        estudio.mostrar_caras(caras, seleccion)
        estudio.mostrar_camaras(motor.camaras(), motor.indice_camara())
        estudio.mostrar_perfiles(motor.perfiles())
        estado = motor.estado()
        estudio.mostrar_estado(
            sesion=bool(estado["cambio_activo"]),
            en_vivo=bool(estado["en_vivo"]),
            original=bool(estado["original"]),
            tiene_foto=bool(estado["tiene_foto"]),
            tiene_camara=bool(estado["tiene_camara"]),
            fps=estado["fps"],
            latencia_ms=estado["latencia_ms"],
            vram=str(estado["vram"] or ""),
            proveedor=str(estado["proveedor"]),
            vigilante=str(estado["vigilante"]),
            mensaje=str(estado["mensaje"] or ""),
            calidad_nota=str(estado["calidad_nota"]),
            virtual=bool(estado["virtual"]),
            salida_texto=str(estado.get("salida_texto") or ""),
            salida_detalle=str(estado.get("salida_detalle") or ""),
            ventana_abierta=bool(estado.get("ventana_abierta")),
            resolucion=str(estado["resolucion"]),
            fps_salida=str(estado["fps_salida"]),
            fondo=str(estado["fondo"]),
        )
    except Exception as exc:
        print(f"[AVISO] No se pudo refrescar la pantalla: {exc}")


def _quitar_lo_que_no_es_la_camara(ventana) -> None:
    """Find Faces y abrir un vídeo o una imagen como objetivo no forman parte del producto."""
    boton = getattr(ventana, "findTargetFacesButton", None)
    if boton is not None:
        try:
            boton.clicked.disconnect()
        except Exception:
            pass
        boton.setEnabled(False)
        boton.hide()
        boton.setParent(None)
    for nombre in ("buttonTargetVideosPath", "buttonInputFacesPath"):
        otro = getattr(ventana, nombre, None)
        if otro is None:
            continue
        try:
            otro.clicked.disconnect()
        except Exception:
            pass
        otro.setEnabled(False)


def _mostrar_asistente(estudio: Estudio, motor: MotorEnVivo) -> None:
    from app.ui.estudio.asistente_obs import AsistenteObs

    dialogo = AsistenteObs(motor._estado_obs(), estudio)
    dialogo.probar.connect(lambda: _probar(dialogo, motor))
    dialogo.pedir_ventana.connect(lambda: motor.abrir_ventana_salida())
    dialogo.finished.connect(lambda _codigo: motor.biblioteca.recordar(obs_visto=True))
    dialogo.exec()


def _probar(dialogo, motor: MotorEnVivo) -> None:
    try:
        dialogo.marcar_prueba(motor.probar_salida())
    except Exception as exc:
        dialogo.marcar_prueba(f"No pude probar la salida. {exc}")


def _ocultar_menus_heredados(ventana) -> None:
    barra = ventana.menuBar()
    for menu in (getattr(ventana, "menuFile", None), getattr(ventana, "menuEdit", None), getattr(ventana, "menuView", None), getattr(ventana, "menuHelp", None)):
        if menu is not None:
            barra.removeAction(menu.menuAction())
