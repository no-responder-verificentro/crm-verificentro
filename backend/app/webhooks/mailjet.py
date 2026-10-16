"""Webhook de Mailjet.

Es la mitad que faltaba. La API dice si Mailjet *aceptó* el mensaje; esto dice
qué pasó después: si llegó, si rebotó, si lo bloquearon o si el filtro
antispam lo descartó sin enviarlo.

Ese último caso —**spam pre-blocked**— es el que se había estado viviendo a
ciegas: Mailjet decide que el servidor del destinatario lo marcaría como
spam, no lo manda, y por SMTP eso era indistinguible de un envío exitoso.

Mailjet no firma los eventos, así que la autenticación va en la propia
dirección: el webhook vive en `/webhooks/mailjet/{secreto}` y solo responde
si el secreto coincide con MAILJET_WEBHOOK_SECRETO.

Dos reglas que Mailjet impone:

- Hay que contestar **200** aunque algo no se procese. Con cualquier otra
  cosa reintenta el lote completo y reprocesa lo que ya estaba bien.
- Los eventos pueden llegar **agrupados** (un arreglo) o de uno en uno.

Tipos de evento y sus campos:
https://dev.mailjet.com/docs/email-api/webhooks/event-types
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.config import obtener_config
from app.dependencias import Sesion
from app.modelos.cliente import Cliente
from app.modelos.recordatorio import EstadoEntrega, Recordatorio
from app.servicios import recordatorios as servicio

router = APIRouter(prefix="/webhooks/mailjet", tags=["Webhooks"],
                   include_in_schema=False)

#: Cómo se traduce cada evento de Mailjet al estado nuestro.
#:
#: 'sent' en Mailjet significa que el servidor del destinatario ACEPTÓ el
#: mensaje, no que nosotros lo mandamos; por eso va a ENTREGADO y no a
#: ENVIADO, que ya se marcó al llamar a la API.
#:
#: 'open' no está en la tabla a propósito. La apertura se mide con un pixel
#: que casi todos los clientes de correo bloquean o precargan, así que ni su
#: presencia ni su ausencia dicen nada. El dato confiable es el clic.
EVENTOS = {
    "sent": EstadoEntrega.ENTREGADO,
    "click": EstadoEntrega.CLIC,
    "spam": EstadoEntrega.SPAM,
    "unsub": EstadoEntrega.BAJA,
}

#: Palabras de Mailjet en el campo `error` de un bloqueo que significan que
#: su filtro antispam lo descartó antes de mandarlo.
SEÑAS_DE_SPAM = ("spam", "preblocked", "pre-blocked", "content")


@router.post("/{secreto}")
async def recibir(secreto: str, request: Request, sesion: Sesion) -> dict:
    config = obtener_config()
    esperado = config.mailjet_webhook_secreto

    if not esperado:
        # Sin secreto configurado, en producción no se acepta nada: cualquiera
        # que conozca la dirección podría ensuciar la bitácora de entregas.
        if config.es_produccion:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Webhook no configurado.")
    elif not hmac.compare_digest(secreto, esperado):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Secreto incorrecto.")

    try:
        datos = await request.json()
    except ValueError:
        return {"procesados": 0}

    eventos = datos if isinstance(datos, list) else [datos]
    procesados = sum(_aplicar(sesion, e) for e in eventos if isinstance(e, dict))

    return {"procesados": procesados}


def _aplicar(sesion, evento: dict) -> int:
    tipo = evento.get("event")
    identificador = evento.get("MessageID")
    if not identificador:
        return 0

    recordatorio = sesion.scalar(
        select(Recordatorio).where(Recordatorio.id_externo == str(identificador))
    )
    if recordatorio is None:
        return 0   # evento de un correo que no salió de aquí

    nuevo, motivo = _interpretar(tipo, evento)
    if nuevo is None:
        return 0

    if motivo and not recordatorio.motivo_error:
        recordatorio.motivo_error = motivo[:255]

    if tipo == "unsub":
        _dar_de_baja(sesion, recordatorio)

    servicio.registrar_entrega(
        sesion, recordatorio, nuevo,
        ocurrido_en=_momento(evento), codigo=tipo,
    )
    return 1


def _interpretar(tipo: str | None, evento: dict) -> tuple[EstadoEntrega | None, str | None]:
    """Traduce un evento. Devuelve el estado nuevo y el motivo legible."""
    if tipo == "bounce":
        duro = bool(evento.get("hard_bounce"))
        return (
            EstadoEntrega.REBOTE_DURO if duro else EstadoEntrega.REBOTE_SUAVE,
            _motivo(evento),
        )

    if tipo == "blocked":
        # Un bloqueo por contenido es el caso de "Mailjet lo detectó como spam
        # y no lo mandó". Se distingue del resto porque es lo único que se
        # arregla cambiando el correo y no la lista de destinatarios.
        texto = (str(evento.get("error") or "")
                 + " " + str(evento.get("error_related_to") or "")).lower()
        es_spam = any(s in texto for s in SEÑAS_DE_SPAM)
        return (
            EstadoEntrega.SPAM if es_spam else EstadoEntrega.FALLIDO,
            _motivo(evento),
        )

    return EVENTOS.get(tipo or ""), _motivo(evento)


def _motivo(evento: dict) -> str | None:
    piezas = [evento.get("error_related_to"), evento.get("error"),
              evento.get("comment")]
    texto = " · ".join(str(p) for p in piezas if p)
    return texto or None


def _momento(evento: dict) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(evento["time"]), UTC).replace(tzinfo=None)
    except (KeyError, TypeError, ValueError):
        return None


def _dar_de_baja(sesion, recordatorio: Recordatorio) -> None:
    """Quien se da de baja deja de recibir, y de inmediato.

    No es cortesía: seguir escribiéndole a alguien que pidió dejar de recibir
    es la vía más rápida a que reporte spam, y eso castiga la entrega de todos
    los demás.
    """
    cliente = sesion.get(Cliente, recordatorio.cliente_id)
    if cliente is not None:
        cliente.consent_correo = False
