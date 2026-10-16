"""Indicadores y tabla de seguimiento del panel de control.

El estado de cada vehículo no se guarda en la base: se calcula al vuelo con
el módulo del calendario. Eso evita que quede desactualizado —un vehículo
pasa de "periodo abierto" a "por vencer" solo porque cambió el día, sin que
nadie toque nada— a cambio de recorrer los vehículos activos en cada consulta.

Con unos miles de registros es instantáneo. Si algún día el padrón crece
mucho, aquí es donde habría que meter caché o una columna materializada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.dominio.calendario import Estado, estado_de_cumplimiento
from app.modelos.cliente import Cliente
from app.modelos.recordatorio import EstadoRecordatorio, Recordatorio
from app.modelos.vehiculo import Resultado, Vehiculo, Verificacion


@dataclass
class Indicadores:
    verificados_del_mes: int
    periodo_abierto: int
    por_vencer: int
    vencidos: int
    al_corriente: int
    sin_forma_de_contacto: int


@dataclass
class FilaSeguimiento:
    vehiculo_id: int
    cliente_id: int
    cliente: str
    placa: str
    ultimo_digito: int | None
    ventana: str | None
    dias_restantes: int | None
    estado: str
    se_le_puede_escribir: bool
    ultimo_aviso: str | None


def _vehiculos_con_todo(sesion: Session) -> list[Vehiculo]:
    """Los vehículos que entran al calendario, con sus verificaciones."""
    return list(
        sesion.scalars(
            select(Vehiculo)
            .options(selectinload(Vehiculo.verificaciones))
            .where(
                Vehiculo.activo.is_(True),
                Vehiculo.en_programa_estatal.is_(True),
                Vehiculo.ultimo_digito.is_not(None),
            )
        )
    )


def indicadores(sesion: Session, hoy: date | None = None) -> Indicadores:
    hoy = hoy or date.today()
    inicio_mes = hoy.replace(day=1)

    verificados = sesion.scalar(
        select(func.count(Verificacion.id)).where(
            Verificacion.fecha >= inicio_mes,
            Verificacion.fecha <= hoy,
            Verificacion.resultado == Resultado.APROBADO,
        )
    )

    conteo = dict.fromkeys(Estado, 0)
    sin_contacto = 0

    for vehiculo in _vehiculos_con_todo(sesion):
        estado, _ = estado_de_cumplimiento(
            vehiculo.ultimo_digito, hoy, vehiculo.fechas_aprobadas
        )
        conteo[estado] += 1
        cliente = sesion.get(Cliente, vehiculo.cliente_id)
        if not cliente.se_le_puede_escribir:
            sin_contacto += 1

    return Indicadores(
        verificados_del_mes=int(verificados or 0),
        periodo_abierto=conteo[Estado.PERIODO_ABIERTO],
        por_vencer=conteo[Estado.POR_VENCER],
        vencidos=conteo[Estado.VENCIDO],
        al_corriente=conteo[Estado.AL_CORRIENTE],
        sin_forma_de_contacto=sin_contacto,
    )


def _ultimo_aviso(sesion: Session, vehiculo_id: int) -> str | None:
    recordatorio = sesion.scalar(
        select(Recordatorio)
        .where(
            Recordatorio.vehiculo_id == vehiculo_id,
            Recordatorio.estado == EstadoRecordatorio.ENVIADO,
        )
        .order_by(Recordatorio.enviado_en.desc())
        .limit(1)
    )
    if recordatorio is None or recordatorio.enviado_en is None:
        return None
    return f"{recordatorio.canal.value} · {recordatorio.enviado_en:%d/%m/%Y}"


def seguimiento(
    sesion: Session,
    filtro: str | None = None,
    hoy: date | None = None,
    limite: int = 100,
) -> list[FilaSeguimiento]:
    """La tabla del panel. `filtro` es el nombre de un Estado, o None."""
    hoy = hoy or date.today()
    filas: list[FilaSeguimiento] = []

    for vehiculo in _vehiculos_con_todo(sesion):
        estado, ventana = estado_de_cumplimiento(
            vehiculo.ultimo_digito, hoy, vehiculo.fechas_aprobadas
        )
        if filtro and estado.value != filtro:
            continue

        cliente = sesion.get(Cliente, vehiculo.cliente_id)
        filas.append(
            FilaSeguimiento(
                vehiculo_id=vehiculo.id,
                cliente_id=cliente.id,
                cliente=cliente.nombre,
                placa=vehiculo.placa,
                ultimo_digito=vehiculo.ultimo_digito,
                ventana=ventana.etiqueta if ventana else None,
                dias_restantes=ventana.dias_restantes(hoy) if ventana else None,
                estado=estado.value,
                se_le_puede_escribir=cliente.se_le_puede_escribir,
                ultimo_aviso=_ultimo_aviso(sesion, vehiculo.id),
            )
        )

    # Primero lo que urge: vencidos, luego por vencer, luego el resto.
    prioridad = {
        Estado.VENCIDO.value: 0,
        Estado.POR_VENCER.value: 1,
        Estado.PERIODO_ABIERTO.value: 2,
        Estado.AL_CORRIENTE.value: 3,
        Estado.PROGRAMADO.value: 4,
    }
    filas.sort(
        key=lambda f: (prioridad.get(f.estado, 9), f.dias_restantes or 9999)
    )
    return filas[:limite]


def verificaciones_por_mes(sesion: Session, meses: int = 8) -> list[tuple[str, int]]:
    """Serie para la gráfica del panel."""
    hoy = date.today()
    inicio = (hoy.replace(day=1) - timedelta(days=31 * (meses - 1))).replace(day=1)

    filas = sesion.execute(
        select(
            func.year(Verificacion.fecha),
            func.month(Verificacion.fecha),
            func.count(Verificacion.id),
        )
        .where(
            Verificacion.fecha >= inicio,
            Verificacion.resultado == Resultado.APROBADO,
        )
        .group_by(func.year(Verificacion.fecha), func.month(Verificacion.fecha))
        .order_by(func.year(Verificacion.fecha), func.month(Verificacion.fecha))
    ).all()

    MESES = ("", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
    return [(f"{MESES[int(m)]} {int(a)}", int(n)) for a, m, n in filas]
