"""Registro y consulta de verificaciones.

Esta es la pieza que cierra el ciclo. El sistema solo sabe que un cliente ya
cumplió porque alguien capturó aquí su verificación; de ahí que convenga que
la captura sea parte del mismo momento en que se entrega el certificado, y no
un trámite aparte al final del día.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.dominio.calendario import ventana_de_fecha
from app.esquemas.verificacion import (
    ResumenVerificaciones,
    VerificacionEnBitacora,
    VerificacionNueva,
)
from app.modelos.cliente import Cliente
from app.modelos.empleado import Empleado
from app.modelos.vehiculo import Resultado, Vehiculo, Verificacion
from app.servicios import citas as servicio_citas
from app.servicios.clientes import ReglaDeNegocio


def _periodo_de(vehiculo: Vehiculo, fecha: date) -> int | None:
    """En qué periodo del calendario cae esa fecha, si es que cae en alguno.

    Queda en NULL cuando el vehículo verificó fuera de su ventana (le urgía,
    se le pasó, o va adelantado) y cuando está fuera del programa estatal.
    """
    if vehiculo.ultimo_digito is None or not vehiculo.en_programa_estatal:
        return None
    ventana = ventana_de_fecha(vehiculo.ultimo_digito, fecha)
    return ventana.periodo if ventana is not None else None


def registrar(
    sesion: Session,
    vehiculo: Vehiculo,
    datos: VerificacionNueva,
    empleado_id: int,
) -> Verificacion:
    hoy = date.today()

    if datos.fecha > hoy:
        raise ReglaDeNegocio("No se puede registrar una verificación con fecha futura.")

    if datos.folio_certificado:
        repetido = sesion.scalar(
            select(Verificacion).where(
                Verificacion.folio_certificado == datos.folio_certificado
            )
        )
        if repetido is not None:
            raise ReglaDeNegocio(
                f"El folio {datos.folio_certificado} ya está registrado "
                f"(placa {repetido.placa_al_verificar}, {repetido.fecha})."
            )

    # Un rechazo no lleva holograma: el vehículo no pasó.
    if datos.resultado is Resultado.RECHAZADO and datos.holograma:
        raise ReglaDeNegocio("Una verificación rechazada no puede llevar holograma.")

    verificacion = Verificacion(
        vehiculo_id=vehiculo.id,
        fecha=datos.fecha,
        hora=datos.hora,
        periodo=_periodo_de(vehiculo, datos.fecha),
        resultado=datos.resultado,
        holograma=datos.holograma,
        folio_certificado=datos.folio_certificado,
        placa_al_verificar=vehiculo.placa,
        observaciones=datos.observaciones,
        tecnico_id=empleado_id,
    )
    sesion.add(verificacion)
    sesion.commit()
    sesion.refresh(verificacion)

    # Si el auto tenía cita ese día, se cierra sola. Así nadie tiene que
    # acordarse de marcarla a mano y el reporte de asistencia sale solo.
    servicio_citas.cerrar_con_verificacion(
        sesion, vehiculo.id, datos.fecha, verificacion.id
    )
    return verificacion


# --------------------------------------------------------------- consulta --

def _consulta_bitacora(
    desde: date | None,
    hasta: date | None,
    resultado: Resultado | None,
    texto: str | None,
) -> Select:
    consulta = (
        select(Verificacion, Vehiculo, Cliente, Empleado.nombre)
        .join(Vehiculo, Verificacion.vehiculo_id == Vehiculo.id)
        .join(Cliente, Vehiculo.cliente_id == Cliente.id)
        .outerjoin(Empleado, Verificacion.tecnico_id == Empleado.id)
    )
    if desde is not None:
        consulta = consulta.where(Verificacion.fecha >= desde)
    if hasta is not None:
        consulta = consulta.where(Verificacion.fecha <= hasta)
    if resultado is not None:
        consulta = consulta.where(Verificacion.resultado == resultado)
    if texto and texto.strip():
        t = texto.strip()
        placa = "".join(c for c in t.upper() if c.isalnum())
        consulta = consulta.where(
            Vehiculo.placa_normalizada.like(f"%{placa}%")
            | Cliente.nombre.like(f"%{t}%")
            | Verificacion.folio_certificado.like(f"%{t}%")
        )
    return consulta


def bitacora(
    sesion: Session,
    desde: date | None = None,
    hasta: date | None = None,
    resultado: Resultado | None = None,
    texto: str | None = None,
    limite: int = 100,
    desplazamiento: int = 0,
) -> list[VerificacionEnBitacora]:
    consulta = (
        _consulta_bitacora(desde, hasta, resultado, texto)
        .order_by(Verificacion.fecha.desc(), Verificacion.id.desc())
        .limit(limite)
        .offset(desplazamiento)
    )

    filas = []
    for verif, vehiculo, cliente, tecnico in sesion.execute(consulta):
        descripcion = " ".join(
            str(p) for p in (vehiculo.marca, vehiculo.linea, vehiculo.modelo_anio) if p
        ).strip()
        filas.append(
            VerificacionEnBitacora(
                id=verif.id,
                vehiculo_id=verif.vehiculo_id,
                fecha=verif.fecha,
                hora=verif.hora,
                periodo=verif.periodo,
                resultado=verif.resultado,
                holograma=verif.holograma,
                folio_certificado=verif.folio_certificado,
                placa_al_verificar=verif.placa_al_verificar,
                observaciones=verif.observaciones,
                tecnico_id=verif.tecnico_id,
                placa=verif.placa_al_verificar or vehiculo.placa,
                cliente_id=cliente.id,
                cliente_nombre=cliente.nombre,
                vehiculo_descripcion=descripcion or None,
                tecnico_nombre=tecnico,
                dentro_de_su_periodo=verif.periodo is not None,
            )
        )
    return filas


def resumen(
    sesion: Session, desde: date, hasta: date
) -> ResumenVerificaciones:
    """Los indicadores del encabezado, en una sola consulta."""
    # CASE en lugar de IF(): IF() es de MySQL y no correría en otro motor.
    es_aprobada = case((Verificacion.resultado == Resultado.APROBADO, 1), else_=0)
    esta_fuera = case((Verificacion.periodo.is_(None), 1), else_=0)

    fila = sesion.execute(
        select(
            func.count(Verificacion.id),
            func.coalesce(func.sum(es_aprobada), 0),
            func.coalesce(func.sum(esta_fuera), 0),
        ).where(Verificacion.fecha.between(desde, hasta))
    ).one()

    total = int(fila[0] or 0)
    aprobadas = int(fila[1] or 0)
    fuera = int(fila[2] or 0)
    rechazadas = total - aprobadas

    return ResumenVerificaciones(
        desde=desde,
        hasta=hasta,
        total=total,
        aprobadas=aprobadas,
        rechazadas=rechazadas,
        indice_rechazo=round(rechazadas / total * 100, 1) if total else 0.0,
        fuera_de_periodo=fuera,
    )
