"""Casos de uso de citas."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dominio.agenda import (
    AgendaNoDisponible,
    ConfiguracionAgenda,
    Horario,
    bloques_agendables,
    bloques_del_dia,
    dia_de_la_semana,
    validar_anticipacion,
)
import app.modelos  # noqa: F401  registra todos los modelos
from app.modelos.cita import (
    ESTADOS_ACTIVOS,
    Cita,
    ConfigCitas,
    DiaNoLaborable,
    EstadoCita,
    HorarioAtencion,
)
from app.modelos.vehiculo import Vehiculo


def _ahora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def normalizar_placa(placa: str) -> str:
    return "".join(c for c in (placa or "").upper() if c.isalnum())


def leer_configuracion(sesion: Session) -> ConfiguracionAgenda:
    fila = sesion.get(ConfigCitas, 1)
    if fila is None:
        return ConfiguracionAgenda()
    return ConfiguracionAgenda(
        duracion_bloque_min=fila.duracion_bloque_min,
        cupos_por_bloque=fila.cupos_por_bloque,
        bloques_por_cita=fila.bloques_por_cita,
        anticipacion_max_dias=fila.anticipacion_max_dias,
        anticipacion_min_horas=fila.anticipacion_min_horas,
        tolerancia_retardo_min=fila.tolerancia_retardo_min,
    )


def _horario_de(sesion: Session, fecha: date) -> Horario:
    """El horario de ese día, o explica por qué no se atiende."""
    no_laborable = sesion.get(DiaNoLaborable, fecha)
    if no_laborable is not None:
        motivo = f" ({no_laborable.motivo})" if no_laborable.motivo else ""
        raise AgendaNoDisponible(f"Ese día no hay servicio{motivo}.")

    fila = sesion.get(HorarioAtencion, dia_de_la_semana(fecha))
    if fila is None or not fila.activo:
        raise AgendaNoDisponible("Ese día no se atiende.")

    return Horario(apertura=fila.hora_apertura, cierre=fila.hora_cierre)


def _ocupacion(sesion: Session, fecha: date) -> dict[time, set[int]]:
    """Qué cupos están tomados en cada bloque de ese día."""
    citas = sesion.scalars(
        select(Cita).where(
            Cita.fecha == fecha,
            Cita.estado.in_(ESTADOS_ACTIVOS),
            Cita.cupo.is_not(None),
        )
    )
    tomados: dict[time, set[int]] = {}
    for cita in citas:
        tomados.setdefault(cita.hora_inicio, set()).add(cita.cupo)
    return tomados


def disponibilidad(sesion: Session, fecha: date, ahora: datetime | None = None):
    """Los horarios libres de un día, listos para pintarse o para el chatbot.

    Devuelve una lista de tuplas (hora, lugares_libres). Se omiten los bloques
    que ya pasaron o que caen dentro del mínimo de anticipación.
    """
    ahora = ahora or _ahora()
    config = leer_configuracion(sesion)
    horario = _horario_de(sesion, fecha)   # puede lanzar AgendaNoDisponible

    bloques = bloques_agendables(
        bloques_del_dia(horario, config.duracion_bloque_min),
        config.bloques_por_cita,
    )
    tomados = _ocupacion(sesion, fecha)

    libres: list[tuple[time, int]] = []
    for hora in bloques:
        try:
            validar_anticipacion(fecha, hora, config, ahora)
        except AgendaNoDisponible:
            continue   # ese bloque ya no alcanza, pero el día sigue abierto
        restantes = config.cupos_por_bloque - len(tomados.get(hora, set()))
        if restantes > 0:
            libres.append((hora, restantes))
    return libres


# ---------------------------------------------------------------- apartar --

def _cita_activa_de(sesion: Session, placa_normalizada: str) -> Cita | None:
    return sesion.scalar(
        select(Cita).where(
            Cita.placa_capturada == placa_normalizada,
            Cita.estado.in_(ESTADOS_ACTIVOS),
            Cita.fecha >= date.today(),
        )
    )


def agendar(
    sesion: Session,
    *,
    placa: str,
    nombre: str,
    telefono: str | None,
    fecha: date,
    hora: time,
    origen,
    empleado_id: int | None = None,
    notas: str | None = None,
    ahora: datetime | None = None,
) -> Cita:
    ahora = ahora or _ahora()
    config = leer_configuracion(sesion)
    placa_norm = normalizar_placa(placa)

    horario = _horario_de(sesion, fecha)
    validar_anticipacion(fecha, hora, config, ahora)

    agendables = bloques_agendables(
        bloques_del_dia(horario, config.duracion_bloque_min),
        config.bloques_por_cita,
    )
    if hora not in agendables:
        # Los bloques que no están en la lista existen, pero se reservan para
        # quien llega sin cita.
        raise AgendaNoDisponible(
            "Ese horario no está disponible para cita. "
            "Consulta los horarios libres del día."
        )

    # Una placa no puede acaparar la agenda. También evita que alguien aparte
    # cinco lugares "por si acaso" desde el chatbot.
    existente = _cita_activa_de(sesion, placa_norm)
    if existente is not None:
        raise AgendaNoDisponible(
            f"La placa {placa} ya tiene una cita el {existente.fecha:%d/%m/%Y} "
            f"a las {existente.hora_inicio:%H:%M}. Cancélala antes de apartar otra."
        )

    vehiculo = sesion.scalar(
        select(Vehiculo).where(Vehiculo.placa_normalizada == placa_norm)
    )

    tomados = _ocupacion(sesion, fecha).get(hora, set())

    # Se intenta cupo por cupo. Si dos personas piden el mismo al mismo tiempo,
    # el índice único rechaza a una y se reintenta con el siguiente.
    for cupo in range(1, config.cupos_por_bloque + 1):
        if cupo in tomados:
            continue
        cita = Cita(
            vehiculo_id=vehiculo.id if vehiculo else None,
            cliente_id=vehiculo.cliente_id if vehiculo else None,
            placa_capturada=placa_norm,
            nombre_contacto=nombre.strip(),
            telefono_contacto=telefono,
            fecha=fecha,
            hora_inicio=hora,
            cupo=cupo,
            origen=origen,
            creada_por=empleado_id,
            notas=notas,
        )
        sesion.add(cita)
        try:
            sesion.commit()
        except IntegrityError:
            sesion.rollback()
            continue
        sesion.refresh(cita)
        return cita

    raise AgendaNoDisponible("Ese horario acaba de ocuparse. Elige otro.")


# -------------------------------------------------------------- cambios ---

def cancelar(sesion: Session, cita: Cita, motivo: str | None = None) -> Cita:
    """Cancela y libera el lugar poniendo `cupo` en NULL."""
    if cita.estado is EstadoCita.ATENDIDA:
        raise AgendaNoDisponible("Esa cita ya fue atendida; no se puede cancelar.")
    if cita.estado is EstadoCita.CANCELADA:
        return cita

    cita.estado = EstadoCita.CANCELADA
    cita.cupo = None
    cita.cancelada_en = _ahora()
    cita.motivo_cancelacion = motivo
    sesion.commit()
    sesion.refresh(cita)
    return cita


def marcar_no_asistio(sesion: Session, cita: Cita) -> Cita:
    if not cita.sigue_activa:
        raise AgendaNoDisponible("Esa cita ya no está activa.")
    cita.estado = EstadoCita.NO_ASISTIO
    cita.cupo = None      # el día ya pasó; se libera para no estorbar
    sesion.commit()
    sesion.refresh(cita)
    return cita


def cerrar_con_verificacion(
    sesion: Session, vehiculo_id: int, fecha: date, verificacion_id: int
) -> Cita | None:
    """Si el auto tenía cita ese día, la marca como atendida.

    Se llama desde el registro de verificaciones: así nadie tiene que acordarse
    de cerrar la cita a mano, y el reporte de asistencia sale solo.
    """
    cita = sesion.scalar(
        select(Cita).where(
            Cita.vehiculo_id == vehiculo_id,
            Cita.fecha == fecha,
            Cita.estado.in_(ESTADOS_ACTIVOS),
        )
    )
    if cita is None:
        return None

    cita.estado = EstadoCita.ATENDIDA
    cita.verificacion_id = verificacion_id
    sesion.commit()
    sesion.refresh(cita)
    return cita


def agenda_del_dia(sesion: Session, fecha: date) -> list[Cita]:
    return list(
        sesion.scalars(
            select(Cita)
            .where(Cita.fecha == fecha)
            .order_by(Cita.hora_inicio, Cita.cupo)
        )
    )
