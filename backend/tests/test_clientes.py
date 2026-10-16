"""Pruebas de clientes y vehículos.

Corren contra MySQL porque `placa_normalizada` y `ultimo_digito` son columnas
generadas por la base. Ver tests/conftest.py para la variable TEST_DB_URL.
"""

from __future__ import annotations

import pytest

BASE = "/api/v1/clientes"

ANA = {
    "nombre": "Ana Karen Domínguez Ruiz",
    "telefono": "228 100 9584",
    "correo": "akdominguez@correo.com",
    "consentimiento": {"whatsapp": True, "correo": True, "origen": "mostrador"},
}

VERSA = {
    "placa": "YUN-047-A",
    "niv": "3N1CB51S62K222173",
    "marca": "Nissan",
    "linea": "Sentra Sedán",
    "modelo_anio": 2002,
    "color": "Rojo intenso",
    "combustible": "gasolina",
}


def alta(api, cabecera, cliente=None, vehiculo=None):
    cuerpo = dict(cliente or ANA)
    if vehiculo is not None:
        cuerpo["vehiculo"] = vehiculo
    return api.post(BASE, headers=cabecera, json=cuerpo)


# ------------------------------------------------------------------ altas --

class TestAltaDeCliente:
    def test_alta_simple(self, api, como_tecnico):
        r = alta(api, como_tecnico)
        assert r.status_code == 201, r.text
        assert r.json()["nombre"] == "Ana Karen Domínguez Ruiz"

    def test_los_acentos_sobreviven_el_viaje(self, api, como_tecnico):
        # Si la conexión no fuera utf8mb4, aquí saldría basura.
        cid = alta(api, como_tecnico).json()["id"]
        r = api.get(f"{BASE}/{cid}", headers=como_tecnico).json()
        assert r["nombre"] == "Ana Karen Domínguez Ruiz"

    def test_el_telefono_se_guarda_en_e164(self, api, como_tecnico):
        r = alta(api, como_tecnico).json()
        assert r["telefono_e164"] == "+522281009584"

    @pytest.mark.parametrize("escrito", [
        "2281009584", "228 100 9584", "(228) 100-95-84",
        "+52 228 100 9584", "52 228 100 9584", "1 228 100 9584",
    ])
    def test_acepta_como_sea_que_lo_dicten(self, api, como_tecnico, escrito):
        cliente = dict(ANA, telefono=escrito, correo=None,
                       consentimiento={"whatsapp": True})
        r = alta(api, como_tecnico, cliente=cliente)
        assert r.status_code == 201, r.text
        assert r.json()["telefono_e164"] == "+522281009584"

    def test_telefono_de_menos_digitos_se_rechaza(self, api, como_tecnico):
        cliente = dict(ANA, telefono="228 100")
        assert alta(api, como_tecnico, cliente=cliente).status_code == 422

    def test_consentimiento_de_whatsapp_sin_telefono_se_rechaza(self, api, como_tecnico):
        cliente = {"nombre": "Sin Teléfono Pérez",
                   "consentimiento": {"whatsapp": True}}
        r = alta(api, como_tecnico, cliente=cliente)
        assert r.status_code == 422
        assert "teléfono" in r.text

    def test_sin_consentimiento_no_se_le_puede_escribir(self, api, como_tecnico):
        cliente = dict(ANA, consentimiento={"whatsapp": False, "correo": False})
        assert alta(api, como_tecnico, cliente=cliente).json()["se_le_puede_escribir"] is False

    def test_con_consentimiento_si(self, api, como_tecnico):
        assert alta(api, como_tecnico).json()["se_le_puede_escribir"] is True


# --------------------------------------------------------------- vehículos --

