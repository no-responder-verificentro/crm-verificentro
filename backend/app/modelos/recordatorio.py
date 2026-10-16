"""Recordatorios, su bitácora de eventos y las plantillas de mensaje."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TipoRecordatorio(str, enum.Enum):
    VENTANA = "ventana"   # le toca verificar
    CITA = "cita"         # tiene cita agendada


class Canal(str, enum.Enum):
    WHATSAPP = "whatsapp"
    CORREO = "correo"


class EstadoRecordatorio(str, enum.Enum):
    """Lo controla nuestro sistema."""

    PROGRAMADO = "programado"   # calculado, aún no sale
    PAUSADO = "pausado"         # alguien lo detuvo a mano
    CANCELADO = "cancelado"     # el cliente verificó antes
    EN_PROCESO = "en_proceso"   # entregado al proveedor, esperando respuesta
    ENVIADO = "enviado"         # el proveedor lo aceptó
    ERROR = "error"             # falló antes de salir


class EstadoEntrega(str, enum.Enum):
    """Lo reporta el proveedor. Solo avanza, nunca retrocede."""

    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    ENTREGADO = "entregado"
    LEIDO = "leido"             # WhatsApp, y solo con palomitas azules activas
    CLIC = "clic"               # correo: el dato confiable, no la apertura
    REBOTE_DURO = "rebote_duro"
    REBOTE_SUAVE = "rebote_suave"
    FALLIDO = "fallido"
    SPAM = "spam"
    BAJA = "baja"


#: Orden de avance. Un webhook que llega tarde no puede retroceder el estado.
ORDEN_ENTREGA = {
    EstadoEntrega.PENDIENTE: 0,
    EstadoEntrega.ENVIADO: 1,
    EstadoEntrega.ENTREGADO: 2,
    EstadoEntrega.LEIDO: 3,
    EstadoEntrega.CLIC: 4,
    # Los finales de fallo no compiten con los de éxito.
    EstadoEntrega.REBOTE_SUAVE: 1,
    EstadoEntrega.REBOTE_DURO: 5,
    EstadoEntrega.FALLIDO: 5,
    EstadoEntrega.SPAM: 5,
    EstadoEntrega.BAJA: 5,
}

#: Estados que cuentan como fallo de contacto.
ENTREGA_FALLIDA = (
    EstadoEntrega.REBOTE_DURO,
    EstadoEntrega.FALLIDO,
    EstadoEntrega.SPAM,
    EstadoEntrega.BAJA,
)


class EstadoAprobacion(str, enum.Enum):
    BORRADOR = "borrador"
    EN_REVISION = "en_revision"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


def _enum(tipo):
    return Enum(tipo, values_callable=lambda e: [m.value for m in e])


class PlantillaMensaje(Base):
    """Texto de cada aviso.

    Se versiona en lugar de sobrescribirse porque cambiar el texto de una
    plantilla de WhatsApp obliga a una nueva aprobación de Meta.
    """

    __tablename__ = "plantillas_mensaje"

    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(String(60))
    canal: Mapped[Canal] = mapped_column(_enum(Canal))
    version: Mapped[int] = mapped_column(SmallInteger, default=1)
    nombre_meta: Mapped[str | None] = mapped_column(String(100), default=None)
    idioma: Mapped[str] = mapped_column(String(10), default="es_MX")
    asunto: Mapped[str | None] = mapped_column(String(200), default=None)
    cuerpo: Mapped[str] = mapped_column(Text)
    estado_aprobacion: Mapped[EstadoAprobacion] = mapped_column(
        _enum(EstadoAprobacion), default=EstadoAprobacion.BORRADOR
    )
    activa: Mapped[bool] = mapped_column(Boolean, default=False)
    actualizado_por: Mapped[int | None] = mapped_column(
        ForeignKey("empleados.id"), default=None
    )


class Recordatorio(Base):
    __tablename__ = "recordatorios"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehiculo_id: Mapped[int] = mapped_column(ForeignKey("vehiculos.id"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))

    tipo: Mapped[TipoRecordatorio] = mapped_column(
        _enum(TipoRecordatorio), default=TipoRecordatorio.VENTANA
    )
    aviso_clave: Mapped[str] = mapped_column(String(30))
    ventana_anio: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    ventana_periodo: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    cita_id: Mapped[int | None] = mapped_column(ForeignKey("citas.id"), default=None)

    canal: Mapped[Canal] = mapped_column(_enum(Canal))
    plantilla_id: Mapped[int | None] = mapped_column(
        ForeignKey("plantillas_mensaje.id"), default=None
    )
    # Se congela al generarse: si mañana cambian el teléfono, la bitácora
    # tiene que seguir diciendo a dónde se mandó.
    destino: Mapped[str] = mapped_column(String(160))
    programado_para: Mapped[datetime] = mapped_column(DateTime)

    estado: Mapped[EstadoRecordatorio] = mapped_column(
        _enum(EstadoRecordatorio), default=EstadoRecordatorio.PROGRAMADO
    )
    estado_entrega: Mapped[EstadoEntrega] = mapped_column(
        _enum(EstadoEntrega), default=EstadoEntrega.PENDIENTE
    )
    motivo_error: Mapped[str | None] = mapped_column(String(255), default=None)
    id_externo: Mapped[str | None] = mapped_column(String(120), default=None)
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    # Columna generada por MySQL. Con su índice único es lo que impide que el
    # cliente reciba el mismo aviso dos veces si el job corre de más.
    clave_idempotencia: Mapped[str] = mapped_column(
        String(160),
        Computed(
            "CONCAT_WS('|', vehiculo_id, tipo, aviso_clave, "
            "COALESCE(ventana_anio, 0), COALESCE(ventana_periodo, 0), "
            "COALESCE(cita_id, 0), canal)",
            persisted=True,
        ),
    )

    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    eventos: Mapped[list["RecordatorioEvento"]] = relationship(
        back_populates="recordatorio", cascade="all, delete-orphan"
    )

    @property
    def puede_cancelarse(self) -> bool:
        return self.estado in (
            EstadoRecordatorio.PROGRAMADO,
            EstadoRecordatorio.PAUSADO,
        )


class RecordatorioEvento(Base):
    """Cada acuse que reporta el proveedor.

    Se guardan todos, no solo el último estado: los webhooks llegan
    desordenados con más frecuencia de la que uno espera, y cuando un cliente
    reclame que nunca le avisaron hay que poder mostrar la secuencia con horas.
    """

    __tablename__ = "recordatorio_eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    recordatorio_id: Mapped[int] = mapped_column(ForeignKey("recordatorios.id"))
    evento: Mapped[str] = mapped_column(String(30))
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime)
    recibido_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    codigo_error: Mapped[str | None] = mapped_column(String(40), default=None)
    payload: Mapped[dict | None] = mapped_column(JSON, default=None)

    recordatorio: Mapped["Recordatorio"] = relationship(back_populates="eventos")
