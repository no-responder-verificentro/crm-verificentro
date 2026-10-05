"""Recordatorios: cola, bitácora y control manual."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.config import obtener_config
from app.dependencias import Sesion, consulta, solo_admin
from app.dominio.calendario import ventanas_del_anio
from app.esquemas.recordatorio import (
    ResultadoEnvio,
    ResultadoGeneracion,
    MotivoPausa,
    RecordatorioEnLista,
    RecordatorioPublico,
    ResumenRecordatorios,
)
from app.modelos.cliente import Cliente, EstadoContacto
from app.modelos.recordatorio import (
    ENTREGA_FALLIDA,
    EstadoEntrega,
    EstadoRecordatorio,
    Recordatorio,
)
from app.modelos.vehiculo import Vehiculo
from app.servicios import recordatorios as servicio

router = APIRouter(prefix="/recordatorios", tags=["Recordatorios"])


def _a_fila(sesion, recordatorio: Recordatorio) -> RecordatorioEnLista:
    vehiculo = sesion.get(Vehiculo, recordatorio.vehiculo_id)
    cliente = sesion.get(Cliente, recordatorio.cliente_id)

    etiqueta = None
    if recordatorio.ventana_anio and vehiculo and vehiculo.ultimo_digito is not None:
        ventanas = ventanas_del_anio(vehiculo.ultimo_digito, recordatorio.ventana_anio)
        etiqueta = ventanas[(recordatorio.ventana_periodo or 1) - 1].etiqueta

    return RecordatorioEnLista(
        **RecordatorioPublico.model_validate(recordatorio).model_dump(),
        cliente_nombre=cliente.nombre if cliente else "—",
        placa=vehiculo.placa if vehiculo else "—",
        ventana=etiqueta,
    )


@router.get("/cola", response_model=list[RecordatorioEnLista],
            dependencies=[Depends(consulta)])
def cola(sesion: Sesion, horas: int = Query(default=48, ge=1, le=24 * 400)):
    """Lo que está por salir. Se puede pausar antes de que se envíe."""
    return [_a_fila(sesion, r) for r in servicio.cola(sesion, horas)]


@router.get("/historial", response_model=list[RecordatorioEnLista],
            dependencies=[Depends(consulta)])
def historial(sesion: Sesion, limite: int = Query(default=100, ge=1, le=500)):
    return [_a_fila(sesion, r) for r in servicio.historial(sesion, limite)]


@router.get("/resumen", response_model=ResumenRecordatorios,
            dependencies=[Depends(consulta)])
def resumen(sesion: Sesion) -> ResumenRecordatorios:
    hoy = date.today()

    programados = sesion.scalar(
        select(func.count(Recordatorio.id)).where(
            Recordatorio.estado == EstadoRecordatorio.PROGRAMADO,
            func.date(Recordatorio.programado_para) == hoy,
        )
    )
    desde = hoy - timedelta(days=7)
    enviados = sesion.scalar(
        select(func.count(Recordatorio.id)).where(
            Recordatorio.estado == EstadoRecordatorio.ENVIADO,
            func.date(Recordatorio.enviado_en) >= desde,
        )
    )
    fallidos = sesion.scalar(
        select(func.count(Recordatorio.id)).where(
            Recordatorio.estado_entrega.in_(ENTREGA_FALLIDA)
        )
    )
    entregados = sesion.scalar(
        select(func.count(Recordatorio.id)).where(
            Recordatorio.estado_entrega.in_(
                [EstadoEntrega.ENTREGADO, EstadoEntrega.LEIDO,
                 EstadoEntrega.CLIC, EstadoEntrega.ENVIADO]
            )
        )
    )
    no_localizables = sesion.scalar(
        select(func.count(Cliente.id)).where(
            Cliente.estado_contacto == EstadoContacto.NO_LOCALIZABLE
        )
    )

    total = int(entregados or 0) + int(fallidos or 0)
    config = obtener_config()
    return ResumenRecordatorios(
        canales_activos=[c.lower() for c in config.canales_activos],
        programados_hoy=int(programados or 0),
        enviados_7_dias=int(enviados or 0),
        tasa_entrega=round(int(entregados or 0) / total * 100, 1) if total else 0.0,
        no_entregados=int(fallidos or 0),
        contactos_no_localizables=int(no_localizables or 0),
    )


# --------------------------------------------------------------------------
#  Ejecutar los procesos desde la pantalla
# --------------------------------------------------------------------------
#  Los mismos que corren solos cada mañana, pero disparados a mano. Hacen
#  falta por dos razones: para que nadie tenga que abrir una terminal, y
#  porque el plan gratuito de Render no tiene tareas programadas.
# --------------------------------------------------------------------------

@router.post("/generar", response_model=ResultadoGeneracion,
             dependencies=[Depends(solo_admin)])
def generar(
    sesion: Sesion,
    dias: int = Query(default=1, ge=1, le=120,
                      description="Cuántos días hacia adelante revisar."),
) -> ResultadoGeneracion:
    """Revisa a quién le toca un aviso y llena la cola. NO envía nada."""
    inicio = date.today()
    total = ResultadoGeneracion(desde=inicio, hasta=inicio)

    for n in range(dias):
        dia = inicio + timedelta(days=n)
        r = servicio.generar_del_dia(sesion, dia)
        total.creados += r.creados
        total.duplicados += r.duplicados
        total.cancelados += r.cancelados
        total.sin_contacto += r.sin_consentimiento
        total.hasta = dia

    return total


@router.post("/enviar", response_model=ResultadoEnvio,
             dependencies=[Depends(solo_admin)])
def enviar(sesion: Sesion) -> ResultadoEnvio:
    """Manda lo que ya está en la cola y a lo que ya le tocaba salir."""
    r = servicio.enviar_pendientes(sesion, silencioso=True)
    return ResultadoEnvio(
        enviados=r.enviados, fallidos=r.fallidos,
        contactos_marcados=r.contactos_marcados,
    )


def _obtener(sesion, recordatorio_id: int) -> Recordatorio:
    recordatorio = sesion.get(Recordatorio, recordatorio_id)
    if recordatorio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Recordatorio no encontrado.")
    return recordatorio


@router.post("/{recordatorio_id}/pausar", response_model=RecordatorioPublico,
             dependencies=[Depends(solo_admin)])
def pausar(recordatorio_id: int, datos: MotivoPausa, sesion: Sesion):
    """Detiene un envío sin cancelarlo: se puede reanudar."""
    recordatorio = _obtener(sesion, recordatorio_id)
    if recordatorio.estado is not EstadoRecordatorio.PROGRAMADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se puede pausar un recordatorio que aún no ha salido.",
        )
    recordatorio.estado = EstadoRecordatorio.PAUSADO
    recordatorio.motivo_error = datos.motivo
    sesion.commit()
    sesion.refresh(recordatorio)
    return recordatorio


@router.post("/{recordatorio_id}/reanudar", response_model=RecordatorioPublico,
             dependencies=[Depends(solo_admin)])
def reanudar(recordatorio_id: int, sesion: Sesion):
    recordatorio = _obtener(sesion, recordatorio_id)
    if recordatorio.estado is not EstadoRecordatorio.PAUSADO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Ese recordatorio no está pausado.")
    recordatorio.estado = EstadoRecordatorio.PROGRAMADO
    recordatorio.motivo_error = None
    sesion.commit()
    sesion.refresh(recordatorio)
    return recordatorio


@router.post("/{recordatorio_id}/cancelar", response_model=RecordatorioPublico,
             dependencies=[Depends(solo_admin)])
def cancelar(recordatorio_id: int, sesion: Sesion):
    """Cancelar es definitivo. Para detener temporalmente, usa pausar."""
    recordatorio = _obtener(sesion, recordatorio_id)
    if not recordatorio.puede_cancelarse:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese recordatorio ya salió; no se puede cancelar.",
        )
    recordatorio.estado = EstadoRecordatorio.CANCELADO
    sesion.commit()
    sesion.refresh(recordatorio)
    return recordatorio
