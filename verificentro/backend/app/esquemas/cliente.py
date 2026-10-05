"""Esquemas de clientes y vehículos.

Los validadores llaman al dominio, así que la misma regla aplica venga el
dato del mostrador, de una edición o del chatbot.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.dominio.calendario import Estado, PlacaSinDigito, ultimo_digito
from app.dominio.placas import (
    NivInvalido,
    TelefonoInvalido,
    normalizar_niv,
    normalizar_telefono,
)
from app.modelos.cliente import EstadoContacto, OrigenConsentimiento
from app.modelos.vehiculo import Combustible, MotivoPlaca, Resultado

Nombre = Annotated[str, Field(min_length=3, max_length=160)]


# --------------------------------------------------------------- vehículos --

class VehiculoBase(BaseModel):
    placa: str = Field(min_length=4, max_length=15, examples=["YUN-047-A"])
    niv: str = Field(examples=["3N1CB51S62K222173"])
    folio_tarjeta: str | None = Field(default=None, max_length=20)
    marca: str | None = Field(default=None, max_length=60)
    linea: str | None = Field(default=None, max_length=80)
    modelo_anio: int | None = Field(default=None, ge=1900, le=2100)
    color: str | None = Field(default=None, max_length=40)
    combustible: Combustible | None = None
    clase: str | None = Field(default=None, max_length=10)
    tipo: str | None = Field(default=None, max_length=10)
    uso: str | None = Field(default=None, max_length=10)
    numero_motor: str | None = Field(default=None, max_length=40)
    capacidad_pasajeros: int | None = Field(default=None, ge=1, le=99)
    entidad_placa: str = Field(default="VER", min_length=2, max_length=3)

    @field_validator("niv")
    @classmethod
    def _validar_niv(cls, v: str) -> str:
        try:
            return normalizar_niv(v)
        except NivInvalido as exc:
            raise ValueError(str(exc)) from None

    @field_validator("placa")
    @classmethod
    def _la_placa_debe_traer_un_numero(cls, v: str) -> str:
        # Las placas de Veracruz terminan en letra, pero el calendario se rige
        # por el último NÚMERO. Sin ningún número no se puede calcular nada.
        try:
            ultimo_digito(v)
        except PlacaSinDigito:
            raise ValueError(
                "La placa no contiene ningún número. Verifica la tarjeta de "
                "circulación: sin un dígito no se puede calcular el periodo."
            ) from None
        return v.strip().upper()

    @field_validator("entidad_placa")
    @classmethod
    def _entidad_mayusculas(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def _fuera_del_programa_si_no_es_veracruz(self) -> Self:
        # No se bloquea: se registra igual, pero sin recordatorios automáticos,
        # porque el calendario del Artículo 9 es del estado de Veracruz.
        return self


class VehiculoNuevo(VehiculoBase):
    pass


class VehiculoEditado(BaseModel):
    """La placa NO se edita aquí: se cambia con el endpoint de cambio de placa,
    que además guarda el historial y recalcula el periodo."""

    marca: str | None = Field(default=None, max_length=60)
    linea: str | None = Field(default=None, max_length=80)
    modelo_anio: int | None = Field(default=None, ge=1900, le=2100)
    color: str | None = Field(default=None, max_length=40)
    combustible: Combustible | None = None
    numero_motor: str | None = Field(default=None, max_length=40)
    capacidad_pasajeros: int | None = Field(default=None, ge=1, le=99)
    activo: bool | None = None


class CambioDePlaca(BaseModel):
    placa_nueva: str = Field(min_length=4, max_length=15)
    vigente_desde: date
    motivo: MotivoPlaca = MotivoPlaca.REEMPLAZO
    entidad_placa: str | None = Field(default=None, min_length=2, max_length=3)

    @field_validator("placa_nueva")
    @classmethod
    def _debe_traer_numero(cls, v: str) -> str:
        try:
            ultimo_digito(v)
        except PlacaSinDigito:
            raise ValueError("La placa nueva no contiene ningún número.") from None
        return v.strip().upper()


class PeriodoResumen(BaseModel):
    etiqueta: str
    inicio: date
    fin: date


class VerificacionPublica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    resultado: Resultado
    holograma: str | None
    folio_certificado: str | None


class VehiculoPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente_id: int
    niv: str
    placa: str
    placa_normalizada: str
    ultimo_digito: int | None
    marca: str | None
    linea: str | None
    modelo_anio: int | None
    color: str | None
    combustible: Combustible | None
    entidad_placa: str
    en_programa_estatal: bool
    activo: bool

    # Se calculan al vuelo con el módulo de dominio
    estado: Estado | None = None
    ventana: PeriodoResumen | None = None
    dias_restantes: int | None = None


class VehiculoDetalle(VehiculoPublico):
    verificaciones: list[VerificacionPublica] = []


# ---------------------------------------------------------------- clientes --

class ConsentimientoEntrada(BaseModel):
    whatsapp: bool = False
    correo: bool = False
    origen: OrigenConsentimiento = OrigenConsentimiento.MOSTRADOR
    aviso_privacidad_ver: str | None = Field(default=None, max_length=20)


class ClienteBase(BaseModel):
    nombre: Nombre
    telefono: str | None = Field(default=None, examples=["228 100 9584"])
    correo: EmailStr | None = None

    @field_validator("telefono")
    @classmethod
    def _normalizar(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        try:
            return normalizar_telefono(v)
        except TelefonoInvalido as exc:
            raise ValueError(str(exc)) from None

    @field_validator("nombre")
    @classmethod
    def _limpiar_nombre(cls, v: str) -> str:
        return " ".join(v.split())


class ClienteNuevo(ClienteBase):
    consentimiento: ConsentimientoEntrada = ConsentimientoEntrada()
    # Permite dar de alta cliente y vehículo en una sola pantalla, que es
    # como funciona el mostrador.
    vehiculo: VehiculoNuevo | None = None

    @model_validator(mode="after")
    def _consentimiento_necesita_medio(self) -> Self:
        if self.consentimiento.whatsapp and not self.telefono:
            raise ValueError(
                "Autorizó recordatorios por WhatsApp pero no se capturó teléfono."
            )
        if self.consentimiento.correo and not self.correo:
            raise ValueError(
                "Autorizó recordatorios por correo pero no se capturó correo."
            )
        return self


class ClienteEditado(BaseModel):
    nombre: Nombre | None = None
    telefono: str | None = None
    correo: EmailStr | None = None
    consent_whatsapp: bool | None = None
    consent_correo: bool | None = None
    estado_contacto: EstadoContacto | None = None

    @field_validator("telefono")
    @classmethod
    def _normalizar_telefono(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        try:
            return normalizar_telefono(v)
        except TelefonoInvalido as exc:
            raise ValueError(str(exc)) from None


class ClientePublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    telefono_e164: str | None
    correo: str | None
    consent_whatsapp: bool
    consent_correo: bool
    consent_fecha: datetime | None
    estado_contacto: EstadoContacto
    se_le_puede_escribir: bool
    creado_en: datetime


class ClienteConVehiculos(ClientePublico):
    vehiculos: list[VehiculoPublico] = []
