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


def test_ocupada_no_es_lo_mismo_que_no_hay_camara():
    assert aviso_si_no_abre(True) == MENSAJE_OCUPADA
    assert aviso_si_no_abre(False) == MENSAJE_AUSENTE
    assert "OBS" in MENSAJE_OCUPADA
    assert "NVIDIA Broadcast" in MENSAJE_OCUPADA
    assert MENSAJE_OCUPADA != MENSAJE_AUSENTE
