"""Citas y la configuración de la agenda."""

from __future__ import annotations

import enum
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EstadoCita(str, enum.Enum):
    AGENDADA = "agendada"
    CONFIRMADA = "confirmada"
    ATENDIDA = "atendida"
    NO_ASISTIO = "no_asistio"
    CANCELADA = "cancelada"


class OrigenCita(str, enum.Enum):
    MOSTRADOR = "mostrador"
    CHATBOT_WHATSAPP = "chatbot_whatsapp"
    CHATBOT_FACEBOOK = "chatbot_facebook"
    WEB = "web"
    TELEFONO = "telefono"


#: Estados en los que la cita todavía ocupa un lugar en la agenda.
ESTADOS_ACTIVOS = (EstadoCita.AGENDADA, EstadoCita.CONFIRMADA)


def _enum(tipo):
    return Enum(tipo, values_callable=lambda e: [m.value for m in e])


class HorarioAtencion(Base):
    __tablename__ = "horarios_atencion"

    dia_semana: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    hora_apertura: Mapped[time] = mapped_column(Time)
    hora_cierre: Mapped[time] = mapped_column(Time)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class DiaNoLaborable(Base):
    __tablename__ = "dias_no_laborables"

    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    motivo: Mapped[str | None] = mapped_column(String(120), default=None)


class ConfigCitas(Base):
    __tablename__ = "config_citas"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    duracion_bloque_min: Mapped[int] = mapped_column(SmallInteger, default=20)
    cupos_por_bloque: Mapped[int] = mapped_column(SmallInteger, default=1)
    bloques_por_cita: Mapped[int] = mapped_column(SmallInteger, default=3)
    anticipacion_max_dias: Mapped[int] = mapped_column(SmallInteger, default=30)
    anticipacion_min_horas: Mapped[int] = mapped_column(SmallInteger, default=2)
    tolerancia_retardo_min: Mapped[int] = mapped_column(SmallInteger, default=15)


class Cita(Base):
    """Una cita apartada.

    `cupo` numera el lugar dentro del bloque (1..cupos_por_bloque) y tiene
    índice único junto con fecha y hora. Eso impide la sobreventa sin candados
    ni transacciones complicadas: si dos personas intentan el último lugar al
    mismo tiempo, la base rechaza a una y la aplicación reintenta con el
    siguiente cupo libre.

    Al cancelar se pone `cupo = NULL`. Como MySQL permite varios NULL en un
    índice único, el lugar queda liberado automáticamente.
    """

    __tablename__ = "citas"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Van en NULL si agendó por chatbot sin estar registrado. Se vinculan
    # cuando llega al mostrador.
    vehiculo_id: Mapped[int | None] = mapped_column(
        ForeignKey("vehiculos.id"), default=None
    )
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id"), default=None
    )

    placa_capturada: Mapped[str] = mapped_column(String(15))
    nombre_contacto: Mapped[str] = mapped_column(String(160))
    telefono_contacto: Mapped[str | None] = mapped_column(String(20), default=None)

    fecha: Mapped[date] = mapped_column(Date)
    hora_inicio: Mapped[time] = mapped_column(Time)
    cupo: Mapped[int | None] = mapped_column(SmallInteger, default=None)

    estado: Mapped[EstadoCita] = mapped_column(
        _enum(EstadoCita), default=EstadoCita.AGENDADA
    )
    origen: Mapped[OrigenCita] = mapped_column(
        _enum(OrigenCita), default=OrigenCita.MOSTRADOR
    )

    creada_por: Mapped[int | None] = mapped_column(
        ForeignKey("empleados.id"), default=None
    )
    verificacion_id: Mapped[int | None] = mapped_column(
        ForeignKey("verificaciones.id"), default=None
    )
    cancelada_en: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(160), default=None)
    notas: Mapped[str | None] = mapped_column(String(255), default=None)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @property
    def sigue_activa(self) -> bool:
        return self.estado in ESTADOS_ACTIVOS
