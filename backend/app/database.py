"""Motor y sesión de SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import obtener_config

config = obtener_config()

motor = create_engine(
    config.db_url,
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
