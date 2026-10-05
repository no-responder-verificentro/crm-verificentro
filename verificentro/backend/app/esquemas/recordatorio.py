"""Esquemas de recordatorios y del panel."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modelos.recordatorio import (
    Canal,
    EstadoEntrega,
    EstadoRecordatorio,
    TipoRecordatorio,
)


class RecordatorioPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehiculo_id: int
    cliente_id: int
    tipo: TipoRecordatorio
    aviso_clave: str
    ventana_anio: int | None
    ventana_periodo: int | None
    canal: Canal
    destino: str
    programado_para: datetime
    estado: EstadoRecordatorio
    estado_entrega: EstadoEntrega
    motivo_error: str | None
    enviado_en: datetime | None


class RecordatorioEnLista(RecordatorioPublico):
    """Fila de la pantalla, con lo que hace falta para leerla sin abrir nada."""

    cliente_nombre: str
    placa: str
    ventana: str | None = None


class ResumenRecordatorios(BaseModel):
    canales_activos: list[str] = []
    programados_hoy: int
    enviados_7_dias: int
    tasa_entrega: float
    no_entregados: int
    contactos_no_localizables: int


class MotivoPausa(BaseModel):
    motivo: str | None = Field(default=None, max_length=160)


# ------------------------------------------------------------------ panel --

class IndicadoresPanel(BaseModel):
    verificados_del_mes: int
    periodo_abierto: int
    por_vencer: int
    vencidos: int
    al_corriente: int
    sin_forma_de_contacto: int


class FilaSeguimiento(BaseModel):
    vehiculo_id: int
    cliente_id: int
    cliente: str
    placa: str
    ultimo_digito: int | None
    ventana: str | None
    dias_restantes: int | None
    estado: str
    se_le_puede_escribir: bool
    ultimo_aviso: str | None


class PuntoGrafica(BaseModel):
    mes: str
    verificaciones: int
