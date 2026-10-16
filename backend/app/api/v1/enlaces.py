"""Redirección de los enlaces de los correos.

Cuando el cliente da clic en "Consultar mi periodo", pasa por aquí: se anota
el clic —el único acuse confiable en correo— y se le manda a la consulta
pública con su placa ya puesta.

No lleva prefijo /api porque es una URL que ve la gente, no la aplicación.
Tampoco requiere token: quien la abre es el destinatario del correo, y la
firma impide que alguien marque los recordatorios de otro.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse

from app.config import obtener_config
from app.dependencias import Sesion
from app.mensajeria.enlaces import verificar
from app.modelos.recordatorio import EstadoEntrega, Recordatorio
from app.modelos.vehiculo import Vehiculo
from app.servicios import recordatorios as servicio

router = APIRouter(prefix="/r", tags=["Enlaces"], include_in_schema=False)


@router.get("/{recordatorio_id}/{firma}")
def seguir(recordatorio_id: int, firma: str, sesion: Sesion) -> RedirectResponse:
    config = obtener_config()

    # Una firma que no cuadra NO se registra —para eso está la firma— pero
    # tampoco se deja al cliente en una página de error: algunos clientes de
    # correo cortan o reescriben las ligas, y quien está del otro lado es una
    # persona que solo quería consultar su placa.
    if not verificar(recordatorio_id, firma):
        return RedirectResponse(config.url_consulta,
                                status_code=status.HTTP_302_FOUND)

    recordatorio = sesion.get(Recordatorio, recordatorio_id)
    destino = config.url_consulta

    if recordatorio is not None:
        servicio.registrar_entrega(sesion, recordatorio, EstadoEntrega.CLIC)
        vehiculo = sesion.get(Vehiculo, recordatorio.vehiculo_id)
        if vehiculo is not None:
            destino = f"{config.url_consulta}?placa={vehiculo.placa_normalizada}"

    # 302 y no 301: un 301 lo cachea el navegador y el siguiente clic ya no
    # pasaría por aquí, así que dejaríamos de contarlos.
    return RedirectResponse(destino, status_code=status.HTTP_302_FOUND)
