"""Infraestructura de pruebas.

Los modelos de `vehiculos` usan columnas GENERADAS con REGEXP_REPLACE, que es
específico de MySQL. Probarlas contra SQLite daría una falsa sensación de
seguridad, así que estas pruebas cargan el mismo `db/schema.sql` que va a
producción en una base de pruebas aparte.

    # Linux / macOS
    export TEST_DB_URL="mysql+pymysql://root:clave@localhost/verificentro_test?charset=utf8mb4"

    # Windows (PowerShell)
    $env:TEST_DB_URL="mysql+pymysql://root:clave@localhost/verificentro_test?charset=utf8mb4"

    pytest

Sin esa variable, estas pruebas se saltan y las de autenticación y calendario
siguen corriendo normalmente.
"""

from __future__ import annotations

import os
import pathlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.database import obtener_sesion
from app.main import aplicacion
from app.modelos.empleado import Empleado, Perfil
from app.seguridad import hashear_contrasena

RUTA_ESQUEMA = pathlib.Path(__file__).resolve().parents[2] / "db" / "schema.sql"
CONTRASENA = "verificentro2026"
# bcrypt es lento a propósito. Se hashea una sola vez para toda la corrida.
_HASH = hashear_contrasena(CONTRASENA)

# El orden importa por las llaves foráneas; se vacían con los checks apagados.
TABLAS = [
    "recordatorio_eventos", "recordatorios", "chatbot_pendientes",
    "verificaciones", "citas", "vehiculo_placas", "vehiculos",
    "clientes", "empleados",
]
# horarios_atencion, config_citas y chatbot_respuestas NO se vacían:
# traen los datos iniciales que el sistema necesita para funcionar.


def _sin_comentarios(linea: str) -> str:
    """Quita el comentario `--` de fin de línea sin tocar lo que va en comillas."""
    en_comillas = False
    salida: list[str] = []
    i = 0
    while i < len(linea):
        c = linea[i]
        if c == "'":
            en_comillas = not en_comillas
        if not en_comillas and linea[i : i + 2] == "--":
            break
        salida.append(c)
        i += 1
    return "".join(salida)


def _sentencias(sql: str) -> list[str]:
    """Parte el archivo en sentencias, quitando comentarios y el CREATE DATABASE.

    Hay que quitar los comentarios ANTES de partir por punto y coma: algunos
    comentarios contienen uno (`-- 1 o 2; lo calcula la app`) y partirían la
    sentencia a la mitad. El cliente de MySQL no tiene ese problema porque
    entiende SQL de verdad; este parser es solo para las pruebas.
    """
    texto = "\n".join(_sin_comentarios(linea) for linea in sql.splitlines())
    texto = re.sub(
        r"^\s*(CREATE DATABASE|USE|SET NAMES)[^;]*;",
        "",
        texto,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return [s.strip() for s in texto.split(";") if s.strip()]


@pytest.fixture(autouse=True)
def _canales_de_prueba(monkeypatch):
    """Las pruebas ejercitan los dos canales.

    En producción `CANALES_ACTIVOS` viene solo con correo, mientras no esté el
    trámite con Meta. Se fija aquí explícitamente para que las pruebas no
    cambien de significado cuando cambie ese valor por omisión.
    """
    from app.config import obtener_config

    monkeypatch.setenv("CANALES_ACTIVOS", '["correo","whatsapp"]')
    obtener_config.cache_clear()
    yield
    obtener_config.cache_clear()


@pytest.fixture(scope="session")
def motor():
    url_texto = os.getenv("TEST_DB_URL")
    if not url_texto:
        pytest.skip("Define TEST_DB_URL para correr las pruebas contra MySQL.")
    if not RUTA_ESQUEMA.exists():
        pytest.skip(f"No se encontró {RUTA_ESQUEMA}")

    url = make_url(url_texto)
    nombre_bd = url.database

    # OJO: url.set(database=None) NO quita la base, porque URL.set() ignora
    # los argumentos en None. Hay que pasar cadena vacía.
    servidor = create_engine(url.set(database=""))
    with servidor.connect() as con:
        con.execute(text(f"DROP DATABASE IF EXISTS `{nombre_bd}`"))
        con.execute(
            text(
                f"CREATE DATABASE `{nombre_bd}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
        con.commit()
    servidor.dispose()

    motor_pruebas = create_engine(url, pool_pre_ping=True)
    with motor_pruebas.begin() as con:
        for sentencia in _sentencias(RUTA_ESQUEMA.read_text(encoding="utf-8")):
            con.execute(text(sentencia))

    yield motor_pruebas

    motor_pruebas.dispose()


@pytest.fixture
def sesion_bd(motor):
    """Vacía las tablas y entrega una fábrica de sesiones limpia."""
    Sesion = sessionmaker(bind=motor, expire_on_commit=False)
    with motor.begin() as con:
        con.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for tabla in TABLAS:
            con.execute(text(f"TRUNCATE TABLE `{tabla}`"))
        con.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    return Sesion


@pytest.fixture
def api(sesion_bd):
    """Cliente HTTP con la base de pruebas y los tres perfiles ya creados."""
    with sesion_bd() as s:
        s.add_all([
            Empleado(nombre="Darly Juárez", correo="admin@v.mx",
                     hash_contrasena=_HASH,
                     perfil=Perfil.ADMINISTRADOR),
            Empleado(nombre="José Herrera", correo="tecnico@v.mx",
                     hash_contrasena=_HASH,
                     perfil=Perfil.TECNICO),
            Empleado(nombre="Cristina Vera", correo="atencion@v.mx",
                     hash_contrasena=_HASH,
                     perfil=Perfil.ATENCION),
        ])
        s.commit()

    # OJO: la sobreescritura tiene que ser un GENERADOR, igual que
    # `obtener_sesion`. Si devuelve la sesión directamente, FastAPI nunca la
    # cierra, la transacción queda abierta y el TRUNCATE del siguiente test
    # se queda esperando el candado para siempre.
    def _sesion():
        s = sesion_bd()
        try:
            yield s
        finally:
            s.close()

    aplicacion.dependency_overrides[obtener_sesion] = _sesion
    with TestClient(aplicacion) as c:
        yield c
    aplicacion.dependency_overrides.clear()


@pytest.fixture
def como_tecnico(api):
    return _cabecera(api, "tecnico@v.mx")


@pytest.fixture
def como_admin(api):
    return _cabecera(api, "admin@v.mx")


@pytest.fixture
def como_atencion(api):
    return _cabecera(api, "atencion@v.mx")


def _cabecera(api, correo: str) -> dict:
    r = api.post("/api/v1/auth/login",
                 json={"correo": correo, "contrasena": CONTRASENA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
