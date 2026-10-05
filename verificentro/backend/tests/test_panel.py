"""Pruebas de la pantalla de Recordatorios y del panel de control."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.dominio.calendario import fechas_de_aviso, ventanas_del_anio
from app.modelos.cliente import Cliente, EstadoContacto, OrigenConsentimiento
from app.modelos.recordatorio import EstadoRecordatorio, Recordatorio
from app.modelos.vehiculo import Resultado, Vehiculo, Verificacion
from app.servicios import recordatorios as servicio

REC = "/api/v1/recordatorios"
PANEL = "/api/v1/panel"
ANIO = date.today().year


def _cliente_y_auto(sesion, placa, niv, nombre="Ana Karen Domínguez"):
    cliente = Cliente(
        nombre=nombre, telefono_e164="+522281009584", correo="ana@correo.com",
        consent_whatsapp=True, consent_correo=True,
        consent_origen=OrigenConsentimiento.MOSTRADOR,
        estado_contacto=EstadoContacto.CONTACTABLE,
    )
    sesion.add(cliente)
    sesion.flush()
    vehiculo = Vehiculo(cliente_id=cliente.id, niv=niv, placa=placa, marca="Nissan")
    sesion.add(vehiculo)
    sesion.commit()
    sesion.refresh(vehiculo)
    return cliente, vehiculo


@pytest.fixture
def con_cola(api, sesion_bd):
    """Un auto de dígito 7 con su cola de avisos ya generada."""
    with sesion_bd() as s:
        _cliente_y_auto(s, "YUN-047-A", "3N1CB51S62K222173")
    _, ventana = ventanas_del_anio(7, ANIO)
    with sesion_bd() as s:
        servicio.generar_del_dia(s, fechas_de_aviso(ventana)[1].fecha)
    return api


class TestCola:
    def test_la_cola_trae_nombre_y_placa(self, con_cola, como_tecnico):
        filas = con_cola.get(REC + "/cola", headers=como_tecnico,
                             params={"horas": 24 * 399}).json()
        assert len(filas) == 2
        assert filas[0]["cliente_nombre"] == "Ana Karen Domínguez"
        assert filas[0]["placa"] == "YUN-047-A"
        assert filas[0]["ventana"] == "Agosto – Septiembre"

    def test_muestra_los_dos_canales(self, con_cola, como_tecnico):
        filas = con_cola.get(REC + "/cola", headers=como_tecnico,
                             params={"horas": 24 * 399}).json()
        assert {f["canal"] for f in filas} == {"whatsapp", "correo"}

    def test_atencion_puede_consultar(self, con_cola, como_atencion):
        assert con_cola.get(REC + "/cola", headers=como_atencion).status_code == 200

    def test_sin_token_no(self, api):
        assert api.get(REC + "/cola").status_code == 401


class TestControlManual:
    def _uno(self, api, cab):
        return api.get(REC + "/cola", headers=cab,
                       params={"horas": 24 * 399}).json()[0]

    def test_pausar_y_reanudar(self, con_cola, como_admin):
        fila = self._uno(con_cola, como_admin)

        r = con_cola.post(f"{REC}/{fila['id']}/pausar", headers=como_admin,
                          json={"motivo": "El cliente pidió esperar"})
        assert r.status_code == 200
        assert r.json()["estado"] == "pausado"

        r = con_cola.post(f"{REC}/{fila['id']}/reanudar", headers=como_admin)
        assert r.json()["estado"] == "programado"

    def test_un_pausado_no_se_envia(self, con_cola, como_admin, sesion_bd):
        fila = self._uno(con_cola, como_admin)
        con_cola.post(f"{REC}/{fila['id']}/pausar", headers=como_admin, json={})

        with sesion_bd() as s:
            r = servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1),
                                           silencioso=True)
        assert r.enviados == 1      # solo el que quedó activo

    def test_cancelar_es_definitivo(self, con_cola, como_admin):
        fila = self._uno(con_cola, como_admin)
        assert con_cola.post(f"{REC}/{fila['id']}/cancelar",
                             headers=como_admin).json()["estado"] == "cancelado"
        r = con_cola.post(f"{REC}/{fila['id']}/pausar", headers=como_admin, json={})
        assert r.status_code == 409

    def test_el_tecnico_no_puede_pausar(self, con_cola, como_tecnico):
        fila = self._uno(con_cola, como_tecnico)
        r = con_cola.post(f"{REC}/{fila['id']}/pausar", headers=como_tecnico,
                          json={})
        assert r.status_code == 403


class TestResumen:
    def test_cuenta_los_enviados(self, con_cola, como_tecnico, sesion_bd):
        with sesion_bd() as s:
            servicio.enviar_pendientes(s, datetime(ANIO + 1, 1, 1), silencioso=True)
        r = con_cola.get(REC + "/resumen", headers=como_tecnico).json()
        assert r["tasa_entrega"] == 100.0
        assert r["no_entregados"] == 0

    def test_sin_datos_no_divide_entre_cero(self, api, como_tecnico):
        r = api.get(REC + "/resumen", headers=como_tecnico).json()
        assert r["tasa_entrega"] == 0.0


class TestPanel:
    @pytest.fixture(autouse=True)
    def _datos(self, api, sesion_bd):
        with sesion_bd() as s:
            # Uno que ya verificó en su ventana vigente.
            _, v1 = _cliente_y_auto(s, "AAA-007-A", "1HGCM82633A004352", "Ya Cumplió")
            for ventana in ventanas_del_anio(7, ANIO):
                if ventana.contiene(date.today()):
                    s.add(Verificacion(
                        vehiculo_id=v1.id, fecha=ventana.inicio + timedelta(days=1),
                        resultado=Resultado.APROBADO, holograma="2",
                    ))
            # Otro sin verificar.
            _cliente_y_auto(s, "BBB-018-B", "JH4KA7561PC008269", "Le Falta")
            s.commit()

    def test_indicadores(self, api, como_tecnico):
        r = api.get(PANEL + "/indicadores", headers=como_tecnico)
        assert r.status_code == 200
        d = r.json()
        assert d["al_corriente"] + d["periodo_abierto"] + d["por_vencer"] \
            + d["vencidos"] + 0 >= 1

    def test_seguimiento_ordena_lo_urgente_primero(self, api, como_tecnico):
        filas = api.get(PANEL + "/seguimiento", headers=como_tecnico).json()
        prioridad = {"vencido": 0, "por_vencer": 1, "periodo_abierto": 2,
                     "al_corriente": 3, "programado": 4}
        valores = [prioridad[f["estado"]] for f in filas]
        assert valores == sorted(valores)

    def test_seguimiento_filtra_por_estado(self, api, como_tecnico):
        filas = api.get(PANEL + "/seguimiento", headers=como_tecnico,
                        params={"estado": "al_corriente"}).json()
        assert all(f["estado"] == "al_corriente" for f in filas)

    def test_seguimiento_dice_si_se_le_puede_escribir(self, api, como_tecnico):
        filas = api.get(PANEL + "/seguimiento", headers=como_tecnico).json()
        assert all("se_le_puede_escribir" in f for f in filas)

    def test_la_grafica_devuelve_meses(self, api, como_tecnico):
        r = api.get(PANEL + "/grafica", headers=como_tecnico)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
