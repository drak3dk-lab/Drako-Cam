"""Cliente de Telegram simulado: sin red, sin configuración y reintento."""

from app.drako.telegram_cliente import (
    ClienteTelegram,
    ErrorConfiguracion,
    ErrorDeRed,
    credenciales_telegram,
)


class TransporteSimulado:
    def __init__(self):
        self.fallar_red = False
        self.rechazar = False
        self.enviados = []

    def enviar(self, token, chat_id, texto):
        if self.fallar_red:
            raise ErrorDeRed("sin red")
        if self.rechazar:
            raise ErrorConfiguracion("token no válido")
        self.enviados.append((token, chat_id, texto))


def test_sin_credenciales_no_falla_ni_encola(tmp_path):
    transporte = TransporteSimulado()
    cliente = ClienteTelegram("", "", transporte, tmp_path / "cola.json")
    assert cliente.avisar("Equipo encendido") == "omitido"
    assert cliente.reintentar() == 0
    assert not (tmp_path / "cola.json").exists()
    assert transporte.enviados == []


def test_sin_red_encola_y_reintenta(tmp_path):
    transporte = TransporteSimulado()
    transporte.fallar_red = True
    cliente = ClienteTelegram(
        "bot-de-prueba", "chat-de-prueba", transporte, tmp_path / "cola.json"
    )
    assert cliente.avisar("aviso uno") == "encolado"
    assert cliente.avisar("aviso dos") == "encolado"
    cola = (tmp_path / "cola.json").read_text(encoding="utf-8")
    assert "aviso uno" in cola and "aviso dos" in cola
    assert "bot-de-prueba" not in cola
    assert cliente.reintentar() == 0

    transporte.fallar_red = False
    assert cliente.reintentar() == 2
    assert [item[2] for item in transporte.enviados] == ["aviso uno", "aviso dos"]
    assert json_pendientes(tmp_path / "cola.json") == []


def test_un_fallo_de_red_a_medias_conserva_el_resto(tmp_path):
    transporte = TransporteSimulado()
    cliente = ClienteTelegram(
        "bot-de-prueba", "chat-de-prueba", transporte, tmp_path / "cola.json"
    )
    transporte.fallar_red = True
    cliente.avisar("primero")
    cliente.avisar("segundo")
    llamadas = {"n": 0}

    def enviar(token, chat_id, texto):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return None
        raise ErrorDeRed("se cayó")

    transporte.enviar = enviar
    transporte.fallar_red = False
    assert cliente.reintentar() == 1
    assert json_pendientes(tmp_path / "cola.json") == ["segundo"]


def test_configuracion_rechazada_no_se_encola(tmp_path):
    transporte = TransporteSimulado()
    transporte.rechazar = True
    cliente = ClienteTelegram(
        "bot-de-prueba", "chat-de-prueba", transporte, tmp_path / "cola.json"
    )
    assert cliente.avisar("no debe encolarse") == "error_configuracion"
    assert not (tmp_path / "cola.json").exists()


def test_el_entorno_tiene_prioridad_sobre_el_archivo():
    config = {"telegram": {"bot_token": "en-archivo", "chat_id": "archivo-chat"}}
    assert credenciales_telegram(config, {}) == ("en-archivo", "archivo-chat")
    entorno = {
        "DRAKO_CAM_TELEGRAM_BOT_TOKEN": "desde-entorno",
        "DRAKO_CAM_TELEGRAM_CHAT_ID": "chat-entorno",
    }
    assert credenciales_telegram(config, entorno) == ("desde-entorno", "chat-entorno")
    assert credenciales_telegram({}, {}) == ("", "")


def json_pendientes(ruta):
    import json

    return json.loads(ruta.read_text(encoding="utf-8"))["pendientes"]
