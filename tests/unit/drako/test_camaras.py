"""El desplegable usa el nombre del dispositivo y distingue cámara ocupada."""

from app.drako.camaras import (
    MENSAJE_AUSENTE,
    MENSAJE_OCUPADA,
    aviso_si_no_abre,
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


def test_si_la_resolucion_mata_la_imagen_vuelve_al_tamano_nativo():
    creadas = []

    def abrir(indice, backend):
        captura = _Captura(frames=["nativo", "nativo2"], se_rompe_al_pedir_tamano=True)
        creadas.append(captura)
        return captura

    def leer(captura):
        ok, frame = captura.read()
        return frame if ok else None

    from app.drako.camaras import abrir_webcam

    apertura = abrir_webcam(
        1,
        1920,
        1080,
        abrir=abrir,
        leer=leer,
        esperar=lambda _s: None,
        soltar=lambda captura: None,
        backends=[("DirectShow", 300)],
    )
    assert apertura is not None
    assert "nativa" in apertura.informe
    assert len(creadas) == 2


def test_ocupada_no_es_lo_mismo_que_no_hay_camara():
    assert aviso_si_no_abre(True) == MENSAJE_OCUPADA
    assert aviso_si_no_abre(False) == MENSAJE_AUSENTE
    assert "OBS" in MENSAJE_OCUPADA
    assert "NVIDIA Broadcast" in MENSAJE_OCUPADA
    assert MENSAJE_OCUPADA != MENSAJE_AUSENTE
