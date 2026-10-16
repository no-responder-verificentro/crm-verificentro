"""Modelo de empleados. Refleja la tabla `empleados` de schema.sql."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Perfil(str, enum.Enum):
    """Los tres perfiles acordados con el cliente.

    Los permisos van por perfil, no por persona: si mañana alguien cambia de
    puesto, se le cambia el perfil y listo.
    """

    ADMINISTRADOR = "administrador"
    TECNICO = "tecnico"
    ATENCION = "atencion"


class Empleado(Base):
    __tablename__ = "empleados"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    correo: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[Perfil] = mapped_column(
        Enum(Perfil, values_callable=lambda e: [m.value for m in e])
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Empleado {self.correo} ({self.perfil.value})>"
