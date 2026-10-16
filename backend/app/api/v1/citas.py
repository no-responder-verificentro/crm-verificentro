"""Citas: consulta de horarios libres, apartado y agenda del día."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencias import Sesion, Usuario, captura, consulta
from app.dominio.agenda import AgendaNoDisponible
from app.esquemas.cita import (
    CancelarCita,
    CitaNueva,
    CitaPublica,
    DisponibilidadDia,
    HorarioLibre,
)
from app.modelos.cita import Cita
from app.servicios import citas as servicio

router = APIRouter(prefix="/citas", tags=["Citas"])


@router.get("/disponibilidad", response_model=DisponibilidadDia)
def horarios_libres(sesion: Sesion, fecha: date = Query(...)) -> DisponibilidadDia:
    """Horarios libres de un día. PÚBLICO: no expone ningún dato personal,
    solo qué lugares quedan. Es el que consulta el chatbot."""
    try:
        libres = servicio.disponibilidad(sesion, fecha)
    except AgendaNoDisponible as exc:
        return DisponibilidadDia(fecha=fecha, atiende=False, motivo=str(exc))
    return DisponibilidadDia(
        fecha=fecha,
        atiende=True,
        horarios=[HorarioLibre(hora=h, lugares=n) for h, n in libres],
    )


@router.post(
    "",
    response_model=CitaPublica,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(captura)],
)
def agendar(datos: CitaNueva, sesion: Sesion, usuario: Usuario) -> Cita:
    try:
        return servicio.agendar(
            sesion,
            placa=datos.placa,
            nombre=datos.nombre,
            telefono=datos.telefono,
            fecha=datos.fecha,
            hora=datos.hora,
            origen=datos.origen,
            empleado_id=usuario.id,
            notas=datos.notas,
        )
    except AgendaNoDisponible as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None


@router.get("", response_model=list[CitaPublica], dependencies=[Depends(consulta)])
def agenda_del_dia(sesion: Sesion, fecha: date | None = None) -> list[Cita]:
    """La agenda de un día, para que el mostrador sepa a quién esperar."""
    return servicio.agenda_del_dia(sesion, fecha or date.today())


def _obtener(sesion, cita_id: int) -> Cita:
    cita = sesion.get(Cita, cita_id)
    if cita is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada."
        )
    return cita


@router.post(
    "/{cita_id}/cancelar",
    response_model=CitaPublica,
    dependencies=[Depends(captura)],
)
def cancelar(cita_id: int, datos: CancelarCita, sesion: Sesion) -> Cita:
    """Cancela y libera el lugar para que alguien más lo pueda apartar."""
    try:
        return servicio.cancelar(sesion, _obtener(sesion, cita_id), datos.motivo)
    except AgendaNoDisponible as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None


@router.post(
    "/{cita_id}/no-asistio",
    response_model=CitaPublica,
    dependencies=[Depends(captura)],
)
def no_asistio(cita_id: int, sesion: Sesion) -> Cita:
    try:
        return servicio.marcar_no_asistio(sesion, _obtener(sesion, cita_id))
    except AgendaNoDisponible as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None
