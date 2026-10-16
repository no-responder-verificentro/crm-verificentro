"""Interfaz de los adaptadores de mensajería.

Todo lo que envía mensajes implementa esto. El resto del sistema no sabe si
detrás hay WhatsApp, correo o solo la consola: pide `enviar()` y recibe un
resultado con la misma forma.

Gracias a eso el job de recordatorios se puede construir y probar completo
antes de terminar el trámite con Meta.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Mensaje:
    destino: str          # teléfono en E.164 o correo
    asunto: str | None    # solo correo
    cuerpo: str
    clave_plantilla: str  # aviso_1, aviso_4, cita_recordatorio…
    enlace: str | None = None   # enlace firmado, para medir el clic
    # Piezas para la versión HTML. Vacías = se arma desde el cuerpo de texto.
    parrafos: tuple[str, ...] = ()
    pie: tuple[str, ...] = ()
    # WhatsApp: nombre de la plantilla aprobada en Meta y sus variables.
    plantilla_meta: str | None = None
    parametros: tuple[str, ...] = ()


@dataclass(frozen=True)
class Resultado:
    exito: bool
    id_externo: str | None = None
    error: str | None = None
    codigo: str | None = None


class Adaptador(ABC):
    """Un canal de envío."""

    nombre: str = "base"

    @abstractmethod
    def enviar(self, mensaje: Mensaje) -> Resultado:
        ...
