"""Un error del servidor tiene que verse como un error del servidor.

Esto existe por el error más engañoso de todo el despliegue.

Cuando el backend truena con una excepción no capturada, la respuesta 500 la
arma Starlette en una capa que está POR ENCIMA de CORS. Sale sin la cabecera
`Access-Control-Allow-Origin`, y el navegador —que solo ve que falta la
cabecera— lo reporta como un problema de CORS:

    Access to fetch ... has been blocked by CORS policy:
    No 'Access-Control-Allow-Origin' header is present

Uno entonces se pasa la tarde revisando ORIGENES_PERMITIDOS, que está bien,
mientras la causa real —la base de datos caída, por ejemplo— ni se menciona.

El middleware de app/main.py atrapa la excepción por dentro de CORS para que
la respuesta sí pase por él.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as principal
from app.main import aplicacion

ORIGEN = "http://localhost:5173"


@aplicacion.get("/_prueba_de_error", include_in_schema=False)
def _truena():
    raise RuntimeError("la base de datos no responde")


@pytest.fixture
def cliente():
    with TestClient(aplicacion, raise_server_exceptions=False) as c:
        yield c


def test_el_500_trae_la_cabecera_de_cors(cliente):
    """Lo que impide que un error del servidor se disfrace de error de CORS."""
    r = cliente.get("/_prueba_de_error", headers={"Origin": ORIGEN})

    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == ORIGEN


def test_el_500_trae_un_mensaje_legible(cliente):
    r = cliente.get("/_prueba_de_error", headers={"Origin": ORIGEN})

    assert r.json()["detail"]


def test_en_produccion_no_se_filtra_el_rastro(cliente, monkeypatch):
    """El detalle técnico va a la bitácora del servidor, no al navegador.

    Se parcha `app.main.config` y no `obtener_config()`: conftest limpia la
    caché de la configuración, así que lo que devuelve esa función ya no es
    el mismo objeto que `main` tomó al importarse.
    """
    monkeypatch.setattr(principal.config, "entorno", "produccion")

    detalle = cliente.get("/_prueba_de_error",
                          headers={"Origin": ORIGEN}).json()["detail"]

    assert "RuntimeError" not in detalle
    assert "no responde" not in detalle


def test_un_origen_no_autorizado_sigue_sin_cabecera(cliente):
    """El arreglo no abre CORS para cualquiera: solo deja que la respuesta
    pase por el middleware, que sigue decidiendo igual que siempre."""
    r = cliente.get("/_prueba_de_error",
                    headers={"Origin": "https://sitio-ajeno.example"})

    assert r.headers.get("access-control-allow-origin") is None


def test_salud_sigue_respondiendo(cliente):
    """No toca la base: sirve para saber si el servidor está vivo cuando todo
    lo demás da 500."""
    r = cliente.get("/salud")

    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


class TestResumenDelError:
    """El mensaje que llega al navegador tiene que decir algo.

    SQLAlchemy cierra todos sus errores con la misma línea:

        (Background on this error at: https://sqlalche.me/e/21/e3q8)

    Tomando la última línea del traceback, eso era literalmente lo único que
    se veía en pantalla: un enlace a la documentación de SQLAlchemy, igual
    para una columna que falta que para una base caída. La línea que sirve es
    la primera.
    """

    def test_descarta_el_pie_de_sqlalchemy(self):
        from sqlalchemy.exc import OperationalError

        error = OperationalError(
            "SELECT config_citas.bloques_por_cita FROM config_citas",
            {},
            Exception('(1054, "Unknown column \'config_citas.bloques_por_cita\'")'),
        )

        resumen = principal.resumen_del_error(error)

        assert "Unknown column" in resumen
        assert "Background on this error" not in resumen

    def test_nombra_el_tipo_de_error(self):
        resumen = principal.resumen_del_error(ValueError("algo salió mal"))

        assert resumen.startswith("ValueError:")
        assert "algo salió mal" in resumen

    def test_una_excepcion_sin_mensaje_no_truena(self):
        assert principal.resumen_del_error(RuntimeError())

    def test_no_se_desborda(self):
        resumen = principal.resumen_del_error(ValueError("x" * 5000))

        assert len(resumen) <= 300
