"""Reportes.

El más importante es `efectividad_de_recordatorios`: compara cuántos de los
que recibieron un aviso regresaron a verificar dentro de su periodo, contra
los que no lo recibieron. Es el número que justifica el proyecto, y si sale
parejo quiere decir que el sistema no está sirviendo y hay que cambiar algo.

Importante sobre cómo leerlo: NO es un experimento controlado. La gente que no
recibió aviso suele ser la que no dejó consentimiento o cuyos datos están mal,
y esa gente probablemente ya era distinta de entrada. La diferencia es una
señal útil, no una medición limpia de causa y efecto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.dominio.calendario import ventanas_del_anio
from app.modelos.cliente import Cliente
from app.modelos.recordatorio import (
    EstadoRecordatorio,
    Recordatorio,
    TipoRecordatorio,
)
from app.modelos.vehiculo import Resultado, Vehiculo, Verificacion


@dataclass
class CumplimientoPorDigito:
    digitos: str          # "5 – 6"
    padron: int
    verificaron: int
    porcentaje: float


@dataclass
class Efectividad:
    anio: int
    con_aviso_total: int
    con_aviso_verificaron: int
    con_aviso_porcentaje: float
    sin_aviso_total: int
    sin_aviso_verificaron: int
    sin_aviso_porcentaje: float
    diferencia_puntos: float
    verificaciones_atribuibles: int


@dataclass
class ResumenCanales:
    canal: str
    enviados: int
    entregados: int
    fallidos: int
    tasa_entrega: float


#: Los cinco grupos del Artículo 9, con un dígito representante de cada uno.
GRUPOS = (("5 – 6", 5), ("7 – 8", 7), ("3 – 4", 3), ("1 – 2", 1), ("9 – 0", 9))


def _ventanas_cerradas(digito: int, anio: int, hoy: date):
    """Las ventanas del año que ya cerraron. Solo esas se pueden evaluar:
    una ventana abierta todavía puede cumplirse."""
    return [v for v in ventanas_del_anio(digito, anio) if v.fin < hoy]


def cumplimiento_por_digito(
    sesion: Session, anio: int | None = None, hoy: date | None = None
) -> list[CumplimientoPorDigito]:
    hoy = hoy or date.today()
    anio = anio or hoy.year

    vehiculos = list(
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

    salida = []
    for etiqueta, representante in GRUPOS:
        ventanas = ventanas_del_anio(representante, anio)
        delgrupo = [
            v for v in vehiculos
            if ventanas_del_anio(v.ultimo_digito, anio) == ventanas
        ]
        cumplieron = sum(
            1 for v in delgrupo
            if any(
                ventana.contiene(f)
                for ventana in ventanas
                for f in v.fechas_aprobadas
            )
        )
        salida.append(
            CumplimientoPorDigito(
                digitos=etiqueta,
                padron=len(delgrupo),
                verificaron=cumplieron,
                porcentaje=round(cumplieron / len(delgrupo) * 100, 1)
                if delgrupo else 0.0,
            )
        )
    return salida


def efectividad_de_recordatorios(
    sesion: Session, anio: int | None = None, hoy: date | None = None
) -> Efectividad:
    """Compara quienes recibieron aviso contra quienes no.

    Solo se cuentan ventanas YA CERRADAS: mientras el periodo sigue abierto,
    el cliente todavía puede venir y contarlo como incumplimiento sería
    falsear el número a la baja.
    """
    hoy = hoy or date.today()
    anio = anio or hoy.year

    vehiculos = list(
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

    con_total = con_ok = sin_total = sin_ok = 0

    for vehiculo in vehiculos:
        for ventana in _ventanas_cerradas(vehiculo.ultimo_digito, anio, hoy):
            recibio = sesion.scalar(
                select(func.count(Recordatorio.id)).where(
                    Recordatorio.vehiculo_id == vehiculo.id,
                    Recordatorio.tipo == TipoRecordatorio.VENTANA,
                    Recordatorio.ventana_anio == anio,
                    Recordatorio.ventana_periodo == ventana.periodo,
                    Recordatorio.estado == EstadoRecordatorio.ENVIADO,
                )
            )
            cumplio = any(ventana.contiene(f) for f in vehiculo.fechas_aprobadas)

            if recibio:
                con_total += 1
                con_ok += bool(cumplio)
            else:
                sin_total += 1
                sin_ok += bool(cumplio)

    con_pct = round(con_ok / con_total * 100, 1) if con_total else 0.0
    sin_pct = round(sin_ok / sin_total * 100, 1) if sin_total else 0.0

    return Efectividad(
        anio=anio,
        con_aviso_total=con_total,
        con_aviso_verificaron=con_ok,
        con_aviso_porcentaje=con_pct,
        sin_aviso_total=sin_total,
        sin_aviso_verificaron=sin_ok,
        sin_aviso_porcentaje=sin_pct,
        diferencia_puntos=round(con_pct - sin_pct, 1),
        # Cuántas verificaciones de más se explican por el aviso, si se supone
        # que sin él habrían cumplido en la misma proporción que los otros.
        verificaciones_atribuibles=max(
            round(con_total * (con_pct - sin_pct) / 100), 0
        ),
    )


def resumen_por_canal(sesion: Session) -> list[ResumenCanales]:
    from app.modelos.recordatorio import ENTREGA_FALLIDA, Canal, EstadoEntrega

    salida = []
    for canal in Canal:
        enviados = sesion.scalar(
            select(func.count(Recordatorio.id)).where(
                Recordatorio.canal == canal,
                Recordatorio.estado == EstadoRecordatorio.ENVIADO,
            )
        ) or 0
        fallidos = sesion.scalar(
            select(func.count(Recordatorio.id)).where(
                Recordatorio.canal == canal,
                Recordatorio.estado_entrega.in_(ENTREGA_FALLIDA),
            )
        ) or 0
        entregados = sesion.scalar(
            select(func.count(Recordatorio.id)).where(
                Recordatorio.canal == canal,
                Recordatorio.estado_entrega.in_(
                    [EstadoEntrega.ENTREGADO, EstadoEntrega.LEIDO,
                     EstadoEntrega.CLIC, EstadoEntrega.ENVIADO]
                ),
            )
        ) or 0
        total = entregados + fallidos
        salida.append(
            ResumenCanales(
                canal=canal.value,
                enviados=int(enviados),
                entregados=int(entregados),
                fallidos=int(fallidos),
                tasa_entrega=round(entregados / total * 100, 1) if total else 0.0,
            )
        )
    return salida


def filas_para_exportar(sesion: Session, anio: int | None = None) -> list[dict]:
    """Datos planos para el Excel. Una fila por verificación."""
    anio = anio or date.today().year

    filas = sesion.execute(
        select(Verificacion, Vehiculo, Cliente)
        .join(Vehiculo, Verificacion.vehiculo_id == Vehiculo.id)
        .join(Cliente, Vehiculo.cliente_id == Cliente.id)
        .where(func.year(Verificacion.fecha) == anio)
        .order_by(Verificacion.fecha)
    ).all()

    return [
        {
            "folio": v.folio_certificado or "",
            "fecha": v.fecha.isoformat(),
            "placa": v.placa_al_verificar or ve.placa,
            "ultimo_digito": ve.ultimo_digito if ve.ultimo_digito is not None else "",
            "periodo": v.periodo or "fuera de periodo",
            "cliente": c.nombre,
            "marca": ve.marca or "",
            "linea": ve.linea or "",
            "modelo": ve.modelo_anio or "",
            "resultado": v.resultado.value,
            "holograma": v.holograma or "",
        }
        for v, ve, c in filas
    ]
