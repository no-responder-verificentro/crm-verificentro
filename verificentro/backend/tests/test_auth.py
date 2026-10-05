"""Pruebas de autenticación y permisos.

Corren contra SQLite en memoria: rápidas y sin depender de que haya un MySQL
levantado. El modelo de empleados no usa nada específico de MySQL, así que la
prueba es representativa.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, obtener_sesion
from app.main import aplicacion
from app.modelos.empleado import Empleado, Perfil
from app.seguridad import hashear_contrasena

CONTRASENA = "verificentro2026"


@pytest.fixture
def cliente():
    # StaticPool: SQLite en memoria vive dentro de UNA conexión. Sin esto,
    # el hilo del TestClient abre otra conexión y encuentra la base vacía.
    motor = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Solo la tabla de empleados: `vehiculos` usa columnas generadas con
    # REGEXP_REPLACE, que SQLite no entiende. Esas se prueban contra MySQL
    # en test_clientes.py.
    Base.metadata.create_all(motor, tables=[Empleado.__table__])
    Sesion = sessionmaker(bind=motor, expire_on_commit=False)

    with Sesion() as s:
        s.add_all([
            Empleado(nombre="Darly Juárez", correo="admin@v.mx",
                     hash_contrasena=hashear_contrasena(CONTRASENA),
                     perfil=Perfil.ADMINISTRADOR),
            Empleado(nombre="José Herrera", correo="tecnico@v.mx",
                     hash_contrasena=hashear_contrasena(CONTRASENA),
                     perfil=Perfil.TECNICO),
            Empleado(nombre="Cristina Vera", correo="atencion@v.mx",
                     hash_contrasena=hashear_contrasena(CONTRASENA),
                     perfil=Perfil.ATENCION),
            Empleado(nombre="Raúl Méndez", correo="baja@v.mx",
                     hash_contrasena=hashear_contrasena(CONTRASENA),
                     perfil=Perfil.TECNICO, activo=False),
        ])
        s.commit()

    def _sesion():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    aplicacion.dependency_overrides[obtener_sesion] = _sesion
    with TestClient(aplicacion) as c:
        yield c
    aplicacion.dependency_overrides.clear()


def entrar(cliente, correo: str) -> dict:
    r = cliente.post("/api/v1/auth/login",
                     json={"correo": correo, "contrasena": CONTRASENA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ------------------------------------------------------------------ login ---

class TestLogin:
    def test_credenciales_correctas_devuelven_token(self, cliente):
        r = cliente.post("/api/v1/auth/login",
                         json={"correo": "admin@v.mx", "contrasena": CONTRASENA})
        assert r.status_code == 200
        assert r.json()["perfil"] == "administrador"
        assert r.json()["access_token"]

    def test_contrasena_incorrecta(self, cliente):
        r = cliente.post("/api/v1/auth/login",
                         json={"correo": "admin@v.mx", "contrasena": "equivocada1"})
        assert r.status_code == 401

    def test_correo_inexistente_da_el_mismo_mensaje(self, cliente):
        # No debe revelar si el correo existe o no.
        r1 = cliente.post("/api/v1/auth/login",
                          json={"correo": "nadie@v.mx", "contrasena": CONTRASENA})
        r2 = cliente.post("/api/v1/auth/login",
                          json={"correo": "admin@v.mx", "contrasena": "equivocada1"})
        assert r1.status_code == r2.status_code == 401
        assert r1.json()["detail"] == r2.json()["detail"]

    def test_empleado_dado_de_baja_no_entra(self, cliente):
        r = cliente.post("/api/v1/auth/login",
                         json={"correo": "baja@v.mx", "contrasena": CONTRASENA})
        assert r.status_code == 403

    def test_la_contrasena_nunca_sale_en_la_respuesta(self, cliente):
        r = cliente.get("/api/v1/auth/yo", headers=entrar(cliente, "admin@v.mx"))
        assert "hash_contrasena" not in r.json()
        assert "contrasena" not in r.json()

    def test_sin_token_no_hay_acceso(self, cliente):
        assert cliente.get("/api/v1/auth/yo").status_code == 401

    def test_token_basura(self, cliente):
        r = cliente.get("/api/v1/auth/yo",
                        headers={"Authorization": "Bearer no-es-un-token"})
        assert r.status_code == 401


# -------------------------------------------------------------- permisos ---

class TestPermisos:
    def test_admin_lista_empleados(self, cliente):
        r = cliente.get("/api/v1/empleados", headers=entrar(cliente, "admin@v.mx"))
        assert r.status_code == 200
        assert len(r.json()) == 3   # los activos

    @pytest.mark.parametrize("correo", ["tecnico@v.mx", "atencion@v.mx"])
    def test_los_demas_perfiles_no_pueden_ver_empleados(self, cliente, correo):
        r = cliente.get("/api/v1/empleados", headers=entrar(cliente, correo))
        assert r.status_code == 403

    def test_tecnico_no_puede_registrar_empleados(self, cliente):
        r = cliente.post("/api/v1/empleados", headers=entrar(cliente, "tecnico@v.mx"),
                         json={"nombre": "Nuevo", "correo": "n@v.mx",
                               "contrasena": CONTRASENA, "perfil": "tecnico"})
        assert r.status_code == 403


class TestAltaDeEmpleados:
    def test_alta_correcta(self, cliente):
        r = cliente.post("/api/v1/empleados", headers=entrar(cliente, "admin@v.mx"),
                         json={"nombre": "Mariana Solís", "correo": "m.solis@v.mx",
                               "contrasena": CONTRASENA, "perfil": "tecnico"})
        assert r.status_code == 201
        assert r.json()["perfil"] == "tecnico"

    def test_correo_repetido(self, cliente):
        r = cliente.post("/api/v1/empleados", headers=entrar(cliente, "admin@v.mx"),
                         json={"nombre": "Otro", "correo": "admin@v.mx",
                               "contrasena": CONTRASENA, "perfil": "tecnico"})
        assert r.status_code == 409

    def test_contrasena_corta_se_rechaza(self, cliente):
        r = cliente.post("/api/v1/empleados", headers=entrar(cliente, "admin@v.mx"),
                         json={"nombre": "Otro", "correo": "otro@v.mx",
                               "contrasena": "123", "perfil": "tecnico"})
        assert r.status_code == 422

    def test_perfil_inventado_se_rechaza(self, cliente):
        r = cliente.post("/api/v1/empleados", headers=entrar(cliente, "admin@v.mx"),
                         json={"nombre": "Otro", "correo": "otro@v.mx",
                               "contrasena": CONTRASENA, "perfil": "superusuario"})
        assert r.status_code == 422


class TestProtecionesContraQuedarseSinAdmin:
    def test_el_admin_no_puede_darse_de_baja_a_si_mismo(self, cliente):
        cab = entrar(cliente, "admin@v.mx")
        yo = cliente.get("/api/v1/auth/yo", headers=cab).json()["id"]
        assert cliente.delete(f"/api/v1/empleados/{yo}", headers=cab).status_code == 400

    def test_el_admin_no_puede_degradarse_a_si_mismo(self, cliente):
        cab = entrar(cliente, "admin@v.mx")
        yo = cliente.get("/api/v1/auth/yo", headers=cab).json()["id"]
        r = cliente.patch(f"/api/v1/empleados/{yo}", headers=cab,
                          json={"perfil": "tecnico"})
        assert r.status_code == 400

    def test_dar_de_baja_desactiva_pero_no_borra(self, cliente):
        cab = entrar(cliente, "admin@v.mx")
        tecnico = [e for e in cliente.get("/api/v1/empleados", headers=cab).json()
                   if e["correo"] == "tecnico@v.mx"][0]

        assert cliente.delete(f"/api/v1/empleados/{tecnico['id']}",
                              headers=cab).status_code == 200
        # Sigue existiendo, solo que inactivo.
        todos = cliente.get("/api/v1/empleados?incluir_bajas=true", headers=cab).json()
        assert any(e["id"] == tecnico["id"] and not e["activo"] for e in todos)

    def test_tras_la_baja_su_token_deja_de_servir(self, cliente):
        cab_tecnico = entrar(cliente, "tecnico@v.mx")
        assert cliente.get("/api/v1/auth/yo", headers=cab_tecnico).status_code == 200

        cab_admin = entrar(cliente, "admin@v.mx")
        tecnico = [e for e in cliente.get("/api/v1/empleados", headers=cab_admin).json()
                   if e["correo"] == "tecnico@v.mx"][0]
        cliente.delete(f"/api/v1/empleados/{tecnico['id']}", headers=cab_admin)

        # El token seguía vigente, pero la cuenta ya no.
        assert cliente.get("/api/v1/auth/yo", headers=cab_tecnico).status_code == 403


# ------------------------------------------------ endpoint público del bot ---

class TestConsultaPublicaDePlaca:
    def test_no_requiere_token(self, cliente):
        r = cliente.get("/api/v1/calendario/consultar",
                        params={"placa": "YUN-047-A", "anio": 2026})
        assert r.status_code == 200

    def test_placa_que_termina_en_letra(self, cliente):
        r = cliente.get("/api/v1/calendario/consultar",
                        params={"placa": "YUN-047-A", "anio": 2026}).json()
        assert r["ultimo_digito"] == 7
        assert r["placa_normalizada"] == "YUN047A"
        assert [p["etiqueta"] for p in r["periodos"]] == [
            "Febrero – Marzo", "Agosto – Septiembre"
        ]

    def test_placa_sin_numeros_da_mensaje_util(self, cliente):
        r = cliente.get("/api/v1/calendario/consultar", params={"placa": "ABC-DEF-G"})
        assert r.status_code == 422
        assert "mostrador" in r.json()["detail"]

    def test_no_devuelve_datos_personales(self, cliente):
        r = cliente.get("/api/v1/calendario/consultar",
                        params={"placa": "YUN-047-A"}).json()
        for campo in ("nombre", "telefono", "correo", "cliente"):
            assert campo not in r
