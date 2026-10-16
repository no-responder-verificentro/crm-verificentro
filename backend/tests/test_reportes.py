"""Pruebas de reportes.

El caso que más importa es la efectividad: solo debe contar periodos que ya
cerraron. Contar los abiertos falsearía el número a la baja, porque el cliente
todavía puede venir.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.dominio.calendario import fechas_de_aviso, ventanas_del_anio
from app.modelos.cliente import Cliente, EstadoContacto, OrigenConsentimiento
from app.modelos.vehiculo import Resultado, Vehiculo, Verificacion
from app.servicios import recordatorios as srec
from app.servicios import reportes as servicio

REP = "/api/v1/reportes"
HOY = date.today()
ANIO = HOY.year


def _digito_con_ventana_cerrada() -> tuple[int, object] | tuple[None, None]:
    """Un dígito cuya primera ventana del año ya cerró."""
    for digito in range(10):
        for ventana in ventanas_del_anio(digito, ANIO):
            if ventana.fin < HOY:
                return digito, ventana
    return None, None


def _alta(sesion, placa, niv, nombre, con_correo=True):
    cliente = Cliente(
        nombre=nombre, telefono_e164="+522281009584",
        correo=f"{niv[:6].lower()}@correo.com" if con_correo else None,
        consent_whatsapp=True, consent_correo=con_correo,
        consent_origen=OrigenConsentimiento.MOSTRADOR,
        estado_contacto=EstadoContacto.CONTACTABLE,
    )
    sesion.add(cliente)
    sesion.flush()
    vehiculo = Vehiculo(cliente_id=cliente.id, niv=niv, placa=placa,
                        marca="Nissan")
    sesion.add(vehiculo)
    sesion.commit()
    sesion.refresh(vehiculo)
    return cliente, vehiculo


class TestEfectividad:
    def test_sin_datos_no_truena(self, api, sesion_bd, como_admin):
        r = api.get(f"{REP}/efectividad", headers=como_admin).json()
        assert r["con_aviso_porcentaje"] == 0.0
        assert r["sin_aviso_porcentaje"] == 0.0
        assert r["verificaciones_atribuibles"] == 0

    def test_solo_cuenta_periodos_cerrados(self, api, sesion_bd, como_admin):
        """Un vehículo cuyo periodo sigue abierto no debe contarse como
        incumplimiento: todavía puede venir."""
        digito, ventana = _digito_con_ventana_cerrada()
        if digito is None:
            pytest.skip("Aún no cierra ninguna ventana este año.")

        # Placa con ese dígito, sin verificar y sin avisos.
        with sesion_bd() as s:
            _alta(s, f"AAA-00{digito}-A", "1HGCM82633A004352", "Sin Aviso")

        with sesion_bd() as s:
            r = servicio.efectividad_de_recordatorios(s, ANIO, HOY)

        # Se cuenta una vez por cada ventana cerrada de ese dígito.
        cerradas = len([v for v in ventanas_del_anio(digito, ANIO) if v.fin < HOY])
        assert r.sin_aviso_total == cerradas
        assert r.sin_aviso_verificaron == 0

    def test_quien_recibio_aviso_y_verifico_cuenta_del_lado_correcto(
        self, api, sesion_bd, como_admin
    ):
        digito, ventana = _digito_con_ventana_cerrada()
        if digito is None:
            pytest.skip("Aún no cierra ninguna ventana este año.")

        with sesion_bd() as s:
            _, vehiculo = _alta(s, f"BBB-00{digito}-B", "3N1CB51S62K222173",
                                "Con Aviso")
            vid = vehiculo.id

        # Se le manda el aviso de esa ventana…
        with sesion_bd() as s:
            srec.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
            srec.enviar_pendientes(s, datetime(ANIO + 1, 1, 1), silencioso=True)

        # …y verifica dentro del periodo.
        with sesion_bd() as s:
            s.add(Verificacion(
                vehiculo_id=vid, fecha=ventana.inicio + timedelta(days=4),
                resultado=Resultado.APROBADO, holograma="2",
            ))
            s.commit()

        with sesion_bd() as s:
            r = servicio.efectividad_de_recordatorios(s, ANIO, HOY)

        assert r.con_aviso_total >= 1
        assert r.con_aviso_verificaron >= 1
        assert r.con_aviso_porcentaje == 100.0

    def test_un_rechazo_no_cuenta_como_cumplimiento(self, api, sesion_bd):
        digito, ventana = _digito_con_ventana_cerrada()
        if digito is None:
            pytest.skip("Aún no cierra ninguna ventana este año.")

        with sesion_bd() as s:
            _, vehiculo = _alta(s, f"CCC-00{digito}-C", "JH4KA7561PC008269",
                                "Rechazado")
            s.add(Verificacion(
                vehiculo_id=vehiculo.id,
                fecha=ventana.inicio + timedelta(days=2),
                resultado=Resultado.RECHAZADO,
            ))
            s.commit()

        with sesion_bd() as s:
            r = servicio.efectividad_de_recordatorios(s, ANIO, HOY)
        assert r.sin_aviso_verificaron == 0


class TestCumplimiento:
    def test_devuelve_los_cinco_grupos(self, api, como_admin):
        filas = api.get(f"{REP}/cumplimiento", headers=como_admin).json()
        assert [f["digitos"] for f in filas] == [
            "5 – 6", "7 – 8", "3 – 4", "1 – 2", "9 – 0"
        ]

    def test_sin_padron_no_divide_entre_cero(self, api, como_admin):
        filas = api.get(f"{REP}/cumplimiento", headers=como_admin).json()
        assert all(f["porcentaje"] == 0.0 for f in filas)

    def test_cuenta_el_vehiculo_en_su_grupo(self, api, sesion_bd, como_admin):
        with sesion_bd() as s:
            _alta(s, "DDD-007-D", "1HGCM82633A004352", "Digito Siete")
        filas = api.get(f"{REP}/cumplimiento", headers=como_admin).json()
        grupo = next(f for f in filas if f["digitos"] == "7 – 8")
        assert grupo["padron"] == 1


class TestCanales:
    def test_lista_los_dos_canales(self, api, como_admin):
        filas = api.get(f"{REP}/canales", headers=como_admin).json()
        assert {f["canal"] for f in filas} == {"whatsapp", "correo"}

    def test_cuenta_los_enviados(self, api, sesion_bd, como_admin):
        _, ventana = ventanas_del_anio(7, ANIO)
        with sesion_bd() as s:
            _alta(s, "EEE-007-E", "3N1CB51S62K222173", "Ana")
        with sesion_bd() as s:
            srec.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
            srec.enviar_pendientes(s, datetime(ANIO + 1, 1, 1), silencioso=True)

        filas = api.get(f"{REP}/canales", headers=como_admin).json()
        assert sum(f["enviados"] for f in filas) == 2


class TestExportacion:
    def test_descarga_csv(self, api, sesion_bd, como_admin):
        with sesion_bd() as s:
            _, vehiculo = _alta(s, "FFF-007-F", "1HGCM82633A004352", "Ana Pérez")
            s.add(Verificacion(
                vehiculo_id=vehiculo.id, fecha=HOY, resultado=Resultado.APROBADO,
                holograma="2", folio_certificado="VC-0001",
                placa_al_verificar=vehiculo.placa,
            ))
            s.commit()

        r = api.get(f"{REP}/exportar", headers=como_admin)
        assert r.status_code == 200
        assert "attachment" in r.headers["content-disposition"]

        texto = r.content.decode("utf-8")
        # El BOM es lo que hace que Excel en español respete los acentos.
        assert texto.startswith("\ufeff")
        # Y el punto y coma, lo que evita que meta todo en una columna.
        assert ";" in texto.splitlines()[0]
        assert "VC-0001" in texto
        assert "Ana Pérez" in texto

    def test_los_acentos_sobreviven(self, api, sesion_bd, como_admin):
        with sesion_bd() as s:
            _, vehiculo = _alta(s, "GGG-007-G", "JH4KA7561PC008269",
                                "Ana Karen Domínguez Ruiz")
            s.add(Verificacion(vehiculo_id=vehiculo.id, fecha=HOY,
                               resultado=Resultado.APROBADO))
            s.commit()
        texto = api.get(f"{REP}/exportar", headers=como_admin).content.decode("utf-8")
        assert "Domínguez" in texto


class TestPermisos:
    @pytest.mark.parametrize("ruta", ["/efectividad", "/cumplimiento",
                                      "/canales", "/exportar"])
    def test_solo_el_administrador_entra(self, api, como_tecnico, ruta):
        assert api.get(f"{REP}{ruta}", headers=como_tecnico).status_code == 403

    def test_sin_token_no(self, api):
        assert api.get(f"{REP}/efectividad").status_code == 401
