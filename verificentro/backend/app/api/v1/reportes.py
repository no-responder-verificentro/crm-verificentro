"""Reportes."""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.dependencias import Sesion, solo_admin
from app.servicios import panel as servicio_panel
from app.servicios import reportes as servicio

router = APIRouter(prefix="/reportes", tags=["Reportes"],
                   dependencies=[Depends(solo_admin)])


class CumplimientoPublico(BaseModel):
    digitos: str
    padron: int
    verificaron: int
    porcentaje: float


class EfectividadPublica(BaseModel):
    anio: int
    con_aviso_total: int
    con_aviso_verificaron: int
    con_aviso_porcentaje: float
    sin_aviso_total: int
    sin_aviso_verificaron: int
    sin_aviso_porcentaje: float
    diferencia_puntos: float
    verificaciones_atribuibles: int


class CanalPublico(BaseModel):
    canal: str
    enviados: int
    entregados: int
    fallidos: int
    tasa_entrega: float


class PuntoGrafica(BaseModel):
    mes: str
    verificaciones: int


@router.get("/efectividad", response_model=EfectividadPublica)
def efectividad(sesion: Sesion, anio: int | None = Query(default=None)):
    """El número que justifica el proyecto: cuántos de los que recibieron
    aviso regresaron, contra los que no."""
    return EfectividadPublica(
        **servicio.efectividad_de_recordatorios(sesion, anio).__dict__
    )


@router.get("/cumplimiento", response_model=list[CumplimientoPublico])
def cumplimiento(sesion: Sesion, anio: int | None = Query(default=None)):
    return [
        CumplimientoPublico(**c.__dict__)
        for c in servicio.cumplimiento_por_digito(sesion, anio)
    ]


@router.get("/canales", response_model=list[CanalPublico])
def canales(sesion: Sesion):
    return [CanalPublico(**c.__dict__) for c in servicio.resumen_por_canal(sesion)]


@router.get("/verificaciones-por-mes", response_model=list[PuntoGrafica])
def por_mes(sesion: Sesion, meses: int = Query(default=12, ge=1, le=36)):
    return [
        PuntoGrafica(mes=m, verificaciones=n)
        for m, n in servicio_panel.verificaciones_por_mes(sesion, meses)
    ]


@router.get("/exportar")
def exportar(sesion: Sesion, anio: int | None = Query(default=None)):
    """Descarga las verificaciones del año en CSV, que Excel abre directo.

    Se usa el punto y coma como separador y se antepone el BOM porque Excel en
    español, con la coma, mete todo en una sola columna y rompe los acentos.
    """
    anio = anio or date.today().year
    filas = servicio.filas_para_exportar(sesion, anio)

    memoria = io.StringIO()
    memoria.write("\ufeff")
    columnas = ["folio", "fecha", "placa", "ultimo_digito", "periodo", "cliente",
                "marca", "linea", "modelo", "resultado", "holograma"]
    escritor = csv.DictWriter(memoria, fieldnames=columnas, delimiter=";",
                              extrasaction="ignore")
    escritor.writeheader()
    escritor.writerows(filas)
    memoria.seek(0)

    return StreamingResponse(
        iter([memoria.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="verificaciones-{anio}.csv"'
        },
    )
