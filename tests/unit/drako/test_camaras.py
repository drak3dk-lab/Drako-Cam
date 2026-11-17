"""El desplegable usa el nombre del dispositivo y distingue cámara ocupada."""

from app.drako.camaras import (
    MENSAJE_AUSENTE,
    MENSAJE_OCUPADA,
    mensaje_de_fallo,
    nombres_de_camaras,
    nombres_desde_ffmpeg,
)


def test_ffmpeg_separa_video_de_audio():
    texto = """
[dshow] "Integrated Webcam" (video)
[dshow] "Microphone (Realtek)" (audio)
[dshow] "NVIDIA Broadcast" (video)
[dshow] "OBS Virtual Camera" (video)
"""
    assert nombres_desde_ffmpeg(texto) == [
        "Integrated Webcam",
        "NVIDIA Broadcast",
        "OBS Virtual Camera",
    ]


def test_el_lector_de_prueba_conserva_el_orden():
    nombres = nombres_de_camaras(
        lector=lambda: ["Integrated Webcam", "NVIDIA Broadcast", ""]
    )
    assert nombres == ["Integrated Webcam", "NVIDIA Broadcast"]


class _Captura:
    def __init__(self, abierta=True, frames=None, se_rompe_al_pedir_tamano=False):
        self._abierta = abierta
        self._frames = list(frames or [])
        self.se_rompe = False
        self._rompe_si_piden_tamano = se_rompe_al_pedir_tamano
        self.ancho = 640
        self.alto = 480
        self.fps = 30

    def isOpened(self):
        return self._abierta

    def read(self):
        if self.se_rompe or not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def set(self, prop, valor):
        if self._rompe_si_piden_tamano:
            self.se_rompe = True
            self._frames.clear()
        return True

    def get(self, prop):
        return {3: self.ancho, 4: self.alto, 5: self.fps}.get(prop, 0)

    def release(self):
        self._abierta = False


def test_en_windows_directshow_va_primero_y_reintenta_el_frame(monkeypatch):
    monkeypatch.setattr("app.drako.camaras.os.name", "nt")
    intentos = []

    def abrir(indice, backend):
        intentos.append((indice, backend))
        if backend == 700:
            raise RuntimeError("MSMF no está")
        if backend == 300:
            return _Captura(frames=[None, None, "frame-dshow"])
        return _Captura(abierta=False)

    def leer(captura):
        ok, frame = captura.read()
        return frame if ok else None

    from app.drako.camaras import abrir_webcam

    apertura = abrir_webcam(
        0,
        abrir=abrir,
        leer=leer,
        esperar=lambda _s: None,
        soltar=lambda captura: captura.release() if captura else None,
        backends=[("DirectShow", 300), ("MSMF", 700), ("Default", 0)],
    )
    assert apertura is not None
    assert apertura.backend == "DirectShow"
    assert apertura.primer_frame == "frame-dshow"
    assert intentos[0] == (0, 300)
    assert "DirectShow" in apertura.informe


def test_no_fuerza_el_formato_aunque_pidan_tamano_y_fps():
    ajustes = []

    class _Nativa(_Captura):
        def set(self, prop, valor):
            ajustes.append((prop, valor))
            return True

    def abrir(indice, backend):
        return _Nativa(frames=["nativo"])

    def leer(captura):
        ok, frame = captura.read()
        return frame if ok else None

    from app.drako.camaras import abrir_webcam

    apertura = abrir_webcam(
        1,
        1920,
        1080,
        60,
        abrir=abrir,
        leer=leer,
        esperar=lambda _s: None,
        soltar=lambda captura: None,
        backends=[("DirectShow", 300)],
    )
    assert apertura is not None
    assert apertura.primer_frame == "nativo"
    assert ajustes == []
    assert "sin MJPG" in apertura.informe


def test_si_directshow_abre_no_prueba_otro_backend():
    vistos = []

    def abrir(indice, backend):
        vistos.append(backend)
        return _Captura(abierta=True, frames=[])

    from app.drako.camaras import abrir_webcam, ultimo_fallo

    apertura = abrir_webcam(
        0,
        abrir=abrir,
        leer=lambda captura: None,
        esperar=lambda _s: None,
        soltar=lambda captura: captura.release() if captura else None,
        backends=[("DirectShow", 300), ("MSMF", 700), ("Default", 0)],
    )
    assert apertura is None
    assert vistos == [300]
    assert "otro backend" in ultimo_fallo()
    assert "MSMF" not in ultimo_fallo()


def test_el_registro_anota_indice_backend_y_fotograma(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="drako")

    def leer(captura):
        ok, frame = captura.read()
        return frame if ok else None

    from app.drako.camaras import abrir_webcam

    apertura = abrir_webcam(
        0,
        abrir=lambda indice, backend: _Captura(frames=["ok"]),
        leer=leer,
        esperar=lambda _s: None,
        soltar=lambda captura: None,
        backends=[("DirectShow", 300)],
    )
    assert apertura is not None
    assert "índice 0" in caplog.text
    assert "DirectShow" in caplog.text
    assert "abierta=sí" in caplog.text
    assert "primer fotograma=sí" in caplog.text
    assert "resolución" in caplog.text


def test_ocupada_solo_si_el_error_es_de_acceso():
    assert mensaje_de_fallo("device or resource busy", True) == MENSAJE_OCUPADA
    assert mensaje_de_fallo("access is denied", True) == MENSAJE_OCUPADA
    assert mensaje_de_fallo("", False) == MENSAJE_AUSENTE
    concreto = mensaje_de_fallo(
        "Cámara índice 0, backend DirectShow (700): abierta=no, error OpenCV: no device",
        True,
    )
    assert concreto != MENSAJE_OCUPADA
    assert "no device" in concreto
    assert "OBS" in MENSAJE_OCUPADA
    assert MENSAJE_OCUPADA != MENSAJE_AUSENTE
