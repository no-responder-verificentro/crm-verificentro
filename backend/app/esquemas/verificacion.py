"""Esquemas de verificaciones."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field

from app.modelos.vehiculo import Resultado


class VerificacionNueva(BaseModel):
    vehiculo_id: int
    fecha: date
    hora: time | None = None
    resultado: Resultado
    holograma: str | None = Field(default=None, max_length=10)
    folio_certificado: str | None = Field(default=None, max_length=30)
    observaciones: str | None = Field(default=None, max_length=255)


class VerificacionPublica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehiculo_id: int
    fecha: date
    hora: time | None
    periodo: int | None
    resultado: Resultado
    holograma: str | None
    folio_certificado: str | None
    # Se congela la placa del momento: si mañana el auto cambia de placa, el
    # certificado tiene que seguir diciendo con cuál se verificó.
    placa_al_verificar: str | None
    observaciones: str | None
    tecnico_id: int | None


class VerificacionEnBitacora(VerificacionPublica):
    """Fila de la pantalla de Verificaciones."""

    placa: str
    cliente_id: int
    cliente_nombre: str
    vehiculo_descripcion: str | None = None
    tecnico_nombre: str | None = None
    dentro_de_su_periodo: bool


class ResumenVerificaciones(BaseModel):
    """Los cuatro indicadores del encabezado de la pantalla."""

    desde: date
    hasta: date
    total: int
    aprobadas: int
    rechazadas: int
    indice_rechazo: float
    fuera_de_periodo: int
