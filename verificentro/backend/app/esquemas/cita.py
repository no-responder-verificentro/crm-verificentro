"""Esquemas de citas."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.dominio.calendario import PlacaSinDigito, ultimo_digito
from app.dominio.placas import TelefonoInvalido, normalizar_telefono
from app.modelos.cita import EstadoCita, OrigenCita


class HorarioLibre(BaseModel):
    hora: time
    lugares: int


class DisponibilidadDia(BaseModel):
    fecha: date
    atiende: bool
    motivo: str | None = None
    horarios: list[HorarioLibre] = []


class CitaNueva(BaseModel):
    placa: str = Field(min_length=4, max_length=15, examples=["YUN-047-A"])
    nombre: str = Field(min_length=3, max_length=160)
    telefono: str | None = None
    fecha: date
    hora: time
    origen: OrigenCita = OrigenCita.MOSTRADOR
    notas: str | None = Field(default=None, max_length=255)

    @field_validator("placa")
    @classmethod
    def _placa_con_numero(cls, v: str) -> str:
        try:
            ultimo_digito(v)
        except PlacaSinDigito:
            raise ValueError("La placa no contiene ningún número.") from None
        return v.strip().upper()

    @field_validator("telefono")
    @classmethod
    def _telefono(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        try:
            return normalizar_telefono(v)
        except TelefonoInvalido as exc:
            raise ValueError(str(exc)) from None


class CancelarCita(BaseModel):
    motivo: str | None = Field(default=None, max_length=160)


class CitaPublica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    placa_capturada: str
    nombre_contacto: str
    telefono_contacto: str | None
    fecha: date
    hora_inicio: time
    estado: EstadoCita
    origen: OrigenCita
    vehiculo_id: int | None
    cliente_id: int | None
    verificacion_id: int | None
    notas: str | None
