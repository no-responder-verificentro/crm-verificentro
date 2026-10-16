"""Motor y sesión de SQLAlchemy."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import obtener_config

config = obtener_config()

#: La carpeta `backend`, donde vive `app`. Se usa para resolver rutas
#: relativas sin depender de desde dónde se haya arrancado el proceso.
RAIZ = Path(__file__).resolve().parent.parent


class CertificadoNoEncontrado(RuntimeError):
    pass


def _ruta_del_certificado(nombre: str) -> Path:
    """Dónde buscar el `ca.pem` de Aiven.

    La `DB_URL` lo nombra como `ssl_ca=ca.pem`, una ruta RELATIVA, y
    pymysql la resuelve contra el directorio desde el que se arrancó el
    proceso. Eso funciona en la laptop, donde uno arranca parado en
    `backend`, y falla en el servidor, donde no necesariamente.

    Aquí se resuelve contra la carpeta del proyecto, que no cambia.
    """
    ruta = Path(nombre)
    if ruta.is_absolute():
        return ruta
    return (RAIZ / ruta).resolve()


def _preparar_certificado(url_texto: str) -> str:
    """Deja la DB_URL apuntando a un `ca.pem` que de verdad existe.

    Hay dos formas de dárselo al servidor y las dos se admiten:

    1. **El archivo en el repositorio**, en `backend/ca.pem`. Es un
       certificado público, no un secreto, así que subirlo es correcto. El
       problema es que muchos `.gitignore` traen `*.pem` de serie y lo
       excluyen sin que nadie se entere.
    2. **DB_CA_PEM**, con el contenido del certificado pegado como variable
       de entorno. Es lo más cómodo en Render y evita por completo el
       enredo anterior.

    Si no hay ninguno, se falla AL ARRANCAR y con un mensaje claro. Antes
    esto reventaba en la primera petición que tocara la base, con un
    `FileNotFoundError` sin nombre de archivo enterrado sesenta líneas abajo
    en el traceback de pymysql. El despliegue se veía verde y lo que fallaba
    era entrar al sistema.
    """
    url = make_url(url_texto)
    nombre = url.query.get("ssl_ca")
    if not nombre:
        return url_texto
    if isinstance(nombre, (tuple, list)):
        nombre = nombre[0]

    destino = _ruta_del_certificado(nombre)

    # El contenido en una variable gana: es lo que se configura en el
    # servidor y debe poder corregir lo que falte en el repositorio.
    if config.db_ca_pem.strip():
        destino = RAIZ / "ca-de-la-variable.pem"
        destino.write_text(config.db_ca_pem.strip() + "\n", encoding="utf-8")

    if not destino.exists():
        raise CertificadoNoEncontrado(
            f"La base pide conexión cifrada con el certificado '{nombre}', "
            f"y no está en {destino}.\n\n"
            "Dos formas de resolverlo:\n"
            "  1. Súbelo al repositorio. Es un certificado PÚBLICO de Aiven, "
            "no un secreto:\n"
            "       git add -f backend/ca.pem\n"
            "     El -f es por si el .gitignore excluye *.pem, que es lo más "
            "común.\n"
            "  2. O pega su contenido completo en la variable DB_CA_PEM, "
            "incluidas\n"
            "     las líneas BEGIN y END CERTIFICATE.\n\n"
            "Lo explica DESPLIEGUE.md, paso 2.4."
        )

    query = dict(url.query)
    query["ssl_ca"] = str(destino)
    return url.set(query=query).render_as_string(hide_password=False)


motor = create_engine(
    _preparar_certificado(config.db_url),
    pool_pre_ping=True,   # revive conexiones que MySQL cerró por inactividad
    pool_recycle=280,     # los servicios gratuitos cortan a los 5 min
    pool_size=config.db_pool,
    max_overflow=config.db_pool_extra,
    pool_timeout=30,
    echo=config.db_echo,
)

SesionLocal = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de todos los modelos."""


def obtener_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión y la cierra al terminar."""
    sesion = SesionLocal()
    try:
        yield sesion
    finally:
        sesion.close()
