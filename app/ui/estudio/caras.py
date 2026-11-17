"""Cara del directo sin botones de la interfaz heredada.

El pipeline solo necesita el identificador, el embedding de quien está
en cámara y el embedding de la foto. Esos datos viven aquí. Si un
QPushButton del editor ya se borró, se quita del diccionario: tocarlo
cierra el programa.
"""

from __future__ import annotations

MENSAJE_PREPARANDO = "Preparando…"
MENSAJE_FOTO_MALA = "No pude leer la foto. Prueba con otra, de frente y con luz."

MOTORES_DIRECTO = (
    ("RetinaFace", "detector de caras"),
    ("Inswapper128ArcFace", "lector de caras"),
    ("Inswapper128", "cambio de cara"),
    ("GFPGANv1.4", "realce"),
    ("FaceParser", "máscara de zonas"),
    ("Occluder", "oclusión"),
)


def texto_motor(indice: int, total: int, etiqueta: str) -> str:
    return (
        f"Preparando el motor TensorRT ({indice}/{total}): {etiqueta}… "
        "La primera vez puede tardar unos minutos"
    )


def paso_lectura(
    *,
    hay_embedding: bool,
    en_curso: bool,
    termino: bool,
    excepcion: bool,
) -> str:
    """Qué hacer mientras se lee una foto.

    ``activar`` cuando el embedding ya está.
    ``esperar`` mientras sigue en curso: no hay tope de tiempo.
    ``error`` solo si la lectura terminó sin cara o con una excepción.
    """
    if hay_embedding:
        return "activar"
    if en_curso or not termino:
        return "esperar"
    return "error"


class CicloCara:
    """Una foto, su lectura y si ya se puede aplicar. Sin Qt."""

    def __init__(self) -> None:
        self.foto: str | None = None
        self.embedding = None
        self.en_curso = False
        self.termino = False
        self.excepcion: str | None = None
        self.aplicadas: list[str] = []

    def nueva_foto(self, ident: str) -> None:
        self.foto = ident
        self.embedding = None
        self.en_curso = True
        self.termino = False
        self.excepcion = None

    def listo(self, embedding) -> None:
        self.embedding = embedding
        self.en_curso = False
        self.termino = True
        self.excepcion = None

    def sin_cara(self) -> None:
        self.embedding = None
        self.en_curso = False
        self.termino = True

    def fallo(self, texto: str) -> None:
        self.embedding = None
        self.en_curso = False
        self.termino = True
        self.excepcion = texto

    def paso(self) -> str:
        return paso_lectura(
            hay_embedding=self.embedding is not None,
            en_curso=self.en_curso,
            termino=self.termino,
            excepcion=self.excepcion is not None,
        )

    def marcar_aplicada(self) -> None:
        if self.foto:
            self.aplicadas.append(self.foto)


def es_widget(obj) -> bool:
    try:
        from PySide6.QtCore import QObject
    except ImportError:
        return False
    return isinstance(obj, QObject)


def quitar_muertos(diccionario) -> int:
    """Quita envoltorios cuyo objeto C++ ya no existe. Devuelve cuántos."""
    if not isinstance(diccionario, dict):
        return 0
    from app.ui.qt_vivo import qt_sigue

    muertos = [
        clave
        for clave, valor in list(diccionario.items())
        if es_widget(valor) and not qt_sigue(valor)
    ]
    for clave in muertos:
        del diccionario[clave]
    return len(muertos)


def _vector(valor):
    try:
        import numpy as np

        arr = np.asarray(valor, dtype=np.float32).reshape(-1)
    except Exception:
        return None
    if arr.size < 32:
        return None
    return arr


class CaraEnVivo:
    """Destino del directo. No es un botón."""

    def __init__(self, face_id: str, embedding_store: dict):
        self.face_id = str(face_id)
        self.embedding_store = dict(embedding_store or {})
        self.cropped_face = None
        self.assigned_input_faces: dict = {}
        self.assigned_merged_embeddings: dict = {}
        self.assigned_input_embedding: dict = {}
        self.assigned_kv_map = None
        self.main_window = None

    def get_embedding(self, modelo: str):
        import numpy as np

        valor = _vector(self.embedding_store.get(modelo))
        if valor is None:
            return np.array([])
        return valor

    def calculate_assigned_input_embedding(self) -> None:
        import numpy as np

        control = {}
        ventana = self.main_window
        if ventana is not None and isinstance(getattr(ventana, "control", None), dict):
            control = ventana.control
        tiendas = list(self.assigned_input_faces.values()) + list(
            self.assigned_merged_embeddings.values()
        )
        modelos: set[str] = set()
        for tienda in tiendas:
            if isinstance(tienda, dict):
                modelos.update(clave for clave, valor in tienda.items() if _vector(valor) is not None)
        if not modelos:
            self.assigned_input_embedding = {}
            return
        metodo = str(control.get("EmbMergeMethodSelection", "Mean"))
        salida = {}
        for modelo in modelos:
            vectores = []
            for tienda in tiendas:
                if not isinstance(tienda, dict):
                    continue
                vector = _vector(tienda.get(modelo))
                if vector is None:
                    continue
                norma = float(np.linalg.norm(vector))
                vectores.append(vector / norma if norma > 0 else vector)
            if not vectores:
                continue
            if metodo == "Median":
                fusion = np.median(vectores, axis=0)
            else:
                fusion = np.mean(vectores, axis=0)
            norma = float(np.linalg.norm(fusion))
            if norma > 0:
                fusion = fusion / norma
            salida[modelo] = fusion
        self.assigned_input_embedding = salida
