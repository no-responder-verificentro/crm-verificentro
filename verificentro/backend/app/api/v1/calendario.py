"""Consulta de periodo por placa.

Este endpoint es PÚBLICO a propósito: es el que alimenta la respuesta estrella
del chatbot ("¿cuándo me toca verificar?"). No expone ningún dato personal,
solo aplica el Artículo 9 a una placa. Quien pregunta ya conoce su placa.

Toda la lógica vive en app/dominio/calendario.py, que no sabe nada de HTTP ni
de base de datos. Este archivo solo traduce entre el dominio y JSON.
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dominio.calendario import (
    PlacaSinDigito,
    normalizar_placa,
    ultimo_digito,
    ventanas_del_anio,
)

router = APIRouter(prefix="/calendario", tags=["Calendario"])


class PeriodoPublico(BaseModel):
    periodo: int
    etiqueta: str
    inicio: date
    fin: date
    abierto_hoy: bool
    dias_para_abrir: int | None = None
    dias_restantes: int | None = None


class ConsultaPlaca(BaseModel):
    placa: str
    placa_normalizada: str
    ultimo_digito: int = Field(description="Último carácter NUMÉRICO de la placa")
    anio: int
    periodos: list[PeriodoPublico]
    mensaje: str


@router.get("/consultar", response_model=ConsultaPlaca)
def consultar_por_placa(
    placa: str = Query(min_length=4, max_length=15, examples=["YUN-047-A"]),
    anio: int | None = Query(default=None, ge=2020, le=2100),
) -> ConsultaPlaca:
    hoy = date.today()
    anio = anio or hoy.year

    try:
        digito = ultimo_digito(placa)
    except PlacaSinDigito:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Esa placa no contiene ningún número. "
                "Revísala o acude al mostrador para que te ayudemos."
            ),
        ) from None

    periodos: list[PeriodoPublico] = []
    for v in ventanas_del_anio(digito, anio):
        abierto = v.contiene(hoy)
        periodos.append(
            PeriodoPublico(
                periodo=v.periodo,
                etiqueta=v.etiqueta,
                inicio=v.inicio,
                fin=v.fin,
                abierto_hoy=abierto,
                dias_para_abrir=None if abierto else v.dias_para_abrir(hoy),
                dias_restantes=v.dias_restantes(hoy) if abierto else None,
            )
        )

    vigente = next((p for p in periodos if p.abierto_hoy), None)
    if vigente is not None:
        mensaje = (
            f"Te toca ahora: {vigente.etiqueta}. "
            f"Quedan {vigente.dias_restantes} días para que cierre."
        )
    else:
        etiquetas = " y ".join(p.etiqueta for p in periodos)
        mensaje = f"En {anio} te toca verificar en {etiquetas}."

    return ConsultaPlaca(
        placa=placa,
        placa_normalizada=normalizar_placa(placa),
        ultimo_digito=digito,
        anio=anio,
        periodos=periodos,
        mensaje=mensaje,
    )
