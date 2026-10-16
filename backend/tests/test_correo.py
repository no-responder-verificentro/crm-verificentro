"""Pruebas del correo y del seguimiento del clic.

El envío SMTP se prueba contra un servidor falso: no se manda nada a internet,
pero sí se arma el mensaje completo y se revisa lo que se habría enviado.
"""

from __future__ import annotations

import smtplib
from datetime import date, datetime, timedelta

import pytest

from app.dominio.calendario import fechas_de_aviso, ventanas_del_anio
from app.mensajeria.base import Mensaje
from app.mensajeria.correo import AdaptadorCorreo, CorreoNoConfigurado
from app.mensajeria.enlaces import enlace_de_seguimiento, firmar, verificar
from app.modelos.cliente import Cliente, EstadoContacto, OrigenConsentimiento
from app.modelos.recordatorio import Canal, EstadoEntrega, Recordatorio
from app.modelos.vehiculo import Vehiculo
from app.servicios import recordatorios as servicio

ANIO = date.today().year


class ServidorFalso:
    """Sustituye a smtplib.SMTP: guarda lo que se le manda."""

    enviados: list = []

    def __init__(self, *args, **kwargs):
        self.autenticado = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, **kwargs):
        pass

    def login(self, usuario, contrasena):
        self.autenticado = True

    def send_message(self, correo):
        ServidorFalso.enviados.append(correo)


@pytest.fixture(autouse=True)
def _limpiar():
    ServidorFalso.enviados = []


