"""Modelos de la base de datos.

Se importan todos aquí a propósito. SQLAlchemy resuelve las relaciones por
nombre ("Cliente", "Vehiculo") contra un registro global, así que si un script
importa solo una parte, las relaciones truenan con `KeyError: 'Cliente'`.

Importando el paquete `app.modelos` queda todo registrado, sin importar por
dónde empiece el programa: la API, un job o una prueba.
"""

from app.modelos.cita import (  # noqa: F401
    Cita, ConfigCitas, DiaNoLaborable, EstadoCita, HorarioAtencion, OrigenCita,
)
from app.modelos.chatbot import (  # noqa: F401
    CanalChat, ChatbotPendiente, ChatbotRespuesta, TipoRespuesta,
)
from app.modelos.cliente import (  # noqa: F401
    Cliente, EstadoContacto, OrigenConsentimiento,
)
from app.modelos.empleado import Empleado, Perfil  # noqa: F401
from app.modelos.recordatorio import (  # noqa: F401
    Canal, EstadoAprobacion, EstadoEntrega, EstadoRecordatorio, PlantillaMensaje,
    Recordatorio, RecordatorioEvento, TipoRecordatorio,
)
from app.modelos.vehiculo import (  # noqa: F401
    Combustible, MotivoPlaca, Resultado, Vehiculo, VehiculoPlaca, Verificacion,
)

__all__ = [
    "Cita", "ConfigCitas", "DiaNoLaborable", "EstadoCita", "HorarioAtencion",
    "OrigenCita", "Cliente", "EstadoContacto", "OrigenConsentimiento",
    "Empleado", "Perfil", "Combustible", "MotivoPlaca", "Resultado",
    "Vehiculo", "VehiculoPlaca", "Verificacion",
    "Canal", "EstadoAprobacion", "EstadoEntrega", "EstadoRecordatorio",
    "PlantillaMensaje", "Recordatorio", "RecordatorioEvento", "TipoRecordatorio",
    "CanalChat", "ChatbotPendiente", "ChatbotRespuesta", "TipoRespuesta",
]