class TestAltaDeVehiculo:
    def test_alta_junto_con_el_cliente(self, api, como_tecnico):
        r = alta(api, como_tecnico, vehiculo=VERSA)
        assert r.status_code == 201, r.text
        assert len(r.json()["vehiculos"]) == 1

    def test_la_base_calcula_el_ultimo_digito_de_una_placa_con_letra(
        self, api, como_tecnico
    ):
        v = alta(api, como_tecnico, vehiculo=VERSA).json()["vehiculos"][0]
        assert v["placa_normalizada"] == "YUN047A"
        assert v["ultimo_digito"] == 7      # el 7, no la 'A'

    def test_el_estado_se_calcula_solo(self, api, como_tecnico):
        v = alta(api, como_tecnico, vehiculo=VERSA).json()["vehiculos"][0]
        assert v["estado"] is not None
        assert v["ventana"]["etiqueta"] in ("Febrero – Marzo", "Agosto – Septiembre")

    def test_placa_sin_ningun_numero_se_rechaza(self, api, como_tecnico):
        r = alta(api, como_tecnico, vehiculo=dict(VERSA, placa="ABC-DEF-G"))
        assert r.status_code == 422
        assert "número" in r.text

    def test_niv_con_letras_confusas_se_rechaza(self, api, como_tecnico):
        # La I y la O no existen en un NIV: son un 1 y un 0 mal transcritos.
        r = alta(api, como_tecnico, vehiculo=dict(VERSA, niv="3N1CB51SO2K222I73"))
        assert r.status_code == 422
        assert "1 o un 0" in r.text

    def test_niv_repetido_se_rechaza_con_explicacion(self, api, como_tecnico):
        alta(api, como_tecnico, vehiculo=VERSA)
        otro = dict(ANA, telefono="229 305 7781", correo="otro@correo.com")
        r = alta(api, como_tecnico, cliente=otro,
                 vehiculo=dict(VERSA, placa="ABC-123-D"))
        assert r.status_code == 409
        assert "cambio de placa" in r.text

    def test_placa_repetida_se_rechaza(self, api, como_tecnico):
        alta(api, como_tecnico, vehiculo=VERSA)
        otro = dict(ANA, telefono="229 305 7781", correo="otro@correo.com")
        r = alta(api, como_tecnico, cliente=otro,
                 vehiculo=dict(VERSA, niv="1HGCM82633A004352"))
        assert r.status_code == 409

    def test_un_cliente_puede_tener_varios_vehiculos(self, api, como_tecnico):
        cid = alta(api, como_tecnico, vehiculo=VERSA).json()["id"]
        r = api.post(f"{BASE}/{cid}/vehiculos", headers=como_tecnico,
                     json=dict(VERSA, placa="GHT-21-33", niv="1HGCM82633A004352"))
        assert r.status_code == 201, r.text
        assert r.json()["ultimo_digito"] == 3

        ficha = api.get(f"{BASE}/{cid}", headers=como_tecnico).json()
        assert len(ficha["vehiculos"]) == 2
        # Cada uno con su propio calendario.
        assert {v["ultimo_digito"] for v in ficha["vehiculos"]} == {7, 3}

    def test_placa_de_otro_estado_queda_fuera_del_programa(self, api, como_tecnico):
        r = alta(api, como_tecnico,
                 vehiculo=dict(VERSA, entidad_placa="PUE"))
        v = r.json()["vehiculos"][0]
        assert v["en_programa_estatal"] is False
        # Sin calendario de Veracruz: no se le generan recordatorios.
        assert v["estado"] is None


class TestCambioDePlaca:
    def test_cambiar_placa_puede_cambiar_el_periodo(self, api, como_tecnico):
        """El caso de la tarjeta real: antes YJX-704-5, ahora YUN-047-A."""
        cid = alta(api, como_tecnico,
                   vehiculo=dict(VERSA, placa="YJX-704-5")).json()["id"]
        v = api.get(f"{BASE}/{cid}", headers=como_tecnico).json()["vehiculos"][0]
        assert v["ultimo_digito"] == 5      # Enero-Febrero / Julio-Agosto

        r = api.post(f"/api/v1/vehiculos/{v['id']}/cambio-de-placa",
                     headers=como_tecnico,
                     json={"placa_nueva": "YUN-047-A",
                           "vigente_desde": "2019-07-11",
                           "motivo": "reemplazo"})
        assert r.status_code == 200, r.text
        assert r.json()["ultimo_digito"] == 7   # Febrero-Marzo / Agosto-Septiembre

    def test_no_se_duplica_el_vehiculo_al_cambiar_placa(self, api, como_tecnico):
        cid = alta(api, como_tecnico,
                   vehiculo=dict(VERSA, placa="YJX-704-5")).json()["id"]
        vid = api.get(f"{BASE}/{cid}", headers=como_tecnico).json()["vehiculos"][0]["id"]
        api.post(f"/api/v1/vehiculos/{vid}/cambio-de-placa", headers=como_tecnico,
                 json={"placa_nueva": "YUN-047-A", "vigente_desde": "2019-07-11"})
        # Sigue siendo el mismo auto, con el mismo NIV.
        ficha = api.get(f"{BASE}/{cid}", headers=como_tecnico).json()
        assert len(ficha["vehiculos"]) == 1
        assert ficha["vehiculos"][0]["niv"] == VERSA["niv"]

    def test_no_se_puede_poner_una_placa_ya_usada(self, api, como_tecnico):
        cid = alta(api, como_tecnico, vehiculo=VERSA).json()["id"]
        api.post(f"{BASE}/{cid}/vehiculos", headers=como_tecnico,
                 json=dict(VERSA, placa="GHT-21-33", niv="1HGCM82633A004352"))
        vid = api.get(f"{BASE}/{cid}", headers=como_tecnico).json()["vehiculos"][0]["id"]
        r = api.post(f"/api/v1/vehiculos/{vid}/cambio-de-placa", headers=como_tecnico,
                     json={"placa_nueva": "GHT-21-33", "vigente_desde": "2026-01-01"})
        assert r.status_code == 409


