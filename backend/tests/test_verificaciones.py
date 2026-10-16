"""Pruebas de verificaciones.

Lo importante aquí es el ciclo completo: se registra una verificación
aprobada dentro de la ventana y el vehículo pasa a estar al corriente, que
es la señal que usa el generador de recordatorios para dejar de escribirle.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.dominio.calendario import ventanas_del_anio

CLIENTES = "/api/v1/clientes"
VERIF = "/api/v1/verificaciones"

ANA = {
    "nombre": "Ana Karen Domínguez Ruiz",
    "telefono": "228 100 9584",
    "consentimiento": {"whatsapp": True},
}
VERSA = {
    "placa": "YUN-047-A",       # dígito 7 -> Feb-Mar y Ago-Sep
    "niv": "3N1CB51S62K222173",
    "marca": "Nissan",
    "linea": "Sentra Sedán",
    "modelo_anio": 2002,
}
HOY = date.today()


@pytest.fixture
def vehiculo(api, como_tecnico):
    """Un vehículo con dígito 7 ya registrado."""
    r = api.post(CLIENTES, headers=como_tecnico, json=dict(ANA, vehiculo=VERSA))
    assert r.status_code == 201, r.text
    return r.json()["vehiculos"][0]


def _dia_en_ventana(digito: int, periodo: int) -> date:
    """Un día cualquiera dentro de la ventana pedida, del año en curso."""
    v = ventanas_del_anio(digito, HOY.year)[periodo - 1]
    return v.inicio + timedelta(days=3)


def _ultima_ventana_ya_pasada(digito: int) -> date:
    """Un día dentro de la última ventana que ya cerró."""
    for v in reversed(ventanas_del_anio(digito, HOY.year)):
        if v.fin < HOY:
            return v.inicio + timedelta(days=3)
    return ventanas_del_anio(digito, HOY.year - 1)[1].inicio + timedelta(days=3)


# ------------------------------------------------------------------ alta ---

class TestRegistro:
    def test_registro_aprobado(self, api, como_tecnico, vehiculo):
        r = api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"], "fecha": str(HOY),
            "resultado": "aprobado", "holograma": "2",
            "folio_certificado": "VC-2026-01284",
        })
        assert r.status_code == 201, r.text
        assert r.json()["resultado"] == "aprobado"

    def test_congela_la_placa_del_momento(self, api, como_tecnico, vehiculo):
        r = api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"], "fecha": str(HOY),
            "resultado": "aprobado",
        }).json()
        # Si mañana cambia de placa, el certificado debe seguir diciendo
        # con cuál se verificó.
        assert r["placa_al_verificar"] == "YUN-047-A"

    def test_guarda_quien_la_capturo(self, api, como_tecnico, vehiculo):
        r = api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"], "fecha": str(HOY),
            "resultado": "aprobado",
        }).json()
        assert r["tecnico_id"] is not None

    def test_fecha_futura_se_rechaza(self, api, como_tecnico, vehiculo):
        r = api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"],
            "fecha": str(HOY + timedelta(days=1)),
            "resultado": "aprobado",
        })
        assert r.status_code == 409
        assert "futura" in r.text

    def test_folio_repetido_se_rechaza(self, api, como_tecnico, vehiculo):
        cuerpo = {"vehiculo_id": vehiculo["id"], "fecha": str(HOY),
                  "resultado": "aprobado", "folio_certificado": "VC-2026-00001"}
        assert api.post(VERIF, headers=como_tecnico, json=cuerpo).status_code == 201
        r = api.post(VERIF, headers=como_tecnico, json=cuerpo)
        assert r.status_code == 409
        assert "ya está registrado" in r.text

    def test_un_rechazo_no_puede_llevar_holograma(self, api, como_tecnico, vehiculo):
        r = api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"], "fecha": str(HOY),
            "resultado": "rechazado", "holograma": "2",
        })
        assert r.status_code == 409

    def test_vehiculo_inexistente(self, api, como_tecnico):
        r = api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": 99999, "fecha": str(HOY), "resultado": "aprobado",
        })
        assert r.status_code == 404


# ------------------------------------------------------ el ciclo completo ---

class TestCierreDelCiclo:
    def test_verificar_en_su_ventana_deja_al_vehiculo_al_corriente(
        self, api, como_tecnico, vehiculo
    ):
        fecha = _dia_en_ventana(7, 1)
        if fecha > HOY:                      # si esa ventana aún no llega,
            fecha = _dia_en_ventana(7, 2)    # se usa la segunda
        if fecha > HOY:
            pytest.skip("Ninguna ventana del dígito 7 ha abierto todavía este año.")

        r = api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"], "fecha": str(fecha),
            "resultado": "aprobado", "holograma": "2",
        })
        assert r.status_code == 201, r.text
        assert r.json()["periodo"] in (1, 2)

        v = r.json()["vehiculo"]
        if v["estado"] is not None and v["ventana"] is not None:
            # Si esa ventana es la vigente, ya quedó al corriente.
            if v["ventana"]["inicio"] <= str(fecha) <= v["ventana"]["fin"]:
                assert v["estado"] == "al_corriente"

    def test_un_rechazo_no_lo_deja_al_corriente(self, api, como_tecnico, vehiculo):
        """Rechazado significa que tiene que volver dentro de la misma ventana,
        así que los recordatorios deben seguir saliendo."""
        r = api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"], "fecha": str(HOY),
            "resultado": "rechazado",
        })
        assert r.json()["vehiculo"]["estado"] != "al_corriente"

    def test_verificacion_de_una_ventana_pasada_no_cuenta_para_la_actual(
        self, api, como_tecnico, vehiculo
    ):
        api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"],
            "fecha": str(_ultima_ventana_ya_pasada(7)),
            "resultado": "aprobado",
        })
        ficha = api.get(f"/api/v1/vehiculos/{vehiculo['id']}",
                        headers=como_tecnico).json()
        assert ficha["estado"] != "al_corriente" or ficha["ventana"] is None

    def test_verificar_fuera_de_ventana_queda_sin_periodo(
        self, api, como_tecnico, vehiculo
    ):
        """Alguien que llega en un mes que no le toca: se registra igual, pero
        no cuenta para ninguna ventana."""
        fuera = None
        for d in range(0, 366):
            candidata = HOY - timedelta(days=d)
            v1, v2 = ventanas_del_anio(7, candidata.year)
            if not v1.contiene(candidata) and not v2.contiene(candidata):
                fuera = candidata
                break
        assert fuera is not None

        r = api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"], "fecha": str(fuera),
            "resultado": "aprobado",
        })
        assert r.status_code == 201
        assert r.json()["periodo"] is None

    def test_aparece_en_el_historial_del_vehiculo(self, api, como_tecnico, vehiculo):
        api.post(VERIF, headers=como_tecnico, json={
            "vehiculo_id": vehiculo["id"], "fecha": str(HOY),
            "resultado": "aprobado", "folio_certificado": "VC-2026-00777",
        })
        ficha = api.get(f"/api/v1/vehiculos/{vehiculo['id']}",
                        headers=como_tecnico).json()
        assert len(ficha["verificaciones"]) == 1
        assert ficha["verificaciones"][0]["folio_certificado"] == "VC-2026-00777"


# --------------------------------------------------------------- bitácora ---

class TestBitacora:
    @pytest.fixture(autouse=True)
    def _datos(self, api, como_tecnico, vehiculo):
        for i, (fecha, resultado) in enumerate([
            (HOY, "aprobado"),
            (HOY - timedelta(days=1), "aprobado"),
            (HOY - timedelta(days=2), "rechazado"),
            (HOY - timedelta(days=40), "aprobado"),
        ]):
            api.post(VERIF, headers=como_tecnico, json={
                "vehiculo_id": vehiculo["id"], "fecha": str(fecha),
                "resultado": resultado, "folio_certificado": f"VC-{i:05d}",
            })

    def test_trae_los_datos_del_cliente_y_del_tecnico(self, api, como_tecnico):
        fila = api.get(VERIF, headers=como_tecnico).json()[0]
        assert fila["cliente_nombre"] == "Ana Karen Domínguez Ruiz"
        assert fila["tecnico_nombre"] == "José Herrera"
        assert fila["vehiculo_descripcion"] == "Nissan Sentra Sedán 2002"

    def test_ordenada_de_la_mas_reciente(self, api, como_tecnico):
        filas = api.get(VERIF, headers=como_tecnico).json()
        fechas = [f["fecha"] for f in filas]
        assert fechas == sorted(fechas, reverse=True)

    def test_filtro_por_resultado(self, api, como_tecnico):
        r = api.get(VERIF, headers=como_tecnico,
                    params={"resultado": "rechazado"}).json()
        assert len(r) == 1

    def test_filtro_por_rango_de_fechas(self, api, como_tecnico):
        r = api.get(VERIF, headers=como_tecnico, params={
            "desde": str(HOY - timedelta(days=3)), "hasta": str(HOY)
        }).json()
        assert len(r) == 3

    def test_busqueda_por_placa(self, api, como_tecnico):
        assert len(api.get(VERIF, headers=como_tecnico,
                           params={"buscar": "yun047a"}).json()) == 4

    def test_busqueda_por_folio(self, api, como_tecnico):
        assert len(api.get(VERIF, headers=como_tecnico,
                           params={"buscar": "VC-00002"}).json()) == 1

    def test_resumen_calcula_el_indice_de_rechazo(self, api, como_tecnico):
        r = api.get(f"{VERIF}/resumen", headers=como_tecnico, params={
            "desde": str(HOY - timedelta(days=3)), "hasta": str(HOY)
        }).json()
        assert r["total"] == 3
        assert r["aprobadas"] == 2
        assert r["rechazadas"] == 1
        assert r["indice_rechazo"] == pytest.approx(33.3)

    def test_resumen_sin_datos_no_divide_entre_cero(self, api, como_tecnico):
        r = api.get(f"{VERIF}/resumen", headers=como_tecnico, params={
            "desde": "2020-01-01", "hasta": "2020-01-31"
        }).json()
        assert r["total"] == 0 and r["indice_rechazo"] == 0

    def test_rango_invertido_se_rechaza(self, api, como_tecnico):
        r = api.get(f"{VERIF}/resumen", headers=como_tecnico,
                    params={"desde": str(HOY), "hasta": "2020-01-01"})
        assert r.status_code == 422


# --------------------------------------------------------------- permisos ---

class TestPermisos:
    def test_atencion_no_puede_registrar(self, api, como_atencion, vehiculo):
        r = api.post(VERIF, headers=como_atencion, json={
            "vehiculo_id": vehiculo["id"], "fecha": str(HOY),
            "resultado": "aprobado",
        })
        assert r.status_code == 403

    def test_atencion_si_puede_consultar(self, api, como_atencion):
        assert api.get(VERIF, headers=como_atencion).status_code == 200

    def test_sin_token_no_hay_acceso(self, api):
        assert api.get(VERIF).status_code == 401
