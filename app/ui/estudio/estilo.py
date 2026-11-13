"""Tokens de la dirección Halo, aplicados solo a la pantalla nueva.

El cian #5CE1F0 es la luz de lo que está en directo. El resto es
tinta clara sobre un escenario casi negro.
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
    padding-left: 44px;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 1px;
    background: #F1F4F9;
    color: #04060A;
    border: none;
}
#Estudio QPushButton#enVivo[vivo="true"] {
    background: #5CE1F0;
    color: #041014;
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
    color: #041014;
    background: #5CE1F0;
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
#Estudio QCheckBox {
    color: #F1F4F9;
    spacing: 8px;
    min-height: 36px;
    font-size: 14px;
}
#Estudio QCheckBox::indicator {
    width: 18px;
    height: 18px;
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
