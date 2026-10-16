"""Validación de los datos que se copian de la tarjeta de circulación.

Estas reglas viven en `dominio` porque no dependen de HTTP ni de la base:
las usan por igual el alta de mostrador, la edición y el chatbot.
"""

from __future__ import annotations

import re

__all__ = [
    "NivInvalido",
    "TelefonoInvalido",
    "normalizar_niv",
    "normalizar_telefono",
    "formatear_telefono",
]

# El NIV no usa I, O ni Q para que no se confundan con 1 y 0.
_NIV_VALIDO = re.compile(r"^[A-HJ-NPR-Z0-9]+$")
_SOLO_DIGITOS = re.compile(r"\D")

LARGO_NIV_ESTANDAR = 17
LARGO_NIV_MINIMO = 8      # los autos anteriores a 1981 traen NIV más cortos

LADA_MEXICO = "52"
LARGO_NACIONAL_MX = 10


class NivInvalido(ValueError):
    """El número de serie no tiene un formato aceptable."""


class TelefonoInvalido(ValueError):
    """El teléfono no se pudo interpretar como número mexicano."""


def normalizar_niv(niv: str) -> str:
    """Deja el NIV en mayúsculas y sin separadores, validando el formato.

    No se rechazan los NIV de menos de 17 caracteres: los vehículos
    anteriores a 1981 los traen más cortos y sí verifican. Lo que sí se
    rechaza es que traiga I, O o Q, porque en esas posiciones siempre son
    un 1 o un 0 mal transcritos.
    """
    if not niv:
        raise NivInvalido("El número de serie viene vacío.")

    limpio = re.sub(r"[\s\-]", "", niv.upper())

    if not _NIV_VALIDO.match(limpio):
        confusos = sorted({c for c in limpio if c in "IOQ"})
        if confusos:
            raise NivInvalido(
                f"El NIV no puede contener {', '.join(confusos)}. "
                "En esa posición casi siempre es un 1 o un 0. Verifica la tarjeta."
            )
        raise NivInvalido("El NIV solo admite letras y números.")

    if len(limpio) > LARGO_NIV_ESTANDAR:
        raise NivInvalido(
            f"El NIV tiene {len(limpio)} caracteres; el máximo es {LARGO_NIV_ESTANDAR}."
        )
    if len(limpio) < LARGO_NIV_MINIMO:
        raise NivInvalido(
            f"El NIV tiene {len(limpio)} caracteres; parece incompleto."
        )
    return limpio


def normalizar_telefono(telefono: str) -> str:
    """Convierte a formato E.164: +52 seguido de 10 dígitos.

    Acepta las formas en que la gente lo dicta o lo trae anotado:
    '2281009584', '228 100 9584', '(228) 100-95-84', '+52 228 100 9584'.

    Se guarda en E.164 porque es lo que exige la API de WhatsApp. Si se
    guarda como lo escribió el cliente, cada envío tendría que adivinar.
    """
    if not telefono:
        raise TelefonoInvalido("El teléfono viene vacío.")

    digitos = _SOLO_DIGITOS.sub("", telefono)

    # Prefijo de larga distancia nacional que todavía mucha gente antepone.
    if len(digitos) == LARGO_NACIONAL_MX + 1 and digitos.startswith("1"):
        digitos = digitos[1:]

    if len(digitos) == LARGO_NACIONAL_MX:
        digitos = LADA_MEXICO + digitos

    # Formato viejo +521 (celular) que Meta ya no usa.
    if len(digitos) == 13 and digitos.startswith(LADA_MEXICO + "1"):
        digitos = LADA_MEXICO + digitos[3:]

    if not (digitos.startswith(LADA_MEXICO) and len(digitos) == 12):
        raise TelefonoInvalido(
            f"'{telefono}' no parece un número mexicano de 10 dígitos."
        )

    return "+" + digitos


def formatear_telefono(e164: str) -> str:
    """Lo contrario: '+522281009584' -> '228 100 9584', para pantalla."""
    d = _SOLO_DIGITOS.sub("", e164)
    if len(d) == 12 and d.startswith(LADA_MEXICO):
        n = d[2:]
        return f"{n[:3]} {n[3:6]} {n[6:]}"
    return e164