# --------------------------------------------------------------- búsqueda --

class TestBusquedaUnificada:
    @pytest.fixture(autouse=True)
    def _datos(self, api, como_tecnico):
        alta(api, como_tecnico, vehiculo=VERSA)
        alta(api, como_tecnico,
             cliente={"nombre": "Transportes del Golfo S.A.",
                      "telefono": "229 940 2210",
                      "consentimiento": {"whatsapp": True}},
             vehiculo=dict(VERSA, placa="GHT-21-33", niv="1HGCM82633A004352"))

    def _buscar(self, api, cab, texto):
        return api.get(BASE, headers=cab, params={"buscar": texto}).json()

    def test_por_nombre(self, api, como_tecnico):
        assert len(self._buscar(api, como_tecnico, "Golfo")) == 1

    def test_por_placa_con_guiones(self, api, como_tecnico):
        r = self._buscar(api, como_tecnico, "YUN-047-A")
        assert len(r) == 1 and r[0]["nombre"].startswith("Ana")

    def test_por_placa_sin_guiones(self, api, como_tecnico):
        assert len(self._buscar(api, como_tecnico, "yun047a")) == 1

    def test_por_niv(self, api, como_tecnico):
        assert len(self._buscar(api, como_tecnico, "3N1CB51S62K222173")) == 1

    def test_por_telefono_como_lo_dicta_el_cliente(self, api, como_tecnico):
        assert len(self._buscar(api, como_tecnico, "228 100 9584")) == 1

    def test_sin_texto_devuelve_todos(self, api, como_tecnico):
        assert len(api.get(BASE, headers=como_tecnico).json()) == 2


# --------------------------------------------------------------- permisos --

class TestPermisos:
    def test_atencion_puede_consultar(self, api, como_atencion, como_tecnico):
        alta(api, como_tecnico)
        assert api.get(BASE, headers=como_atencion).status_code == 200

    def test_atencion_no_puede_registrar(self, api, como_atencion):
        assert alta(api, como_atencion).status_code == 403

    def test_tecnico_no_puede_editar_datos_de_contacto(self, api, como_tecnico):
        cid = alta(api, como_tecnico).json()["id"]
        r = api.patch(f"{BASE}/{cid}", headers=como_tecnico,
                      json={"telefono": "229 305 7781"})
        assert r.status_code == 403

    def test_el_admin_si_puede(self, api, como_tecnico, como_admin):
        cid = alta(api, como_tecnico).json()["id"]
        r = api.patch(f"{BASE}/{cid}", headers=como_admin,
                      json={"telefono": "229 305 7781"})
        assert r.status_code == 200
        assert r.json()["telefono_e164"] == "+522293057781"

    def test_sin_token_no_hay_acceso(self, api):
        assert api.get(BASE).status_code == 401


class TestBajaDeContacto:
    def test_la_baja_apaga_los_consentimientos_pero_conserva_al_cliente(
        self, api, como_tecnico
    ):
        cid = alta(api, como_tecnico, vehiculo=VERSA).json()["id"]
        r = api.post(f"{BASE}/{cid}/baja-de-contacto", headers=como_tecnico).json()

        assert r["estado_contacto"] == "baja"
        assert r["consent_whatsapp"] is False
        assert r["se_le_puede_escribir"] is False

        # Sigue existiendo, con su vehículo, para la bitácora.
        ficha = api.get(f"{BASE}/{cid}", headers=como_tecnico).json()
        assert len(ficha["vehiculos"]) == 1
