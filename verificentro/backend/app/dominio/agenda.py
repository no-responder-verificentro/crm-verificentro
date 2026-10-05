"""Agenda de citas: qué bloques existen y cuáles se ofrecen.

Con una sola línea de verificación, el día se parte en bloques del tamaño que
tarda una verificación. No todos se ofrecen para cita: hay que dejar lugar a
quien llega sin avisar, que es como llega casi toda la gente.

Con bloques de 20 minutos y `bloques_por_cita = 3`, de 9:00 a 16:00 quedan
21 bloques, de los cuales 7 son agendables — uno por hora:

    9:00 CITA   9:20 libre   9:40 libre
   10:00 CITA  10:20 libre  10:40 libre
   ...

Igual que `calendario.py`, este módulo no importa nada de infraestructura.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

__all__ = [
    "AgendaNoDisponible",
    "Horario",
    "ConfiguracionAgenda",
    "bloques_del_dia",
    "bloques_agendables",
    "dia_de_la_semana",
    "validar_anticipacion",
]


class AgendaNoDisponible(Exception):
    """Ese día u hora no admite citas. El mensaje explica por qué."""


@dataclass(frozen=True)
class Horario:
    """Horario de atención de un día de la semana."""

    apertura: time
    cierre: time


@dataclass(frozen=True)
class ConfiguracionAgenda:
    """Refleja la tabla `config_citas`."""

    duracion_bloque_min: int = 20
    cupos_por_bloque: int = 1
    bloques_por_cita: int = 3
    anticipacion_max_dias: int = 30
    anticipacion_min_horas: int = 2
    tolerancia_retardo_min: int = 15


def dia_de_la_semana(fecha: date) -> int:
    """1 = lunes … 7 = domingo, como en `horarios_atencion.dia_semana`."""
    return fecha.isoweekday()


def bloques_del_dia(horario: Horario, duracion_min: int) -> list[time]:
    """Todos los bloques en que se parte la jornada.

    El último bloque tiene que caber completo antes del cierre: no se ofrece
    uno a las 15:50 si la verificación tarda 20 minutos y cierran a las 16:00.
    """
    if duracion_min <= 0:
        raise ValueError("La duración del bloque debe ser mayor a cero.")

    inicio = datetime.combine(date.min, horario.apertura)
    fin = datetime.combine(date.min, horario.cierre)
    paso = timedelta(minutes=duracion_min)

    bloques: list[time] = []
    actual = inicio
    while actual + paso <= fin:
        bloques.append(actual.time())
        actual += paso
    return bloques


def bloques_agendables(bloques: list[time], bloques_por_cita: int) -> list[time]:
    """De todos los bloques, cuáles se ofrecen para cita.

    `bloques_por_cita` es cada cuántos se aparta uno:
        1 = toda la agenda para citas
        2 = intercalado estricto, uno sí y uno no
        3 = uno por hora, si los bloques son de 20 minutos
    """
    if bloques_por_cita < 1:
        raise ValueError("bloques_por_cita debe ser 1 o mayor.")
    return bloques[::bloques_por_cita]


def validar_anticipacion(
    fecha: date,
    hora: time,
    config: ConfiguracionAgenda,
    ahora: datetime | None = None,
) -> None:
    """Revisa que la cita no sea ni demasiado pronto ni demasiado lejana.

    Lanza `AgendaNoDisponible` con un mensaje que se le puede mostrar tal cual
    a la persona, venga del mostrador o del chatbot.
    """
    ahora = ahora or datetime.now()
    momento = datetime.combine(fecha, hora)

    if momento < ahora:
        raise AgendaNoDisponible("Ese horario ya pasó.")

    minimo = ahora + timedelta(hours=config.anticipacion_min_horas)
    if momento < minimo:
        horas = config.anticipacion_min_horas
        raise AgendaNoDisponible(
            f"Las citas se apartan con al menos {horas} "
            f"hora{'s' if horas != 1 else ''} de anticipación. "
            "Si necesitas venir hoy mismo, puedes llegar sin cita."
        )

    limite = ahora.date() + timedelta(days=config.anticipacion_max_dias)
    if fecha > limite:
        raise AgendaNoDisponible(
            f"Solo se pueden apartar citas con {config.anticipacion_max_dias} "
            "días de anticipación."
        )
