"""Catálogo de respuestas del chatbot y preguntas sin resolver."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, SmallInteger, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TipoRespuesta(str, enum.Enum):
    TEXTO_FIJO = "texto_fijo"
    AUTOMATICA = "automatica"     # la calcula el sistema, como el periodo
    CON_ENLACE = "con_enlace"
    TRANSFIERE = "transfiere"     # pasa con una persona


class CanalChat(str, enum.Enum):
    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"
    WEB = "web"


def _enum(tipo):
    return Enum(tipo, values_callable=lambda e: [m.value for m in e])


class ChatbotRespuesta(Base):
    __tablename__ = "chatbot_respuestas"

    id: Mapped[int] = mapped_column(primary_key=True)
    pregunta: Mapped[str] = mapped_column(String(255))
    respuesta: Mapped[str] = mapped_column(Text)
    tipo: Mapped[TipoRespuesta] = mapped_column(
        _enum(TipoRespuesta), default=TipoRespuesta.TEXTO_FIJO
    )
    palabras_clave: Mapped[str | None] = mapped_column(String(255), default=None)
    orden: Mapped[int] = mapped_column(SmallInteger, default=100)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    actualizado_por: Mapped[int | None] = mapped_column(
        ForeignKey("empleados.id"), default=None
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class ChatbotPendiente(Base):
    """Lo que el bot no supo contestar.

    Convertir estas en respuestas es lo que hace que el bot mejore con el uso.
    """

    __tablename__ = "chatbot_pendientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    canal: Mapped[CanalChat] = mapped_column(_enum(CanalChat))
    contacto_externo: Mapped[str] = mapped_column(String(120))
    pregunta: Mapped[str] = mapped_column(String(500))
    veces: Mapped[int] = mapped_column(SmallInteger, default=1)
    ultima_vez: Mapped[datetime] = mapped_column(DateTime)
    # 24 h después del último mensaje. Pasada esa hora, en WhatsApp ya no se
    # puede contestar libremente y solo queda agregar la pregunta al catálogo.
    ventana_expira_en: Mapped[datetime | None] = mapped_column(
        DateTime, default=None
    )
    resuelta: Mapped[bool] = mapped_column(Boolean, default=False)
    respuesta_id: Mapped[int | None] = mapped_column(
        ForeignKey("chatbot_respuestas.id"), default=None
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
