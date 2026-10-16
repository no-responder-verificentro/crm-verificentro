"""Pruebas del job de recordatorios.

Lo que más importa aquí: que salgan los cinco avisos en su día, que NO salgan
si el cliente ya verificó, y que correr el job dos veces no duplique mensajes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.dominio.calendario import fechas_de_aviso, ventanas_del_anio
from app.modelos.cliente import Cliente, EstadoContacto, OrigenConsentimiento
from app.modelos.recordatorio import (
    Canal,
    EstadoEntrega,
    EstadoRecordatorio,
    Recordatorio,
    TipoRecordatorio,
)
from app.modelos.vehiculo import Resultado, Vehiculo, Verificacion
from app.servicios import recordatorios as servicio

ANIO = date.today().year


def crear_cliente(sesion, *, whatsapp=True, correo=True, estado=None):
    cliente = Cliente(
        nombre="Ana Karen Domínguez Ruiz",
        telefono_e164="+522281009584" if whatsapp else None,
        correo="ana@correo.com" if correo else None,
        consent_whatsapp=whatsapp,
        consent_correo=correo,
        consent_origen=OrigenConsentimiento.MOSTRADOR,
        estado_contacto=estado or EstadoContacto.CONTACTABLE,
    )
    sesion.add(cliente)
    sesion.flush()
    return cliente


def crear_vehiculo(sesion, cliente, placa="YUN-047-A", niv="3N1CB51S62K222173",
                   entidad="VER"):
    vehiculo = Vehiculo(
        cliente_id=cliente.id, niv=niv, placa=placa, marca="Nissan",
        entidad_placa=entidad, en_programa_estatal=(entidad == "VER"),
    )
    sesion.add(vehiculo)
    sesion.commit()
    sesion.refresh(vehiculo)
    return vehiculo


@pytest.fixture
def escenario(sesion_bd):
    """Un cliente con un auto de dígito 7 (Feb–Mar y Ago–Sep)."""
    with sesion_bd() as sesion:
        cliente = crear_cliente(sesion)
        vehiculo = crear_vehiculo(sesion, cliente)
        return sesion_bd, cliente.id, vehiculo.id


# ------------------------------------------------------------ generación ---

class TestGeneracion:
    def test_no_genera_nada_en_un_dia_sin_avisos(self, escenario):
        Sesion, _, _ = escenario
        # 1 de enero no cae en ningún aviso del dígito 7.
        with Sesion() as s:
            r = servicio.generar_del_dia(s, date(ANIO, 1, 1))
        assert r.creados == 0

    def test_genera_los_dos_canales_el_dia_del_aviso(self, escenario):
        Sesion, _, _ = escenario
        _, ventana = ventanas_del_anio(7, ANIO)
        dia = fechas_de_aviso(ventana)[1].fecha   # aviso_2: abre el periodo

        with Sesion() as s:
            r = servicio.generar_del_dia(s, dia)
        assert r.creados == 2       # WhatsApp y correo

        with Sesion() as s:
            filas = s.query(Recordatorio).all()
            assert {f.canal for f in filas} == {Canal.WHATSAPP, Canal.CORREO}
            assert all(f.aviso_clave == "aviso_2" for f in filas)
            assert all(f.estado is EstadoRecordatorio.PROGRAMADO for f in filas)

    def test_congela_el_destino(self, escenario):
        Sesion, _, _ = escenario
        _, ventana = ventanas_del_anio(7, ANIO)
        with Sesion() as s:
            servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
        with Sesion() as s:
            wa = s.query(Recordatorio).filter_by(canal=Canal.WHATSAPP).one()
            assert wa.destino == "+522281009584"

    def test_correr_dos_veces_no_duplica(self, escenario):
        """La regla que evita que el cliente reciba el mismo aviso dos veces."""
        Sesion, _, _ = escenario
        _, ventana = ventanas_del_anio(7, ANIO)
        dia = fechas_de_aviso(ventana)[1].fecha

        with Sesion() as s:
            primera = servicio.generar_del_dia(s, dia)
        with Sesion() as s:
            segunda = servicio.generar_del_dia(s, dia)

        assert primera.creados == 2
        assert segunda.creados == 0
        assert segunda.duplicados == 2
        with Sesion() as s:
            assert s.query(Recordatorio).count() == 2

    def test_sin_consentimiento_no_se_genera(self, sesion_bd):
        with sesion_bd() as s:
            cliente = crear_cliente(s, whatsapp=False, correo=False)
            crear_vehiculo(s, cliente)
        _, ventana = ventanas_del_anio(7, ANIO)
        with sesion_bd() as s:
            r = servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
        assert r.creados == 0
        assert r.sin_consentimiento == 1

    def test_dado_de_baja_no_recibe(self, sesion_bd):
        with sesion_bd() as s:
            cliente = crear_cliente(s, estado=EstadoContacto.BAJA)
            crear_vehiculo(s, cliente)
        _, ventana = ventanas_del_anio(7, ANIO)
        with sesion_bd() as s:
            r = servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
        assert r.creados == 0

    def test_solo_whatsapp_si_solo_autorizo_whatsapp(self, sesion_bd):
        with sesion_bd() as s:
            cliente = crear_cliente(s, correo=False)
            crear_vehiculo(s, cliente)
        _, ventana = ventanas_del_anio(7, ANIO)
        with sesion_bd() as s:
            r = servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
        assert r.creados == 1

    def test_vehiculo_de_otro_estado_no_entra_al_calendario(self, sesion_bd):
        with sesion_bd() as s:
            cliente = crear_cliente(s)
            crear_vehiculo(s, cliente, entidad="PUE")
        _, ventana = ventanas_del_anio(7, ANIO)
        with sesion_bd() as s:
            r = servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
        assert r.creados == 0

    def test_placa_sin_digito_no_entra(self, sesion_bd):
        with sesion_bd() as s:
            cliente = crear_cliente(s)
            crear_vehiculo(s, cliente, placa="ABC-DEF-G", niv="1HGCM82633A004352")
        with sesion_bd() as s:
            total = 0
            _, ventana = ventanas_del_anio(7, ANIO)
            total += servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha).creados
        assert total == 0


class TestNoMolestarAQuienYaVerifico:
    def test_si_ya_verifico_no_se_genera(self, escenario):
        Sesion, _, vehiculo_id = escenario
        _, ventana = ventanas_del_anio(7, ANIO)

        with Sesion() as s:
            s.add(Verificacion(
                vehiculo_id=vehiculo_id,
                fecha=ventana.inicio + timedelta(days=1),
                resultado=Resultado.APROBADO,
            ))
            s.commit()

        with Sesion() as s:
            r = servicio.generar_del_dia(s, fechas_de_aviso(ventana)[3].fecha)
        assert r.creados == 0

    def test_un_rechazo_no_lo_libra(self, escenario):
        """Rechazado significa volver dentro de la misma ventana."""
        Sesion, _, vehiculo_id = escenario
        _, ventana = ventanas_del_anio(7, ANIO)

        with Sesion() as s:
            s.add(Verificacion(
                vehiculo_id=vehiculo_id,
                fecha=ventana.inicio + timedelta(days=1),
                resultado=Resultado.RECHAZADO,
            ))
            s.commit()

        with Sesion() as s:
            r = servicio.generar_del_dia(s, fechas_de_aviso(ventana)[3].fecha)
        assert r.creados == 2

    def test_verificar_despues_cancela_lo_que_falta(self, escenario):
        """El caso real: se le mandó el aviso 2, luego vino a verificar, y los
        avisos 3 y 4 que ya estaban en la cola se apagan solos."""
        Sesion, _, vehiculo_id = escenario
        _, ventana = ventanas_del_anio(7, ANIO)
        avisos = fechas_de_aviso(ventana)

        with Sesion() as s:
            servicio.generar_del_dia(s, avisos[1].fecha)
        with Sesion() as s:
            assert s.query(Recordatorio).filter_by(
                estado=EstadoRecordatorio.PROGRAMADO).count() == 2

        with Sesion() as s:
            s.add(Verificacion(
                vehiculo_id=vehiculo_id,
                fecha=ventana.inicio + timedelta(days=3),
                resultado=Resultado.APROBADO,
            ))
            s.commit()

        with Sesion() as s:
            r = servicio.generar_del_dia(s, avisos[2].fecha)
        assert r.cancelados == 2
        assert r.creados == 0

        with Sesion() as s:
            assert s.query(Recordatorio).filter_by(
                estado=EstadoRecordatorio.CANCELADO).count() == 2


class TestPeriodoCompleto:
    def test_los_cinco_avisos_salen_uno_por_uno(self, escenario):
        """Se simula día por día toda la ventana: deben salir exactamente
        cinco avisos por canal, cada uno en su fecha."""
        Sesion, _, _ = escenario
        _, ventana = ventanas_del_anio(7, ANIO)
        avisos = fechas_de_aviso(ventana)

        dia = avisos[0].fecha - timedelta(days=3)
        fin = avisos[-1].fecha + timedelta(days=3)
        creados_por_dia = {}

        while dia <= fin:
            with Sesion() as s:
                r = servicio.generar_del_dia(s, dia)
            if r.creados:
                creados_por_dia[dia] = r.creados
            dia += timedelta(days=1)

        assert sorted(creados_por_dia) == [a.fecha for a in avisos]
        assert all(n == 2 for n in creados_por_dia.values())

        with Sesion() as s:
            claves = {r.aviso_clave for r in s.query(Recordatorio).all()}
        assert claves == {"aviso_1", "aviso_2", "aviso_3", "aviso_4", "seguimiento"}


# ---------------------------------------------------------------- envío ---

class TestEnvio:
    def _encolar(self, Sesion):
        _, ventana = ventanas_del_anio(7, ANIO)
        with Sesion() as s:
            servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
        return ventana

    def test_envia_lo_que_ya_toca(self, escenario):
        Sesion, _, _ = escenario
        self._encolar(Sesion)
        with Sesion() as s:
            r = servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1),
                                           silencioso=True)
        assert r.enviados == 2
        with Sesion() as s:
            filas = s.query(Recordatorio).all()
            assert all(f.estado is EstadoRecordatorio.ENVIADO for f in filas)
            assert all(f.estado_entrega is EstadoEntrega.ENVIADO for f in filas)
            assert all(f.id_externo for f in filas)

    def test_no_envia_lo_que_todavia_no_toca(self, escenario):
        Sesion, _, _ = escenario
        self._encolar(Sesion)
        with Sesion() as s:
            r = servicio.enviar_pendientes(s, datetime(ANIO - 1, 1, 1),
                                           silencioso=True)
        assert r.enviados == 0

    def test_enviar_dos_veces_no_reenvia(self, escenario):
        Sesion, _, _ = escenario
        self._encolar(Sesion)
        with Sesion() as s:
            servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1), silencioso=True)
        with Sesion() as s:
            r = servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1),
                                           silencioso=True)
        assert r.enviados == 0

    def test_queda_bitacora_de_cada_evento(self, escenario):
        Sesion, _, _ = escenario
        self._encolar(Sesion)
        with Sesion() as s:
            servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1), silencioso=True)
        with Sesion() as s:
            recordatorio = s.query(Recordatorio).first()
            assert [e.evento for e in recordatorio.eventos] == ["enviado"]

    def test_pausado_no_sale(self, escenario):
        Sesion, _, _ = escenario
        self._encolar(Sesion)
        with Sesion() as s:
            for r in s.query(Recordatorio).all():
                r.estado = EstadoRecordatorio.PAUSADO
            s.commit()
        with Sesion() as s:
            r = servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1),
                                           silencioso=True)
        assert r.enviados == 0

    def test_el_texto_del_mensaje_trae_lo_indispensable(self, escenario):
        Sesion, _, _ = escenario
        self._encolar(Sesion)
        from app.mensajeria.consola import AdaptadorConsola

        capturados = []

        def falso_adaptador(canal, silencioso=False):
            adaptador = AdaptadorConsola(canal.value, silencioso=True)
            capturados.append(adaptador)
            return adaptador

        original = servicio.obtener_adaptador
        servicio.obtener_adaptador = falso_adaptador
        try:
            with Sesion() as s:
                servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1))
        finally:
            servicio.obtener_adaptador = original

        textos = [m.cuerpo for a in capturados for m in a.enviados]
        assert textos
        for texto in textos:
            assert "Ana" in texto              # se dirige a la persona
            assert "YUN-047-A" in texto        # dice de qué auto habla
            assert "BAJA" in texto             # y cómo dejar de recibirlos


class TestCola:
    def test_la_cola_muestra_lo_proximo(self, escenario):
        Sesion, _, _ = escenario
        hoy = date.today()
        with Sesion() as s:
            # Se fuerza un recordatorio para hoy usando la ventana vigente.
            for ventana in ventanas_del_anio(7, ANIO):
                for aviso in fechas_de_aviso(ventana):
                    servicio.generar_del_dia(s, aviso.fecha)
        with Sesion() as s:
            pendientes = servicio.cola(s, horas=24 * 400)
        assert len(pendientes) > 0
        assert all(
            r.estado in (EstadoRecordatorio.PROGRAMADO, EstadoRecordatorio.PAUSADO)
            for r in pendientes
        )


# ------------------------------------------------------- canales activos ---

class TestCanalesActivos:
    """Con WhatsApp apagado no se deben encolar mensajes que nadie va a poder
    enviar. Es la configuración con la que arranca el verificentro, mientras
    no esté el trámite con Meta."""

    def _generar(self, Sesion):
        _, ventana = ventanas_del_anio(7, ANIO)
        with Sesion() as s:
            return servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)

    @staticmethod
    def _fijar(monkeypatch, canales: str) -> None:
        from app.config import obtener_config

        monkeypatch.setenv("CANALES_ACTIVOS", canales)
        obtener_config.cache_clear()

    def test_solo_correo_genera_una_fila(self, escenario, monkeypatch):
        Sesion, _, _ = escenario
        self._fijar(monkeypatch, '["correo"]')
        r = self._generar(Sesion)
        assert r.creados == 1
        with Sesion() as s:
            assert s.query(Recordatorio).one().canal is Canal.CORREO

    def test_los_dos_canales_generan_dos(self, escenario, monkeypatch):
        Sesion, _, _ = escenario
        self._fijar(monkeypatch, '["correo","whatsapp"]')
        assert self._generar(Sesion).creados == 2

    def test_ningun_canal_activo_no_genera_nada(self, escenario, monkeypatch):
        Sesion, _, _ = escenario
        self._fijar(monkeypatch, "[]")
        r = self._generar(Sesion)
        assert r.creados == 0
        assert r.sin_consentimiento == 1


class TestConfiguracionDeEnvio:
    """La pantalla necesita poder decir «esto no está saliendo de verdad».

    Con PROVEEDOR_CORREO=consola el sistema imprime los correos en la bitácora
    del servidor y reporta el envío como exitoso. Desde la pantalla eso era
    idéntico a un envío real —acuse en «Enviado» incluido— mientras en la
    bandeja del cliente no llegaba nada, ni a spam. Este endpoint es lo que
    permite distinguirlos.
    """

    RUTA = "/api/v1/recordatorios/configuracion"

    def test_el_modo_consola_se_reporta_como_que_no_manda(self, api, como_admin):
        from app.config import obtener_config

        obtener_config.cache_clear()
        r = api.get(self.RUTA, headers=como_admin)

        assert r.status_code == 200
        datos = r.json()
        assert datos["proveedor_correo"] == "consola"
        assert datos["manda_de_verdad"] is False
        assert "modo prueba" in datos["motivo"]

    def test_apps_script_sin_token_no_manda(self, api, como_admin, monkeypatch):
        from app.config import obtener_config

        config = obtener_config()
        monkeypatch.setattr(config, "proveedor_correo", "apps_script")
        monkeypatch.setattr(
            config, "apps_script_url",
            "https://script.google.com/macros/s/AK/exec",
        )
        monkeypatch.setattr(config, "apps_script_token", "")

        datos = api.get(self.RUTA, headers=como_admin).json()

        assert datos["manda_de_verdad"] is False
        assert "APPS_SCRIPT_TOKEN" in datos["motivo"]

    def test_bien_configurado_no_avisa_nada(self, api, como_admin, monkeypatch):
        from app.config import obtener_config

        config = obtener_config()
        monkeypatch.setattr(config, "proveedor_correo", "apps_script")
        monkeypatch.setattr(
            config, "apps_script_url",
            "https://script.google.com/macros/s/AK/exec",
        )
        monkeypatch.setattr(config, "apps_script_token", "secreto")

        datos = api.get(self.RUTA, headers=como_admin).json()

        assert datos["manda_de_verdad"] is True
        assert datos["motivo"] is None

    def test_no_devuelve_ninguna_credencial(self, api, como_admin, monkeypatch):
        """Lo ve cualquier empleado con permiso de consulta, no solo el admin."""
        from app.config import obtener_config

        config = obtener_config()
        monkeypatch.setattr(config, "apps_script_token", "token-secretisimo")
        monkeypatch.setattr(config, "smtp_contrasena", "contrasena-secretisima")

        cuerpo = api.get(self.RUTA, headers=como_admin).text

        assert "secretisim" not in cuerpo

    def test_sin_token_no_hay_acceso(self, api):
        assert api.get(self.RUTA).status_code == 401


class TestReintentar:
    """Un aviso que falló tiene que poder volver a intentarse.

    Sin esto quedaba muerto: `enviar_pendientes` solo mira los que están en
    PROGRAMADO, así que nada ni nadie volvía a tocarlo. Un fallo pasajero
    —la red, un tope del proveedor, una credencial que se arregló diez
    minutos después— se convertía en un cliente que no recibió su aviso y en
    una fila en pantalla que no se podía hacer nada por ella.
    """

    def _fallido(self, sesion_bd):
        with sesion_bd() as s:
            cliente = crear_cliente(s)
            vehiculo = crear_vehiculo(s, cliente)
            r = Recordatorio(
                vehiculo_id=vehiculo.id, cliente_id=cliente.id,
                tipo=TipoRecordatorio.VENTANA, aviso_clave="aviso_2",
                ventana_anio=ANIO, ventana_periodo=2,
                canal=Canal.CORREO, destino="ana@correo.com",
                programado_para=datetime(ANIO, 10, 1, 9, 0),
                estado=EstadoRecordatorio.ERROR,
                estado_entrega=EstadoEntrega.FALLIDO,
                motivo_error="You do not have permission",
                id_externo="algo-viejo",
                enviado_en=datetime(ANIO, 10, 1, 9, 1),
            )
            s.add(r)
            s.commit()
            return r.id

    def test_vuelve_a_la_cola_y_sale_ya(self, api, como_admin, sesion_bd):
        rec = self._fallido(sesion_bd)

        r = api.post(f"/api/v1/recordatorios/{rec}/reintentar", headers=como_admin)

        assert r.status_code == 200
        with sesion_bd() as s:
            guardado = s.get(Recordatorio, rec)
            assert guardado.estado is EstadoRecordatorio.PROGRAMADO
            assert guardado.estado_entrega is EstadoEntrega.PENDIENTE
            assert guardado.motivo_error is None
            # El identificador del intento anterior no sirve para el nuevo:
            # si se quedara, un acuse viejo podría vincularse con este envío.
            assert guardado.id_externo is None
            assert guardado.enviado_en is None

    def test_y_el_job_lo_recoge(self, api, como_admin, sesion_bd):
        """La prueba que importa: que el reintento de verdad salga."""
        rec = self._fallido(sesion_bd)
        api.post(f"/api/v1/recordatorios/{rec}/reintentar", headers=como_admin)

        with sesion_bd() as s:
            resumen = servicio.enviar_pendientes(s, silencioso=True)

        assert resumen.enviados == 1

    def test_no_se_reintenta_uno_que_salio_bien(self, api, como_admin, sesion_bd):
        with sesion_bd() as s:
            cliente = crear_cliente(s)
            vehiculo = crear_vehiculo(s, cliente)
            r = Recordatorio(
                vehiculo_id=vehiculo.id, cliente_id=cliente.id,
                tipo=TipoRecordatorio.VENTANA, aviso_clave="aviso_2",
                ventana_anio=ANIO, ventana_periodo=2,
                canal=Canal.CORREO, destino="ana@correo.com",
                programado_para=datetime(ANIO, 10, 1, 9, 0),
                estado=EstadoRecordatorio.ENVIADO,
                estado_entrega=EstadoEntrega.ENTREGADO,
            )
            s.add(r)
            s.commit()
            rec = r.id

        respuesta = api.post(f"/api/v1/recordatorios/{rec}/reintentar",
                             headers=como_admin)

        assert respuesta.status_code == 409

    def test_solo_el_administrador(self, api, como_tecnico, sesion_bd):
        rec = self._fallido(sesion_bd)

        r = api.post(f"/api/v1/recordatorios/{rec}/reintentar",
                     headers=como_tecnico)

        assert r.status_code == 403


class TestCorreoDePrueba:
    """Comprobar que el correo sale, desde la pantalla.

    Antes solo se podía con `python -m jobs.probar_correo` desde una
    terminal. Quien administra el verificentro no tiene por qué abrir una
    terminal para eso, y en una demostración frente al dueño se ve mal.
    """

    RUTA = "/api/v1/recordatorios/probar"

    def test_el_modo_consola_lo_dice_en_vez_de_fingir(self, api, como_admin):
        """En modo consola no sale nada, y el endpoint tiene que decirlo.

        Reportar «enviado» aquí sería repetir el mismo engaño que nos costó
        encontrar el problema del correo.
        """
        r = api.post(self.RUTA, headers=como_admin,
                     json={"correo": "alguien@ejemplo.mx"})

        assert r.status_code == 200
        datos = r.json()
        assert datos["enviado"] is False
        assert "modo prueba" in datos["detalle"]

    def test_manda_el_mismo_aviso_que_el_job(self, api, como_admin, monkeypatch):
        """Los dos caminos tienen que comprobar exactamente lo mismo."""
        from app.config import obtener_config
        from app.mensajeria.base import Resultado
        from app.mensajeria.prueba import armar_mensaje_de_prueba

        monkeypatch.setattr(obtener_config(), "proveedor_correo", "smtp")

        enviados = []

        class Falso:
            def enviar(self, mensaje):
                enviados.append(mensaje)
                return Resultado(exito=True, id_externo="abc")

        monkeypatch.setattr("app.api.v1.recordatorios.obtener_adaptador",
                            lambda canal: Falso())

        r = api.post(self.RUTA, headers=como_admin,
                     json={"correo": "zs21016023@estudiantes.uv.mx"})

        assert r.json()["enviado"] is True
        assert len(enviados) == 1
        esperado = armar_mensaje_de_prueba("zs21016023@estudiantes.uv.mx")
        assert enviados[0].asunto == esperado.asunto
        assert enviados[0].cuerpo == esperado.cuerpo
        assert enviados[0].destino == "zs21016023@estudiantes.uv.mx"

    def test_un_fallo_del_proveedor_se_ve_tal_cual(self, api, como_admin,
                                                   monkeypatch):
        from app.config import obtener_config
        from app.mensajeria.base import Resultado

        monkeypatch.setattr(obtener_config(), "proveedor_correo", "mailjet")

        class Falso:
            def enviar(self, mensaje):
                return Resultado(exito=False, codigo="fallido",
                                 error="Mailjet bloqueó el mensaje por contenido.")

        monkeypatch.setattr("app.api.v1.recordatorios.obtener_adaptador",
                            lambda canal: Falso())

        datos = api.post(self.RUTA, headers=como_admin,
                         json={"correo": "alguien@ejemplo.mx"}).json()

        assert datos["enviado"] is False
        assert "bloqueó el mensaje" in datos["detalle"]

    def test_un_correo_mal_escrito_se_rechaza(self, api, como_admin):
        r = api.post(self.RUTA, headers=como_admin, json={"correo": "no-es-correo"})

        assert r.status_code == 422

    def test_no_deja_rastro_en_la_cola(self, api, como_admin, sesion_bd):
        """No es el recordatorio de nadie: no debe ensuciar la bitácora."""
        api.post(self.RUTA, headers=como_admin, json={"correo": "a@b.mx"})

        with sesion_bd() as s:
            assert s.query(Recordatorio).count() == 0

    def test_solo_el_administrador(self, api, como_tecnico):
        r = api.post(self.RUTA, headers=como_tecnico, json={"correo": "a@b.mx"})

        assert r.status_code == 403
