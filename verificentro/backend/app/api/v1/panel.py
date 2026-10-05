"""Panel de control."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencias import Sesion, consulta
from app.esquemas.recordatorio import (
    FilaSeguimiento,
    IndicadoresPanel,
    PuntoGrafica,
)
from app.servicios import panel as servicio

router = APIRouter(prefix="/panel", tags=["Panel"],
                   dependencies=[Depends(consulta)])


@router.get("/indicadores", response_model=IndicadoresPanel)
def indicadores(sesion: Sesion) -> IndicadoresPanel:
    return IndicadoresPanel(**servicio.indicadores(sesion).__dict__)


@router.get("/seguimiento", response_model=list[FilaSeguimiento])
def seguimiento(
    sesion: Sesion,
    estado: str | None = Query(
        default=None,
        description="al_corriente, periodo_abierto, por_vencer, vencido o programado",
    ),
    limite: int = Query(default=100, ge=1, le=500),
) -> list[FilaSeguimiento]:
    return [
        FilaSeguimiento(**f.__dict__)
        for f in servicio.seguimiento(sesion, estado, limite=limite)
    ]


@router.get("/grafica", response_model=list[PuntoGrafica])
def grafica(sesion: Sesion, meses: int = Query(default=8, ge=1, le=24)):
    return [
        PuntoGrafica(mes=m, verificaciones=n)
        for m, n in servicio.verificaciones_por_mes(sesion, meses)
    ]
