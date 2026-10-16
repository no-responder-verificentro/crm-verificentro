"""Pruebas de Mailjet: envío por API y acuses por webhook.

El caso que motivó todo esto está en
`TestEnvio::test_un_rechazo_de_mailjet_si_se_reporta` y en
`TestWebhook::test_bloqueo_por_contenido_se_marca_como_spam`.

Por SMTP, Mailjet contesta `250 OK` en el acto y *después* pasa el mensaje por
su filtro antispam. Si decide descartarlo —"spam pre-blocked"— nosotros ya
habíamos reportado el envío como exitoso. El recordatorio quedaba en
«Enviado», nadie recibía nada y no había ningún error que ver. Estas pruebas
fijan que eso deje de poder pasar: por API el rechazo viene en la respuesta,
y lo que Mailjet decide más tarde llega por webhook.
"""

from __future__ import annotations

from datetime import date, datetime

import httpx
import pytest

from app.mensajeria.base import Mensaje
from app.mensajeria.mailjet import AdaptadorMailjet, MailjetNoConfigurado
from app.modelos.cliente import Cliente, EstadoContacto, OrigenConsentimiento
from app.modelos.recordatorio import (
    ENTREGA_FALLIDA,
    Canal,
    EstadoEntrega,
    EstadoRecordatorio,
    Recordatorio,
    TipoRecordatorio,
)
from app.modelos.vehiculo import Vehiculo

SECRETO = "secreto-del-webhook"


class RespuestaFalsa:
    def __init__(self, status_code=200, datos=None):
        self.status_code = status_code
        self._datos = datos

    def json(self):
        if self._datos is None:
            raise ValueError("no es JSON")
        return self._datos


