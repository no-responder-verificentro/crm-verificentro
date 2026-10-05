"""Verificaciones: registro y bitácora."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencias import Sesion, Usuario, captura, consulta
from app.esquemas.cliente import VehiculoPublico
from app.esquemas.verificacion import (
    ResumenVerificaciones,
    VerificacionEnBitacora,
    VerificacionNueva,
    VerificacionPublica,
)
from app.modelos.vehiculo import Resultado, Vehiculo
from app.servicios import clientes as servicio_clientes
from app.servicios import verificaciones as servicio
from app.servicios.clientes import ReglaDeNegocio

router = APIRouter(prefix="/verificaciones", tags=["Verificaciones"])


class RespuestaRegistro(VerificacionPublica):
    """Se devuelve el vehículo actualizado para que la pantalla vea el cambio
    de estado sin tener que volver a consultar."""

    vehiculo: VehiculoPublico


@router.post(
    "",
    response_model=RespuestaRegistro,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(captura)],
)
def registrar(datos: VerificacionNueva, sesion: Sesion, usuario: Usuario):
    """Registra la verificación y con eso el vehículo queda al corriente.

    A partir de aquí el generador de recordatorios lo salta: ya cumplió su
    ventana. Por eso conviene capturar en el mismo momento en que se entrega
    el certificado y no al final del día — si no se captura, el cliente sigue
    recibiendo avisos después de haber verificado, que es justo lo que molesta.
    """
    vehiculo = sesion.get(Vehiculo, datos.vehiculo_id)
    if vehiculo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado."
        )

    try:
        verificacion = servicio.registrar(sesion, vehiculo, datos, usuario.id)
    except ReglaDeNegocio as exc:
        sesion.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None

    sesion.refresh(vehiculo)
    return RespuestaRegistro(
        **VerificacionPublica.model_validate(verificacion).model_dump(),
        vehiculo=servicio_clientes.describir_vehiculo(vehiculo),
    )


@router.get(
    "",
    response_model=list[VerificacionEnBitacora],
    dependencies=[Depends(consulta)],
)
def listar(
    sesion: Sesion,
    desde: date | None = None,
    hasta: date | None = None,
    resultado: Resultado | None = None,
    buscar: str | None = Query(default=None, description="Placa, cliente o folio."),
    limite: int = Query(default=100, ge=1, le=500),
    desplazamiento: int = Query(default=0, ge=0),
) -> list[VerificacionEnBitacora]:
    return servicio.bitacora(
        sesion, desde, hasta, resultado, buscar, limite, desplazamiento
    )


@router.get(
    "/resumen",
    response_model=ResumenVerificaciones,
    dependencies=[Depends(consulta)],
)
def resumen(
    sesion: Sesion,
    desde: date | None = None,
    hasta: date | None = None,
) -> ResumenVerificaciones:
    """Indicadores del encabezado. Por omisión, los últimos 30 días."""
    hasta = hasta or date.today()
    desde = desde or (hasta - timedelta(days=30))
    if desde > hasta:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha inicial es posterior a la final.",
        )
    return servicio.resumen(sesion, desde, hasta)
