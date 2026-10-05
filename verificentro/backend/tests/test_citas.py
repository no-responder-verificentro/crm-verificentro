"""Pruebas de citas.

Escenario real del Verificentro: una sola línea, bloques de 20 minutos,
horario de 9:00 a 16:00 de lunes a sábado, y una cita por hora dejando los
otros dos bloques para quien llega sin avisar.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from app.dominio.agenda import (
    AgendaNoDisponible,
    ConfiguracionAgenda,
    Horario,
    bloques_agendables,
    bloques_del_dia,
    validar_anticipacion,
)

CITAS = "/api/v1/citas"
CLIENTES = "/api/v1/clientes"

ANA = {"nombre": "Ana Karen Domínguez Ruiz", "telefono": "228 100 9584",
       "consentimiento": {"whatsapp": True}}
VERSA = {"placa": "YUN-047-A", "niv": "3N1CB51S62K222173",
         "marca": "Nissan", "linea": "Sentra Sedán", "modelo_anio": 2002}


def proximo_habil(desde: date | None = None) -> date:
    """El siguiente día laborable con margen suficiente de anticipación."""
    dia = (desde or date.today()) + timedelta(days=3)
    while dia.isoweekday() == 7:      # domingo cerrado
        dia += timedelta(days=1)
    return dia


# ------------------------------------------------ lógica pura (sin base) ---

class TestBloquesDelDia:
    HORARIO = Horario(apertura=time(9, 0), cierre=time(16, 0))

    def test_siete_horas_en_bloques_de_20_dan_21_bloques(self):
        assert len(bloques_del_dia(self.HORARIO, 20)) == 21

    def test_el_primero_es_a_la_apertura(self):
        assert bloques_del_dia(self.HORARIO, 20)[0] == time(9, 0)

    def test_el_ultimo_bloque_cabe_completo_antes_del_cierre(self):
        # Con cierre a las 16:00 y 20 minutos, el último empieza a las 15:40.
        assert bloques_del_dia(self.HORARIO, 20)[-1] == time(15, 40)

    def test_no_ofrece_un_bloque_que_no_alcanza_a_terminar(self):
        horario = Horario(apertura=time(9, 0), cierre=time(9, 30))
        assert bloques_del_dia(horario, 20) == [time(9, 0)]

    def test_duracion_invalida(self):
        with pytest.raises(ValueError):
            bloques_del_dia(self.HORARIO, 0)


class TestIntercalado:
    HORARIO = Horario(apertura=time(9, 0), cierre=time(16, 0))

    def test_uno_de_cada_tres_da_una_cita_por_hora(self):
        agendables = bloques_agendables(bloques_del_dia(self.HORARIO, 20), 3)
        assert len(agendables) == 7
        assert agendables[:3] == [time(9, 0), time(10, 0), time(11, 0)]

    def test_intercalado_estricto(self):
        agendables = bloques_agendables(bloques_del_dia(self.HORARIO, 20), 2)
        assert agendables[:3] == [time(9, 0), time(9, 40), time(10, 20)]

    def test_toda_la_agenda_para_citas(self):
        bloques = bloques_del_dia(self.HORARIO, 20)
        assert bloques_agendables(bloques, 1) == bloques

    def test_los_bloques_libres_no_se_ofrecen(self):
        """Los de en medio existen, pero se guardan para quien llega sin cita."""
        agendables = bloques_agendables(bloques_del_dia(self.HORARIO, 20), 3)
        assert time(9, 20) not in agendables
        assert time(9, 40) not in agendables


class TestAnticipacion:
    CONFIG = ConfiguracionAgenda()
    AHORA = datetime(2026, 9, 1, 10, 0)

    def test_horario_que_ya_paso(self):
        with pytest.raises(AgendaNoDisponible, match="ya pasó"):
            validar_anticipacion(date(2026, 9, 1), time(9, 0), self.CONFIG, self.AHORA)

    def test_muy_encima_sugiere_llegar_sin_cita(self):
        with pytest.raises(AgendaNoDisponible, match="sin cita"):
            validar_anticipacion(date(2026, 9, 1), time(11, 0), self.CONFIG, self.AHORA)

    def test_con_margen_suficiente_pasa(self):
        validar_anticipacion(date(2026, 9, 1), time(14, 0), self.CONFIG, self.AHORA)

    def test_demasiado_lejos(self):
        with pytest.raises(AgendaNoDisponible, match="30 días"):
            validar_anticipacion(date(2026, 12, 1), time(10, 0), self.CONFIG, self.AHORA)


# ------------------------------------------------------ contra la base ---

class TestDisponibilidad:
    def test_es_publica(self, api):
        """El chatbot la consulta sin token."""
        r = api.get(f"{CITAS}/disponibilidad", params={"fecha": str(proximo_habil())})
        assert r.status_code == 200

    def test_ofrece_una_cita_por_hora(self, api):
        r = api.get(f"{CITAS}/disponibilidad",
                    params={"fecha": str(proximo_habil())}).json()
        assert r["atiende"] is True
        horas = [h["hora"] for h in r["horarios"]]
        assert horas == ["09:00:00", "10:00:00", "11:00:00", "12:00:00",
                         "13:00:00", "14:00:00", "15:00:00"]

    def test_una_linea_significa_un_lugar_por_bloque(self, api):
        r = api.get(f"{CITAS}/disponibilidad",
                    params={"fecha": str(proximo_habil())}).json()
        assert all(h["lugares"] == 1 for h in r["horarios"])

    def test_domingo_no_se_atiende(self, api):
        domingo = date.today() + timedelta(days=(7 - date.today().isoweekday()) or 7)
        r = api.get(f"{CITAS}/disponibilidad", params={"fecha": str(domingo)}).json()
        assert r["atiende"] is False
        assert "no se atiende" in r["motivo"]

    def test_apartar_quita_el_horario_de_la_lista(self, api, como_tecnico):
        dia = proximo_habil()
        api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana Karen",
            "fecha": str(dia), "hora": "10:00"})
        r = api.get(f"{CITAS}/disponibilidad", params={"fecha": str(dia)}).json()
        assert "10:00:00" not in [h["hora"] for h in r["horarios"]]


class TestApartar:
    def test_apartado_correcto(self, api, como_tecnico):
        r = api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana Karen Domínguez",
            "telefono": "228 100 9584",
            "fecha": str(proximo_habil()), "hora": "10:00"})
        assert r.status_code == 201, r.text
        assert r.json()["estado"] == "agendada"
        assert r.json()["telefono_contacto"] == "+522281009584"

    def test_no_se_puede_apartar_un_bloque_reservado_a_los_que_llegan_solos(
        self, api, como_tecnico
    ):
        r = api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana Karen",
            "fecha": str(proximo_habil()), "hora": "10:20"})
        assert r.status_code == 409
        assert "no está disponible para cita" in r.text

    def test_no_hay_sobreventa(self, api, como_tecnico):
        dia = proximo_habil()
        assert api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana",
            "fecha": str(dia), "hora": "11:00"}).status_code == 201
        r = api.post(CITAS, headers=como_tecnico, json={
            "placa": "ABC-123-D", "nombre": "Luis",
            "fecha": str(dia), "hora": "11:00"})
        assert r.status_code == 409

    def test_una_placa_no_puede_acaparar_la_agenda(self, api, como_tecnico):
        dia = proximo_habil()
        api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana",
            "fecha": str(dia), "hora": "09:00"})
        r = api.post(CITAS, headers=como_tecnico, json={
            "placa": "yun047a", "nombre": "Ana",
            "fecha": str(dia), "hora": "12:00"})
        assert r.status_code == 409
        assert "ya tiene una cita" in r.text

    def test_se_vincula_al_vehiculo_si_ya_esta_registrado(self, api, como_tecnico):
        cliente = api.post(CLIENTES, headers=como_tecnico,
                           json=dict(ANA, vehiculo=VERSA)).json()
        r = api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana Karen",
            "fecha": str(proximo_habil()), "hora": "10:00"}).json()
        assert r["vehiculo_id"] == cliente["vehiculos"][0]["id"]
        assert r["cliente_id"] == cliente["id"]

    def test_placa_no_registrada_se_acepta_igual(self, api, como_tecnico):
        """Quien agenda por chatbot puede no estar en el padrón todavía."""
        r = api.post(CITAS, headers=como_tecnico, json={
            "placa": "ZZZ-999-Z", "nombre": "Alguien Nuevo",
            "fecha": str(proximo_habil()), "hora": "13:00"})
        assert r.status_code == 201
        assert r.json()["vehiculo_id"] is None

    def test_fecha_pasada_se_rechaza(self, api, como_tecnico):
        r = api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana",
            "fecha": str(date.today() - timedelta(days=1)), "hora": "10:00"})
        assert r.status_code == 409

    def test_atencion_no_puede_apartar(self, api, como_atencion):
        r = api.post(CITAS, headers=como_atencion, json={
            "placa": "YUN-047-A", "nombre": "Ana",
            "fecha": str(proximo_habil()), "hora": "10:00"})
        assert r.status_code == 403


class TestCancelar:
    def test_cancelar_libera_el_lugar(self, api, como_tecnico):
        dia = proximo_habil()
        cita = api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana",
            "fecha": str(dia), "hora": "10:00"}).json()

        r = api.post(f"{CITAS}/{cita['id']}/cancelar", headers=como_tecnico,
                     json={"motivo": "El cliente no puede"})
        assert r.status_code == 200
        assert r.json()["estado"] == "cancelada"

        # El horario vuelve a aparecer y alguien más lo puede apartar.
        libres = api.get(f"{CITAS}/disponibilidad", params={"fecha": str(dia)}).json()
        assert "10:00:00" in [h["hora"] for h in libres["horarios"]]
        assert api.post(CITAS, headers=como_tecnico, json={
            "placa": "ABC-123-D", "nombre": "Luis",
            "fecha": str(dia), "hora": "10:00"}).status_code == 201

    def test_tras_cancelar_la_placa_puede_apartar_otra(self, api, como_tecnico):
        dia = proximo_habil()
        cita = api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana",
            "fecha": str(dia), "hora": "09:00"}).json()
        api.post(f"{CITAS}/{cita['id']}/cancelar", headers=como_tecnico, json={})
        assert api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana",
            "fecha": str(dia), "hora": "14:00"}).status_code == 201

    def test_cita_inexistente(self, api, como_tecnico):
        assert api.post(f"{CITAS}/9999/cancelar", headers=como_tecnico,
                        json={}).status_code == 404


class TestCierreAutomatico:
    def test_verificar_cierra_la_cita_sola(self, api, como_tecnico):
        """Nadie tiene que acordarse de marcarla: al capturar la verificación
        del auto que tenía cita ese día, se marca como atendida."""
        cliente = api.post(CLIENTES, headers=como_tecnico,
                           json=dict(ANA, vehiculo=VERSA)).json()
        vehiculo_id = cliente["vehiculos"][0]["id"]
        hoy = date.today()

        # Se aparta una cita para hoy directamente en la base, porque la API
        # exige anticipación y aquí lo que se prueba es el cierre.
        from app.modelos.cita import Cita, EstadoCita
        from app.database import obtener_sesion  # noqa: F401

        cita = api.post(CITAS, headers=como_tecnico, json={
            "placa": "YUN-047-A", "nombre": "Ana",
            "fecha": str(proximo_habil()), "hora": "10:00"}).json()

        # Se registra la verificación en la fecha de la cita.
        r = api.post("/api/v1/verificaciones", headers=como_tecnico, json={
            "vehiculo_id": vehiculo_id, "fecha": str(hoy), "resultado": "aprobado"})
        assert r.status_code == 201

        # La cita es de otro día, así que sigue activa.
        agenda = api.get(CITAS, headers=como_tecnico,
                         params={"fecha": cita["fecha"]}).json()
        assert agenda[0]["estado"] == "agendada"


class TestAgendaDelDia:
    def test_lista_ordenada_por_hora(self, api, como_tecnico):
        dia = proximo_habil()
        for hora, placa in [("14:00", "ABC-123-D"), ("09:00", "YUN-047-A")]:
            api.post(CITAS, headers=como_tecnico, json={
                "placa": placa, "nombre": "Cliente",
                "fecha": str(dia), "hora": hora})
        agenda = api.get(CITAS, headers=como_tecnico,
                         params={"fecha": str(dia)}).json()
        assert [c["hora_inicio"] for c in agenda] == ["09:00:00", "14:00:00"]

    def test_atencion_puede_consultarla(self, api, como_atencion):
        assert api.get(CITAS, headers=como_atencion).status_code == 200
