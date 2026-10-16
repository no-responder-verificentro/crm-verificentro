"""Modelo de clientes. Refleja la tabla `clientes` de schema.sql."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.modelos.vehiculo import Vehiculo


class OrigenConsentimiento(str, enum.Enum):
    MOSTRADOR = "mostrador"
    CHATBOT = "chatbot"
    WEB = "web"
    TELEFONO = "telefono"


class EstadoContacto(str, enum.Enum):
    CONTACTABLE = "contactable"
    NO_LOCALIZABLE = "no_localizable"   # lo pone el sistema tras varios fallos
    BAJA = "baja"                       # lo pidió el cliente


def _enum(tipo):
    return Enum(tipo, values_callable=lambda e: [m.value for m in e])


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    telefono_e164: Mapped[str | None] = mapped_column(String(20), default=None)
    correo: Mapped[str | None] = mapped_column(String(160), default=None)

    consent_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_correo: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_fecha: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    consent_origen: Mapped[OrigenConsentimiento | None] = mapped_column(
        _enum(OrigenConsentimiento), default=None
    )
    aviso_privacidad_ver: Mapped[str | None] = mapped_column(String(20), default=None)

    estado_contacto: Mapped[EstadoContacto] = mapped_column(
        _enum(EstadoContacto), default=EstadoContacto.CONTACTABLE
    )

    registrado_por: Mapped[int | None] = mapped_column(
        ForeignKey("empleados.id"), default=None
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vehiculos: Mapped[list["Vehiculo"]] = relationship(
        back_populates="cliente", lazy="selectin"
    )

    @property
    def se_le_puede_escribir(self) -> bool:
        """Sin consentimiento y sin contacto vigente, no se genera nada.

        Se consulta antes de encolar cualquier recordatorio.
        """
        if self.estado_contacto is not EstadoContacto.CONTACTABLE:
            return False
        return bool(
            (self.consent_whatsapp and self.telefono_e164)
            or (self.consent_correo and self.correo)
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Cliente {self.id} {self.nombre}>"
