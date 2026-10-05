"""Esquemas del chatbot."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modelos.chatbot import CanalChat, TipoRespuesta


class MensajeEntrante(BaseModel):
    texto: str = Field(min_length=1, max_length=500)
    canal: CanalChat = CanalChat.WEB


class MensajeSaliente(BaseModel):
    texto: str
    tipo: str
    entendida: bool
    sugerencias: list[str] = []


class RespuestaNueva(BaseModel):
    pregunta: str = Field(min_length=5, max_length=255)
    respuesta: str = Field(min_length=2, max_length=2000)
    tipo: TipoRespuesta = TipoRespuesta.TEXTO_FIJO
    palabras_clave: str | None = Field(default=None, max_length=255)
    orden: int = Field(default=100, ge=1, le=999)


class RespuestaEditada(BaseModel):
    pregunta: str | None = Field(default=None, min_length=5, max_length=255)
    respuesta: str | None = Field(default=None, min_length=2, max_length=2000)
    tipo: TipoRespuesta | None = None
    palabras_clave: str | None = Field(default=None, max_length=255)
    orden: int | None = Field(default=None, ge=1, le=999)
    activa: bool | None = None


class RespuestaPublica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pregunta: str
    respuesta: str
    tipo: TipoRespuesta
    palabras_clave: str | None
    orden: int
    activa: bool
    actualizado_en: datetime


class PendientePublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    canal: CanalChat
    pregunta: str
    veces: int
    ultima_vez: datetime
    ventana_expira_en: datetime | None
    resuelta: bool
