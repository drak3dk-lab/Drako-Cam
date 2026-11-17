"""Tokens de la dirección Halo, aplicados solo a la pantalla nueva.

El rojo #F20A1C, el del ojo del logo, marca solo lo que está en directo
y el foco. El resto es tinta clara sobre un escenario casi negro.
"""

ESTILO = """
#Estudio {
    background: #04060A;
    color: #F1F4F9;
    font-family: "Geist", "Segoe UI", "Inter", sans-serif;
    font-size: 14px;
}
#Estudio QLabel {
    background: transparent;
    color: #F1F4F9;
}
#Estudio QLabel#secundario, #Estudio QLabel#pista {
    color: #B7C0CE;
}
#Estudio QLabel#marcaSub {
    color: #B7C0CE;
    font-weight: 500;
    letter-spacing: 0.5px;
}
#Estudio QLabel#marca {
    font-weight: 700;
    letter-spacing: 2px;
    font-size: 13px;
}
#Estudio QLabel#tituloPanel {
    font-size: 18px;
    font-weight: 650;
}
#Estudio QLabel#numero {
    font-family: "Geist Mono", "Cascadia Mono", "Consolas", monospace;
    font-size: 13px;
}
#Estudio QPushButton {
    min-height: 44px;
    border-radius: 22px;
    padding: 0 16px;
    font-weight: 600;
    font-size: 14px;
    color: #F1F4F9;
    background: #121620;
    border: 1px solid rgba(160, 190, 255, 0.16);
}
#Estudio QPushButton:hover {
    background: #1A1F2B;
}
#Estudio QPushButton:disabled {
    color: #8E97A6;
}
#Estudio QPushButton#enVivo {
    min-height: 52px;
    min-width: 180px;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 1px;
    background: #F1F4F9;
    color: #04060A;
    border: none;
}
#Estudio QPushButton#enVivo[vivo="true"] {
    background: #F20A1C;
    color: #FFF6F6;
}
#Estudio QComboBox:focus, #Estudio QLineEdit:focus {
    border: 1px solid rgba(242, 10, 28, 0.85);
}
#Estudio QPushButton#anadirFoto {
    border: 1px dashed rgba(160, 190, 255, 0.35);
    background: transparent;
    color: #F1F4F9;
}
#Estudio QPushButton#compacto, #Estudio QPushButton#copiarObs {
    min-height: 44px;
}
#Estudio QPushButton#copiarObs {
    background: #F1F4F9;
    color: #04060A;
    border: none;
}
#Estudio QPushButton#segmento {
    min-height: 36px;
    border-radius: 18px;
    background: transparent;
    border: none;
    color: #B7C0CE;
    font-weight: 600;
}
#Estudio QPushButton#segmento:checked {
    background: #1A1F2B;
    color: #F1F4F9;
    border: 1px solid rgba(160, 190, 255, 0.16);
}
#Estudio QPushButton#segmento[vivo="true"]:checked {
    color: #FFF6F6;
    background: #F20A1C;
    border: none;
}
#Estudio QComboBox, #Estudio QSlider {
    min-height: 36px;
    font-size: 16px;
    color: #F1F4F9;
    background: #0B0E14;
    border: 1px solid rgba(160, 190, 255, 0.16);
    border-radius: 12px;
    padding: 0 10px;
}
#Estudio QPushButton#refrescar {
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    padding: 0;
    font-size: 18px;
    color: #F1F4F9;
    background: #0B0E14;
    border: 1px solid rgba(160, 190, 255, 0.16);
    border-radius: 12px;
}
#Estudio QComboBox::drop-down {
    border: none;
    width: 28px;
}
#Estudio QComboBox QAbstractItemView {
    background: #121620;
    color: #F1F4F9;
    selection-background-color: #1A1F2B;
    selection-color: #F1F4F9;
    font-size: 16px;
}
#Estudio QScrollArea {
    background: transparent;
    border: none;
}
#Estudio QScrollArea > QWidget > QWidget {
    background: transparent;
}
#Estudio QCheckBox {
    color: #F1F4F9;
    spacing: 8px;
    min-height: 36px;
    font-size: 14px;
}
#Estudio QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid rgba(160, 190, 255, 0.40);
    background: #0B0E14;
}
#Estudio QCheckBox::indicator:checked {
    background: #F1F4F9;
    border-color: #F1F4F9;
}
#Estudio QCheckBox#interruptorGrupo {
    font-size: 15px;
    font-weight: 650;
    min-height: 40px;
}
#Estudio QCheckBox#interruptorGrupo[activo="false"] {
    color: #8E97A6;
    font-weight: 600;
}
#Estudio QCheckBox#interruptorGrupo[activo="true"] {
    color: #F1F4F9;
}
#Estudio QWidget#grupoAjuste {
    background: transparent;
    border-top: 1px solid rgba(160, 190, 255, 0.10);
}
#Estudio QToolButton#plegar {
    min-height: 44px;
    padding: 0 12px;
    font-size: 14px;
    font-weight: 650;
    text-align: left;
    color: #F1F4F9;
    background: #121620;
    border: 1px solid rgba(160, 190, 255, 0.16);
    border-radius: 12px;
}
#Estudio QToolButton#plegar:hover,
#Estudio QToolButton#plegar:checked {
    background: #1A1F2B;
}
#Estudio QToolButton#plegar:focus {
    border: 1px solid rgba(242, 10, 28, 0.85);
}
#Estudio QToolButton#restablecer {
    min-height: 36px;
    padding: 0 12px;
    font-size: 13px;
    font-weight: 600;
    color: #F1F4F9;
    background: #121620;
    border: 1px solid rgba(160, 190, 255, 0.16);
    border-radius: 8px;
}
#Estudio QToolButton#restablecer:hover {
    background: #1A1F2B;
}
#Estudio QToolButton#restablecer:focus {
    border: 1px solid rgba(242, 10, 28, 0.85);
}
#Estudio QScrollArea#scrollAjustes {
    background: transparent;
    border: none;
}
#barraEstado {
    background: #04060A;
    color: #B7C0CE;
    border-top: 1px solid rgba(160, 190, 255, 0.08);
}
#columnaObs {
    background: #0B0E14;
    border-left: 1px solid rgba(160, 190, 255, 0.08);
}
#railFavoritos {
    background: #04060A;
    border-right: 1px solid rgba(160, 190, 255, 0.08);
}
"""
