"""Vehículos, su historial de placas y sus verificaciones.

Detalle importante: `placa_normalizada` y `ultimo_digito` son columnas
GENERADAS por MySQL. Se declaran con `Computed(...)` para que SQLAlchemy
sepa que son de solo lectura y nunca las incluya en un INSERT. Después de
guardar hay que hacer `refresh()` para leer el valor que calculó la base.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.modelos.cliente import Cliente

_EXPR_NORMALIZADA = "REGEXP_REPLACE(UPPER(placa), '[^A-Z0-9]', '')"
_EXPR_DIGITO = "NULLIF(RIGHT(REGEXP_REPLACE(placa, '[^0-9]', ''), 1), '') + 0"


class Combustible(str, enum.Enum):
    GASOLINA = "gasolina"
    DIESEL = "diesel"
    GAS_LP = "gas_lp"
    GAS_NATURAL = "gas_natural"
    HIBRIDO = "hibrido"
    ELECTRICO = "electrico"


class MotivoPlaca(str, enum.Enum):
    ALTA = "alta"
    REEMPLAZO = "reemplazo"
    CAMBIO_ENTIDAD = "cambio_entidad"
    CORRECCION = "correccion"


class Resultado(str, enum.Enum):
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"


def _enum(tipo):
    return Enum(tipo, values_callable=lambda e: [m.value for m in e])


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))

    # El identificador estable. La placa cambia; el NIV no.
    niv: Mapped[str] = mapped_column(String(17), unique=True)
    placa: Mapped[str] = mapped_column(String(15))

    placa_normalizada: Mapped[str] = mapped_column(
        String(15), Computed(_EXPR_NORMALIZADA, persisted=True)
    )
    ultimo_digito: Mapped[int | None] = mapped_column(
        SmallInteger, Computed(_EXPR_DIGITO, persisted=True)
    )

    folio_tarjeta: Mapped[str | None] = mapped_column(String(20), default=None)
    marca: Mapped[str | None] = mapped_column(String(60), default=None)
    linea: Mapped[str | None] = mapped_column(String(80), default=None)
    modelo_anio: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    color: Mapped[str | None] = mapped_column(String(40), default=None)
    combustible: Mapped[Combustible | None] = mapped_column(
        _enum(Combustible), default=None
    )
    clase: Mapped[str | None] = mapped_column(String(10), default=None)
    tipo: Mapped[str | None] = mapped_column(String(10), default=None)
    uso: Mapped[str | None] = mapped_column(String(10), default=None)
    numero_motor: Mapped[str | None] = mapped_column(String(40), default=None)
    capacidad_pasajeros: Mapped[int | None] = mapped_column(
        SmallInteger, default=None
    )

    entidad_placa: Mapped[str] = mapped_column(String(3), default="VER")
    # Si la placa es de otro estado, el calendario de Veracruz no aplica y no
    # se le generan recordatorios automáticos.
    en_programa_estatal: Mapped[bool] = mapped_column(Boolean, default=True)

    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    registrado_por: Mapped[int | None] = mapped_column(
        ForeignKey("empleados.id"), default=None
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cliente: Mapped["Cliente"] = relationship(back_populates="vehiculos")
    placas: Mapped[list["VehiculoPlaca"]] = relationship(
        back_populates="vehiculo", cascade="all, delete-orphan", lazy="selectin"
    )
    verificaciones: Mapped[list["Verificacion"]] = relationship(
        back_populates="vehiculo", lazy="selectin",
    )

    @property
    def genera_recordatorios(self) -> bool:
        """Un vehículo entra al calendario solo si cumple las tres cosas."""
        return (
            self.activo
            and self.en_programa_estatal
            and self.ultimo_digito is not None
        )

    @property
    def fechas_aprobadas(self) -> list[date]:
        """Solo las verificaciones aprobadas cuentan como cumplimiento.

        Un rechazo obliga a volver dentro de la misma ventana, así que no
        cancela los recordatorios.
        """
        return [
            v.fecha for v in self.verificaciones if v.resultado is Resultado.APROBADO
        ]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vehiculo {self.id} {self.placa}>"


class VehiculoPlaca(Base):
    """Historial de placas del mismo vehículo.

    Cuando un auto cambia de placa puede cambiar el periodo que le toca:
    en la tarjeta de ejemplo, la placa anterior terminaba en 5 y la nueva
    en 7. Sin este historial el sistema no podría explicar por qué le
    cambiaron las fechas.
    """

    __tablename__ = "vehiculo_placas"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehiculo_id: Mapped[int] = mapped_column(ForeignKey("vehiculos.id"))
    placa: Mapped[str] = mapped_column(String(15))
    placa_normalizada: Mapped[str] = mapped_column(
        String(15), Computed(_EXPR_NORMALIZADA, persisted=True)
    )
    ultimo_digito: Mapped[int | None] = mapped_column(
        SmallInteger, Computed(_EXPR_DIGITO, persisted=True)
    )
    vigente_desde: Mapped[date] = mapped_column(Date)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, default=None)
    motivo: Mapped[MotivoPlaca] = mapped_column(
        _enum(MotivoPlaca), default=MotivoPlaca.ALTA
    )
    registrado_por: Mapped[int | None] = mapped_column(
        ForeignKey("empleados.id"), default=None
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vehiculo: Mapped["Vehiculo"] = relationship(back_populates="placas")


class Verificacion(Base):
    __tablename__ = "verificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehiculo_id: Mapped[int] = mapped_column(ForeignKey("vehiculos.id"))
    fecha: Mapped[date] = mapped_column(Date)
    hora: Mapped[time | None] = mapped_column(Time, default=None)
    periodo: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    resultado: Mapped[Resultado] = mapped_column(_enum(Resultado))
    holograma: Mapped[str | None] = mapped_column(String(10), default=None)
    folio_certificado: Mapped[str | None] = mapped_column(String(30), default=None)
    placa_al_verificar: Mapped[str | None] = mapped_column(String(15), default=None)
    tecnico_id: Mapped[int | None] = mapped_column(
        ForeignKey("empleados.id"), default=None
    )
    observaciones: Mapped[str | None] = mapped_column(String(255), default=None)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vehiculo: Mapped["Vehiculo"] = relationship(back_populates="verificaciones")
