"""Pruebas del envío de correo por Google Apps Script.

No se llama a Google: se sustituye httpx.post y se revisa qué se le habría
mandado y cómo se interpreta cada respuesta.

Lo que más importa aquí no es el camino feliz, sino que un fallo pasajero
—la cuota del día— se distinga de uno definitivo. Si se confunden, tres
límites de cuota seguidos marcan al cliente como no localizable y el sistema
deja de escribirle para siempre por algo que no fue culpa suya.
"""

from __future__ import annotations

import httpx
import pytest

from app.mensajeria.apps_script import (
    AdaptadorAppsScript,
    AppsScriptNoConfigurado,
)
from app.mensajeria.base import Mensaje
from app.modelos.recordatorio import ENTREGA_FALLIDA, EstadoEntrega

URL = "https://script.google.com/macros/s/AKfyABC123/exec"


class RespuestaFalsa:
    def __init__(self, status_code=200, datos=None, texto=None):
        self.status_code = status_code
        self._datos = datos
        self._texto = texto

    def json(self):
        if self._datos is None:
            raise ValueError("no es JSON")
        return self._datos


@pytest.fixture
def adaptador():
    return AdaptadorAppsScript(
        url=URL, token="secreto-largo",
        remitente="no-responder@verificentro.mx",
        nombre_remitente="Verificentro",
    )


@pytest.fixture
def mensaje():
    return Mensaje(
        destino="cliente@ejemplo.mx",
        asunto="Te toca verificar",
        cuerpo="Hola Ana.\n\nTu periodo abre el 1 de octubre.",
        clave_plantilla="aviso_2",
        enlace="https://verificentro.mx/r/9/abc",
        parrafos=("Hola Ana.", "Tu periodo abre el 1 de octubre."),
        pie=("Av. Ruíz Cortines 256",),
    )


def _responder(monkeypatch, respuesta):
    """Sustituye httpx.post y guarda con qué se llamó."""
    capturado = {}

    def falso_post(url, **kwargs):
        capturado["url"] = url
        capturado.update(kwargs)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(httpx, "post", falso_post)
    return capturado


# ------------------------------------------------------------ configuración --

def test_exige_la_url():
    with pytest.raises(AppsScriptNoConfigurado, match="APPS_SCRIPT_URL"):
        AdaptadorAppsScript(url="", token="t", remitente="a@b.mx")


def test_rechaza_la_url_de_pruebas():
    """La de /dev solo responde con la sesión del dueño abierta.

    Es un error fácil de cometer —las dos direcciones aparecen juntas en el
    editor— y el síntoma es confuso: funciona mientras lo pruebas tú y falla
    en el servidor.
    """
    with pytest.raises(AppsScriptNoConfigurado, match="/exec"):
        AdaptadorAppsScript(
            url="https://script.google.com/macros/s/AKfyABC123/dev",
            token="t", remitente="a@b.mx",
        )


def test_exige_el_token():
    with pytest.raises(AppsScriptNoConfigurado, match="APPS_SCRIPT_TOKEN"):
        AdaptadorAppsScript(url=URL, token="", remitente="a@b.mx")


# ------------------------------------------------------------------ envío --

def test_envia_y_devuelve_el_identificador(adaptador, mensaje, monkeypatch):
    capturado = _responder(
        monkeypatch, RespuestaFalsa(datos={"ok": True, "id": "uuid-1", "restantes": 87})
    )

    resultado = adaptador.enviar(mensaje)

    assert resultado.exito
    assert resultado.id_externo == "uuid-1"
    assert capturado["url"] == URL


def test_manda_el_token_y_el_contenido(adaptador, mensaje, monkeypatch):
    capturado = _responder(monkeypatch, RespuestaFalsa(datos={"ok": True}))

    adaptador.enviar(mensaje)
    cuerpo = capturado["json"]

    assert cuerpo["token"] == "secreto-largo"
    assert cuerpo["para"] == "cliente@ejemplo.mx"
    assert cuerpo["asunto"] == "Te toca verificar"
    assert "Tu periodo abre el 1 de octubre." in cuerpo["texto"]
    assert cuerpo["responder_a"] == "no-responder@verificentro.mx"


def test_el_html_trae_el_enlace_como_boton(adaptador, mensaje, monkeypatch):
    """Mismo cuerpo HTML que por SMTP: el correo se ve igual salga por donde salga."""
    capturado = _responder(monkeypatch, RespuestaFalsa(datos={"ok": True}))

    adaptador.enviar(mensaje)
    html = capturado["json"]["html"]

    assert 'href="https://verificentro.mx/r/9/abc"' in html
    assert "Consultar mi periodo" in html
    assert "Av. Ruíz Cortines 256" in html


def test_sigue_la_redireccion(adaptador, mensaje, monkeypatch):
    """Apps Script contesta 302 hacia googleusercontent y la respuesta de
    verdad está del otro lado. Sin seguir el redirect no llega nada."""
    capturado = _responder(monkeypatch, RespuestaFalsa(datos={"ok": True}))

    adaptador.enviar(mensaje)

    assert capturado["follow_redirects"] is True


# ------------------------------------------------------------------ fallos --

def test_la_cuota_agotada_no_quema_al_contacto(adaptador, mensaje, monkeypatch):
    _responder(monkeypatch, RespuestaFalsa(
        datos={"ok": False, "error": "Se agotó la cuota diaria de correo de Google."}
    ))

    resultado = adaptador.enviar(mensaje)

    assert not resultado.exito
    assert resultado.codigo == "rebote_suave"
    assert EstadoEntrega(resultado.codigo) not in ENTREGA_FALLIDA


def test_la_red_caida_no_quema_al_contacto(adaptador, mensaje, monkeypatch):
    _responder(monkeypatch, httpx.ConnectError("sin red"))

    resultado = adaptador.enviar(mensaje)

    assert not resultado.exito
    assert resultado.codigo == "rebote_suave"
    assert EstadoEntrega(resultado.codigo) not in ENTREGA_FALLIDA


def test_un_error_del_script_si_es_definitivo(adaptador, mensaje, monkeypatch):
    _responder(monkeypatch, RespuestaFalsa(
        datos={"ok": False, "error": "Invalid email: no-es-un-correo"}
    ))

    resultado = adaptador.enviar(mensaje)

    assert not resultado.exito
    assert resultado.codigo == "fallido"
    assert "Invalid email" in resultado.error


def test_token_rechazado(adaptador, mensaje, monkeypatch):
    _responder(monkeypatch, RespuestaFalsa(datos={"ok": False, "error": "Token inválido."}))

    resultado = adaptador.enviar(mensaje)

    assert not resultado.exito
    assert "Token" in resultado.error


def test_respuesta_html_explica_que_falta_autorizar(adaptador, mensaje, monkeypatch):
    """Sin autorizar el script, Google devuelve una página, no JSON.

    Es el tropiezo más común al conectarlo, así que el mensaje tiene que
    decir qué hacer y no solo que falló.
    """
    _responder(monkeypatch, RespuestaFalsa(datos=None))

    resultado = adaptador.enviar(mensaje)

    assert not resultado.exito
    assert "autorización" in resultado.error


def test_acceso_restringido_se_explica(adaptador, mensaje, monkeypatch):
    _responder(monkeypatch, RespuestaFalsa(status_code=403))

    resultado = adaptador.enviar(mensaje)

    assert not resultado.exito
    assert "Cualquier persona" in resultado.error
