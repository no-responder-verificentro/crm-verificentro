"""
Calendario de Verificación Vehicular Obligatoria — Estado de Veracruz.

Implementa la regla del Artículo 9 del Programa de Verificación Vehicular
Obligatoria: cada vehículo tiene dos periodos al año, determinados por el
último dígito de su placa de circulación.

REGLA IMPORTANTE
----------------
Las placas de Veracruz terminan en LETRA (formato AAA-000-A). El programa se
rige por el último *dígito*, no por el último carácter. Por eso se extrae el
último carácter numérico de la placa e ignoran letras, guiones y espacios.

Este módulo no depende de nada externo: solo la librería estándar. Así se
puede probar sin base de datos y reutilizar desde el job de recordatorios,
desde la API y desde el chatbot.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

__all__ = [
    "PlacaSinDigito",
    "DigitoInvalido",
    "Ventana",
    "Estado",
    "normalizar_placa",
    "ultimo_digito",
    "ventanas_del_anio",
    "ventana_de_fecha",
    "ventana_vigente",
    "proxima_ventana",
    "ultima_ventana_cerrada",
    "estado_de_cumplimiento",
    "fechas_de_aviso",
]


# --------------------------------------------------------------------------
# Errores
# --------------------------------------------------------------------------

class PlacaSinDigito(ValueError):
    """La placa no contiene ningún carácter numérico.

    No se debe asumir un dígito por omisión: el registro tiene que quedar
    marcado para revisión humana. Si se asumiera 0, el vehículo caería en el
    grupo 9-0 y recibiría recordatorios en el mes equivocado sin que nadie
    se diera cuenta.
    """


class DigitoInvalido(ValueError):
    """El dígito recibido no está entre 0 y 9."""


# --------------------------------------------------------------------------
# Tabla oficial: dígito -> ((mes_ini, mes_fin) primer periodo,
#                           (mes_ini, mes_fin) segundo periodo)
# --------------------------------------------------------------------------

PERIODOS_POR_DIGITO: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {
    5: ((1, 2), (7, 8)),    # Enero-Febrero    / Julio-Agosto
    6: ((1, 2), (7, 8)),
    7: ((2, 3), (8, 9)),    # Febrero-Marzo    / Agosto-Septiembre
    8: ((2, 3), (8, 9)),
    3: ((3, 4), (9, 10)),   # Marzo-Abril      / Septiembre-Octubre
    4: ((3, 4), (9, 10)),
    1: ((4, 5), (10, 11)),  # Abril-Mayo       / Octubre-Noviembre
    2: ((4, 5), (10, 11)),
    9: ((5, 6), (11, 12)),  # Mayo-Junio       / Noviembre-Diciembre
    0: ((5, 6), (11, 12)),
}

MESES = (
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)

# Cuántos días antes del cierre se considera que la ventana está "por vencer".
DIAS_POR_VENCER = 15


# --------------------------------------------------------------------------
# Placas
# --------------------------------------------------------------------------

_NO_ALFANUMERICO = re.compile(r"[^A-Z0-9]")
_NO_DIGITO = re.compile(r"\D")


def normalizar_placa(placa: str) -> str:
    """Deja la placa en mayúsculas y sin guiones ni espacios.

    En el mostrador la misma placa se captura de varias formas
    ('yun047a', 'YUN-047-A', 'YUN 047 A'). Guardar la forma normalizada en
    su propia columna con índice único evita duplicados y hace que la
    búsqueda funcione sin importar cómo la escriban.
    """
    if placa is None:
        raise PlacaSinDigito("(vacía)")
    return _NO_ALFANUMERICO.sub("", placa.upper())


def ultimo_digito(placa: str) -> int:
    """Devuelve el último carácter numérico de la placa.

    >>> ultimo_digito("YUN-047-A")
    7
    >>> ultimo_digito("VZM317C")
    7
    """
    solo_digitos = _NO_DIGITO.sub("", normalizar_placa(placa))
    if not solo_digitos:
        raise PlacaSinDigito(placa)
    return int(solo_digitos[-1])


# --------------------------------------------------------------------------
# Ventanas
# --------------------------------------------------------------------------

@dataclass(frozen=True, order=True)
class Ventana:
    """Un periodo de verificación concreto, ya aterrizado en fechas."""

    inicio: date
    fin: date
    anio: int
    periodo: int  # 1 = primer periodo del año, 2 = segundo

    def contiene(self, dia: date) -> bool:
        return self.inicio <= dia <= self.fin

    def dias_restantes(self, desde: date) -> int:
        """Días que faltan para el cierre. Negativo si ya cerró."""
        return (self.fin - desde).days

    def dias_para_abrir(self, desde: date) -> int:
        """Días que faltan para que abra. Negativo si ya abrió."""
        return (self.inicio - desde).days

    @property
    def etiqueta(self) -> str:
        """Texto listo para pantalla: 'Agosto – Septiembre'."""
        if self.inicio.month == self.fin.month:
            return MESES[self.inicio.month]
        return f"{MESES[self.inicio.month]} – {MESES[self.fin.month]}"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.etiqueta} {self.anio}"


def _validar_digito(digito: int) -> int:
    if not isinstance(digito, int) or isinstance(digito, bool):
        raise DigitoInvalido(digito)
    if digito not in PERIODOS_POR_DIGITO:
        raise DigitoInvalido(digito)
    return digito


def _ventana(anio: int, mes_ini: int, mes_fin: int, periodo: int) -> Ventana:
    ultimo_dia = calendar.monthrange(anio, mes_fin)[1]
    return Ventana(
        inicio=date(anio, mes_ini, 1),
        fin=date(anio, mes_fin, ultimo_dia),
        anio=anio,
        periodo=periodo,
    )


def ventanas_del_anio(digito: int, anio: int) -> tuple[Ventana, Ventana]:
    """Los dos periodos que le tocan a ese dígito en ese año."""
    _validar_digito(digito)
    (a_ini, a_fin), (b_ini, b_fin) = PERIODOS_POR_DIGITO[digito]
    return (
        _ventana(anio, a_ini, a_fin, 1),
        _ventana(anio, b_ini, b_fin, 2),
    )


def ventana_de_fecha(digito: int, dia: date) -> Ventana | None:
    """La ventana que contiene esa fecha, o None si cae fuera de ambas."""
    for v in ventanas_del_anio(digito, dia.year):
        if v.contiene(dia):
            return v
    return None


def ventana_vigente(digito: int, hoy: date) -> Ventana | None:
    """Alias explícito de `ventana_de_fecha` para leerse mejor en el job."""
    return ventana_de_fecha(digito, hoy)


def proxima_ventana(digito: int, hoy: date) -> Ventana:
    """La siguiente ventana que abre después de `hoy`.

    Si hoy cae dentro de una ventana, devuelve la que sigue, no la actual.
    """
    candidatas = [
        *ventanas_del_anio(digito, hoy.year),
        *ventanas_del_anio(digito, hoy.year + 1),
    ]
    return min(v for v in candidatas if v.inicio > hoy)


def ultima_ventana_cerrada(digito: int, hoy: date) -> Ventana | None:
    """La última ventana cuyo cierre ya pasó."""
    candidatas = [
        *ventanas_del_anio(digito, hoy.year - 1),
        *ventanas_del_anio(digito, hoy.year),
    ]
    cerradas = [v for v in candidatas if v.fin < hoy]
    return max(cerradas) if cerradas else None


# --------------------------------------------------------------------------
# Estado de cumplimiento
# --------------------------------------------------------------------------

class Estado(str, Enum):
    """Estado de un vehículo frente al calendario, en un día dado."""

    AL_CORRIENTE = "al_corriente"      # ya verificó en su ventana vigente
    PERIODO_ABIERTO = "periodo_abierto"  # le toca ahora y aún tiene tiempo
    POR_VENCER = "por_vencer"          # le toca ahora y quedan pocos días
    VENCIDO = "vencido"                # se le pasó la ventana anterior
    PROGRAMADO = "programado"          # su ventana todavía no abre


def estado_de_cumplimiento(
    digito: int,
    hoy: date,
    verificaciones_aprobadas: list[date] | tuple[date, ...] = (),
    dias_por_vencer: int = DIAS_POR_VENCER,
) -> tuple[Estado, Ventana | None]:
    """Devuelve el estado del vehículo y la ventana de referencia.

    `verificaciones_aprobadas` son las fechas de las verificaciones con
    resultado aprobatorio. Las rechazadas no cuentan como cumplimiento:
    el vehículo tiene que volver a pasar dentro de la misma ventana.

    Regresa una tupla (estado, ventana) donde la ventana es la que explica
    ese estado: la vigente si está abierta, la vencida si se pasó, o la
    próxima si todavía no abre.
    """
    _validar_digito(digito)
    aprobadas = tuple(verificaciones_aprobadas)

    vigente = ventana_vigente(digito, hoy)
    if vigente is not None:
        if any(vigente.contiene(f) for f in aprobadas):
            return Estado.AL_CORRIENTE, vigente
        if vigente.dias_restantes(hoy) <= dias_por_vencer:
            return Estado.POR_VENCER, vigente
        return Estado.PERIODO_ABIERTO, vigente

    anterior = ultima_ventana_cerrada(digito, hoy)
    if anterior is not None and not any(anterior.contiene(f) for f in aprobadas):
        return Estado.VENCIDO, anterior

    return Estado.PROGRAMADO, proxima_ventana(digito, hoy)


# --------------------------------------------------------------------------
# Cadencia de recordatorios
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Aviso:
    clave: str
    fecha: date
    descripcion: str


def fechas_de_aviso(ventana: Ventana, dias_antes: int = 15) -> list[Aviso]:
    """Las fechas en que deben salir los recordatorios de esa ventana.

    El job diario compara estas fechas contra el día de hoy. Cada aviso se
    genera una sola vez y se cancela en automático si el vehículo verifica
    antes de que salga.
    """
    mitad = ventana.inicio + (ventana.fin - ventana.inicio) / 2
    return [
        Aviso("aviso_1", ventana.inicio - timedelta(days=dias_antes),
              f"Faltan {dias_antes} días para que abra su periodo"),
        Aviso("aviso_2", ventana.inicio,
              "Hoy abre su periodo de verificación"),
        Aviso("aviso_3", mitad,
              "Va a la mitad del periodo y aún no verifica"),
        Aviso("aviso_4", ventana.fin - timedelta(days=5),
              "Quedan 5 días para que cierre su periodo"),
        Aviso("seguimiento", ventana.fin + timedelta(days=1),
              "Su periodo cerró sin verificar"),
    ]
