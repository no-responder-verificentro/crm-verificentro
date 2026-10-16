"""Pruebas de WhatsApp: envío por plantilla y webhook de acuses.

Todo corre contra una Cloud API falsa. No sale ni una petición a Meta, pero sí
se arma la petición completa y se revisa lo que se habría mandado.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime

import httpx
import pytest

from app.dominio.calendario import fechas_de_aviso, ventanas_del_anio
from app.mensajeria.base import Mensaje
from app.mensajeria.whatsapp import AdaptadorWhatsApp, WhatsAppNoConfigurado
from app.modelos.cliente import Cliente, EstadoContacto, OrigenConsentimiento
from app.modelos.recordatorio import Canal, EstadoEntrega, Recordatorio
from app.modelos.vehiculo import Vehiculo
from app.servicios import recordatorios as servicio

ANIO = date.today().year
WEBHOOK = "/webhooks/whatsapp"
WAMID = "wamid.HBgNNTIyMjgxMDA5NTg0FQIAERgSMUEyQjNDNEQ1RTZGN0c4SDkA"


class RespuestaFalsa:
    def __init__(self, status_code: int, datos: dict):
        self.status_code = status_code
        self._datos = datos

    def json(self):
        return self._datos


@pytest.fixture
def adaptador():
    return AdaptadorWhatsApp(token="TOKEN", phone_id="123456", idioma="es_MX")


def _mensaje(**cambios) -> Mensaje:
    base = dict(
        destino="+522281009584", asunto=None,
        cuerpo="Hola Ana. Te toca verificar.", clave_plantilla="aviso_4",
        plantilla_meta="verificentro_ultimos_dias",
        parametros=("Ana", "YUN-047-A", "30 de septiembre"),
    )
    base.update(cambios)
    return Mensaje(**base)


# ------------------------------------------------------------------ envío ---

class TestEnvio:
    def test_sin_credenciales_no_arranca(self):
        with pytest.raises(WhatsAppNoConfigurado):
            AdaptadorWhatsApp(token="", phone_id="")

    def test_manda_plantilla_y_no_texto_libre(self, adaptador, monkeypatch):
        """Meta no acepta texto libre cuando nosotros iniciamos: va el nombre
        de la plantilla aprobada y sus variables por separado."""
        capturado = {}

        def falso_post(url, json=None, headers=None, timeout=None):
            capturado["url"] = url
            capturado["cuerpo"] = json
            capturado["headers"] = headers
            return RespuestaFalsa(200, {"messages": [{"id": WAMID}]})

        monkeypatch.setattr(httpx, "post", falso_post)
        resultado = adaptador.enviar(_mensaje())

        assert resultado.exito
        assert resultado.id_externo == WAMID

        cuerpo = capturado["cuerpo"]
        assert cuerpo["type"] == "template"
        assert cuerpo["template"]["name"] == "verificentro_ultimos_dias"
        assert cuerpo["template"]["language"]["code"] == "es_MX"
        assert [p["text"] for p in cuerpo["template"]["components"][0]["parameters"]] \
            == ["Ana", "YUN-047-A", "30 de septiembre"]
        # Meta pide el número sin el signo de más.
        assert cuerpo["to"] == "522281009584"
        assert capturado["headers"]["Authorization"] == "Bearer TOKEN"

    def test_sin_plantilla_registrada_falla_con_mensaje_claro(self, adaptador):
        resultado = adaptador.enviar(_mensaje(plantilla_meta=None))
        assert not resultado.exito
        assert "PLANTILLAS_META" in resultado.error

    def test_numero_sin_whatsapp(self, adaptador, monkeypatch):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: RespuestaFalsa(
            400, {"error": {"code": 131026, "message": "Message undeliverable"}}))
        resultado = adaptador.enviar(_mensaje())
        assert not resultado.exito
        assert resultado.codigo == "fallido"
        assert "no tiene WhatsApp" in resultado.error

    def test_plantilla_no_aprobada(self, adaptador, monkeypatch):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: RespuestaFalsa(
            400, {"error": {"code": 132001, "message": "Template not found"}}))
        resultado = adaptador.enviar(_mensaje())
        assert "no está aprobada" in resultado.error

    def test_el_limite_de_envios_es_reintentable(self, adaptador, monkeypatch):
        """No es culpa del contacto: marcarlo como fallido definitivo lo
        quemaría injustamente."""
        monkeypatch.setattr(httpx, "post", lambda *a, **k: RespuestaFalsa(
            429, {"error": {"code": 130429, "message": "Rate limit hit"}}))
        assert adaptador.enviar(_mensaje()).codigo == "reintentar"

    def test_si_meta_no_responde_tampoco_se_quema_el_contacto(
        self, adaptador, monkeypatch
    ):
        def truena(*a, **k):
            raise httpx.ConnectError("sin red")

        monkeypatch.setattr(httpx, "post", truena)
        resultado = adaptador.enviar(_mensaje())
        assert resultado.codigo == "reintentar"

    def test_el_usuario_que_se_dio_de_baja(self, adaptador, monkeypatch):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: RespuestaFalsa(
            400, {"error": {"code": 131050, "message": "User stopped"}}))
        assert adaptador.enviar(_mensaje()).codigo == "baja"


# ------------------------------------------------------- alta del webhook ---

class TestVerificacionDelWebhook:
    def test_devuelve_el_reto_con_el_token_correcto(self, api, monkeypatch):
        from app.config import obtener_config

        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "mi-token-secreto")
        obtener_config.cache_clear()
        try:
            r = api.get(WEBHOOK, params={
                "hub.mode": "subscribe",
                "hub.verify_token": "mi-token-secreto",
                "hub.challenge": "1234567890",
            })
            assert r.status_code == 200
            assert r.text == "1234567890"
        finally:
            obtener_config.cache_clear()

    def test_rechaza_un_token_equivocado(self, api, monkeypatch):
        from app.config import obtener_config

        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "mi-token-secreto")
        obtener_config.cache_clear()
        try:
            r = api.get(WEBHOOK, params={
                "hub.mode": "subscribe", "hub.verify_token": "otro",
                "hub.challenge": "123",
            })
            assert r.status_code == 403
        finally:
            obtener_config.cache_clear()


# ------------------------------------------------------------- acuses ---

def _sobre_acuse(wamid: str, estado: str, errores=None) -> dict:
    acuse = {"id": wamid, "status": estado, "timestamp": "1789260000",
             "recipient_id": "522281009584"}
    if errores:
        acuse["errors"] = errores
    return {"object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"statuses": [acuse]}}]}]}


@pytest.fixture
def con_envio(api, sesion_bd):
    """Un recordatorio de WhatsApp ya enviado, con su wamid guardado."""
    with sesion_bd() as s:
        cliente = Cliente(
            nombre="Ana Karen Domínguez", telefono_e164="+522281009584",
            consent_whatsapp=True, consent_correo=False,
            consent_origen=OrigenConsentimiento.MOSTRADOR,
            estado_contacto=EstadoContacto.CONTACTABLE,
        )
        s.add(cliente)
        s.flush()
        s.add(Vehiculo(cliente_id=cliente.id, niv="3N1CB51S62K222173",
                       placa="YUN-047-A"))
        s.commit()

    _, ventana = ventanas_del_anio(7, ANIO)
    with sesion_bd() as s:
        servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
        servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1), silencioso=True)
    with sesion_bd() as s:
        r = s.query(Recordatorio).filter_by(canal=Canal.WHATSAPP).one()
        r.id_externo = WAMID
        s.commit()
    return api, sesion_bd


class TestAcuses:
    def _estado(self, sesion_bd):
        with sesion_bd() as s:
            return s.query(Recordatorio).filter_by(
                canal=Canal.WHATSAPP).one().estado_entrega

    def test_entregado_y_leido_avanzan(self, con_envio):
        api, sesion_bd = con_envio

        api.post(WEBHOOK, json=_sobre_acuse(WAMID, "delivered"))
        assert self._estado(sesion_bd) is EstadoEntrega.ENTREGADO

        api.post(WEBHOOK, json=_sobre_acuse(WAMID, "read"))
        assert self._estado(sesion_bd) is EstadoEntrega.LEIDO

    def test_un_acuse_atrasado_no_retrocede(self, con_envio):
        """Meta manda los eventos desordenados con frecuencia."""
        api, sesion_bd = con_envio
        api.post(WEBHOOK, json=_sobre_acuse(WAMID, "read"))
        api.post(WEBHOOK, json=_sobre_acuse(WAMID, "delivered"))
        assert self._estado(sesion_bd) is EstadoEntrega.LEIDO

    def test_repetir_el_mismo_acuse_no_hace_dano(self, con_envio):
        api, sesion_bd = con_envio
        for _ in range(3):
            api.post(WEBHOOK, json=_sobre_acuse(WAMID, "delivered"))
        assert self._estado(sesion_bd) is EstadoEntrega.ENTREGADO

    def test_un_fallo_guarda_el_motivo(self, con_envio):
        api, sesion_bd = con_envio
        api.post(WEBHOOK, json=_sobre_acuse(
            WAMID, "failed",
            errores=[{"code": 131049, "title": "No entregado por calidad"}]))
        with sesion_bd() as s:
            r = s.query(Recordatorio).filter_by(canal=Canal.WHATSAPP).one()
            assert r.estado_entrega is EstadoEntrega.FALLIDO
            assert "calidad" in (r.motivo_error or "")

    def test_un_acuse_de_otro_sistema_se_ignora(self, con_envio):
        api, sesion_bd = con_envio
        r = api.post(WEBHOOK, json=_sobre_acuse("wamid.DESCONOCIDO", "read"))
        assert r.status_code == 200
        assert r.json()["acuses"] == 0

    def test_siempre_responde_200(self, api):
        """Si devolviéramos error, Meta reintentaría el lote completo."""
        assert api.post(WEBHOOK, json={"entry": []}).status_code == 200
        assert api.post(WEBHOOK, json={"basura": True}).status_code == 200


# --------------------------------------------------------- baja entrante ---

def _sobre_mensaje(texto: str, de: str = "522281009584") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{
            "from": de, "id": "wamid.ENTRANTE", "type": "text",
            "timestamp": "1789260000", "text": {"body": texto},
        }]}}]}],
    }


class TestBajaPorWhatsApp:
    @pytest.mark.parametrize("texto", ["BAJA", "baja", "  Baja  ", "stop",
                                       "darme de baja"])
    def test_da_de_baja_al_cliente(self, con_envio, texto):
        api, sesion_bd = con_envio
        r = api.post(WEBHOOK, json=_sobre_mensaje(texto))
        assert r.json()["entrantes"] == 1
        with sesion_bd() as s:
            cliente = s.query(Cliente).one()
            assert cliente.estado_contacto is EstadoContacto.BAJA
            assert cliente.consent_whatsapp is False

    def test_un_mensaje_normal_no_da_de_baja(self, con_envio):
        api, sesion_bd = con_envio
        api.post(WEBHOOK, json=_sobre_mensaje("¿Cuándo me toca verificar?"))
        with sesion_bd() as s:
            assert s.query(Cliente).one().estado_contacto is \
                EstadoContacto.CONTACTABLE

    def test_un_numero_desconocido_no_truena(self, con_envio):
        api, _ = con_envio
        r = api.post(WEBHOOK, json=_sobre_mensaje("BAJA", de="529999999999"))
        assert r.status_code == 200
        assert r.json()["entrantes"] == 0

    def test_tras_la_baja_no_se_le_generan_recordatorios(self, con_envio):
        api, sesion_bd = con_envio
        api.post(WEBHOOK, json=_sobre_mensaje("BAJA"))
        _, ventana = ventanas_del_anio(7, ANIO)
        with sesion_bd() as s:
            r = servicio.generar_del_dia(s, fechas_de_aviso(ventana)[3].fecha)
        assert r.creados == 0


class TestFirmaDelWebhook:
    def test_en_produccion_se_exige_la_firma(self, api, monkeypatch):
        from app.config import obtener_config

        monkeypatch.setenv("WHATSAPP_APP_SECRET", "secreto-de-la-app")
        obtener_config.cache_clear()
        try:
            sobre = _sobre_acuse(WAMID, "read")
            # Sin firma: rechazado.
            assert api.post(WEBHOOK, json=sobre).status_code == 403

            # Con la firma correcta: aceptado.
            cuerpo = json.dumps(sobre).encode()
            firma = hmac.new(b"secreto-de-la-app", cuerpo,
                             hashlib.sha256).hexdigest()
            r = api.post(WEBHOOK, content=cuerpo, headers={
                "X-Hub-Signature-256": f"sha256={firma}",
                "Content-Type": "application/json",
            })
            assert r.status_code == 200
        finally:
            obtener_config.cache_clear()