@pytest.fixture
def adaptador(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", ServidorFalso)
    return AdaptadorCorreo(
        host="smtp.ejemplo.mx", puerto=587, usuario="u", contrasena="c",
        remitente="no-responder@verificentro.mx",
    )


# ----------------------------------------------------------------- firma ---

class TestEnlacesFirmados:
    def test_la_firma_es_estable(self):
        assert firmar(42) == firmar(42)

    def test_cada_recordatorio_tiene_firma_distinta(self):
        assert firmar(42) != firmar(43)

    def test_verifica_la_propia(self):
        assert verificar(42, firmar(42))

    def test_rechaza_la_de_otro(self):
        # Sin esto, cualquiera marcaría como leídos los correos ajenos
        # cambiando el número en la URL.
        assert not verificar(42, firmar(43))

    def test_rechaza_una_inventada(self):
        assert not verificar(42, "abc123")
        assert not verificar(42, "")

    def test_el_enlace_trae_id_y_firma(self):
        enlace = enlace_de_seguimiento(7)
        assert enlace.endswith(f"/r/7/{firmar(7)}")


# ----------------------------------------------------------------- SMTP ---

class TestEnvioPorCorreo:
    def test_sin_host_no_arranca(self):
        with pytest.raises(CorreoNoConfigurado):
            AdaptadorCorreo("", 587, "", "", "x@y.mx")

    def test_envia_y_devuelve_id(self, adaptador):
        resultado = adaptador.enviar(Mensaje(
            destino="ana@correo.com", asunto="Tu verificación",
            cuerpo="Hola Ana.\n\nTe toca verificar.", clave_plantilla="aviso_2",
        ))
        assert resultado.exito
        assert resultado.id_externo
        assert len(ServidorFalso.enviados) == 1

    def test_va_en_texto_y_en_html(self, adaptador):
        """Un correo solo-HTML tiene más probabilidad de caer en spam."""
        adaptador.enviar(Mensaje(destino="ana@correo.com", asunto="A",
                                 cuerpo="Hola Ana.", clave_plantilla="aviso_2"))
        correo = ServidorFalso.enviados[0]
        tipos = {p.get_content_type() for p in correo.walk()}
        assert "text/plain" in tipos
        assert "text/html" in tipos

    def test_trae_la_cabecera_para_darse_de_baja(self, adaptador):
        adaptador.enviar(Mensaje(destino="ana@correo.com", asunto="A",
                                 cuerpo="Hola.", clave_plantilla="aviso_2"))
        assert "List-Unsubscribe" in ServidorFalso.enviados[0]

    def test_el_enlace_aparece_en_el_html(self, adaptador):
        adaptador.enviar(Mensaje(
            destino="ana@correo.com", asunto="A", cuerpo="Hola.",
            clave_plantilla="aviso_2", enlace="https://x.mx/r/1/abc",
        ))
        html = ServidorFalso.enviados[0].get_body(("html",)).get_content()
        assert "https://x.mx/r/1/abc" in html

    def test_una_direccion_rechazada_es_rebote_duro(self, adaptador, monkeypatch):
        class Rechaza(ServidorFalso):
            def send_message(self, correo):
                raise smtplib.SMTPRecipientsRefused({})

        monkeypatch.setattr(smtplib, "SMTP", Rechaza)
        resultado = adaptador.enviar(Mensaje("nadie@nada.mx", "A", "Hola", "aviso_2"))
        assert not resultado.exito
        assert resultado.codigo == "rebote_duro"

    def test_credenciales_malas_no_tumban_el_job(self, adaptador, monkeypatch):
        class MalAuth(ServidorFalso):
            def login(self, u, c):
                raise smtplib.SMTPAuthenticationError(535, b"nope")

        monkeypatch.setattr(smtplib, "SMTP", MalAuth)
        resultado = adaptador.enviar(Mensaje("ana@correo.com", "A", "Hola", "aviso_2"))
        assert not resultado.exito
        assert resultado.codigo == "auth"


# ------------------------------------------------------------- integración -

@pytest.fixture
def con_correo_en_cola(api, sesion_bd):
    with sesion_bd() as s:
        cliente = Cliente(
            nombre="Ana Karen Domínguez", correo="ana@correo.com",
            consent_whatsapp=False, consent_correo=True,
            consent_origen=OrigenConsentimiento.MOSTRADOR,
            estado_contacto=EstadoContacto.CONTACTABLE,
        )
        s.add(cliente)
        s.flush()
        s.add(Vehiculo(cliente_id=cliente.id, niv="3N1CB51S62K222173",
                       placa="YUN-047-A", marca="Nissan"))
        s.commit()

    _, ventana = ventanas_del_anio(7, ANIO)
    with sesion_bd() as s:
        servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
    return api, sesion_bd


class TestClicEnElCorreo:
    def _enviar(self, sesion_bd):
        with sesion_bd() as s:
            servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1), silencioso=True)
        with sesion_bd() as s:
            return s.query(Recordatorio).filter_by(canal=Canal.CORREO).one().id

    def test_el_correo_lleva_enlace_firmado(self, con_correo_en_cola):
        _, sesion_bd = con_correo_en_cola
        with sesion_bd() as s:
            recordatorio = s.query(Recordatorio).filter_by(canal=Canal.CORREO).one()
            mensaje = servicio._armar_mensaje(s, recordatorio)
        assert mensaje.enlace and f"/r/{recordatorio.id}/" in mensaje.enlace
        assert mensaje.enlace in mensaje.cuerpo

    def test_whatsapp_no_lleva_enlace(self, api, sesion_bd):
        """En WhatsApp el acuse lo reporta Meta; el enlace sobraría."""
        with sesion_bd() as s:
            cliente = Cliente(nombre="Ana", telefono_e164="+522281009584",
                              consent_whatsapp=True, consent_correo=False)
            s.add(cliente)
            s.flush()
            s.add(Vehiculo(cliente_id=cliente.id, niv="1HGCM82633A004352",
                           placa="ABC-047-A"))
            s.commit()
        _, ventana = ventanas_del_anio(7, ANIO)
        with sesion_bd() as s:
            servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
            recordatorio = s.query(Recordatorio).filter_by(canal=Canal.WHATSAPP).one()
            mensaje = servicio._armar_mensaje(s, recordatorio)
        assert mensaje.enlace is None

    def test_dar_clic_registra_el_acuse(self, con_correo_en_cola):
        api, sesion_bd = con_correo_en_cola
        rid = self._enviar(sesion_bd)

        respuesta = api.get(f"/r/{rid}/{firmar(rid)}", follow_redirects=False)
        assert respuesta.status_code == 302
        assert "placa=YUN047A" in respuesta.headers["location"]

        with sesion_bd() as s:
            assert s.get(Recordatorio, rid).estado_entrega is EstadoEntrega.CLIC

    def test_una_firma_falsa_no_registra_nada(self, con_correo_en_cola):
        """No se registra el clic, pero tampoco se deja al cliente en un error:
        se le manda a la consulta pública, que es lo que iba buscando."""
        api, sesion_bd = con_correo_en_cola
        rid = self._enviar(sesion_bd)

        respuesta = api.get(f"/r/{rid}/000000", follow_redirects=False)
        assert respuesta.status_code == 302
        assert "placa=" not in respuesta.headers["location"]

        with sesion_bd() as s:
            assert s.get(Recordatorio, rid).estado_entrega is EstadoEntrega.ENVIADO


class TestOrdenDeLosAcuses:
    def test_el_estado_solo_avanza(self, con_correo_en_cola):
        _, sesion_bd = con_correo_en_cola
        with sesion_bd() as s:
            servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1), silencioso=True)

        with sesion_bd() as s:
            r = s.query(Recordatorio).filter_by(canal=Canal.CORREO).one()
            assert servicio.registrar_entrega(s, r, EstadoEntrega.ENTREGADO)
            assert servicio.registrar_entrega(s, r, EstadoEntrega.CLIC)
            # Un acuse atrasado no debe retroceder lo que ya se sabía.
            assert not servicio.registrar_entrega(s, r, EstadoEntrega.ENTREGADO)
            assert r.estado_entrega is EstadoEntrega.CLIC

    def test_los_acuses_atrasados_igual_quedan_en_la_bitacora(self, con_correo_en_cola):
        _, sesion_bd = con_correo_en_cola
        with sesion_bd() as s:
            servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1), silencioso=True)
        with sesion_bd() as s:
            r = s.query(Recordatorio).filter_by(canal=Canal.CORREO).one()
            servicio.registrar_entrega(s, r, EstadoEntrega.CLIC)
            servicio.registrar_entrega(s, r, EstadoEntrega.ENTREGADO)
            eventos = [e.evento for e in r.eventos]
        # Se guardan los dos, aunque uno no haya cambiado el estado.
        assert "clic" in eventos and "entregado" in eventos