@pytest.fixture
def adaptador():
    return AdaptadorMailjet(
        api_key="llave", api_secret="secreto",
        remitente="avisos@verificentro.mx", nombre_remitente="Verificentro",
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
    capturado = {}

    def falso_post(url, **kwargs):
        capturado["url"] = url
        capturado.update(kwargs)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(httpx, "post", falso_post)
    return capturado


def _exito(message_id=112233):
    return {"Messages": [{"Status": "success",
                          "To": [{"Email": "cliente@ejemplo.mx",
                                  "MessageID": message_id,
                                  "MessageUUID": "abc-def"}]}]}


# =========================================================== envío por API ==

class TestEnvio:

    def test_exige_credenciales(self):
        with pytest.raises(MailjetNoConfigurado, match="MAILJET_API_KEY"):
            AdaptadorMailjet("", "", "a@b.mx")

    def test_guarda_el_message_id_para_el_webhook(self, adaptador, mensaje,
                                                  monkeypatch):
        """Sin el MessageID, los eventos que lleguen después no se pueden
        vincular con ningún recordatorio."""
        _responder(monkeypatch, RespuestaFalsa(datos=_exito(112233)))

        resultado = adaptador.enviar(mensaje)

        assert resultado.exito
        assert resultado.id_externo == "112233"

    def test_manda_texto_y_html(self, adaptador, mensaje, monkeypatch):
        """Un correo solo-HTML puntúa peor en los filtros antispam, que es
        justo lo que estamos tratando de evitar."""
        capturado = _responder(monkeypatch, RespuestaFalsa(datos=_exito()))

        adaptador.enviar(mensaje)
        envio = capturado["json"]["Messages"][0]

        assert "Tu periodo abre el 1 de octubre." in envio["TextPart"]
        assert 'href="https://verificentro.mx/r/9/abc"' in envio["HTMLPart"]
        assert envio["From"]["Email"] == "avisos@verificentro.mx"
        assert envio["Headers"]["List-Unsubscribe"]

    def test_un_rechazo_de_mailjet_si_se_reporta(self, adaptador, mensaje,
                                                monkeypatch):
        """Lo que por SMTP se perdía: el 250 llegaba igual y lo dábamos por
        enviado."""
        _responder(monkeypatch, RespuestaFalsa(datos={
            "Messages": [{
                "Status": "error",
                "Errors": [{"ErrorCode": "mj-0013",
                            "ErrorMessage": '"cliente@ejemplo.mx" is an invalid email address.'}],
            }]
        }))

        resultado = adaptador.enviar(mensaje)

        assert not resultado.exito
        assert "invalid email address" in resultado.error
        assert resultado.codigo == "fallido"

    def test_credenciales_malas_se_explican(self, adaptador, mensaje, monkeypatch):
        _responder(monkeypatch, RespuestaFalsa(status_code=401))

        resultado = adaptador.enviar(mensaje)

        assert not resultado.exito
        assert "MAILJET_API_KEY" in resultado.error

    def test_la_red_caida_no_quema_al_contacto(self, adaptador, mensaje,
                                               monkeypatch):
        _responder(monkeypatch, httpx.ConnectError("sin red"))

        resultado = adaptador.enviar(mensaje)

        assert EstadoEntrega(resultado.codigo) not in ENTREGA_FALLIDA


# ================================================================ webhook ==

def _escenario(sesion_bd, id_externo="112233", niv="3VWRA81H2PM024517",
               placa="XPL-381-C"):
    """Un recordatorio ya enviado, listo para recibir su acuse."""
    with sesion_bd() as s:
        cliente = Cliente(
            nombre="Ana Sofía Mendoza", telefono_e164="+522281452207",
            correo="ana@ejemplo.mx", consent_correo=True, consent_whatsapp=False,
            consent_origen=OrigenConsentimiento.MOSTRADOR,
            estado_contacto=EstadoContacto.CONTACTABLE,
        )
        s.add(cliente)
        s.flush()
        vehiculo = Vehiculo(
            cliente_id=cliente.id, placa=placa, niv=niv,
            activo=True, en_programa_estatal=True,
        )
        s.add(vehiculo)
        s.flush()
        recordatorio = Recordatorio(
            vehiculo_id=vehiculo.id, cliente_id=cliente.id,
            tipo=TipoRecordatorio.VENTANA, aviso_clave="aviso_2",
            ventana_anio=date.today().year, ventana_periodo=2,
            canal=Canal.CORREO, destino="ana@ejemplo.mx",
            programado_para=datetime(date.today().year, 10, 1, 9, 0),
            estado=EstadoRecordatorio.ENVIADO,
            estado_entrega=EstadoEntrega.ENVIADO,
            id_externo=id_externo,
        )
        s.add(recordatorio)
        s.commit()
        return cliente.id, recordatorio.id


class TestWebhook:

    RUTA = f"/webhooks/mailjet/{SECRETO}"

    @pytest.fixture(autouse=True)
    def _secreto(self, monkeypatch):
        from app.config import obtener_config

        monkeypatch.setattr(obtener_config(), "mailjet_webhook_secreto", SECRETO)

    def _estado(self, sesion_bd, recordatorio_id):
        with sesion_bd() as s:
            return s.get(Recordatorio, recordatorio_id).estado_entrega

    def test_rechaza_un_secreto_equivocado(self, api):
        r = api.post("/webhooks/mailjet/no-es-el-secreto",
                     json=[{"event": "sent", "MessageID": 1}])
        assert r.status_code == 403

    def test_sent_significa_entregado(self, api, sesion_bd):
        """En Mailjet 'sent' quiere decir que el servidor del destinatario lo
        aceptó, no que nosotros lo mandamos: eso ya se sabía."""
        _, rec = _escenario(sesion_bd)

        api.post(self.RUTA, json=[{"event": "sent", "MessageID": 112233,
                                   "time": 1760000000}])

        assert self._estado(sesion_bd, rec) is EstadoEntrega.ENTREGADO

    def test_bloqueo_por_contenido_se_marca_como_spam(self, api, sesion_bd):
        """El caso que nos tenía a ciegas.

        Mailjet decide que el servidor del destinatario lo marcaría, no lo
        manda, y antes eso era indistinguible de un envío bueno.
        """
        _, rec = _escenario(sesion_bd)

        api.post(self.RUTA, json=[{
            "event": "blocked", "MessageID": 112233,
            "error_related_to": "content",
            "error": "preblocked",
        }])

        with sesion_bd() as s:
            r = s.get(Recordatorio, rec)
            assert r.estado_entrega is EstadoEntrega.SPAM
            assert "preblocked" in r.motivo_error

    def test_otro_bloqueo_es_fallido_normal(self, api, sesion_bd):
        _, rec = _escenario(sesion_bd)

        api.post(self.RUTA, json=[{
            "event": "blocked", "MessageID": 112233,
            "error_related_to": "recipient", "error": "duplicate in campaign",
        }])

        assert self._estado(sesion_bd, rec) is EstadoEntrega.FALLIDO

    def test_rebote_duro_y_suave_se_distinguen(self, api, sesion_bd):
        _, rec = _escenario(sesion_bd)
        api.post(self.RUTA, json=[{"event": "bounce", "MessageID": 112233,
                                   "hard_bounce": True, "error": "user unknown"}])
        assert self._estado(sesion_bd, rec) is EstadoEntrega.REBOTE_DURO

        _, rec2 = _escenario(sesion_bd, id_externo="445566",
                             niv="1HGCM82633A004352", placa="YUN-047-A")
        api.post(self.RUTA, json=[{"event": "bounce", "MessageID": 445566,
                                   "hard_bounce": False, "error": "mailbox full"}])
        assert self._estado(sesion_bd, rec2) is EstadoEntrega.REBOTE_SUAVE

    def test_el_clic_es_el_dato_confiable(self, api, sesion_bd):
        _, rec = _escenario(sesion_bd)

        api.post(self.RUTA, json=[{"event": "click", "MessageID": 112233,
                                   "url": "https://verificentro.mx/consulta"}])

        assert self._estado(sesion_bd, rec) is EstadoEntrega.CLIC

    def test_la_apertura_no_mueve_nada(self, api, sesion_bd):
        """El pixel de apertura lo bloquean o lo precargan casi todos los
        clientes de correo, así que ni su presencia ni su ausencia dicen nada."""
        _, rec = _escenario(sesion_bd)

        api.post(self.RUTA, json=[{"event": "open", "MessageID": 112233}])

        assert self._estado(sesion_bd, rec) is EstadoEntrega.ENVIADO

    def test_la_baja_apaga_el_consentimiento(self, api, sesion_bd):
        """Seguir escribiéndole a quien pidió dejar de recibir es la vía más
        rápida a que reporte spam, y eso castiga la entrega de todos."""
        cliente_id, rec = _escenario(sesion_bd)

        api.post(self.RUTA, json=[{"event": "unsub", "MessageID": 112233}])

        with sesion_bd() as s:
            assert s.get(Cliente, cliente_id).consent_correo is False
            assert s.get(Recordatorio, rec).estado_entrega is EstadoEntrega.BAJA

    def test_un_evento_de_otro_sistema_se_ignora(self, api, sesion_bd):
        _escenario(sesion_bd)

        r = api.post(self.RUTA, json=[{"event": "sent", "MessageID": 999999}])

        assert r.status_code == 200
        assert r.json()["procesados"] == 0

    def test_acepta_un_evento_suelto_y_tambien_agrupados(self, api, sesion_bd):
        """Mailjet manda las dos formas según cómo esté configurado."""
        _, rec = _escenario(sesion_bd)

        r = api.post(self.RUTA, json={"event": "sent", "MessageID": 112233})

        assert r.json()["procesados"] == 1
        assert self._estado(sesion_bd, rec) is EstadoEntrega.ENTREGADO

    def test_siempre_responde_200(self, api):
        """Con cualquier otra cosa, Mailjet reintenta el lote completo."""
        assert api.post(self.RUTA, content=b"no es json").status_code == 200
        assert api.post(self.RUTA, json=[{"sin": "evento"}]).status_code == 200

    def test_repetir_el_mismo_evento_no_hace_dano(self, api, sesion_bd):
        _, rec = _escenario(sesion_bd)
        evento = [{"event": "click", "MessageID": 112233}]

        api.post(self.RUTA, json=evento)
        api.post(self.RUTA, json=evento)

        assert self._estado(sesion_bd, rec) is EstadoEntrega.CLIC

    def test_un_evento_atrasado_no_retrocede(self, api, sesion_bd):
        _, rec = _escenario(sesion_bd)

        api.post(self.RUTA, json=[{"event": "click", "MessageID": 112233}])
        api.post(self.RUTA, json=[{"event": "sent", "MessageID": 112233}])

        assert self._estado(sesion_bd, rec) is EstadoEntrega.CLIC
