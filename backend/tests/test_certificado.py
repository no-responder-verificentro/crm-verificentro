"""El certificado de Aiven: que su ausencia se note al arrancar.

Esto nació de un 500 en el inicio de sesión que el navegador reportaba como
error de CORS. El traceback real terminaba así, sesenta líneas adentro de
pymysql:

    ssl.create_default_context(cafile=ca, capath=capath)
    FileNotFoundError: [Errno 2] No such file or directory

Sin nombre de archivo, sin pista. La causa era que `DB_URL` pide
`ssl_ca=ca.pem` —una ruta relativa— y ese archivo no estaba en el servidor,
casi siempre porque el `.gitignore` trae `*.pem` y lo excluyó sin avisar.

Dos cosas tienen que ser ciertas para que no se repita: que la ruta relativa
se resuelva contra la carpeta del proyecto y no contra el directorio desde el
que se arrancó, y que si falta el archivo se falle al arrancar con un mensaje
que diga qué hacer.
"""

from __future__ import annotations

import pytest

from sqlalchemy.engine import make_url

from app import database

CON_SSL = "mysql+pymysql://u:c@host:3306/bd?charset=utf8mb4&ssl_ca=ca.pem"
SIN_SSL = "mysql+pymysql://u:c@host:3306/bd?charset=utf8mb4"


def test_una_url_sin_ssl_no_se_toca():
    assert database._preparar_certificado(SIN_SSL) == SIN_SSL


def test_si_falta_el_certificado_se_falla_con_instrucciones():
    with pytest.raises(database.CertificadoNoEncontrado) as excepcion:
        database._preparar_certificado(CON_SSL)

    mensaje = str(excepcion.value)
    assert "ca.pem" in mensaje
    assert "git add -f" in mensaje      # qué hacer, no solo qué falló
    assert "DB_CA_PEM" in mensaje       # y la otra salida


def test_la_ruta_relativa_se_resuelve_contra_el_proyecto(tmp_path, monkeypatch):
    """No contra el directorio desde el que se arrancó el proceso.

    En la laptop uno arranca parado en `backend` y coincide; en el servidor
    no tiene por qué.
    """
    certificado = database.RAIZ / "ca.pem"
    certificado.write_text("-----BEGIN CERTIFICATE-----\nfalso\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)   # otro directorio de trabajo a propósito

    try:
        resultado = database._preparar_certificado(CON_SSL)

        # Se comprueba sobre la URL ya interpretada, no sobre el texto: la
        # ruta viaja codificada (%2F) y SQLAlchemy la descodifica al leerla,
        # que es lo que acaba recibiendo pymysql.
        assert make_url(resultado).query["ssl_ca"] == str(certificado)
    finally:
        certificado.unlink()


def test_el_contenido_en_la_variable_tambien_sirve(monkeypatch):
    """La salida para Render: pegar el certificado en DB_CA_PEM.

    Evita por completo el enredo del .gitignore.
    """
    monkeypatch.setattr(
        database.config, "db_ca_pem",
        "-----BEGIN CERTIFICATE-----\nfalso\n-----END CERTIFICATE-----",
    )

    resultado = database._preparar_certificado(CON_SSL)

    escrito = database.RAIZ / "ca-de-la-variable.pem"
    try:
        assert escrito.exists()
        assert "BEGIN CERTIFICATE" in escrito.read_text()
        assert make_url(resultado).query["ssl_ca"] == str(escrito)
    finally:
        escrito.unlink()


def test_no_se_pierde_el_resto_de_la_url(monkeypatch):
    """El charset tiene que sobrevivir: sin utf8mb4 los acentos se rompen."""
    monkeypatch.setattr(database.config, "db_ca_pem", "-----BEGIN-----\nx\n")

    resultado = database._preparar_certificado(CON_SSL)

    try:
        url = make_url(resultado)
        assert url.query["charset"] == "utf8mb4"
        assert url.database == "bd"
        assert url.host == "host"
    finally:
        (database.RAIZ / "ca-de-la-variable.pem").unlink(missing_ok=True)


def test_la_contrasena_no_se_pierde_al_rearmar_la_url(monkeypatch):
    """SQLAlchemy oculta la contraseña al imprimir una URL. Si se rearmara
    así, la conexión saldría con '***' y fallaría la autenticación."""
    monkeypatch.setattr(database.config, "db_ca_pem", "-----BEGIN-----\nx\n")

    resultado = database._preparar_certificado(
        "mysql+pymysql://avnadmin:contrasena-real@host:12345/bd?ssl_ca=ca.pem"
    )

    try:
        assert make_url(resultado).password == "contrasena-real"
        assert "***" not in resultado
    finally:
        (database.RAIZ / "ca-de-la-variable.pem").unlink(missing_ok=True)
